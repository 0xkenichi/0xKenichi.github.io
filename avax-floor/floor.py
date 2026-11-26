"""Pin the C-Chain gas floor (ACP-283 minimum gas price) from block headers.

After Helicon, every C-Chain header carries `minPriceExponent`. The floor in wei is
    floor = 2 ** (minPriceExponent / 2**58)
(fitted from the headers themselves: the base fee in quiet blocks equals this value exactly,
e.g. 5.0, 2.5 and 7.5 nAVAX; see results.md). Before Helicon the header has no such field and
the floor was the ACP-176 minimum of 1 wei.

Outputs:
  data/headers_hourly.csv   one header roughly every hour (3,600 blocks) from 1 Aug 2026
  data/floor_changes.csv    exact first block of Helicon and of every floor transition (start/end)
"""
import csv
import datetime as dt
import json
import math
import os
import sys
from concurrent.futures import ThreadPoolExecutor

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))  # python3 -I drops the script dir
from netlib import rpc, block, block_at

HERE = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(HERE, "data")
START = int(dt.datetime(2026, 8, 1, tzinfo=dt.timezone.utc).timestamp())
STEP = 3600


def floor_wei(mpe):
    return 2 ** (mpe / 2 ** 58) if mpe is not None else 1.0


def hdr(n):
    b = block(n)
    m = b.get("minPriceExponent")
    return {"block": n, "ts": int(b["timestamp"], 16), "base_fee_wei": int(b["baseFeePerGas"], 16),
            "gas_used": int(b["gasUsed"], 16), "mpe": int(m, 16) if m else None}


def iso(t):
    return dt.datetime.fromtimestamp(t, dt.timezone.utc).strftime("%Y-%m-%d %H:%M:%S")


def first_block(lo, hi, pred):
    """Smallest n in (lo, hi] with pred(hdr(n)) true; pred(lo) false, pred(hi) true, monotone."""
    while hi - lo > 1:
        mid = (lo + hi) // 2
        if pred(hdr(mid)):
            hi = mid
        else:
            lo = mid
    return hi


def main():
    os.makedirs(DATA, exist_ok=True)
    if "--changes-only" in sys.argv:  # reuse the hourly headers already on disk
        rows = []
        with open(os.path.join(DATA, "headers_hourly.csv")) as f:
            for r in csv.DictReader(f):
                rows.append({"block": int(r["block"]), "ts": 0, "base_fee_wei": 0, "gas_used": 0,
                             "mpe": int(r["min_price_exponent"]) if r["min_price_exponent"] else None})
        return find_changes(rows)
    latest = int(rpc("eth_blockNumber", []), 16)
    b0 = block_at(START, lo=88_000_000, hi=latest)
    ns = list(range(b0, latest + 1, STEP))
    print(f"sampling {len(ns)} headers from block {b0} to {latest}", flush=True)
    with ThreadPoolExecutor(4) as ex:
        rows = list(ex.map(hdr, ns))
    with open(os.path.join(DATA, "headers_hourly.csv"), "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["block", "utc", "base_fee_navax", "floor_navax", "gas_used", "min_price_exponent"])
        for r in rows:
            w.writerow([r["block"], iso(r["ts"]), f"{r['base_fee_wei'] / 1e9:.9f}",
                        f"{floor_wei(r['mpe']) / 1e9:.9f}", r["gas_used"], r["mpe"] if r["mpe"] is not None else ""])
    find_changes(rows)


def find_changes(rows):

    # Episodes: runs of hourly samples whose mpe differs from the previous sample.
    changes = []
    i = 1
    while i < len(rows):
        if rows[i]["mpe"] == rows[i - 1]["mpe"]:
            i += 1
            continue
        old = rows[i - 1]
        j = i
        while j + 1 < len(rows) and rows[j + 1]["mpe"] != rows[j]["mpe"]:
            j += 1
        new = rows[j]
        # exact first block that leaves the old value, and first block that reaches the new value
        s = first_block(old["block"], rows[i]["block"], lambda h, v=old["mpe"]: h["mpe"] != v)
        e = first_block(rows[j - 1]["block"] if j > i else old["block"], new["block"],
                        lambda h, v=new["mpe"]: h["mpe"] == v) if j > i else s
        hs, he = hdr(s), hdr(e)
        changes.append({
            "from_floor_navax": floor_wei(old["mpe"]) / 1e9, "to_floor_navax": floor_wei(new["mpe"]) / 1e9,
            "start_block": s, "start_utc": iso(hs["ts"]), "start_floor_navax": floor_wei(hs["mpe"]) / 1e9,
            "end_block": e, "end_utc": iso(he["ts"]), "end_floor_navax": floor_wei(he["mpe"]) / 1e9,
            "hours": round((he["ts"] - hs["ts"]) / 3600, 2),
            "is_helicon_activation": old["mpe"] is None,
        })
        print(changes[-1], flush=True)
        if old["mpe"] is None:
            # During the Helicon ramp the floor only binds once it passes the market base fee.
            # Record when it first reached 0.1 nAVAX (pre-Helicon median base fee was ~0.07) and 1 nAVAX.
            for thr in (0.1, 1.0):
                t = thr * 1e9
                nb = first_block(s, e, lambda h, t=t: h["mpe"] is not None and floor_wei(h["mpe"]) >= t)
                hb = hdr(nb)
                changes.append({
                    "from_floor_navax": floor_wei(old["mpe"]) / 1e9, "to_floor_navax": floor_wei(new["mpe"]) / 1e9,
                    "start_block": nb, "start_utc": iso(hb["ts"]), "start_floor_navax": floor_wei(hb["mpe"]) / 1e9,
                    "end_block": "", "end_utc": "", "end_floor_navax": "", "hours": "",
                    "is_helicon_activation": f"ramp crossed {thr} nAVAX",
                })
                print(changes[-1], flush=True)
        i = j + 1
    with open(os.path.join(DATA, "floor_changes.csv"), "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(changes[0].keys()))
        w.writeheader()
        for c in changes:
            w.writerow({k: (f"{v:.6g}" if isinstance(v, float) else v) for k, v in c.items()})


if __name__ == "__main__":
    main()
