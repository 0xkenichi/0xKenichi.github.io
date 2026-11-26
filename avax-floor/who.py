"""Who left? Summarise the sampled transactions (sample.py) per floor regime.

Classes (each tx in exactly one):
  failed            receipt status 0
  native transfer   succeeded, empty calldata (plain AVAX send)
  contract call     succeeded, calldata present, emitted >= 1 log
  call, no logs     succeeded, calldata present, emitted no log (typical of bots that probe/no-op)
  contract creation `to` empty
Also: share of txs from the top 1 / top 10 senders, top `to` addresses with an estimated tx/day
(share of sampled txs x the regime's Routescan mean tx/day), and the base-fee vs tip split of fees.

Labels for addresses come only from Routescan's verified-contract name (getsourcecode, keyless),
cached in data/raw/labels.json.  Output: data/who_summary.json, data/who_top_to.csv
"""
import collections
import csv
import gzip
import json
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))  # python3 -I drops the script dir
from netlib import get_json, rpc, block_at
import datetime as dt
from regimes import REGIMES

HERE = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(HERE, "data")
RS = "https://api.routescan.io/v2/network/mainnet/evm/43114/etherscan/api"


def label(addr, cache):
    if addr in cache:
        return cache[addr]
    lab = ""
    try:
        code = rpc("eth_getCode", [addr, "latest"])
        if code in ("0x", ""):
            lab = "EOA (no code)"
        elif code.startswith("0xef0100"):
            lab = "EOA with EIP-7702 delegation"
        else:
            r = get_json(f"{RS}?module=contract&action=getsourcecode&address={addr}")
            name = (r.get("result") or [{}])[0].get("ContractName") or ""
            lab = name if name else "unverified contract"
            time.sleep(0.4)
    except Exception as e:  # keep going; record the failure
        lab = f"lookup failed: {e}"[:80]
    cache[addr] = lab
    return lab


def classify(r):
    if not r["to"]:
        return "contract creation"
    if r["status"] == "0":
        return "failed"
    if r["input_bytes"] == "0":
        return "native transfer"
    return "contract call" if int(r["logs"]) > 0 else "call, no logs"


def main():
    with open(os.path.join(DATA, "regimes.csv")) as f:
        txday = {r["regime"]: int(r["tx_per_day_mean"]) for r in csv.DictReader(f)}
    by = collections.defaultdict(list)
    with gzip.open(os.path.join(DATA, "sample_txs.csv.gz"), "rt") as f:
        for r in csv.DictReader(f):
            by[r["regime"]].append(r)
    nblocks = collections.Counter()
    with open(os.path.join(DATA, "sample_blocks.csv")) as f:
        for r in csv.DictReader(f):
            nblocks[r["regime"]] += 1
    lab_path = os.path.join(DATA, "raw", "labels.json")
    cache = json.load(open(lab_path)) if os.path.exists(lab_path) else {}

    # blocks per day in each regime (to scale per-block sample means to per-day totals)
    latest = int(rpc("eth_blockNumber", []), 16)
    bpd = {}
    for key, _, a, b in REGIMES:
        t0 = int(dt.datetime.fromisoformat(a).replace(tzinfo=dt.timezone.utc).timestamp())
        t1 = int((dt.datetime.fromisoformat(b) + dt.timedelta(days=1)).replace(tzinfo=dt.timezone.utc).timestamp())
        lo = block_at(t0, lo=88_000_000, hi=latest)
        hi = block_at(t1, lo=lo, hi=latest)
        bpd[key] = (hi - lo) / ((t1 - t0) / 86400)
    summary, top_rows = {}, []
    classes = ["native transfer", "contract call", "call, no logs", "failed", "contract creation"]
    for key, lab, a, b in REGIMES:
        rows = by[key]
        n = len(rows)
        cls = collections.Counter(classify(r) for r in rows)
        snd = collections.Counter(r["from"] for r in rows)
        to = collections.Counter(r["to"] for r in rows)
        base = sum(int(r["gas_used"]) * int(r["base_fee"]) for r in rows)
        tot = sum(int(r["gas_used"]) * int(r["eff_gas_price"]) for r in rows)
        fees = sorted(int(r["gas_used"]) * int(r["eff_gas_price"]) for r in rows)
        zero_val = sum(1 for r in rows if r["value_wei"] == "0")
        # fee share paid by the top 10 senders
        fee_by_sender = collections.Counter()
        for r in rows:
            fee_by_sender[r["from"]] += int(r["gas_used"]) * int(r["eff_gas_price"])
        top10s = [s for s, _ in snd.most_common(10)]
        summary[key] = {
            "label": lab, "blocks_sampled": nblocks[key], "txs_sampled": n, "tx_per_block": round(n / nblocks[key], 2),
            "est_tx_per_day": txday[key],
            "class_share_pct": {c: round(100 * cls[c] / n, 1) for c in classes},
            "class_est_tx_per_day": {c: round(txday[key] * cls[c] / n) for c in classes},
            "zero_value_share_pct": round(100 * zero_val / n, 1),
            "distinct_senders": len(snd),
            "top1_sender_share_pct": round(100 * snd.most_common(1)[0][1] / n, 1),
            "top10_senders_share_pct": round(100 * sum(c for _, c in snd.most_common(10)) / n, 1),
            "top10_senders_share_of_fees_pct": round(100 * sum(fee_by_sender[s] for s in top10s) / tot, 1) if tot else None,
            "top10_to_share_pct": round(100 * sum(c for _, c in to.most_common(10)) / n, 1),
            "base_fee_share_of_fees_pct": round(100 * base / tot, 1) if tot else None,
            "median_fee_per_tx_navax": round(fees[n // 2] / 1e9),
            "blocks_per_day": round(bpd[key]),
            "est_base_fee_burn_avax_per_day": round(base / nblocks[key] * bpd[key] / 1e18, 1),
            "est_tip_burn_avax_per_day": round((tot - base) / nblocks[key] * bpd[key] / 1e18, 1),
            "est_total_burn_avax_per_day_from_sample": round(tot / nblocks[key] * bpd[key] / 1e18, 1),
            "est_tx_per_day_from_sample": round(n / nblocks[key] * bpd[key]),
            "est_gas_per_day_billion": round(sum(int(r["gas_used"]) for r in rows) / nblocks[key] * bpd[key] / 1e9, 1),
            "mean_fee_per_tx_navax": round(tot / n / 1e9),
        }
        for addr, c in to.most_common(10):
            top_rows.append({"regime": key, "to": addr or "(creation)", "label": label(addr, cache) if addr else "",
                             "share_pct": round(100 * c / n, 2), "sampled_txs": c,
                             "est_tx_per_day": round(txday[key] * c / n),
                             "distinct_senders": len({r["from"] for r in rows if r["to"] == addr}),
                             "top_selector": collections.Counter(r["selector"] for r in rows if r["to"] == addr).most_common(1)[0][0]})
    # 95% bootstrap intervals (resampling whole blocks) for the per-day estimates
    import random
    rnd = random.Random(283)
    for key, *_ in REGIMES:
        per_block = collections.defaultdict(lambda: [0, 0, 0, 0])  # gas, base wei, tip wei, ntx
        for r in by[key]:
            g, bf, e = int(r["gas_used"]), int(r["base_fee"]), int(r["eff_gas_price"])
            pb = per_block[r["block"]]
            pb[0] += g; pb[1] += g * bf; pb[2] += g * (e - bf); pb[3] += 1
        blocks = list(per_block.values()) + [[0, 0, 0, 0]] * (nblocks[key] - len(per_block))  # empty blocks
        reps = {"gas_bn": [], "base_avax": [], "tip_avax": []}
        for _ in range(1000):
            smp = [blocks[rnd.randrange(len(blocks))] for _ in blocks]
            f = bpd[key] / len(smp)
            reps["gas_bn"].append(sum(x[0] for x in smp) * f / 1e9)
            reps["base_avax"].append(sum(x[1] for x in smp) * f / 1e18)
            reps["tip_avax"].append(sum(x[2] for x in smp) * f / 1e18)
        for k2, v in reps.items():
            v.sort()
            summary[key][f"ci95_{k2}_per_day"] = [round(v[25], 1), round(v[974], 1)]

    # How much pre-Helicon traffic went to destinations never seen again after the floor bound
    post_to = {r["to"] for k in ("f5", "f2_5", "f7_5") for r in by[k]}
    for key in ("pre_aug", "pre_sep", "pre_last10"):
        rows = by[key]
        gone = [r for r in rows if r["to"] not in post_to]
        summary[key]["share_to_destinations_absent_after_pct"] = round(100 * len(gone) / len(rows), 1)
        summary[key]["est_tx_per_day_to_absent_destinations"] = round(txday[key] * len(gone) / len(rows))
    xp = {a for a, l in cache.items() if l == "XPower"}
    for key, *_ in REGIMES:
        rows = by[key]
        summary[key]["xpower_share_pct"] = round(100 * sum(1 for r in rows if r["to"] in xp) / len(rows), 1)
        summary[key]["xpower_est_tx_per_day"] = round(txday[key] * sum(1 for r in rows if r["to"] in xp) / len(rows))
    # Follow the biggest pre-Helicon destinations through every regime
    follow = {}
    for r in top_rows:
        if r["regime"] in ("pre_aug", "pre_last10"):
            follow[r["to"]] = r["label"]
    track = []
    for addr, lab in follow.items():
        row = {"to": addr, "label": lab}
        for key, *_ in REGIMES:
            rows = by[key]
            c = sum(1 for x in rows if x["to"] == addr)
            row[f"{key}_est_tx_per_day"] = round(txday[key] * c / len(rows))
        track.append(row)
    track.sort(key=lambda r: -r["pre_last10_est_tx_per_day"])
    with open(lab_path, "w") as f:
        json.dump(cache, f, indent=1)
    with open(os.path.join(DATA, "who_top_to.csv"), "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(top_rows[0].keys()))
        w.writeheader()
        w.writerows(top_rows)
    with open(os.path.join(DATA, "who_track.csv"), "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(track[0].keys()))
        w.writeheader()
        w.writerows(track)
    with open(os.path.join(DATA, "who_summary.json"), "w") as f:
        json.dump(summary, f, indent=1)
    # Chart file: one row per period, daily table + sample estimates
    with open(os.path.join(DATA, "regimes.csv")) as f:
        reg = {r["regime"]: r for r in csv.DictReader(f)}
    with open(os.path.join(DATA, "chart_regimes.csv"), "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["regime", "label", "from", "to", "days", "floor_navax", "tx_per_day", "avax_burned_per_day_median",
                    "chain_share_pct", "gas_per_day_bn", "base_fee_burn_avax_per_day", "base_ci_lo", "base_ci_hi",
                    "tip_burn_avax_per_day", "tip_ci_lo", "tip_ci_hi", "tx_day_contract_call_with_logs",
                    "tx_day_call_no_logs", "tx_day_failed", "tx_day_native_transfer", "tx_day_xpower"])
        for key, lab, a, b in REGIMES:
            r, m = reg[key], summary[key]
            c = m["class_est_tx_per_day"]
            w.writerow([key, lab, a, b, r["days"], r["floor_navax"], r["tx_per_day_mean"], r["avax_burned_per_day_median"],
                        r["chain_share_pct_pooled"], m["est_gas_per_day_billion"], m["est_base_fee_burn_avax_per_day"],
                        *m["ci95_base_avax_per_day"], m["est_tip_burn_avax_per_day"], *m["ci95_tip_avax_per_day"],
                        c["contract call"], c["call, no logs"], c["failed"], c["native transfer"], m["xpower_est_tx_per_day"]])
    print(json.dumps(summary, indent=1))
    for r in top_rows:
        print(r)
    for r in track:
        print(r)


if __name__ == "__main__":
    main()
