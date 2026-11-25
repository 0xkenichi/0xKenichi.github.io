#!/usr/bin/env python3
"""Independent cross-check of the mint totals, using a public block-explorer indexer instead of JSON-RPC nodes.
Default: Routescan's keyless Etherscan-compatible API (api.routescan.io). Fallback: Blockscout (eth.blockscout.com).

Re-pulls rETH TokensMinted and the deposit pool's DepositReceived / CreditWithdrawn logs for the same
block window and compares counts and sums with data/mints.csv. Writes data/crosscheck.json.
Usage: python3 -I crosscheck.py   (run after fetch.py)
"""
import csv
import json
import os
import sys
import time
import urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from rpclib import topic, words  # noqa: E402

DATA = os.path.join(HERE, "data")
meta = json.load(open(os.path.join(DATA, "meta.json")))
SB, EB = meta["window"]["start_block"], meta["window"]["end_block"]
RETH = meta["rocketTokenRETH"]
DP = meta["rocketDepositPool_now"]
SOURCES = {
    "routescan": "https://api.routescan.io/v2/network/mainnet/evm/1/etherscan/api?module=logs&action=getLogs"
                 "&address=%s&topic0=%s&fromBlock=%d&toBlock=%d",
    "blockscout": "https://eth.blockscout.com/api?module=logs&action=getLogs&address=%s&topic0=%s&fromBlock=%d&toBlock=%d",
}
CAP = {"routescan": 100, "blockscout": 1000}  # rows returned per call
SRC = sys.argv[1] if len(sys.argv) > 1 else "routescan"
API = SOURCES[SRC]


def get(url):
    for i in range(10):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "reth-mints-crosscheck/1.0"})
            with urllib.request.urlopen(req, timeout=120) as r:
                return json.loads(r.read())
        except Exception as e:  # noqa
            print("  retry", e)
            time.sleep(min(120, 20 * (i + 1)))
    raise SystemExit(SRC + " unavailable")


def pull(addr, t0, step=10**7):  # whole window in one call unless the row cap is hit
    out, b = [], SB
    while b <= EB:
        e = min(EB, b + step - 1)
        j = get(API % (addr, t0, b, e))
        res = j.get("result") or []
        if len(res) >= CAP[SRC] and e > b:  # hit the per-call row cap: split the range
            step = max(1, (e - b + 1) // 2)
            continue
        if len(res) >= CAP[SRC]:
            raise SystemExit("too many logs in a single block")
        out.extend(res)
        b = e + 1
        step = step * 2
        time.sleep(1)
    return out


mints = pull(RETH, topic("TokensMinted(address,uint256,uint256,uint256)"))
deps = pull(DP, topic("DepositReceived(address,uint256,uint256)"))
creds = pull(DP, topic("CreditWithdrawn(address,uint256,uint256)"))

bs = {
    "mint_events": len(mints),
    "reth_minted": sum(int(words(l["data"])[0], 16) for l in mints) / 1e18,
    "eth_net": sum(int(words(l["data"])[1], 16) for l in mints) / 1e18,
    "deposit_received_events": len(deps),
    "eth_deposited_gross": sum(int(words(l["data"])[0], 16) for l in deps) / 1e18,
    "credit_withdrawn_events": len(creds),
    "credit_withdrawn_eth": sum(int(words(l["data"])[0], 16) for l in creds) / 1e18,
}
rows = list(csv.DictReader(open(os.path.join(DATA, "mints.csv"))))
ours = {
    "mint_events": len(rows),
    "reth_minted": sum(int(r["reth_minted_wei"]) for r in rows) / 1e18,
    "eth_net": sum(int(r["eth_net_wei"]) for r in rows) / 1e18,
    "deposit_received_events": sum(1 for r in rows if r["mint_path"] == "deposit"),
    "eth_deposited_gross": sum(int(r["eth_gross_wei"]) for r in rows if r["mint_path"] == "deposit") / 1e18,
    "credit_withdrawn_events": sum(1 for r in rows if r["mint_path"] == "credit_withdrawal"),
    "credit_withdrawn_eth": sum(int(r["eth_gross_wei"]) for r in rows if r["mint_path"] == "credit_withdrawal") / 1e18,
}
gap = {k: ours[k] - bs[k] for k in ours}
res = {"source": {"routescan": "api.routescan.io Etherscan-compatible logs API (independent indexer, no key)",
                  "blockscout": "eth.blockscout.com logs API (independent indexer)"}[SRC], "blocks": [SB, EB],
       "indexer": bs, "rpc_pipeline": ours, "gap_rpc_minus_indexer": gap}
json.dump(res, open(os.path.join(DATA, "crosscheck.json"), "w"), indent=1)
print(json.dumps(res, indent=1))
