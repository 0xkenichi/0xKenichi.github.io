# Draw the stacked supply chart from cngn-supply-series.json.
# Usage: python3 chart.py cngn-supply-series.json out.png SOLANA_SUPPLY_4NOV [phone]
# Needs matplotlib. Add "phone" as a fourth argument for the narrow, large-type version.
import sys, warnings, json, datetime as dt
warnings.filterwarnings("ignore")
import matplotlib; matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
src, out, sol = sys.argv[1], sys.argv[2], float(sys.argv[3])
phone = len(sys.argv) > 4 and sys.argv[4] == "phone"
d=json.load(open(src))
x=[dt.date.fromisoformat(s) for s in d["dates"]]
order=["Base","BNB Chain","Celo","Asset Chain","Ethereum"]
colors={"Base":"#2F6BFF","BNB Chain":"#E8A317","Celo":"#2BB673","Asset Chain":"#8E6CEF","Ethereum":"#8A94A6"}
ys=[[v/1e9 for v in d["series"][k]] for k in order]
tot=[sum(t) for t in zip(*ys)]
bnb=d["series"]["BNB Chain"]; i0=d["dates"].index("2026-08-01")
base_now=ys[0][-1]
if not phone:
    fig,ax=plt.subplots(figsize=(10,5.6),dpi=200)
    ax.stackplot(x,ys,labels=order,colors=[colors[k] for k in order],alpha=0.92,linewidth=0)
    ax.set_title("cNGN supply by chain, Jan 2025 – Nov 2026",loc="left",fontsize=15,fontweight="bold",pad=26)
    ax.text(0,1.02,f"Billions of cNGN (1 cNGN = ₦1). EVM chains, sampled twice a month. 4 Nov: {tot[-1]:.2f}B, plus {sol/1e9:.2f}B on Solana.",transform=ax.transAxes,fontsize=9.5,color="#555")
    ax.set_ylabel("cNGN, billions"); ax.set_xlim(x[0],x[-1]); ax.set_ylim(0,max(tot)*1.12)
    ax.xaxis.set_major_locator(mdates.MonthLocator(bymonth=[1,4,7,10])); ax.xaxis.set_major_formatter(mdates.DateFormatter("%b %Y"))
    ax.annotate(f"BNB Chain: ₦{bnb[i0]/1e6:.0f}M → ₦{bnb[-1]/1e9:.2f}B since 1 Aug", xy=(x[-1],base_now+bnb[-1]/2e9), xytext=(dt.date(2026,3,1),4.55),
        fontsize=9.5, color="#7a5200", arrowprops=dict(arrowstyle="->",color="#7a5200",lw=1))
    ax.annotate("Celo goes live", xy=(dt.date(2026,8,15),2.75), xytext=(dt.date(2026,6,1),3.35), fontsize=9, color="#1b7a4b",
        arrowprops=dict(arrowstyle="->",color="#1b7a4b",lw=1))
    legend_size, foot = 9.5, "Data: totalSupply() read from each chain's public RPC at historical blocks; contracts from docs.cngn.co. Chart: Kenichi (@0xKenichi), 4 Nov 2026."
    foot_size, rect = 7.5, (0,0.03,1,1)
else:
    fig,ax=plt.subplots(figsize=(5.4,6.6),dpi=200)
    ax.stackplot(x,ys,labels=order,colors=[colors[k] for k in order],alpha=0.92,linewidth=0)
    ax.set_title("cNGN supply by chain",loc="left",fontsize=19,fontweight="bold",pad=52)
    ax.text(0,1.025,f"Billions of cNGN (1 cNGN = ₦1), 1st and 15th\nof each month. 4 Nov: {tot[-1]:.2f}B, plus {sol/1e9:.2f}B on Solana.",transform=ax.transAxes,fontsize=13,color="#444",linespacing=1.3)
    ax.set_xlim(x[0],x[-1]); ax.set_ylim(0,max(tot)*1.45)
    ax.xaxis.set_major_locator(mdates.MonthLocator(bymonth=[1,7])); ax.xaxis.set_major_formatter(mdates.DateFormatter("%b\n%Y"))
    ax.tick_params(labelsize=13)
    ax.annotate(f"BNB Chain:\n₦{bnb[i0]/1e6:.0f}M → ₦{bnb[-1]/1e9:.2f}B\nsince 1 Aug", xy=(x[-1],base_now+bnb[-1]/2e9), xytext=(dt.date(2025,12,20),5.25),
        fontsize=13, color="#7a5200", arrowprops=dict(arrowstyle="->",color="#7a5200",lw=1.2))
    legend_size, foot = 13, "Data: totalSupply() from each chain's public RPC;\ncontracts from docs.cngn.co. Chart: Kenichi, 4 Nov 2026."
    foot_size, rect = 10, (0,0.065,1,1)
for s in ("top","right"): ax.spines[s].set_visible(False)
ax.grid(axis="y",color="#e6e6e6",linewidth=0.8); ax.set_axisbelow(True)
h,l=ax.get_legend_handles_labels(); ax.legend(h[::-1],l[::-1],loc="upper left",frameon=False,fontsize=legend_size)
fig.text(0.01,0.01,foot,fontsize=foot_size,color="#777")
fig.tight_layout(rect=rect); fig.savefig(out,facecolor="white"); print("saved",out)
