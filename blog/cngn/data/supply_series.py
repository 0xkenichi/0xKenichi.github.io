import sys, warnings, json, time, datetime as dt
warnings.filterwarnings("ignore")
import requests
OUT=sys.argv[1]
CH={"Base":("0x46C85152bFe9f96829aA94755D9f915F9B10EF5F",["https://mainnet.base.org"]),
 "BNB Chain":("0xa8AEA66B361a8d53e8865c62D142167Af28Af058",["https://bsc-mainnet.public.blastapi.io"]),
 "Celo":("0xF6829D7393dAe24509eb1E52eE8e572e2E271a4f",["https://forno.celo.org"]),
 "Ethereum":("0x17CDB2a01e7a34CbB3DD4b83260B05d0274C8dab",["https://eth.drpc.org","https://1rpc.io/eth"]),
 "Asset Chain":("0x7923C0f6FA3d1BA6EAFCAedAaD93e737Fd22FC4F",["https://mainnet-rpc.assetchain.org"])}
S=requests.Session()
def rpc(urls,m,p):
    err=None
    for attempt in range(6):
        for u in urls:
            try:
                j=S.post(u,json={"jsonrpc":"2.0","id":1,"method":m,"params":p},timeout=30).json()
                if "result" in j: return j["result"]
                err=j.get("error",j)
            except Exception as e: err=e
            time.sleep(0.6*(attempt+1))
    raise RuntimeError(f"{m} failed: {str(err)[:150]}")
tsc={}
def ts(urls,b):
    k=(urls[0],b)
    if k not in tsc:
        for i in range(6):
            r=rpc(urls,"eth_getBlockByNumber",[hex(b),False])
            if isinstance(r,dict) and "timestamp" in r: tsc[k]=int(r["timestamp"],16); break
            time.sleep(1.5); urls=urls[1:]+urls[:1]
        else: raise RuntimeError("no timestamp for block %d"%b)
    return tsc[k]
def block_at(urls,target,latest):
    lo,hi=1,latest; tlo,thi=ts(urls,lo),ts(urls,hi)
    if target<=tlo: return None
    if target>=thi: return hi
    for _ in range(40):
        if hi-lo<=1: break
        g=lo+int((target-tlo)*(hi-lo)/max(1,thi-tlo)); g=min(max(g,lo+1),hi-1)
        tg=ts(urls,g)
        if abs(tg-target)<=1800: return g
        if tg<target: lo,tlo=g,tg
        else: hi,thi=g,tg
    return lo
dates=[]
d=dt.date(2025,1,1)
while d<=dt.date(2026,11,1):
    dates.append(d); dates.append(d.replace(day=15)) if d<dt.date(2026,11,1) else None
    d=(d.replace(day=28)+dt.timedelta(days=4)).replace(day=1)
dates=[x for x in dates if x<=dt.date(2026,11,4)]
import os
res=json.load(open(OUT)) if os.path.exists(OUT) else {"dates":[x.isoformat() for x in dates]+["2026-11-04"],"series":{}}
ONLY=sys.argv[2].split(",") if len(sys.argv)>2 else list(CH)
for name,(addr,urls) in [(n,CH[n]) for n in ONLY]:
    latest=int(rpc(urls,"eth_blockNumber",[]),16)
    vals=[]
    for x in dates:
        target=int(dt.datetime(x.year,x.month,x.day,12,tzinfo=dt.timezone.utc).timestamp())
        b=block_at(urls,target,latest)
        if b is None: vals.append(0.0); continue
        s=rpc(urls,"eth_call",[{"to":addr,"data":"0x18160ddd"},hex(b)])
        vals.append(int(s,16)/1e6 if s not in ("0x","0x0") else 0.0)
    s=rpc(urls,"eth_call",[{"to":addr,"data":"0x18160ddd"},"latest"]); vals.append(int(s,16)/1e6)
    res["series"][name]=vals
    print(name, [round(v/1e6,1) for v in vals], flush=True)
    json.dump(res,open(OUT,"w"),indent=1)
print("saved",OUT)
