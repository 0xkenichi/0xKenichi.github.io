# What happened when Avalanche validators raised the gas floor?

After the Helicon upgrade (ACP-283, live 22 Sep 2026) C-Chain validators vote the minimum gas price. They moved it from 1 wei to 5 nAVAX (reached 27 Sep), then down to 2.5 nAVAX (19 Oct), then up to 7.5 nAVAX (10 Nov). This folder measures what happened to transactions, AVAX burned, and the chain's share of what users pay apps, from 1 Aug to 25 Nov 2026.

- Page: https://0xkenichi.github.io/avax-floor/ · results in plain English: [results.md](results.md)
- Chart data: `data/chart_daily.csv` (one row per day: floor, tx, AVAX burned, chain share, price, plus 7-day means) and `data/chart_regimes.csv` (one row per period: tx/day, base-fee vs tip burn with 95% intervals, tx by class)
- Everything else is in `data/`: exact floor-change blocks, hourly headers, the daily series, cross-checks, calibration, and the block sample used for "who left"

## Check it in 60 seconds

1. `data/floor_changes.csv`: each floor change has an exact first block and UTC time, read from the `minPriceExponent` field in C-Chain block headers. They come from the chain itself, not from announcements.
2. `data/regimes.csv`: the before/after table. Each row covers full UTC days at one floor level. Days when the floor was moving are left out.
3. `data/crosscheck.json`: daily AVAX burned from Routescan matches the Avalanche metrics API within 0.01% in total, and matches DefiLlama's chain fees within 0.5% (USD). Daily tx counts match within 0.01%.
4. `data/calibration.json`: these free inputs set against the Avalanche Foundation's published figures (for example $9.53M of fees over Jan 2025 to Aug 2026, against their $9.6M).
5. `data/chart_regimes.csv` and `data/who_summary.json`: from 300 random whole blocks per period, gas use stays about flat (82B–93B gas/day) across the 2.5, 5 and 7.5 floors, so the floor-driven burn tracks the floor (about 240 / 455 / 690 AVAX/day). What left was mostly bot-like traffic: no-log calls, failed transactions, and contracts fed by 1, 1 and exactly 100 senders.
6. Read "Reading the numbers" and the caveats in results.md before quoting any number.

## Reproduce

Free public endpoints only, Python 3.9 standard library, no API keys, no accounts:

```
python3 -I fetch.py      # daily series from Routescan, DefiLlama, CoinGecko and the Avalanche metrics API -> data/raw/
python3 -I floor.py      # hourly C-Chain headers from 1 Aug, exact floor-change blocks by bisection -> data/
python3 -I analyze.py    # daily.csv, chart_daily.csv, regimes.csv, crosscheck.json, calibration.json
python3 -I sample.py     # 300 random whole blocks per regime with receipts -> data/sample_*.csv(.gz)
python3 -I who.py        # who left: tx classes, sender concentration, top destinations, base fee vs tip
```

`floor.py` makes about 2,800 RPC calls and `sample.py` about 3,600; each takes 10 to 25 minutes on the public RPC. `sample.py` caches blocks in `data/raw/blocks/` (git-ignored), so an interrupted run picks up where it stopped. The fixed seed (283) draws the same blocks every run. DefiLlama revises app-fee history as adapters are fixed, so a later rerun can move app-fee totals slightly.

## Sources

| What | Source |
|---|---|
| Floor (minimum gas price), base fee, gas used | Block headers from the public C-Chain RPC (`api.avax.network/ext/bc/C/rpc`, `avalanche-c-chain-rpc.publicnode.com`). The floor in wei is `2 ** (minPriceExponent / 2**58)`. Base fees in quiet blocks equal this value exactly (5, 2.5 and 7.5 nAVAX), which confirms the formula. |
| Daily tx count, daily AVAX fees (all burned) | Routescan's Etherscan-compatible API (`module=stats&action=dailytx`, `dailytxnfee`, chain 43114) |
| Second source for burns and tx | Avalanche metrics API (`metrics.avax.network/v2/chains/43114/metrics/feesPaid`, `txCount`) and DefiLlama chain fees (`api.llama.fi/summary/fees/avalanche`) |
| App fees on Avalanche | DefiLlama `api.llama.fi/overview/fees/avalanche` (sum over all protocols; the chain's own gas fees are not in it) |
| AVAX price | DefiLlama `coins.llama.fi/prices/historical` at 12:00 UTC, cross-checked against CoinGecko's public daily series |
| Foundation figures | The economics page and four Foundation posts, linked below |

### Links

Avalanche Foundation (figures used for calibration):
- Economic Research Agenda: https://avalanche.com/about/economics
- Agenda launch post (30 Jul 2026): https://avalanche.com/about/blog/the-avalanche-foundation-unveils-its-economic-research-agenda
- Gross Chain Product post (7 May 2026): https://avalanche.com/about/blog/measuring-blockchain-economies-introducing-gross-chain-product
- Gross Chain Income post (12 Aug 2026): https://avalanche.com/about/blog/from-gross-chain-product-to-gross-chain-income-where-the-value-goes
- "The Price of a Transaction" (5 Nov 2026): https://avalanche.com/about/blog/the-price-of-a-transaction-benchmarking-the-avalanche-c-chain-on-cost-and-capture

Data (all free, no keys):
- C-Chain JSON-RPC: https://api.avax.network/ext/bc/C/rpc and https://avalanche-c-chain-rpc.publicnode.com
- Routescan Etherscan-compatible API (chain 43114): https://api.routescan.io/v2/network/mainnet/evm/43114/etherscan/api (`module=stats&action=dailytx`, `dailytxnfee`; `module=contract&action=getsourcecode` for contract names)
- DefiLlama: https://api.llama.fi/overview/fees/avalanche (app fees), https://api.llama.fi/summary/fees/avalanche (chain fees), https://coins.llama.fi (AVAX price)
- CoinGecko public API: https://api.coingecko.com/api/v3/coins/avalanche-2/market_chart (price cross-check)
- Avalanche metrics API: https://metrics.avax.network/v2/chains/43114/metrics/feesPaid and `txCount` (cross-check)

By Kenichi ([@0xKenichi](https://x.com/0xKenichi)). Independent work, not affiliated with the Avalanche Foundation or Ava Labs.
