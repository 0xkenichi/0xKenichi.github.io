"""Who left? Sample whole blocks in each floor regime and classify every transaction.

For each regime we draw N block numbers uniformly at random (fixed seed) from the regime's block
range, fetch the block with full transactions plus its receipts from public RPC, and keep one row
per transaction. Sampling whole blocks uniformly by block number gives an unbiased estimate of each
class's share of all transactions in the range.

Output: data/sample_txs.csv.gz (one row per sampled tx), data/sample_blocks.csv
Usage: python3 -I sample.py [blocks_per_regime]   (default 300)
"""
import csv
import datetime as dt
import gzip
import os
import random
import sys
from concurrent.futures import ThreadPoolExecutor

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))  # python3 -I drops the script dir
from netlib import rpc, block, block_at
from regimes import REGIMES

HERE = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(HERE, "data")


def utc(day, end=False):
    d = dt.datetime.fromisoformat(day).replace(tzinfo=dt.timezone.utc)
    return int((d + dt.timedelta(days=1)).timestamp()) if end else int(d.timestamp())


CACHE = os.path.join(DATA, "raw", "blocks")


def fetch_cached(n):
    """Block with full txs + receipts, cached on disk so an interrupted run resumes."""
    import json
    p = os.path.join(CACHE, f"{n}.json.gz")
    if os.path.exists(p):
        with gzip.open(p, "rt") as f:
            return json.load(f)
    d = {"block": block(n, True), "receipts": rpc("eth_getBlockReceipts", [hex(n)])}
    with gzip.open(p + ".tmp", "wt") as f:
        json.dump(d, f)
    os.replace(p + ".tmp", p)
    return d


def one(n):
    d = fetch_cached(n)
    b, rc = d["block"], d["receipts"]
    st = {r["transactionHash"]: r for r in rc}
    base = int(b["baseFeePerGas"], 16)
    rows = []
    for t in b["transactions"]:
        r = st[t["hash"]]
        gu = int(r["gasUsed"], 16)
        egp = int(r["effectiveGasPrice"], 16)
        inp = t.get("input") or "0x"
        rows.append({
            "block": n, "ts": int(b["timestamp"], 16), "hash": t["hash"], "from": t["from"].lower(),
            "to": (t.get("to") or "").lower(), "value_wei": int(t["value"], 16), "selector": inp[:10] if len(inp) >= 10 else "",
            "input_bytes": (len(inp) - 2) // 2, "gas_used": gu, "eff_gas_price": egp, "base_fee": base,
            "status": int(r.get("status", "0x1"), 16), "type": int(t.get("type", "0x0"), 16),
            "logs": len(r.get("logs", [])),
        })
    return {"block": n, "ts": int(b["timestamp"], 16), "base_fee": base, "gas_used": int(b["gasUsed"], 16),
            "ntx": len(rows)}, rows


def main():
    n_per = int(sys.argv[1]) if len(sys.argv) > 1 else 300
    rnd = random.Random(283)
    latest = int(rpc("eth_blockNumber", []), 16)
    jobs = []
    for key, label, a, b in REGIMES:
        lo = block_at(utc(a), lo=88_000_000, hi=latest)
        hi = block_at(utc(b, end=True), lo=lo, hi=latest) - 1
        picks = sorted(rnd.sample(range(lo, hi + 1), n_per))
        print(key, a, b, "blocks", lo, hi, flush=True)
        jobs += [(key, n) for n in picks]
    os.makedirs(CACHE, exist_ok=True)
    done = [0]

    def run(j):
        r = (j[0], one(j[1]))
        done[0] += 1
        if done[0] % 100 == 0:
            print("fetched", done[0], "of", len(jobs), flush=True)
        return r
    with ThreadPoolExecutor(4) as ex:
        res = list(ex.map(run, jobs))
    bf = os.path.join(DATA, "sample_blocks.csv")
    tf = os.path.join(DATA, "sample_txs.csv.gz")
    with open(bf, "w", newline="") as f1, gzip.open(tf, "wt", newline="") as f2:
        w1 = csv.writer(f1)
        w1.writerow(["regime", "block", "ts", "base_fee", "gas_used", "ntx"])
        w2 = None
        for key, (bk, rows) in res:
            w1.writerow([key, bk["block"], bk["ts"], bk["base_fee"], bk["gas_used"], bk["ntx"]])
            for r in rows:
                if w2 is None:
                    w2 = csv.DictWriter(f2, fieldnames=["regime"] + list(r.keys()))
                    w2.writeheader()
                w2.writerow({"regime": key, **r})
    print("blocks", len(res), "txs", sum(len(r[1][1]) for r in res))


if __name__ == "__main__":
    main()
