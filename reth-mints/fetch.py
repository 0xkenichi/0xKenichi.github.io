#!/usr/bin/env python3
"""Who actually mints rETH? Reproducible, key-free data pull.

Usage:  python3 -I fetch.py [START_DATE END_DATE]     (dates UTC, YYYY-MM-DD; END exclusive)
Default window: the 90 days 2026-08-22 00:00 UTC -> 2026-11-20 00:00 UTC.

Only free public JSON-RPC endpoints (see rpclib.ENDPOINTS) plus, for address labels,
public Etherscan address pages (page <title> = public name tag) and the public
Blockscout API (verified contract name). No keys, no logins, no paid services.

Outputs (in ./data):
  meta.json        resolved addresses, block window, supply check inputs
  mints.csv        one row per rETH TokensMinted event, joined to its tx and DepositReceived
  burns.csv        rETH TokensBurned events (for the supply cross-check)
  dex_buys.csv     rETH paid out by Uniswap v3 rETH/WETH pools and Balancer v2 (tokenOut = rETH)
  addresses.csv    every address that appears as tx.to / tx.from / depositor: code type, Safe check, labels
Intermediate caches in ./data/cache so a rerun resumes.
"""
import csv
import datetime as dt
import json
import os
import re
import sys
import time
import urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from rpclib import (keccak256, topic, selector, pad_addr, enc_addr, enc_uint, dec_addr, words,  # noqa: E402
                    to_int, to_signed, rpc, rpc_batch, eth_call, get_logs_chunked, RPCError, STATS)

DATA = os.path.join(HERE, "data")
CACHE = os.path.join(DATA, "cache")
os.makedirs(CACHE, exist_ok=True)

ROCKET_STORAGE = "0x1d8f8f00cfa6758d7be78336684788fb0ee0fa46"
EXPECTED_RETH = "0xae78736cd615f374d3085123a210448e74fc6393"
WETH = "0xc02aaa39b223fe8d0a0e5c4f27ead9083c756cc2"
UNIV3_FACTORY = "0x1f98431c8ad98523631ae4a59f267346ea31f984"   # Uniswap v3 factory (Uniswap docs)
UNIV2_FACTORY = "0x5c69bee701ef814a2b6a3edd4b1652cb9cc5aa6f"   # Uniswap v2 factory (Uniswap docs)
BALANCER_V2_VAULT = "0xba12222222228d8ba445958a75a0704d566bf2c8"  # Balancer v2 Vault (Balancer docs)

T_TOKENS_MINTED = topic("TokensMinted(address,uint256,uint256,uint256)")
T_TOKENS_BURNED = topic("TokensBurned(address,uint256,uint256,uint256)")
T_DEPOSIT_RECEIVED = topic("DepositReceived(address,uint256,uint256)")
T_CREDIT_WITHDRAWN = topic("CreditWithdrawn(address,uint256,uint256)")  # Saturn 1: node credit taken as rETH
T_UNIV3_SWAP = topic("Swap(address,address,int256,int256,uint160,uint128,int24)")
T_UNIV2_SWAP = topic("Swap(address,uint256,uint256,uint256,uint256,address)")
T_BAL_SWAP = topic("Swap(bytes32,address,address,uint256,uint256)")
T_TRANSFER = topic("Transfer(address,address,uint256)")
SINGLETON_VAULTS = {  # addresses from Uniswap and Balancer docs; Etherscan tags fetched into addresses.csv
    "Uniswap v4 PoolManager": "0x000000000004444c5dc75cb358380d2e3de08a90",
    "Balancer v3 Vault": "0xba1333333333a1ba1108e8412f11850a5c319ba9",
}


def cached(name, fn):
    p = os.path.join(CACHE, name + ".json")
    if os.path.exists(p):
        with open(p) as f:
            return json.load(f)
    v = fn()
    with open(p, "w") as f:
        json.dump(v, f)
    return v


def block_ts(n):
    return to_int(rpc("eth_getBlockByNumber", [hex(n), False])["timestamp"])


def block_at_or_after(ts):
    """First block with timestamp >= ts (binary search)."""
    hi = to_int(rpc("eth_blockNumber", []))
    lo = hi - 2_000_000
    while lo < hi:
        mid = (lo + hi) // 2
        if block_ts(mid) < ts:
            lo = mid + 1
        else:
            hi = mid
    return lo


def storage_key(prefix, name_or_addr):
    if name_or_addr.startswith("0x") and len(name_or_addr) == 42:
        return keccak256(prefix.encode() + bytes.fromhex(name_or_addr[2:])).hex()
    return keccak256((prefix + name_or_addr).encode()).hex()


def rs_get_address(name, block="latest"):
    r = eth_call(ROCKET_STORAGE, selector("getAddress(bytes32)") + storage_key("contract.address", name), block)
    return dec_addr(r[2:])


def rs_get_bool(prefix, addr, block="latest"):
    r = eth_call(ROCKET_STORAGE, selector("getBool(bytes32)") + storage_key(prefix, addr), block)
    return to_int(r) == 1


def rs_get_string(prefix, addr, block="latest"):
    r = eth_call(ROCKET_STORAGE, selector("getString(bytes32)") + storage_key(prefix, addr), block)
    w = words(r)
    if len(w) < 2:
        return ""
    ln = int(w[1], 16)
    return bytes.fromhex("".join(w[2:])[:ln * 2]).decode(errors="replace")


# ---------------------------------------------------------------- labels (public pages only)
def http_get(url, timeout=30):
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 (reth-mints-analysis)"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.read().decode("utf-8", "replace")


def clean_tag(t):
    """Etherscan page title -> public name tag, or '' when the page shows no tag.
    Untagged pages read "Address: 0x1234...abcd | Etherscan" (or "Contract Address ...")."""
    if t in ("", "?"):
        return t
    head = t.split(" | ")[0].strip()
    if head.startswith("Address") or head.startswith("Contract Address") or re.match(r"^0x[0-9a-fA-F.]+$", head):
        return ""
    return head


def etherscan_tag(addr):
    """Public Etherscan name tag, read from the address page <title>. '' if none."""
    for attempt in range(3):
        try:
            html = http_get("https://etherscan.io/address/" + addr, timeout=20)
            m = re.search(r"<title>\s*(.*?)\s*</title>", html, re.S)
            if not m:
                raise ValueError("no title")
            return clean_tag(" ".join(m.group(1).split()))
        except Exception:
            time.sleep(3 * (attempt + 1))
    return "?"  # could not fetch


def blockscout_info(addr):
    for attempt in range(2):
        try:
            j = json.loads(http_get("https://eth.blockscout.com/api/v2/addresses/" + addr, timeout=20))
            tags = []
            md = j.get("metadata") or {}
            for t in md.get("tags") or []:
                tags.append(t.get("name", ""))
            impl = ",".join((i.get("name") or "") + "@" + (i.get("address_hash") or i.get("address") or "")
                            for i in (j.get("implementations") or []))
            return {"bs_name": j.get("name") or "", "bs_verified": bool(j.get("is_verified")),
                    "bs_tags": "|".join(t for t in tags if t), "bs_impl": impl}
        except Exception:
            time.sleep(2)
    return {"bs_name": "?", "bs_verified": False, "bs_tags": "", "bs_impl": ""}


# ---------------------------------------------------------------- main
def main():
    if len(sys.argv) == 3:
        d0, d1 = sys.argv[1], sys.argv[2]
    else:
        d0, d1 = "2026-08-22", "2026-11-20"
    t0 = int(dt.datetime.strptime(d0, "%Y-%m-%d").replace(tzinfo=dt.timezone.utc).timestamp())
    t1 = int(dt.datetime.strptime(d1, "%Y-%m-%d").replace(tzinfo=dt.timezone.utc).timestamp())
    print("window", d0, "->", d1)

    win = cached("window_%s_%s" % (d0, d1), lambda: {
        "start_block": block_at_or_after(t0), "end_block": block_at_or_after(t1) - 1})
    sb, eb = win["start_block"], win["end_block"]
    print("blocks", sb, eb)

    # 1. resolve contracts through RocketStorage
    reth = rs_get_address("rocketTokenRETH")
    dp_now = rs_get_address("rocketDepositPool")
    dp_at_start = rs_get_address("rocketDepositPool", sb)
    dp_at_end = rs_get_address("rocketDepositPool", eb)
    assert reth == EXPECTED_RETH, reth
    print("rETH", reth, "depositPool now", dp_now, "at start", dp_at_start, "at end", dp_at_end)

    # 2. mint / burn / deposit logs
    mints = cached("mints_%d_%d" % (sb, eb), lambda: get_logs_chunked(
        reth, [T_TOKENS_MINTED], sb, eb, 10000, "TokensMinted"))
    burns = cached("burns_%d_%d" % (sb, eb), lambda: get_logs_chunked(
        reth, [T_TOKENS_BURNED], sb, eb, 10000, "TokensBurned"))
    # DepositReceived from ANY emitter (catches older deposit pool versions); filter to RP later
    # DepositReceived from every deposit pool that was registered during the window
    dp_addrs = sorted({dp_at_start, dp_at_end, dp_now})
    deps = cached("deposits_%d_%d" % (sb, eb), lambda: get_logs_chunked(
        dp_addrs, [T_DEPOSIT_RECEIVED], sb, eb, 10000, "DepositReceived"))
    credits = cached("credits_%d_%d" % (sb, eb), lambda: get_logs_chunked(
        dp_addrs, [T_CREDIT_WITHDRAWN], sb, eb, 10000, "CreditWithdrawn"))
    print(len(credits), "CreditWithdrawn")
    print(len(mints), "mints", len(burns), "burns", len(deps), "DepositReceived (deposit pools)")

    mint_txs = sorted({l["transactionHash"] for l in mints})
    mint_tx_set = set(mint_txs)
    deps_rp = [l for l in deps if l["transactionHash"] in mint_tx_set]
    emitters = sorted({l["address"].lower() for l in deps_rp})
    emitter_info = {}
    for e in emitters:
        emitter_info[e] = {
            "rocketstorage_name_at_start": rs_get_string("contract.name", e, sb),
            "rocketstorage_exists_at_start": rs_get_bool("contract.exists", e, sb),
            "rocketstorage_exists_now": rs_get_bool("contract.exists", e),
            "n_events": sum(1 for l in deps_rp if l["address"].lower() == e),
        }
    print("deposit pool emitters", emitter_info)

    # 3. transactions behind each mint
    def fetch_txs():
        res = rpc_batch([("eth_getTransactionByHash", [h]) for h in mint_txs], 20)
        return {h: {"from": r["from"].lower(), "to": (r["to"] or "").lower(), "type": r.get("type"),
                    "value": r["value"], "input4": r["input"][:10], "block": r["blockNumber"]}
                for h, r in zip(mint_txs, res)}
    txs = cached("txs_%d_%d" % (sb, eb), fetch_txs)

    # 4. supply cross-check inputs (archive eth_call)
    ts_sel = selector("totalSupply()")
    supply_before = to_int(eth_call(reth, ts_sel, sb - 1))
    supply_end = to_int(eth_call(reth, ts_sel, eb))

    # 5. DEX pools (resolved on-chain from factories)
    pools = {}
    for fee in (100, 500, 3000, 10000):
        a, b = sorted([reth, WETH])
        r = eth_call(UNIV3_FACTORY, selector("getPool(address,address,uint24)") + enc_addr(a) + enc_addr(b)
                     + enc_uint(fee))
        p = dec_addr(r[2:])
        if int(p, 16):
            t0a = dec_addr(eth_call(p, selector("token0()"))[2:])
            pools[p] = {"dex": "Uniswap v3", "fee_bps": fee / 100, "token0": t0a,
                        "source": "UniswapV3Factory.getPool(rETH, WETH, %d)" % fee}
    r = eth_call(UNIV2_FACTORY, selector("getPair(address,address)") + enc_addr(reth) + enc_addr(WETH))
    v2 = dec_addr(r[2:])
    if int(v2, 16):
        pools[v2] = {"dex": "Uniswap v2", "token0": dec_addr(eth_call(v2, selector("token0()"))[2:]),
                     "source": "UniswapV2Factory.getPair(rETH, WETH)"}
    print("pools", pools)

    def fetch_dex():
        out = []
        for p, info in pools.items():
            if info["dex"] == "Uniswap v3":
                logs = get_logs_chunked(p, [T_UNIV3_SWAP], sb, eb, 10000, "univ3 " + p[:8])
                for l in logs:
                    w = words(l["data"])
                    a0, a1 = to_signed(w[0]), to_signed(w[1])
                    reth_delta = a0 if info["token0"] == reth else a1  # +in to pool, -out of pool
                    if reth_delta < 0:
                        out.append({"venue": "Uniswap v3 rETH/WETH %.2f%%" % (info["fee_bps"] / 100), "pool": p,
                                    "block": to_int(l["blockNumber"]), "tx": l["transactionHash"],
                                    "recipient": dec_addr(l["topics"][2]), "reth_out": -reth_delta})
            else:
                logs = get_logs_chunked(p, [T_UNIV2_SWAP], sb, eb, 10000, "univ2")
                for l in logs:
                    w = words(l["data"])
                    a0out, a1out = int(w[2], 16), int(w[3], 16)
                    ro = a0out if info["token0"] == reth else a1out
                    if ro:
                        out.append({"venue": "Uniswap v2 rETH/WETH", "pool": p, "block": to_int(l["blockNumber"]),
                                    "tx": l["transactionHash"], "recipient": dec_addr(l["topics"][2]),
                                    "reth_out": ro})
        logs = get_logs_chunked(BALANCER_V2_VAULT, [T_BAL_SWAP, None, None, pad_addr(reth)], sb, eb, 10000,
                                "balancer v2")
        for l in logs:
            w = words(l["data"])
            out.append({"venue": "Balancer v2 (all pools, tokenOut=rETH)", "pool": l["topics"][1],
                        "block": to_int(l["blockNumber"]), "tx": l["transactionHash"],
                        "token_in": dec_addr(l["topics"][2]), "recipient": "", "reth_out": int(w[1], 16)})
        return out
    dex = cached("dex_%d_%d" % (sb, eb), fetch_dex)

    # Singleton vaults where pool-level Swap filtering needs pool ids we don't have: count rETH Transfer events
    # OUT of the vault instead (approximate: includes liquidity withdrawals, not only swaps).
    def fetch_dex_extra():
        out = []
        for venue, vault in SINGLETON_VAULTS.items():
            logs = get_logs_chunked(reth, [T_TRANSFER, pad_addr(vault)], sb, eb, 10000, venue)
            for l in logs:
                out.append({"venue": venue + " (rETH Transfer out, approx.)", "pool": vault,
                            "block": to_int(l["blockNumber"]), "tx": l["transactionHash"],
                            "recipient": dec_addr(l["topics"][2]), "reth_out": int(l["data"], 16)})
        return out
    dex = dex + cached("dexextra_%d_%d" % (sb, eb), fetch_dex_extra)

    # block timestamps for DEX rows: interpolate from samples every 7200 blocks (~1 day)
    def fetch_samples():
        pts = list(range(sb, eb + 1, 7200)) + [eb]
        res = rpc_batch([("eth_getBlockByNumber", [hex(n), False]) for n in pts], 20)
        return [[n, to_int(r["timestamp"])] for n, r in zip(pts, res)]
    samples = cached("blocksamples_%d_%d" % (sb, eb), fetch_samples)

    def interp(n):
        for (a, ta), (b, tb) in zip(samples, samples[1:]):
            if a <= n <= b:
                return ta + (tb - ta) * (n - a) // max(1, b - a)
        return samples[-1][1]

    # 6. address classification inputs: code, Safe probe, labels
    addrs = set()
    for l in mints:
        addrs.add(dec_addr(l["topics"][1]))
    for t in txs.values():
        addrs.add(t["from"])
        if t["to"]:
            addrs.add(t["to"])
    addrs = sorted(addrs)

    def fetch_codes():
        res = rpc_batch([("eth_getCode", [a, "latest"]) for a in addrs], 25)
        return {a: c for a, c in zip(addrs, res)}
    codes = cached("codes_%d_%d" % (sb, eb), fetch_codes)

    def code_kind(c):
        if not c or c == "0x":
            return "EOA"
        if c.startswith("0xef0100") and len(c) == 2 + 46:
            return "EOA+7702->" + "0x" + c[8:]
        return "contract"
    contracts = [a for a in addrs if code_kind(codes[a]) == "contract"]

    def fetch_safe():
        out = {}
        for a in contracts:
            try:
                thr = to_int(eth_call(a, selector("getThreshold()")))
                ver = eth_call(a, selector("VERSION()"))
                w = words(ver)
                v = bytes.fromhex("".join(w[2:])[:int(w[1], 16) * 2]).decode() if len(w) > 2 else ""
                out[a] = {"safe_threshold": thr, "safe_version": v}
            except Exception:
                out[a] = {}
        return out
    safes = cached("safe_%d_%d" % (sb, eb), fetch_safe)

    # Labels only for contracts and 7702 delegates seen as tx.to or depositor (EOA senders are not labelled)
    to_label = sorted(set(contracts) | set(pools) | set(emitters) | set(SINGLETON_VAULTS.values()) |
                      {"0x" + codes[a][8:] for a in addrs if code_kind(codes[a]).startswith("EOA+7702")})
    lab_path = os.path.join(CACHE, "labels.json")
    labels = json.load(open(lab_path)) if os.path.exists(lab_path) else {}
    for i, a in enumerate(to_label):
        old = labels.get(a)
        if old and old.get("etherscan_tag") != "?" and old.get("bs_name") != "?":
            continue
        info = dict(old) if old else {}
        if not old or old.get("etherscan_tag") == "?":
            info["etherscan_tag"] = etherscan_tag(a)
        if not old or old.get("bs_name") == "?":
            info.update(blockscout_info(a))
        labels[a] = info
        print("  label %d/%d %s %s | %s" % (i + 1, len(to_label), a, info["etherscan_tag"], info["bs_name"]),
              flush=True)
        json.dump(labels, open(lab_path, "w"), indent=1)
        time.sleep(1.5)

    # ---------------------------------------------------------------- write outputs
    # Each mint is followed in the same tx by the deposit pool event that caused it:
    # DepositReceived (user deposit(), new ETH) or CreditWithdrawn (node operator credit taken as rETH).
    dp_events = {}
    for kind, ls in (("deposit", deps), ("credit_withdrawal", credits)):
        for l in ls:
            dp_events.setdefault(l["transactionHash"], []).append((to_int(l["logIndex"]), kind, l))
    for v in dp_events.values():
        v.sort(key=lambda x: x[0])

    with open(os.path.join(DATA, "mints.csv"), "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["block", "time_utc", "tx_hash", "log_index", "depositor", "reth_minted_wei", "eth_net_wei",
                    "eth_gross_wei", "mint_path", "node_address", "deposit_pool", "tx_from", "tx_to", "tx_type", "tx_selector"])
        used = set()
        for l in sorted(mints, key=lambda x: (to_int(x["blockNumber"]), to_int(x["logIndex"]))):
            h = l["transactionHash"]
            wd = words(l["data"])
            t = txs[h]
            li = to_int(l["logIndex"])
            ev = next((e for e in dp_events.get(h, []) if e[0] > li and (h, e[0]) not in used), None)
            if ev:
                used.add((h, ev[0]))
                gross, path, pool = int(words(ev[2]["data"])[0], 16), ev[1], ev[2]["address"].lower()
                node = dec_addr(ev[2]["topics"][1]) if path == "credit_withdrawal" else ""
            else:
                gross, path, pool, node = "", "unmatched", "", ""
            w.writerow([to_int(l["blockNumber"]),
                        dt.datetime.fromtimestamp(int(wd[2], 16), dt.timezone.utc).strftime("%Y-%m-%d %H:%M:%S"),
                        h, li, dec_addr(l["topics"][1]), int(wd[0], 16), int(wd[1], 16), gross,
                        path, node, pool, t["from"], t["to"], t["type"], t["input4"]])

    with open(os.path.join(DATA, "burns.csv"), "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["block", "time_utc", "tx_hash", "from", "reth_burned_wei", "eth_wei"])
        for l in burns:
            wd = words(l["data"])
            w.writerow([to_int(l["blockNumber"]),
                        dt.datetime.fromtimestamp(int(wd[2], 16), dt.timezone.utc).strftime("%Y-%m-%d %H:%M:%S"),
                        l["transactionHash"], dec_addr(l["topics"][1]), int(wd[0], 16), int(wd[1], 16)])

    with open(os.path.join(DATA, "dex_buys.csv"), "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["block", "time_utc_approx", "tx_hash", "venue", "pool_or_poolid", "token_in", "recipient",
                    "reth_out_wei"])
        for r in sorted(dex, key=lambda x: x["block"]):
            w.writerow([r["block"], dt.datetime.fromtimestamp(interp(r["block"]), dt.timezone.utc)
                        .strftime("%Y-%m-%d %H:%M"), r["tx"], r["venue"], r["pool"], r.get("token_in", WETH),
                        r["recipient"], r["reth_out"]])

    with open(os.path.join(DATA, "addresses.csv"), "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["address", "code_kind", "safe_threshold", "safe_version", "etherscan_tag", "blockscout_name",
                    "blockscout_verified", "blockscout_tags", "blockscout_impl"])
        for a in sorted(set(addrs) | set(to_label)):
            ck = code_kind(codes.get(a, "")) if a in codes else "contract(label-only)"
            s = safes.get(a, {})
            lb = labels.get(a, {})
            w.writerow([a, ck, s.get("safe_threshold", ""), s.get("safe_version", ""), clean_tag(lb.get("etherscan_tag", "")),
                        lb.get("bs_name", ""), lb.get("bs_verified", ""), lb.get("bs_tags", ""),
                        lb.get("bs_impl", "")])

    meta = {"window": {"start_date": d0, "end_date_exclusive": d1, "start_block": sb, "end_block": eb},
            "rocket_storage": ROCKET_STORAGE, "rocketTokenRETH": reth, "rETH_matches_expected": reth == EXPECTED_RETH,
            "rocketDepositPool_now": dp_now, "rocketDepositPool_at_start_block": dp_at_start,
            "rocketDepositPool_at_end_block": dp_at_end, "deposit_received_emitters": emitter_info,
            "pools": pools, "balancer_v2_vault": BALANCER_V2_VAULT,
            "reth_total_supply_at_block_before_start": str(supply_before),
            "reth_total_supply_at_end_block": str(supply_end),
            "topics": {"CreditWithdrawn": T_CREDIT_WITHDRAWN, "TokensMinted": T_TOKENS_MINTED, "TokensBurned": T_TOKENS_BURNED,
                       "DepositReceived": T_DEPOSIT_RECEIVED},
            "rpc_stats": STATS, "fetched_at_utc": dt.datetime.utcnow().isoformat() + "Z"}
    json.dump(meta, open(os.path.join(DATA, "meta.json"), "w"), indent=1)
    print("done", STATS)


if __name__ == "__main__":
    main()
