# Who actually mints rETH?

Every rETH mint from 22 Aug to 20 Nov 2026 (Ethereum blocks 25,806,959 to 26,452,577), split by the contract each mint transaction was sent to.

- Results: [results.md](results.md) · page: https://0xkenichi.github.io/reth-mints/
- Data: `data/` (mints, burns, DEX outflows, address labels, cross-check)
- Reproduce with free public RPC and the Python 3.9 standard library, no API keys:
  `python3 -I fetch.py && python3 -I crosscheck.py && python3 -I analyze.py && python3 -I report.py`

Mint and burn totals match rETH `totalSupply()` to the wei. Mint totals match Routescan's indexer.

By Kenichi ([@0xKenichi](https://x.com/0xKenichi)). Independent work, not affiliated with Rocket Pool.
