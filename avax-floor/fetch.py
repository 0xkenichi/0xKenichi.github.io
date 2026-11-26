"""Download the daily inputs (free, keyless public APIs) into data/raw/.

  Routescan (Etherscan-compatible API, chain 43114): daily tx fees in AVAX, daily tx count, daily gas used
  DefiLlama: Avalanche app fees by protocol (overview/fees/avalanche), the chain's own fees and burn
             (summary/fees/avalanche, dailyFees and dailyRevenue), AVAX price (coins.llama.fi)
  Avalanche metrics API (metrics.avax.network): feesPaid and txCount, kept only to show why we don't use it
"""
import datetime as dt
import json
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))  # python3 -I drops the script dir
from netlib import get_json

HERE = os.path.dirname(os.path.abspath(__file__))
RAW = os.path.join(HERE, "data", "raw")
RS = "https://api.routescan.io/v2/network/mainnet/evm/43114/etherscan/api"
START, END = "2026-07-01", None  # END defaults to yesterday (last complete UTC day)


def save(name, obj):
    with open(os.path.join(RAW, name), "w") as f:
        json.dump(obj, f)
    print("saved", name, flush=True)


def main():
    os.makedirs(RAW, exist_ok=True)
    end = END or (dt.datetime.now(dt.timezone.utc).date() - dt.timedelta(days=1)).isoformat()
    meta = {"pulled_utc": dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%d %H:%M"), "start": START, "end": end}
    for action in ("dailytxnfee", "dailytx", "dailygasused", "dailyavggasprice"):
        r = get_json(f"{RS}?module=stats&action={action}&startdate={START}&enddate={end}&sort=asc")
        save(f"routescan_{action}.json", r)
        time.sleep(1)
    save("llama_overview_fees_avalanche.json",
         get_json("https://api.llama.fi/overview/fees/avalanche?excludeTotalDataChart=false"
                  "&excludeTotalDataChartBreakdown=false"))
    save("llama_summary_fees_avalanche.json", get_json("https://api.llama.fi/summary/fees/avalanche?dataType=dailyFees"))
    save("llama_summary_revenue_avalanche.json",
         get_json("https://api.llama.fi/summary/fees/avalanche?dataType=dailyRevenue"))
    # AVAX price: one call per day at 00:00 UTC + 12h (noon), so no day is missing.
    d0 = dt.date.fromisoformat(START)
    d1 = dt.date.fromisoformat(end)
    px = {}
    d = d0
    while d <= d1:
        t = int(dt.datetime(d.year, d.month, d.day, 12, tzinfo=dt.timezone.utc).timestamp())
        r = get_json(f"https://coins.llama.fi/prices/historical/{t}/coingecko:avalanche-2?searchWidth=6h")
        c = r.get("coins", {}).get("coingecko:avalanche-2")
        px[d.isoformat()] = c
        d += dt.timedelta(days=1)
        time.sleep(0.2)
    save("llama_avax_price_noon.json", px)
    for m in ("feesPaid", "txCount"):
        out, tok = [], None
        for _ in range(20):
            u = (f"https://metrics.avax.network/v2/chains/43114/metrics/{m}?timeInterval=day&pageSize=100"
                 f"&startTimestamp={int(dt.datetime(2026, 7, 1, tzinfo=dt.timezone.utc).timestamp())}")
            if tok:
                u += f"&pageToken={tok}"
            r = get_json(u)
            out += r["results"]
            tok = r.get("nextPageToken")
            if not tok:
                break
        save(f"avax_metrics_{m}.json", out)
    # Calibration window (Foundation figures cover Jan 2024 / Jan 2025 to Aug 2026)
    save("routescan_dailytxnfee_2024_2026.json",
         get_json(f"{RS}?module=stats&action=dailytxnfee&startdate=2024-01-01&enddate=2026-08-31&sort=asc"))
    prices = []
    for start in (1704067200, 1704067200 + 500 * 86400):  # 2024-01-01, two 500-day chunks (API max 500)
        r = get_json(f"https://coins.llama.fi/chart/coingecko:avalanche-2?start={start}&span=500&period=1d")
        prices += r["coins"]["coingecko:avalanche-2"]["prices"]
    save("llama_avax_price_chart_2024_2026.json", prices)
    # Second, independent price source for the study window (CoinGecko public API, no key)
    save("coingecko_avax_365d.json",
         get_json("https://api.coingecko.com/api/v3/coins/avalanche-2/market_chart?vs_currency=usd&days=365&interval=daily"))
    save("meta.json", meta)


if __name__ == "__main__":
    main()
