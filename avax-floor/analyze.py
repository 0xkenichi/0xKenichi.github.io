"""Build the daily series, the before/after table per floor level, the burn cross-check and the
calibration against the Foundation's published figures. Reads only data/ (run fetch.py and floor.py first).

Outputs:
  data/daily.csv          one row per UTC day, 1 Aug 2026 to the last complete day (chart data)
  data/regimes.csv        before/after table per floor level
  data/crosscheck.json    burn and price cross-checks between independent sources
  data/calibration.json   our free inputs vs the Foundation's published numbers
"""
import csv
import datetime as dt
import json
import os
import statistics as st
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))  # python3 -I drops the script dir
from regimes import REGIMES, regime_of

HERE = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(HERE, "data")
RAW = os.path.join(DATA, "raw")
SERIES_START = "2026-08-01"


def load(name):
    with open(os.path.join(RAW, name)) as f:
        return json.load(f)


def day(t):
    return dt.datetime.fromtimestamp(int(t), dt.timezone.utc).strftime("%Y-%m-%d")


def main():
    meta = load("meta.json")
    end = meta["end"]
    burn_rs = {r["UTCDate"]: float(r["transactionFee_Eth"]) for r in load("routescan_dailytxnfee.json")["result"]}
    tx_rs = {r["UTCDate"]: int(r["transactionCount"]) for r in load("routescan_dailytx.json")["result"]}
    burn_m = {day(r["timestamp"]): r["value"] for r in load("avax_metrics_feesPaid.json")}
    tx_m = {day(r["timestamp"]): r["value"] for r in load("avax_metrics_txCount.json")}
    px = {d: v["price"] for d, v in load("llama_avax_price_noon.json").items() if v}
    cg = {day(t / 1000): p for t, p in load("coingecko_avax_365d.json")["prices"]}
    chain_usd = {day(t): v for t, v in load("llama_summary_fees_avalanche.json")["totalDataChart"]}
    chain_rev_usd = {day(t): v for t, v in load("llama_summary_revenue_avalanche.json")["totalDataChart"]}
    ov = load("llama_overview_fees_avalanche.json")
    app = {day(t): v for t, v in ov["totalDataChart"]}
    # Floor and base fee per day from the hourly headers
    hdr = {}
    with open(os.path.join(DATA, "headers_hourly.csv")) as f:
        for r in csv.DictReader(f):
            hdr.setdefault(r["utc"][:10], []).append(r)

    days = []
    d = dt.date.fromisoformat(SERIES_START)
    while d.isoformat() <= end:
        days.append(d.isoformat())
        d += dt.timedelta(days=1)
    rows = []
    for k in days:
        h = hdr.get(k, [])
        bf = [float(x["base_fee_navax"]) for x in h]
        fl = [float(x["floor_navax"]) for x in h]
        p = px.get(k)
        b = burn_rs.get(k)
        rows.append({
            "date": k,
            "regime": regime_of(k) or "",
            "floor_navax_end_of_day": float(f"{fl[-1]:.6g}") if fl else "",
            "floor_navax_min": float(f"{min(fl):.6g}") if fl else "",
            "base_fee_navax_median": round(st.median(bf), 4) if bf else "",
            "header_samples": len(h),
            "tx_count": tx_rs.get(k, ""),
            "avax_burned": round(b, 3) if b is not None else "",
            "avax_price_usd": round(p, 4) if p else "",
            "usd_burned": round(b * p, 2) if (b is not None and p) else "",
            "app_fees_usd_defillama": round(app[k], 2) if k in app else "",
            "chain_share_pct": round(100 * b * p / app[k], 3) if (b is not None and p and app.get(k)) else "",
            "fee_per_tx_navax": round(b / tx_rs[k] * 1e9) if (b is not None and tx_rs.get(k)) else "",
            "usd_burned_defillama": round(chain_usd[k], 2) if k in chain_usd else "",
            "avax_burned_avax_metrics_api": round(burn_m[k], 3) if k in burn_m else "",
            "tx_count_avax_metrics_api": tx_m.get(k, ""),
            "avax_price_usd_coingecko": round(cg[k], 4) if k in cg else "",
        })
    with open(os.path.join(DATA, "daily.csv"), "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        w.writeheader()
        w.writerows(rows)

    # Chart file: the main chart columns plus 7-day centred means
    def roll(col, i):
        w = [rows[j][col] for j in range(max(0, i - 3), min(len(rows), i + 4)) if rows[j][col] != ""]
        return round(st.mean(w), 3) if len(w) == 7 else ""
    with open(os.path.join(DATA, "chart_daily.csv"), "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["date", "floor_navax", "base_fee_navax_median", "tx_count", "tx_count_7d", "avax_burned",
                    "avax_burned_7d", "usd_burned", "app_fees_usd", "chain_share_pct", "chain_share_pct_7d", "avax_price_usd"])
        for i, r in enumerate(rows):
            w.writerow([r["date"], r["floor_navax_end_of_day"], r["base_fee_navax_median"], r["tx_count"], roll("tx_count", i),
                        r["avax_burned"], roll("avax_burned", i), r["usd_burned"], r["app_fees_usd_defillama"],
                        r["chain_share_pct"], roll("chain_share_pct", i), r["avax_price_usd"]])

    # ---------------------------------------------------------------- before/after per regime
    out = []
    ref = [r for r in rows if "2026-09-12" <= r["date"] <= "2026-09-21"]  # last 10 days before Helicon
    ref_burn_med = st.median([r["avax_burned"] for r in ref])
    ref_tx_min = min(r["tx_count"] for r in ref)
    for key, label, a, b in REGIMES:
        rr = [r for r in rows if a <= r["date"] <= b]
        n = len(rr)
        tx = [r["tx_count"] for r in rr]
        av = [r["avax_burned"] for r in rr]
        usd = [r["usd_burned"] for r in rr]
        appf = [r["app_fees_usd_defillama"] for r in rr]
        out.append({
            "regime": key, "label": label, "from": a, "to": b, "days": n,
            "floor_navax": rr[-1]["floor_navax_end_of_day"],
            "base_fee_navax_median": round(st.median([r["base_fee_navax_median"] for r in rr]), 3),
            "tx_per_day_mean": round(st.mean(tx)), "tx_per_day_median": round(st.median(tx)),
            "avax_burned_per_day_mean": round(st.mean(av), 1), "avax_burned_per_day_median": round(st.median(av), 1),
            "usd_burned_per_day_mean": round(st.mean(usd)), "usd_burned_per_day_median": round(st.median(usd)),
            "app_fees_usd_per_day_mean": round(st.mean(appf)),
            "chain_share_pct_pooled": round(100 * sum(usd) / sum(appf), 2),
            "chain_share_pct_median_day": round(st.median([r["chain_share_pct"] for r in rr]), 2),
            "avax_price_mean": round(st.mean([r["avax_price_usd"] for r in rr]), 2),
            "fee_per_tx_navax_pooled": round(sum(av) / sum(tx) * 1e9),
            "max_day_share_of_burn_pct": round(100 * max(av) / sum(av), 1),
            "days_burn_above_last10_pre_median_pct": round(100 * sum(1 for x in av if x > ref_burn_med) / n),
            "days_tx_below_last10_pre_min_pct": round(100 * sum(1 for x in tx if x < ref_tx_min) / n),
        })
    with open(os.path.join(DATA, "regimes.csv"), "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(out[0].keys()))
        w.writeheader()
        w.writerows(out)
    for o in out:
        print(o)

    # ---------------------------------------------------------------- cross-checks
    def gap(xs, ys):
        common = [k for k in days if k in xs and k in ys and xs[k] and ys[k]]
        sx, sy = sum(xs[k] for k in common), sum(ys[k] for k in common)
        daily = sorted(abs(xs[k] / ys[k] - 1) for k in common)
        return {"days": len(common), "first": common[0], "last": common[-1], "sum_a": round(sx, 2), "sum_b": round(sy, 2),
                "total_gap_pct": round(100 * (sx / sy - 1), 3),
                "median_abs_daily_gap_pct": round(100 * daily[len(daily) // 2], 3),
                "max_abs_daily_gap_pct": round(100 * daily[-1], 3)}
    burn_usd_rs = {r["date"]: r["usd_burned"] for r in rows if r["usd_burned"] != ""}
    llama_avax = {k: chain_usd[k] / px[k] for k in days if k in chain_usd and k in px}
    xc = {
        "burn_AVAX_routescan_vs_avax_metrics_api": gap(burn_rs, burn_m),
        "burn_USD_routescan_x_price_vs_defillama_chain_fees": gap(burn_usd_rs, chain_usd),
        "burn_AVAX_routescan_vs_defillama_usd_div_price": gap(burn_rs, llama_avax),
        "defillama_fees_vs_defillama_revenue_burned": gap(chain_usd, chain_rev_usd),
        "tx_routescan_vs_avax_metrics_api": gap(tx_rs, tx_m),
        "price_defillama_noon_vs_coingecko_daily": gap(px, cg),
    }
    # per regime gap Routescan vs DefiLlama (USD)
    for key, label, a, b in REGIMES:
        xs = {k: v for k, v in burn_usd_rs.items() if a <= k <= b}
        ys = {k: v for k, v in chain_usd.items() if a <= k <= b}
        xc[f"burn_USD_routescan_vs_defillama__{key}"] = gap(xs, ys)
    with open(os.path.join(DATA, "crosscheck.json"), "w") as f:
        json.dump(xc, f, indent=1)
    print(json.dumps(xc, indent=1))

    # ---------------------------------------------------------------- calibration
    long_burn = {r["UTCDate"]: float(r["transactionFee_Eth"]) for r in load("routescan_dailytxnfee_2024_2026.json")["result"]}
    lp = {}
    for p in load("llama_avax_price_chart_2024_2026.json"):
        lp.setdefault(day(p["timestamp"]), p["price"])

    def window(a, b):
        ks = [k for k in sorted(long_burn) if a <= k <= b]
        miss = [k for k in ks if k not in lp]
        # fill a missing price day with the previous known day
        last, usd = None, 0.0
        for k in ks:
            last = lp.get(k, last)
            usd += long_burn[k] * last
        appsum = sum(v for k, v in app.items() if a <= k <= b)
        chainsum = sum(v for k, v in chain_usd.items() if a <= k <= b)
        return {"from": a, "to": b, "days": len(ks), "price_days_filled": len(miss),
                "routescan_burn_avax": round(sum(long_burn[k] for k in ks)), "routescan_burn_usd": round(usd),
                "defillama_chain_fees_usd": round(chainsum), "defillama_app_fees_usd": round(appsum),
                "ratio_defillama_chain_over_app_pct": round(100 * chainsum / appsum, 2),
                "ratio_routescan_burn_over_app_pct": round(100 * usd / appsum, 2)}
    cal = {
        "foundation_price_of_a_transaction_jan2025_aug2026": {
            "published": {"protocol_revenue_usd": 282.2e6, "tx_fees_usd": 9.6e6, "fee_over_revenue_pct": 3.39,
                          "source": "avalanche.com/about/blog/the-price-of-a-transaction-benchmarking-the-avalanche-c-chain-on-cost-and-capture"},
            "ours": window("2025-01-01", "2026-08-31")},
        "foundation_latest_month_aug2026": {"published": {"fee_over_revenue_pct": 1.13}, "ours": window("2026-08-01", "2026-08-31")},
        "foundation_jan2025_month": {"published": {"fee_over_revenue_pct": 5.79}, "ours": window("2025-01-01", "2025-01-31")},
        "foundation_burn_since_2024": {
            "published": {"burned_usd": 23.5e6, "note": "GCI post (12 Aug 2026): burned C-Chain fees since start of 2024, ~$23.5M; end date not stated, assumed end of Jun/Jul 2026"},
            "ours_to_jun_30": window("2024-01-01", "2026-06-30"), "ours_to_jul_31": window("2024-01-01", "2026-07-31")},
        "foundation_aug2026_tx_per_day": {"published": 2.23e6,
                                           "ours_routescan_aug_mean": round(st.mean([v for k, v in tx_rs.items() if k.startswith("2026-08")]))},
        "foundation_june2026_month": {"published": {"ngcp_usd": 3.1e6, "note": "NGCP needs on-chain expense data we don't have; shown for scale only"},
                                      "ours": window("2026-06-01", "2026-06-30")},
    }
    with open(os.path.join(DATA, "calibration.json"), "w") as f:
        json.dump(cal, f, indent=1)
    print(json.dumps(cal, indent=1))


if __name__ == "__main__":
    main()
