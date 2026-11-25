"""Tiny stdlib-only helpers: keccak256, ABI bits and a polite JSON-RPC client.

No API keys. Uses free public Ethereum RPC endpoints in rotation.
"""
import json
import time
import urllib.request
import urllib.error

# ---------------------------------------------------------------- keccak256
# Pure-Python Keccak-256 (the pre-NIST padding Ethereum uses; hashlib.sha3_256 is different).
_RC = [
    0x0000000000000001, 0x0000000000008082, 0x800000000000808A, 0x8000000080008000,
    0x000000000000808B, 0x0000000080000001, 0x8000000080008081, 0x8000000000008009,
    0x000000000000008A, 0x0000000000000088, 0x0000000080008009, 0x000000008000000A,
    0x000000008000808B, 0x800000000000008B, 0x8000000000008089, 0x8000000000008003,
    0x8000000000008002, 0x8000000000000080, 0x000000000000800A, 0x800000008000000A,
    0x8000000080008081, 0x8000000000008080, 0x0000000080000001, 0x8000000080008008,
]
_ROT = [
    [0, 36, 3, 41, 18], [1, 44, 10, 45, 2], [62, 6, 43, 15, 61],
    [28, 55, 25, 21, 56], [27, 20, 39, 8, 14],
]
_M = (1 << 64) - 1


def _rol(x, n):
    n %= 64
    return ((x << n) | (x >> (64 - n))) & _M if n else x


def _f(A):
    for rc in _RC:
        C = [A[x][0] ^ A[x][1] ^ A[x][2] ^ A[x][3] ^ A[x][4] for x in range(5)]
        D = [C[(x - 1) % 5] ^ _rol(C[(x + 1) % 5], 1) for x in range(5)]
        A = [[A[x][y] ^ D[x] for y in range(5)] for x in range(5)]
        B = [[0] * 5 for _ in range(5)]
        for x in range(5):
            for y in range(5):
                B[y][(2 * x + 3 * y) % 5] = _rol(A[x][y], _ROT[x][y])
        A = [[B[x][y] ^ ((~B[(x + 1) % 5][y]) & B[(x + 2) % 5][y]) for y in range(5)] for x in range(5)]
        A[0][0] ^= rc
    return A


def keccak256(data):
    if isinstance(data, str):
        data = data.encode()
    rate = 136
    p = bytearray(data)
    p.append(0x01)
    while len(p) % rate:
        p.append(0)
    p[-1] |= 0x80
    A = [[0] * 5 for _ in range(5)]
    for off in range(0, len(p), rate):
        blk = p[off:off + rate]
        for i in range(rate // 8):
            x, y = i % 5, i // 5
            A[x][y] ^= int.from_bytes(blk[8 * i:8 * i + 8], "little")
        A = _f(A)
    out = b"".join(A[i % 5][i // 5].to_bytes(8, "little") for i in range(4))
    return out


def topic(sig):
    return "0x" + keccak256(sig).hex()


def selector(sig):
    return "0x" + keccak256(sig)[:4].hex()


assert keccak256(b"").hex() == "c5d2460186f7233c927e7db2dcc703c0e500b653ca82273b7bfad8045d85a470"
assert topic("Transfer(address,address,uint256)") == \
    "0xddf252ad1be2c89b69c2b068fc378daa952ba7f163c4a11628f55a4df523b3ef"

# ---------------------------------------------------------------- ABI helpers


def pad_addr(a):
    return "0x" + "0" * 24 + a.lower().replace("0x", "")


def enc_addr(a):
    return "0" * 24 + a.lower().replace("0x", "")


def enc_uint(n):
    return "%064x" % n


def dec_addr(word):
    return "0x" + word[-40:]


def words(data):
    d = data[2:] if data.startswith("0x") else data
    return [d[i:i + 64] for i in range(0, len(d), 64)]


def to_int(h):
    return int(h, 16) if h and h != "0x" else 0


def to_signed(word):
    v = int(word, 16)
    return v - (1 << 256) if v >= (1 << 255) else v


# ---------------------------------------------------------------- RPC client
ENDPOINTS = [  # free, keyless; publicnode serves archive eth_call but not old-range eth_getLogs
    "https://ethereum-rpc.publicnode.com",
    "https://gateway.tenderly.co/public/mainnet",
    "https://rpc.mevblocker.io",
]
LOG_ENDPOINTS = [  # keyless endpoints that accepted 10,000-block eth_getLogs ranges (tested Nov 2026)
    "https://gateway.tenderly.co/public/mainnet",
    "https://rpc.mevblocker.io",
]
PACE = 0.25  # seconds between requests (polite pacing)
_last = [0.0]
_ep = [0]
STATS = {"requests": 0, "retries": 0}


class RPCError(Exception):
    pass


def _post(url, payload, timeout=60):
    body = json.dumps(payload).encode()
    req = urllib.request.Request(url, data=body, headers={
        "Content-Type": "application/json", "User-Agent": "reth-mints-analysis/1.0"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read())


def call_raw(payload, tries=8, endpoints=None):
    """POST payload (single or batch) with retries, rotating endpoints on failure."""
    endpoints = endpoints or ENDPOINTS
    err = None
    for attempt in range(tries):
        wait = PACE - (time.time() - _last[0])
        if wait > 0:
            time.sleep(wait)
        url = endpoints[_ep[0] % len(endpoints)]
        _last[0] = time.time()
        STATS["requests"] += 1
        try:
            res = _post(url, payload)
            if isinstance(res, dict) and "error" in res:
                raise RPCError(str(res["error"]))
            if isinstance(res, list):
                bad = [x for x in res if "error" in x]
                if bad:
                    raise RPCError(str(bad[0]["error"]))
            return res
        except Exception as e:  # noqa
            err = e
            STATS["retries"] += 1
            msg = str(e).lower()
            # range/size errors are the caller's problem: surface immediately
            if any(k in msg for k in ("range", "too many", "limit exceeded", "10000", "response size",
                                      "query returned more", "revert", "invalid opcode")):
                raise RPCError(str(e))
            _ep[0] += 1
            if "archive" in msg or "token" in msg or "api key" in msg or "apikey" in msg:
                continue  # endpoint can't serve this; try the next one right away
            time.sleep(min(30, 1.5 * (attempt + 1)))
    raise RPCError("giving up: %s" % err)


def rpc(method, params, endpoints=None):
    return call_raw({"jsonrpc": "2.0", "id": 1, "method": method, "params": params}, endpoints=endpoints)["result"]


def rpc_batch(calls, size=25):
    """calls: list of (method, params). Returns results in order."""
    out = []
    for i in range(0, len(calls), size):
        chunk = calls[i:i + size]
        payload = [{"jsonrpc": "2.0", "id": j, "method": m, "params": p} for j, (m, p) in enumerate(chunk)]
        res = call_raw(payload)
        res = sorted(res, key=lambda x: x["id"])
        out.extend(x["result"] for x in res)
    return out


def eth_call(to, data, block="latest"):
    if isinstance(block, int):
        block = hex(block)
    return rpc("eth_call", [{"to": to, "data": data}, block])


def get_logs_chunked(address, topics, start, end, chunk=5000, label=""):
    """eth_getLogs over [start, end] in chunks, halving the chunk on range/size errors."""
    logs = []
    b = start
    size = chunk
    while b <= end:
        e = min(end, b + size - 1)
        flt = {"fromBlock": hex(b), "toBlock": hex(e), "topics": topics}
        if address:
            flt["address"] = address
        try:
            res = rpc("eth_getLogs", [flt], endpoints=LOG_ENDPOINTS)
        except RPCError as ex:
            if size > 50:
                size = max(50, size // 2)
                continue
            raise
        logs.extend(res)
        b = e + 1
        if size < chunk:
            size = min(chunk, size * 2)
        if label:
            print("  %s: block %d/%d, %d logs" % (label, e, end, len(logs)), flush=True)
    return logs
