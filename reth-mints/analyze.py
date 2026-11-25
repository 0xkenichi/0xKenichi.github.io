#!/usr/bin/env python3
"""Classify every rETH mint by entry point and build results.json + index.html.
Usage: python3 -I analyze.py   (after fetch.py and crosscheck.py)
"""
import csv
import datetime as dt
import html
import json
import os
from collections import defaultdict, Counter

HERE = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(HERE, "data")
meta = json.load(open(os.path.join(DATA, "meta.json")))
DP = meta["rocketDepositPool_now"]
SWAP_ROUTER = "0x16d5a408e807db8ef7c578279beeee6b228f1c1c"

addr = {r["address"]: r for r in csv.DictReader(open(os.path.join(DATA, "addresses.csv")))}
mints = list(csv.DictReader(open(os.path.join(DATA, "mints.csv"))))
dex = list(csv.DictReader(open(os.path.join(DATA, "dex_buys.csv"))))
burns = list(csv.DictReader(open(os.path.join(DATA, "burns.csv"))))
cross = json.load(open(os.path.join(DATA, "crosscheck.json"))) if os.path.exists(
    os.path.join(DATA, "crosscheck.json")) else None

# Category for a labelled contract used as tx.to. Keyed by address; the label text itself always comes
# from data/addresses.csv (Etherscan public name tag or Blockscout verified contract name), never from here.
# Filled in after reviewing addresses.csv; anything not listed falls back to the rules in classify().
CATEGORY_BY_ADDRESS = json.load(open(os.path.join(HERE, "categories.json")))

CATS = [
    "Direct deposit (EOA -> deposit pool)",
    "Node operator credit withdrawal (no new ETH)",
    "Rocket Pool swap router",
    "DEX aggregator / router",
    "Smart wallet (Safe / ERC-4337 / EIP-7702)",
    "Wallet staking feature (MetaMask)",
    "Vault or other protocol",
    "Unlabelled contract",
]


def label_of(a):
    r = addr.get(a, {})
    if r.get("etherscan_tag") and r["etherscan_tag"] != "?":
        return r["etherscan_tag"], "Etherscan name tag (etherscan.io/address/%s)" % a
    if r.get("blockscout_name") and r["blockscout_name"] != "?" and r.get("blockscout_verified") == "True":
        return r["blockscout_name"], "Blockscout verified contract name (eth.blockscout.com/address/%s)" % a
    return "", ""


def describe(a):
    """Public label for an address, or a factual on-chain description; never an invented name."""
    lab, src = label_of(a)
    r = addr.get(a, {})
    if lab:
        return lab, src
    if is_safe(a):
        return ("Safe v%s (threshold %s)" % (r["safe_version"], r["safe_threshold"]),
                "on-chain: getThreshold() and VERSION() answer at this address")
    if r.get("code_kind", "").startswith("EOA+7702"):
        dlg = r["code_kind"].split("->")[1]
        dl, ds = label_of(dlg)
        return ("EOA, EIP-7702 delegated to %s (%s)" % (dlg[:10] + "…", dl or "unlabelled"),
                "on-chain eth_getCode (0xef0100 prefix)" + ("; delegate label: " + ds if ds else ""))
    if r.get("code_kind") == "EOA":
        return "EOA (no public tag)", "on-chain eth_getCode is empty"
    return "", ""


def is_safe(a):
    r = addr.get(a, {})
    return (r.get("safe_threshold") or "0") not in ("", "0") and bool(r.get("safe_version"))


def classify(m):
    to, frm = m["tx_to"], m["tx_from"]
    if m["mint_path"] == "credit_withdrawal":
        return CATS[1]
    if to == DP:  # a type-0/2 tx signed by an EOA straight to deposit() (tx.from is always an EOA)
        return CATS[0]
    if to == SWAP_ROUTER:
        return CATS[2]
    if to in CATEGORY_BY_ADDRESS:
        return CATEGORY_BY_ADDRESS[to]["category"]
    if is_safe(to):
        return CATS[4]
    if addr.get(to, {}).get("code_kind", "").startswith("EOA+7702"):
        return CATS[4]  # EOA executing its own EIP-7702 delegated code (smart account)
    return CATS[7] if not label_of(to)[0] else CATS[6]


E = 1e18
W0 = dt.datetime.strptime(meta["window"]["start_date"], "%Y-%m-%d")
W1 = dt.datetime.strptime(meta["window"]["end_date_exclusive"], "%Y-%m-%d")
NWEEKS = ((W1 - W0).days + 6) // 7


def week(ts):
    d = dt.datetime.strptime(ts[:16], "%Y-%m-%d %H:%M")
    return min(NWEEKS - 1, (d - W0).days // 7)


def wk_label(i):
    a = W0 + dt.timedelta(days=7 * i)
    b = min(W1, a + dt.timedelta(days=7)) - dt.timedelta(days=1)
    return "%s–%s" % (a.strftime("%d %b"), b.strftime("%d %b"))


for m in mints:
    m["cat"] = classify(m)
    m["eth_net"] = int(m["eth_net_wei"]) / E
    m["eth_gross"] = int(m["eth_gross_wei"]) / E if m["eth_gross_wei"] else m["eth_net"]
    m["reth"] = int(m["reth_minted_wei"]) / E
    m["wk"] = week(m["time_utc"])

tot = {"mints": len(mints), "mint_txs": len({m["tx_hash"] for m in mints}),
       "reth_minted": sum(m["reth"] for m in mints), "eth_net": sum(m["eth_net"] for m in mints),
       "eth_gross_all": sum(m["eth_gross"] for m in mints)}
dep = [m for m in mints if m["mint_path"] == "deposit"]
cred = [m for m in mints if m["mint_path"] == "credit_withdrawal"]
tot["deposit_mints"] = len(dep)
tot["eth_deposited_new"] = sum(m["eth_gross"] for m in dep)
tot["credit_mints"] = len(cred)
tot["eth_credit_withdrawn"] = sum(m["eth_gross"] for m in cred)
tot["unmatched"] = sum(1 for m in mints if m["mint_path"] == "unmatched")
tot["deposit_fee_eth"] = tot["eth_gross_all"] - tot["eth_net"]
tot["unique_depositors"] = len({m["depositor"] for m in mints})
tot["unique_tx_senders"] = len({m["tx_from"] for m in mints})

by_cat = {}
for c in CATS:
    ms = [m for m in mints if m["cat"] == c]
    by_cat[c] = {"mints": len(ms), "eth_gross": sum(m["eth_gross"] for m in ms),
                 "reth": sum(m["reth"] for m in ms),
                 "share_eth": sum(m["eth_gross"] for m in ms) / tot["eth_gross_all"] if tot["eth_gross_all"] else 0,
                 "share_count": len(ms) / len(mints) if mints else 0}

# entry-point contracts (tx.to other than deposit pool)
entry = defaultdict(lambda: {"mints": 0, "eth": 0.0})
for m in mints:
    if m["tx_to"] != DP:
        entry[m["tx_to"]]["mints"] += 1
        entry[m["tx_to"]]["eth"] += m["eth_gross"]
entry_rows = []
for a, v in sorted(entry.items(), key=lambda x: -x[1]["eth"]):
    lab, src = describe(a)
    r = addr.get(a, {})
    entry_rows.append({"address": a, "mints": v["mints"], "eth": v["eth"], "label": lab or "unlabelled contract",
                       "label_source": src, "category": classify(next(m for m in mints if m["tx_to"] == a)),
                       "safe": is_safe(a), "safe_version": r.get("safe_version", ""), "code_kind": r.get("code_kind", ""),
                       "note": CATEGORY_BY_ADDRESS.get(a, {}).get("note", "")})

# top 10 minting addresses: the address that received the rETH (depositor = TokensMinted.to)
dep_tot = defaultdict(lambda: {"mints": 0, "eth": 0.0, "cats": Counter(), "entry": Counter()})
for m in mints:
    d = dep_tot[m["depositor"]]
    d["mints"] += 1
    d["eth"] += m["eth_gross"]
    d["cats"][m["cat"]] += 1
    d["entry"][m["tx_to"]] += 1
top10 = []
for a, v in sorted(dep_tot.items(), key=lambda x: -x[1]["eth"])[:10]:
    lab, src = describe(a)
    r = addr.get(a, {})
    top10.append({"address": a, "mints": v["mints"], "eth": v["eth"], "share": v["eth"] / tot["eth_gross_all"],
                  "kind": r.get("code_kind", ""), "label": lab or "unlabelled contract",
                  "label_source": src, "path": v["cats"].most_common(1)[0][0]})
top10_share = sum(t["eth"] for t in top10) / tot["eth_gross_all"]

# weekly
weekly = [{"week": wk_label(i), **{c: 0.0 for c in CATS}, "mints": 0, "dex_reth": 0.0, "mint_reth": 0.0,
           "burn_reth": 0.0} for i in range(NWEEKS)]
for m in mints:
    w = weekly[m["wk"]]
    w[m["cat"]] += m["eth_gross"]
    w["mints"] += 1
    w["mint_reth"] += m["reth"]
for r in dex:
    weekly[week(r["time_utc_approx"])]["dex_reth"] += int(r["reth_out_wei"]) / E
for b in burns:
    weekly[week(b["time_utc"])]["burn_reth"] += int(b["reth_burned_wei"]) / E

# DEX contrast
mint_tx = {m["tx_hash"] for m in mints}
venues = defaultdict(lambda: {"swaps": 0, "reth": 0.0})
for r in dex:
    venues[r["venue"]]["swaps"] += 1
    venues[r["venue"]]["reth"] += int(r["reth_out_wei"]) / E
dex_tot = {"swaps": len(dex), "txs": len({r["tx_hash"] for r in dex}), "reth": sum(v["reth"] for v in venues.values()),
           "swaps_in_mint_txs": sum(1 for r in dex if r["tx_hash"] in mint_tx)}
# multi-hop / arbitrage proxy: txs where rETH also flowed INTO a tracked pool are not in this file; we can only
# flag txs with more than one rETH-out swap
txc = Counter(r["tx_hash"] for r in dex)
dex_tot["txs_with_multiple_reth_out_swaps"] = sum(1 for v in txc.values() if v > 1)

supply = {"before": int(meta["reth_total_supply_at_block_before_start"]) / E,
          "end": int(meta["reth_total_supply_at_end_block"]) / E,
          "burned": sum(int(b["reth_burned_wei"]) for b in burns) / E, "burn_events": len(burns)}
supply["delta"] = supply["end"] - supply["before"]
supply["minted_minus_burned"] = tot["reth_minted"] - supply["burned"]
supply["gap"] = supply["delta"] - supply["minted_minus_burned"]

res = {"window": meta["window"], "totals": tot, "by_category": by_cat, "entry_points": entry_rows,
       "top10": top10, "top10_share": top10_share, "weekly": weekly, "dex_venues": venues, "dex_totals": dex_tot,
       "supply_check": supply, "crosscheck": cross, "categories": CATS,
       "pools": meta["pools"], "balancer_v2_vault": meta["balancer_v2_vault"]}
json.dump(res, open(os.path.join(DATA, "results.json"), "w"), indent=1, default=dict)
print(json.dumps({k: res[k] for k in ("totals", "by_category", "top10_share", "dex_totals", "supply_check")},
                 indent=1, default=dict))
for e in entry_rows:
    print(e)
for t in top10:
    print(t)
