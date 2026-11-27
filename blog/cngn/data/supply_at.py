# Read cNGN totalSupply() on the five EVM chains at the last block at or before a UTC moment.
# Usage: python3 supply_at.py 2026-08-31T20:45:00
# Prints each chain's block, block time and exact supply (raw integer / 10^6, no float rounding).
import sys, json, time, datetime as dt, urllib.request
from decimal import Decimal
CH={"Base":("0x46C85152bFe9f96829aA94755D9f915F9B10EF5F",["https://mainnet.base.org"]),
 "BNB Chain":("0xa8AEA66B361a8d53e8865c62D142167Af28Af058",["https://bsc-mainnet.public.blastapi.io","https://bsc-dataseed.bnbchain.org"]),
 "Celo":("0xF6829D7393dAe24509eb1E52eE8e572e2E271a4f",["https://forno.celo.org"]),
 "Ethereum":("0x17CDB2a01e7a34CbB3DD4b83260B05d0274C8dab",["https://eth.drpc.org","https://1rpc.io/eth"]),
 "Asset Chain":("0x7923C0f6FA3d1BA6EAFCAedAaD93e737Fd22FC4F",["https://mainnet-rpc.assetchain.org"])}
DECIMALS=6  # all five contracts return 6 from decimals()
def rpc(urls,m,p):
    err=None
    for attempt in range(5):
        for u in urls:
            try:
                req=urllib.request.Request(u,data=json.dumps({"jsonrpc":"2.0","id":1,"method":m,"params":p}).encode(),headers={"Content-Type":"application/json","User-Agent":"generic-client"})
                j=json.loads(urllib.request.urlopen(req,timeout=30).read())
                if "result" in j: return j["result"]
                err=j.get("error",j)
            except Exception as e: err=e
            time.sleep(0.6*(attempt+1))
    raise RuntimeError(f"{m} failed: {str(err)[:150]}")
def ts(urls,b): return int(rpc(urls,"eth_getBlockByNumber",[hex(b),False])["timestamp"],16)
def block_before(urls,target):
    hi=int(rpc(urls,"eth_blockNumber",[]),16); lo=1
    while hi-lo>1:
        mid=(lo+hi)//2
        if ts(urls,mid)<=target: lo=mid
        else: hi=mid
    return lo
when=sys.argv[1]  # UTC, e.g. 2026-08-31T20:45:00 (= 9:45 pm WAT)
target=int(dt.datetime.fromisoformat(when).replace(tzinfo=dt.timezone.utc).timestamp())
tot=Decimal(0)
for name,(addr,urls) in CH.items():
    try:
        b=block_before(urls,target)
        s=rpc(urls,"eth_call",[{"to":addr,"data":"0x18160ddd"},hex(b)])
        raw=int(s,16) if s not in ("0x","0x0") else 0
        v=Decimal(raw)/Decimal(10**DECIMALS)
        tot+=v
        t=dt.datetime.fromtimestamp(ts(urls,b),dt.timezone.utc).strftime("%Y-%m-%d %H:%M:%S")
        print(f"{name:12s} block {b:>10d}  {t} UTC  supply {v:,.6f}", flush=True)
    except Exception as e:
        print(name, "ERROR", e, flush=True)
print(f"{'TOTAL':12s} {tot:,.6f} cNGN at {when} UTC")
