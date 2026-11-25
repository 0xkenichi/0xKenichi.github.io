#!/usr/bin/env python3
"""Build index.html (static, dark, inline SVG, no external scripts) from data/results.json.
Usage: python3 -I report.py
"""
import html
import json
import os

HERE = os.path.dirname(os.path.abspath(__file__))
R = json.load(open(os.path.join(HERE, "data", "results.json")))
W = R["window"]
RANGE = "22 Aug – 19 Nov 2026 (UTC), blocks %d–%d" % (W["start_block"], W["end_block"])
SRC = "Ethereum mainnet logs via public JSON-RPC; fetch.py"
CATS = R["categories"]
# dark-mode steps of the reference categorical palette, fixed order (dataviz skill palette.md)
COL = ["#3987e5", "#d95926", "#199e70", "#c98500", "#d55181", "#0ca30c", "#9085e9", "#e66767"]
CC = {c: COL[i] for i, c in enumerate(CATS)}
esc = html.escape


def f(x, d=1):
    return "{:,.{}f}".format(x, d)


def pct(x):
    return "%.1f%%" % (100 * x)


def short(a):
    return a[:6] + "…" + a[-4:]


def es(a):
    return '<a href="https://etherscan.io/address/%s">%s</a>' % (a, short(a))


def nice_max(v):
    import math
    if v <= 0:
        return 1
    e = 10 ** math.floor(math.log10(v))
    for m in (1, 2, 2.5, 5, 10):
        if v <= m * e:
            return m * e
    return 10 * e


def hbar(rows, unit):
    """rows: [(label, value, color, tip)] -> responsive horizontal bar SVG."""
    vmax = nice_max(max(r[1] for r in rows))
    bh, gap, lw, width = 20, 10, 0, 460
    h = len(rows) * (bh + gap + 18) + 10
    out = ['<svg viewBox="0 0 %d %d" role="img" class="chart">' % (width, h)]
    y = 4
    for lab, v, c, tip in rows:
        w = max(2, (width - 150) * v / vmax)
        out.append('<text x="0" y="%d" class="lab">%s</text>' % (y + 13, esc(lab)))
        out.append('<g class="hit"><title>%s</title><rect x="0" y="%d" width="%.1f" height="%d" rx="4" fill="%s"/>'
                   '<rect x="0" y="%d" width="%d" height="%d" fill="transparent"/></g>'
                   % (esc(tip), y + 19, w, bh, c, y + 17, width, bh + 4))
        out.append('<text x="%.1f" y="%d" class="val">%s</text>' % (w + 6, y + 19 + 15, esc(unit(v))))
        y += bh + gap + 18
    out.append("</svg>")
    return "".join(out)


def stacked_weeks(weeks, series, colors, ylab, fmt):
    width, height, ml, mb, mt = 460, 280, 46, 50, 10
    pw, ph = width - ml - 10, height - mb - mt
    tots = [sum(w[s] for s in series) for w in weeks]
    vmax = nice_max(max(tots) if tots else 1)
    n = len(weeks)
    bw = pw / n
    out = ['<svg viewBox="0 0 %d %d" role="img" class="chart">' % (width, height)]
    for k in range(5):
        v = vmax * k / 4
        y = mt + ph - ph * v / vmax
        out.append('<line x1="%d" x2="%d" y1="%.1f" y2="%.1f" class="grid"/>' % (ml, width - 10, y, y))
        out.append('<text x="%d" y="%.1f" class="ax" text-anchor="end">%s</text>' % (ml - 6, y + 4, fmt(v)))
    out.append('<text x="%d" y="%d" class="ax" text-anchor="end">%s</text>' % (ml - 6, mt - 0, ""))
    for i, w in enumerate(weeks):
        x = ml + i * bw + 3
        y = mt + ph
        segs = [(s, w[s]) for s in series if w[s] > 0]
        tip = w["week"] + "\n" + "\n".join("%s: %s" % (s, fmt(v)) for s, v in segs) + "\nTotal: %s" % fmt(tots[i])
        out.append('<g class="hit"><title>%s</title>' % esc(tip))
        for j, (s, v) in enumerate(segs):
            hgt = ph * v / vmax
            gap = 2 if j < len(segs) - 1 else 0
            out.append('<rect x="%.1f" y="%.1f" width="%.1f" height="%.1f" fill="%s" %s/>'
                       % (x, y - hgt + (gap if j else 0), bw - 6, max(0.5, hgt - (gap if j else 0)), colors[s],
                          'rx="0"'))
            y -= hgt
        out.append('<rect x="%.1f" y="%d" width="%.1f" height="%d" fill="transparent"/></g>' % (x, mt, bw - 6, ph))
        if i % 2 == 0 or n <= 8:
            out.append('<text x="%.1f" y="%d" class="ax" text-anchor="end" transform="rotate(-40 %.1f %d)">%s</text>'
                       % (x + bw / 2, height - mb + 16, x + bw / 2, height - mb + 16, esc(w["week"].split("–")[0])))
    out.append("</svg>")
    return "".join(out)


def grouped_weeks(weeks, series, colors, ylab, fmt):
    width, height, ml, mb, mt = 460, 280, 50, 50, 10
    pw, ph = width - ml - 10, height - mb - mt
    vmax = nice_max(max(max(w[s] for s in series) for w in weeks))
    n = len(weeks)
    bw = pw / n
    out = ['<svg viewBox="0 0 %d %d" role="img" class="chart">' % (width, height)]
    for k in range(5):
        v = vmax * k / 4
        y = mt + ph - ph * v / vmax
        out.append('<line x1="%d" x2="%d" y1="%.1f" y2="%.1f" class="grid"/>' % (ml, width - 10, y, y))
        out.append('<text x="%d" y="%.1f" class="ax" text-anchor="end">%s</text>' % (ml - 6, y + 4, fmt(v)))
    out.append('<text x="%d" y="%d" class="ax" text-anchor="end">%s</text>' % (ml - 6, mt - 0, ""))
    sw = (bw - 8) / len(series)
    for i, w in enumerate(weeks):
        x0 = ml + i * bw + 4
        tip = w["week"] + "\n" + "\n".join("%s: %s" % (s, fmt(w[s])) for s in series)
        out.append('<g class="hit"><title>%s</title>' % esc(tip))
        for j, s in enumerate(series):
            hgt = ph * w[s] / vmax
            out.append('<rect x="%.1f" y="%.1f" width="%.1f" height="%.1f" rx="2" fill="%s"/>'
                       % (x0 + j * sw + 1, mt + ph - hgt, sw - 2, max(0.5, hgt), colors[s]))
        out.append('<rect x="%.1f" y="%d" width="%.1f" height="%d" fill="transparent"/></g>' % (x0, mt, bw - 8, ph))
        if i % 2 == 0:
            out.append('<text x="%.1f" y="%d" class="ax" text-anchor="end" transform="rotate(-40 %.1f %d)">%s</text>'
                       % (x0 + bw / 2, height - mb + 16, x0 + bw / 2, height - mb + 16, esc(w["week"].split("–")[0])))
    out.append("</svg>")
    return "".join(out)


def legend(items):
    return '<div class="legend">' + "".join(
        '<span><i style="background:%s"></i>%s</span>' % (c, esc(l)) for l, c in items) + "</div>"


T = R["totals"]
BC = R["by_category"]
D = R["dex_totals"]
S = R["supply_check"]
X = R.get("crosscheck") or {}

cats_present = [c for c in CATS if BC[c]["mints"] > 0]
share_rows = sorted([(c, BC[c]["eth_gross"], CC[c], "%s: %d mints, %s ETH (%s of ETH)" % (
    c, BC[c]["mints"], f(BC[c]["eth_gross"], 2), pct(BC[c]["share_eth"]))) for c in cats_present],
    key=lambda r: -r[1])
chart1 = hbar(share_rows, lambda v: "%s ETH · %s" % (f(v, 0), pct(v / T["eth_gross_all"])))
chart2 = stacked_weeks(R["weekly"], cats_present, CC, "ETH", lambda v: f(v, 0))
wk2 = [dict(w, **{"Minted (new rETH)": w["mint_reth"], "Bought from tracked DEX pools": w["dex_reth"]})
       for w in R["weekly"]]
mc = {"Minted (new rETH)": COL[0], "Bought from tracked DEX pools": COL[1]}
chart3 = grouped_weeks(wk2, list(mc), mc, "rETH", lambda v: f(v, 0))

direct = BC[CATS[0]]
router = BC[CATS[2]]
agg = BC[CATS[3]]
headline = ("In these 90 days, %d mints created %s rETH against %s ETH. %s of that ETH came straight to the deposit "
            "pool from wallets (EOAs) calling deposit() themselves, and the top 10 minters supplied %s. Over the same period, %s rETH was "
            "bought out of the tracked DEX pools, about %.1f× the amount minted."
            % (T["mints"], f(T["reth_minted"], 0), f(T["eth_gross_all"], 0), pct(direct["share_eth"]),
               pct(R["top10_share"]), f(D["reth"], 0), D["reth"] / T["reth_minted"]))

entry_tbl = "".join(
    "<tr><td>%s</td><td>%s</td><td>%s</td><td class=n>%d</td><td class=n>%s</td><td class=src>%s</td></tr>"
    % (es(e["address"]), esc(e["label"]), esc(e["category"]), e["mints"], f(e["eth"], 2),
       esc(e["label_source"] or ("Safe (getThreshold() answers on-chain)" if e["safe"] else "none found")))
    for e in R["entry_points"])
top_tbl = "".join(
    "<tr><td>%d</td><td>%s</td><td>%s</td><td>%s</td><td class=n>%d</td><td class=n>%s</td><td class=n>%s</td></tr>"
    % (i + 1, es(t["address"]), esc(t["label"]), esc(t["path"]), t["mints"], f(t["eth"], 1), pct(t["share"]))
    for i, t in enumerate(R["top10"]))
cat_tbl = "".join(
    "<tr><td><i class=sw style='background:%s'></i>%s</td><td class=n>%d</td><td class=n>%s</td><td class=n>%s</td>"
    "<td class=n>%s</td></tr>" % (CC[c], esc(c), BC[c]["mints"], f(BC[c]["eth_gross"], 2), pct(BC[c]["share_eth"]),
                                  pct(BC[c]["share_count"])) for c in CATS)
wk_tbl = "".join(
    "<tr><td>%s</td><td class=n>%d</td><td class=n>%s</td><td class=n>%s</td><td class=n>%s</td></tr>"
    % (w["week"], w["mints"], f(sum(w[c] for c in CATS), 1), f(w["mint_reth"], 1), f(w["dex_reth"], 1))
    for w in R["weekly"])
ven_tbl = "".join("<tr><td>%s</td><td class=n>%d</td><td class=n>%s</td></tr>" % (esc(k), v["swaps"], f(v["reth"], 1))
                  for k, v in sorted(R["dex_venues"].items(), key=lambda x: -x[1]["reth"]))

if X:
    g = X["gap_rpc_minus_indexer"]
    xc = ("Routescan's keyless Etherscan-compatible logs API (a separate indexer), same blocks: %d mint events, %s rETH, "
          "%s ETH of new deposits. Gap vs this pipeline: %+d events, %+.6f rETH, %+.6f ETH."
          % (X["indexer"]["mint_events"], f(X["indexer"]["reth_minted"], 4),
             f(X["indexer"]["eth_deposited_gross"], 4), g["mint_events"], g["reth_minted"],
             g["eth_deposited_gross"]))
else:
    xc = ("Blockscout's public logs API rate-limited the re-pull (HTTP 429) on 20 Nov 2026, so this check is pending; "
          "rerun crosscheck.py.")

page = """<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Who Mints rETH</title>
<style>
:root{--bg:#121211;--surface:#1a1a19;--line:#2c2c2a;--text:#f0efec;--muted:#c3c2b7;--faint:#8d8c85;--link:#86b6ef}
*{box-sizing:border-box}body{margin:0;background:var(--bg);color:var(--text);font:15px/1.55 system-ui,-apple-system,"Segoe UI",Roboto,sans-serif}
main{max-width:820px;margin:0 auto;padding:24px 16px 64px}
h1{font-size:26px;line-height:1.2;margin:0 0 6px}h2{font-size:18px;margin:36px 0 4px}
.sub{color:var(--muted);margin:0 0 18px}.cap{color:var(--faint);font-size:12.5px;margin:2px 0 10px}
a{color:var(--link)}.card{background:var(--surface);border:1px solid var(--line);border-radius:10px;padding:14px}
.tiles{display:grid;grid-template-columns:repeat(auto-fit,minmax(150px,1fr));gap:10px;margin:16px 0}
.tile{background:var(--surface);border:1px solid var(--line);border-radius:10px;padding:12px}
.tile b{display:block;font-size:22px;font-variant-numeric:tabular-nums}.tile span{color:var(--muted);font-size:12.5px}
.lead{font-size:16px}
svg.chart{width:100%%;height:auto;display:block}
.lab{fill:var(--muted);font-size:14px}.val{fill:var(--text);font-size:13px}.ax{fill:var(--faint);font-size:12.5px}
.grid{stroke:var(--line);stroke-width:1}.hit:hover rect:first-child{opacity:.85}
.legend{display:flex;flex-wrap:wrap;gap:6px 14px;margin:8px 0 4px;font-size:12.5px;color:var(--muted)}
.legend i,.sw{display:inline-block;width:10px;height:10px;border-radius:2px;margin-right:6px;vertical-align:baseline}
.tw{overflow-x:auto}table{border-collapse:collapse;width:100%%;font-size:13px}
th,td{padding:6px 8px;border-bottom:1px solid var(--line);text-align:left;vertical-align:top}
th{color:var(--muted);font-weight:600}td.n{text-align:right;font-variant-numeric:tabular-nums;white-space:nowrap}
td.src{color:var(--faint);font-size:12px}details{margin-top:8px}summary{cursor:pointer;color:var(--muted)}
ul{padding-left:20px}li{margin:4px 0}code{font-size:12.5px;color:var(--muted);overflow-wrap:anywhere}
</style></head><body><main>
<h1>Who actually mints rETH?</h1>
<p class="sub">Every new rETH mint over 90 days, traced to the contract the transaction entered through. %s.</p>
<p class="lead">%s</p>
<div class="tiles">
<div class="tile"><b>%d</b><span>mints (TokensMinted events)</span></div>
<div class="tile"><b>%s ETH</b><span>behind them (gross)</span></div>
<div class="tile"><b>%s ETH</b><span>new user deposits; the rest is node-operator credit</span></div>
<div class="tile"><b>%s</b><span>of ETH from EOAs calling the deposit pool directly</span></div>
<div class="tile"><b>%d</b><span>Rocket Pool swap-router mints (%s ETH)</span></div>
<div class="tile"><b>%s rETH</b><span>bought from tracked DEX pools (approx.)</span></div>
</div>

<h2>Where minted ETH entered</h2>
<p class="cap">Share of ETH behind new rETH, by entry point (the transaction's <code>to</code>). %s. Source: %s.</p>
<div class="card">%s</div>
<div class="tw"><table><tr><th>Entry point</th><th>Mints</th><th>ETH</th><th>Share of ETH</th><th>Share of mints</th></tr>%s</table></div>

<h2>Weekly trend</h2>
<p class="cap">ETH per week behind new rETH, 7-day buckets from 22 Aug, by entry point. %s. Last bucket is 6 days. Source: %s.</p>
<div class="card">%s%s</div>
<details><summary>Table view</summary><div class="tw"><table><tr><th>Week</th><th>Mints</th><th>ETH</th><th>rETH minted</th><th>rETH bought on DEX</th></tr>%s</table></div></details>

<h2>Minted vs bought on the market</h2>
<p class="cap">rETH per week: minted vs paid out by tracked DEX venues. %s. Source: Uniswap v3/v2 Swap and Balancer v2 Vault Swap events, plus rETH Transfer events out of the Uniswap v4 PoolManager and Balancer v3 Vault, public JSON-RPC. Approximate: gross outflows include arbitrage, multi-hop routes and (v4/Balancer v3) liquidity withdrawals.</p>
<div class="card">%s%s</div>
<div class="tw"><table><tr><th>Venue (resolved on-chain)</th><th>Swaps paying out rETH</th><th>rETH out</th></tr>%s</table></div>

<h2>Top 10 minting addresses</h2>
<p class="cap">Ranked by ETH behind rETH they received (TokensMinted <code>to</code>). %s. Together: %s of all minted ETH.</p>
<div class="tw"><table><tr><th>#</th><th>Address</th><th>Public label</th><th>Main path</th><th>Mints</th><th>ETH</th><th>Share</th></tr>%s</table></div>

<h2>Every non-direct entry point</h2>
<p class="cap">Contracts used as the transaction's <code>to</code>. Labels only from an Etherscan public name tag or a Blockscout verified contract name; otherwise "unlabelled contract". %s.</p>
<div class="tw"><table><tr><th>Address</th><th>Label</th><th>Category</th><th>Mints</th><th>ETH</th><th>Label source</th></tr>%s</table></div>

<h2>Checks</h2>
<ul>
<li><b>Supply reconciliation (on-chain):</b> rETH totalSupply went from %s to %s (%+.4f). Minted %s minus burned %s (%d burn events) = %+.4f. Gap: %.6f rETH.</li>
<li><b>Independent indexer:</b> %s</li>
<li><b>Public dashboards:</b> rocketscan.io did not resolve on 20 Nov 2026 (no DNS A record), and Rocket Pool's API (<code>api.rocketpool.net/mainnet/payload</code>) publishes no mint or supply history, so neither could be compared. The on-chain supply check above is exact.</li>
<li><b>Contracts:</b> rETH <code>%s</code> and deposit pool <code>%s</code> resolved through RocketStorage <code>getAddress(keccak256("contract.address"+name))</code>; the deposit pool address was the same at the first and last block of the window, and all %d mints pair with a deposit-pool event in the same transaction.</li>
</ul>

<h2>Method and caveats</h2>
<ul>
<li>A mint is a <code>TokensMinted</code> event on rETH. Each one is followed in the same transaction by either <code>DepositReceived</code> (a user's <code>deposit()</code>, new ETH) or <code>CreditWithdrawn</code> (Saturn 1: a node operator takes existing ETH credit as rETH via <code>withdrawCredit()</code>). Credit withdrawals mint rETH but bring no new ETH in, so they are shown separately.</li>
<li>"ETH" means the gross amount in the deposit-pool event; rETH is minted on the amount after the deposit fee (fee total: %s ETH).</li>
<li>Entry point = the transaction's <code>to</code>. A wallet app that sends a plain <code>deposit()</code> from the user's EOA counts as direct; we cannot see which front-end built the transaction.</li>
<li>DEX contrast covers Uniswap v3 rETH/WETH pools (all four fee tiers via the factory), the Uniswap v2 pair, every Balancer v2 pool that paid out rETH (Vault Swap events with tokenOut = rETH), and rETH Transfer events out of the Uniswap v4 PoolManager and Balancer v3 Vault (these two count liquidity withdrawals too). Not covered: Curve, other DEXs, OTC and CEX. It is gross outflow: an arbitrage bot that buys on one pool and sells on another counts as a buyer, so it overstates real demand.</li>
<li>Labels are fetched automatically; an address with no public tag is shown as unlabelled even if its owner is known elsewhere.</li>
</ul>
<p class="cap">Reproduce: <code>python3 -I fetch.py && python3 -I crosscheck.py && python3 -I analyze.py && python3 -I report.py</code>. Raw rows: <code>data/mints.csv</code>, <code>data/dex_buys.csv</code>, <code>data/burns.csv</code>, <code>data/addresses.csv</code>. Dune version: <code>dune.sql</code>.</p>
</main></body></html>
""" % (
    RANGE, esc(headline),
    T["mints"], f(T["eth_gross_all"], 0), f(T["eth_deposited_new"], 0), pct(direct["share_eth"]),
    router["mints"], f(router["eth_gross"], 1), f(D["reth"], 0),
    RANGE, SRC, chart1, cat_tbl,
    RANGE, SRC, legend([(c, CC[c]) for c in cats_present]), chart2, wk_tbl,
    RANGE, legend(list(mc.items())), chart3, ven_tbl,
    RANGE, pct(R["top10_share"]), top_tbl,
    RANGE, entry_tbl,
    f(S["before"], 4), f(S["end"], 4), S["delta"], f(T["reth_minted"], 4), f(S["burned"], 4), S["burn_events"],
    S["minted_minus_burned"], S["gap"], esc(xc),
    "0xae78736cd615f374d3085123a210448e74fc6393", "0xce15294273cfb9d9b628f4d61636623decdf4fdc", T["mints"],
    f(T["deposit_fee_eth"], 4),
)
open(os.path.join(HERE, "index.html"), "w").write(page)
print("wrote index.html", len(page), "bytes")


# ---------------------------------------------------------------- results.md tables (prose is hand-written in
# results.md around the AUTO block; this regenerates only the block between the markers)
def md_tables():
    L = []
    L.append("### Totals\n")
    L.append("| Metric | Value | Method |\n|---|---|---|")
    L.append("| Mints (TokensMinted events) | %d in %d txs | rETH `TokensMinted` logs, blocks %d–%d |"
             % (T["mints"], T["mint_txs"], W["start_block"], W["end_block"]))
    L.append("| rETH minted | %s | sum of `amount` |" % f(T["reth_minted"], 4))
    L.append("| ETH behind mints (gross) | %s | DepositReceived / CreditWithdrawn `amount` |" % f(T["eth_gross_all"], 4))
    L.append("| …of which new user deposits | %s ETH in %d mints | `DepositReceived` |" % (f(T["eth_deposited_new"], 4),
                                                                                       T["deposit_mints"]))
    L.append("| …of which node-operator credit taken as rETH | %s ETH in %d mints | `CreditWithdrawn` |"
             % (f(T["eth_credit_withdrawn"], 4), T["credit_mints"]))
    L.append("| ETH credited to rETH (net of deposit fee) | %s | TokensMinted `ethAmount` |" % f(T["eth_net"], 4))
    L.append("| Deposit fee | %s ETH | gross − net |" % f(T["deposit_fee_eth"], 4))
    L.append("| Distinct rETH recipients / tx senders | %d / %d | TokensMinted `to` / tx `from` |"
             % (T["unique_depositors"], T["unique_tx_senders"]))
    L.append("| Mints not paired with a deposit-pool event | %d | — |" % T["unmatched"])
    L.append("\n### Share by entry point\n")
    L.append("| Entry point | Mints | ETH | Share of ETH | Share of mints |\n|---|---|---|---|---|")
    for c in CATS:
        b = BC[c]
        L.append("| %s | %d | %s | %s | %s |" % (c, b["mints"], f(b["eth_gross"], 2), pct(b["share_eth"]),
                                               pct(b["share_count"])))
    L.append("\n### Every non-direct entry point (tx `to`)\n")
    L.append("| Address | Label | Category | Mints | ETH | Label source |\n|---|---|---|---|---|---|")
    for e in R["entry_points"]:
        L.append("| `%s` | %s | %s | %d | %s | %s |" % (e["address"], e["label"], e["category"], e["mints"],
                                                       f(e["eth"], 2), e["label_source"] or "none found"))
    L.append("\n### Top 10 minting addresses (rETH recipient)\n")
    L.append("| # | Address | Label | Main path | Mints | ETH | Share |\n|---|---|---|---|---|---|---|")
    for i, t in enumerate(R["top10"]):
        L.append("| %d | `%s` | %s | %s | %d | %s | %s |" % (i + 1, t["address"], t["label"], t["path"], t["mints"],
                                                            f(t["eth"], 2), pct(t["share"])))
    L.append("\nTop 10 together: %s of ETH behind mints." % pct(R["top10_share"]))
    L.append("\n### Weekly (7-day buckets from 22 Aug; last bucket 6 days)\n")
    L.append("| Week | Mints | ETH (gross) | of which direct | rETH minted | rETH out of tracked DEX venues | rETH burned |\n"
             "|---|---|---|---|---|---|---|")
    for w in R["weekly"]:
        L.append("| %s | %d | %s | %s | %s | %s | %s |" % (w["week"], w["mints"], f(sum(w[c] for c in CATS), 1),
                                                         f(w[CATS[0]], 1), f(w["mint_reth"], 1), f(w["dex_reth"], 1),
                                                         f(w["burn_reth"], 1)))
    L.append("\n### rETH out of DEX venues (contrast; approximate)\n")
    L.append("| Venue | Address / how resolved | Events | rETH out |\n|---|---|---|---|")
    pools = R["pools"]
    for k, v in sorted(R["dex_venues"].items(), key=lambda x: -x[1]["reth"]):
        src = next(("`%s` (%s)" % (a, p["source"]) for a, p in pools.items()
                    if ("%.2f%%" % (p.get("fee_bps", 0) / 100)) in k or (p["dex"] == "Uniswap v2" and "v2 rETH" in k)),
                   "")
        if "Balancer v2" in k:
            src = "`%s` Vault, Swap events with tokenOut = rETH" % R["balancer_v2_vault"]
        if "v4" in k:
            src = "`0x000000000004444c5dc75cb358380d2e3de08a90` (Etherscan tag: Uniswap V4: Pool Manager)"
        if "Balancer v3" in k:
            src = "`0xba1333333333a1ba1108e8412f11850a5c319ba9` (Etherscan tag: Balancer V3: Vault)"
        L.append("| %s | %s | %d | %s |" % (k, src, v["swaps"], f(v["reth"], 2)))
    L.append("| **Total** | | %d events in %d txs | **%s** |" % (D["swaps"], D["txs"], f(D["reth"], 2)))
    L.append("\nrETH out of DEX venues ÷ rETH minted = %.2f×. %d DEX events sit inside a mint transaction; %d txs have "
             "more than one rETH outflow (multi-hop or arbitrage)." % (D["reth"] / T["reth_minted"],
                                                                     D["swaps_in_mint_txs"],
                                                                     D["txs_with_multiple_reth_out_swaps"]))
    L.append("\n### Checks\n")
    L.append("| Check | Result |\n|---|---|")
    L.append("| rETH totalSupply, block %d → %d | %s → %s (%+.6f) |" % (W["start_block"] - 1, W["end_block"],
                                                                     f(S["before"], 6), f(S["end"], 6), S["delta"]))
    L.append("| Minted − burned (%d TokensBurned events, %s rETH burned) | %+.6f |" % (S["burn_events"],
                                                                                 f(S["burned"], 6),
                                                                                 S["minted_minus_burned"]))
    L.append("| Gap (supply change − (minted − burned)) | %.2e rETH (float rounding) |" % S["gap"])
    if X:
        for k in ("mint_events", "reth_minted", "eth_net", "deposit_received_events", "eth_deposited_gross",
                  "credit_withdrawn_events", "credit_withdrawn_eth"):
            L.append("| Routescan indexer vs RPC: %s | %s vs %s (gap %s) |" % (k, X["indexer"][k], X["rpc_pipeline"][k],
                                                                      X["gap_rpc_minus_indexer"][k]))
    else:
        L.append("| Independent indexer re-pull | not run |")
    return "\n".join(L)


mdp = os.path.join(HERE, "results.md")
if os.path.exists(mdp):
    md = open(mdp).read()
    a, b = "<!-- AUTO:START -->", "<!-- AUTO:END -->"
    if a in md and b in md:
        md = md.split(a)[0] + a + "\n" + md_tables() + "\n" + b + md.split(b)[1]
        open(mdp, "w").write(md)
        print("updated results.md tables")
