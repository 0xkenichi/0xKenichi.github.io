"""Stdlib-only HTTP helpers: a polite JSON-RPC client for the Avalanche C-Chain and a JSON GET.

No API keys. Uses free public endpoints only.
"""
import json
import time
import urllib.request
import urllib.error

RPCS = [
    "https://api.avax.network/ext/bc/C/rpc",           # Ava Labs public RPC
    "https://avalanche-c-chain-rpc.publicnode.com",    # Allnodes publicnode
]
UA = {"user-agent": "avax-floor/1.0 (python urllib)", "content-type": "application/json"}

_i = 0


def rpc(method, params, tries=8):
    """Call a JSON-RPC method, rotating endpoints on errors and backing off."""
    global _i
    err = None
    for k in range(tries):
        url = RPCS[_i % len(RPCS)]
        body = json.dumps({"jsonrpc": "2.0", "id": 1, "method": method, "params": params}).encode()
        try:
            req = urllib.request.Request(url, data=body, headers=UA)
            r = json.load(urllib.request.urlopen(req, timeout=60))
            if "error" in r:
                raise RuntimeError(f"{url}: {r['error']}")
            return r["result"]
        except (urllib.error.URLError, RuntimeError, TimeoutError, ValueError, OSError) as e:
            err = e
            _i += 1
            time.sleep(min(30, 1.5 * (k + 1)))
    raise RuntimeError(f"rpc {method} failed after {tries} tries: {err}")


def get_json(url, tries=6):
    err = None
    for k in range(tries):
        try:
            req = urllib.request.Request(url, headers={"user-agent": UA["user-agent"]})
            return json.load(urllib.request.urlopen(req, timeout=120))
        except (urllib.error.URLError, TimeoutError, ValueError, OSError) as e:
            err = e
            time.sleep(min(60, 3 * (k + 1)))
    raise RuntimeError(f"GET {url} failed: {err}")


def block(n, full=False):
    return rpc("eth_getBlockByNumber", [hex(n), full])


def ts(n):
    return int(block(n)["timestamp"], 16)


def block_at(t, lo=None, hi=None):
    """First block with timestamp >= t (binary search on the public RPC)."""
    if lo is None:
        lo = 1
    if hi is None:
        hi = int(rpc("eth_blockNumber", []), 16)
    while lo < hi:
        mid = (lo + hi) // 2
        if ts(mid) < t:
            lo = mid + 1
        else:
            hi = mid
    return lo
