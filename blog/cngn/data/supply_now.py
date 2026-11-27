import sys, warnings; warnings.filterwarnings("ignore")
import requests, json
EVM = {
 "Ethereum":("0x17CDB2a01e7a34CbB3DD4b83260B05d0274C8dab",["https://ethereum-rpc.publicnode.com","https://eth.llamarpc.com"]),
 "BNB Chain":("0xa8AEA66B361a8d53e8865c62D142167Af28Af058",["https://bsc-rpc.publicnode.com","https://bsc-dataseed.bnbchain.org"]),
 "Polygon":("0x52828daa48C1a9A06F37500882b42daf0bE04C3B",["https://polygon-bor-rpc.publicnode.com","https://polygon-rpc.com"]),
 "Base":("0x46C85152bFe9f96829aA94755D9f915F9B10EF5F",["https://base-rpc.publicnode.com","https://mainnet.base.org"]),
 "Celo":("0xF6829D7393dAe24509eb1E52eE8e572e2E271a4f",["https://forno.celo.org"]),
 "Monad":("0x567BB1CA4748cD316F25fa502E77362A632771eE",["https://rpc.monad.xyz","https://monad-rpc.publicnode.com"]),
 "Arc":("0x5d1C90779f9de46B65cF368caa1f36B39E5F2614",["https://rpc.arc.network","https://rpc.arc.io"]),
 "ADI":("0x502e4244b1265Da71Ced46a749060894dD7264E3",["https://rpc.adifoundation.ai","https://rpc.adi.network"]),
 "Asset Chain":("0x7923C0f6FA3d1BA6EAFCAedAaD93e737Fd22FC4F",["https://mainnet-rpc.assetchain.org"]),
}
def call(rpc, to, data):
    r=requests.post(rpc,json={"jsonrpc":"2.0","id":1,"method":"eth_call","params":[{"to":to,"data":data},"latest"]},timeout=20)
    j=r.json()
    if "result" not in j: raise RuntimeError(str(j)[:200])
    return j["result"]
out={}
for name,(addr,rpcs) in EVM.items():
    for rpc in rpcs:
        try:
            dec=int(call(rpc,addr,"0x313ce567"),16)
            ts=int(call(rpc,addr,"0x18160ddd"),16)
            out[name]={"supply":ts/10**dec,"decimals":dec,"rpc":rpc}
            break
        except Exception as e:
            out[name]={"error":f"{rpc}: {str(e)[:120]}"}
# Solana
try:
    r=requests.post("https://api.mainnet-beta.solana.com",json={"jsonrpc":"2.0","id":1,"method":"getTokenSupply","params":["3jiqwBQVRC5zRwHyqvnkQurebJ5RNxg3F5fXMwaxgkv8"]},timeout=20).json()
    v=r["result"]["value"]; out["Solana"]={"supply":float(v["uiAmountString"]),"decimals":v["decimals"],"rpc":"api.mainnet-beta.solana.com"}
except Exception as e: out["Solana"]={"error":str(e)[:150]}
for k,v in out.items(): print(f"{k:12s}", json.dumps(v))
