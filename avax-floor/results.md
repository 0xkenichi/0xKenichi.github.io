# What happened when Avalanche validators raised the gas floor? Results

**Window:** 1 Aug 2026 to 25 Nov 2026 (the last complete UTC day), Avalanche C-Chain.
**Data pulled:** 26 Nov 2026, from free public endpoints (C-Chain RPC, Routescan, DefiLlama, CoinGecko, Avalanche metrics API). No API keys, no accounts, no paid services.
**Reproduce:** `python3 -I fetch.py && python3 -I floor.py && python3 -I analyze.py && python3 -I sample.py && python3 -I who.py` (Python 3.9 standard library only).

## In plain English

After Helicon, validators raised the C-Chain's minimum gas price from 1 wei to 5 nAVAX (in force from 27 Sep). They cut it to 2.5 nAVAX on 19 Oct and raised it to 7.5 nAVAX on 10 Nov. Each time, the chain used about the same amount of gas (roughly 90B gas a day), so the burn that comes from the floor moved with the floor: about 240 AVAX/day at 2.5, 455 at 5 and 690 at 7.5, against about 30 before. Transactions fell about 60% when the floor first bound. The ones that left were mostly bot traffic: calls that do nothing visible on-chain, failed transactions, and three contracts fed by 1, 1 and exactly 100 senders. The other ~300K transactions a day stayed and barely reacted to the floor moving between 2.5 and 7.5. App fees didn't fall apart. Burned fees went from about 2.4% of app fees (1.3% in August) to 3.8–4.9%.

### Reading the numbers

- The market base fee went from about 0.07 nAVAX to 5 nAVAX, about 70x. (The floor itself went from 1 wei to 5 nAVAX.)
- The fall in transactions depends on the baseline: −61% against the 10 days before Helicon, −87% against August. Most of the August-to-September fall happened before Helicon.
- The chain's share of app fees rose from 2.44% (10 days before Helicon) or 1.31% (August) to 3.8–4.9%. USD figures move with the AVAX price.
- App fees per day stayed in the same range ($254K–$331K against $306K before). They were 14–17% lower in the two later periods, while the AVAX price fell.

## Headline findings

1. **The floor changes are on-chain, to the block.** Helicon went live at block 95,921,105 (22 Sep 2026 15:00:00 UTC). From then on, every header carries `minPriceExponent`, and the floor is `2^(minPriceExponent / 2^58)` wei. Validators moved it in three steps:

   | Change | First block | Started (UTC) | Reached (UTC) | Duration |
   |---|---|---|---|---|
   | 1 wei → 5 nAVAX | 95,921,105 | 22 Sep 15:00 | 27 Sep 06:06 (block 96,241,276) | 111 h, doubling about every 3.5 h |
   | …it passed the old market base fee (0.1 nAVAX) | 96,185,920 | 26 Sep 09:52 | | |
   | 5 → 2.5 nAVAX | 97,979,371 | 19 Oct 15:16 | 19 Oct 19:10 (block 97,994,369) | 3.9 h |
   | 2.5 → 7.5 nAVAX | 99,889,866 | 9 Nov 23:14 | 10 Nov 05:14 (block 99,910,288) | 6.0 h |

   The floor stopped being a formality on 26 Sep. Before that the ramp sat below the ~0.07 nAVAX base fee the market was already paying. The 2.5 cut happened on 19 Oct and the 7.5 rise started late on 9 Nov.

2. **Transactions fell about 60% when the floor started to bind. Most of the 87% drop since August happened before Helicon.** August averaged 2.23M tx/day. By the last 10 days before Helicon (12–21 Sep) that was already down to 720K/day, with the floor still at 1 wei. After the floor reached 5 nAVAX, the chain did 284K/day. That is −61% against those last 10 days, and −87% against August. Every day at every new floor level had fewer transactions than the quietest day in the 10 days before Helicon.

3. **AVAX burned per day rose 1.2–2.4x (median), and the burn followed the floor up, down and up again.** Median AVAX burned per day: 704 in the 10 days before Helicon; **1,304 at 5 nAVAX; 827 at 2.5; 1,724 at 7.5**. The floor went 5 → 2.5 → 7.5 over time, not in a straight line, and the burn went down and back up with it. A steady upward trend can't produce that pattern. Counted in AVAX, the result doesn't depend on the token price.

4. **The chain's cut of what users pay apps went from about 1–2.5% to about 4–5%.** Burned fees in USD as a share of DefiLlama app fees on Avalanche (pooled per period): August 1.31%, last 10 days before Helicon 2.44%, **5 nAVAX 4.50%, 2.5 nAVAX 3.82%, 7.5 nAVAX 4.91%**. That is about 3–3.7x August, or 1.6–2x the 10 days just before Helicon.

5. **App fees didn't collapse.** App fees per day averaged $306K in the 10 days before Helicon. They were $331K at 5 nAVAX, $263K at 2.5 and $254K at 7.5. The later dip is in the same direction as the AVAX price (−13% against those 10 days by the 7.5 period). These figures don't show the higher floor hurting apps, and they can't prove it didn't.

6. **Between 2.5 and 7.5 nAVAX, transaction counts didn't respond to the floor.** Tx/day was 284K at 5, 297K at 2.5 and 348K at 7.5. Tripling the floor from 2.5 to 7.5 came with *more* transactions, not fewer. The traffic that was sensitive to price had already left at the first step.

7. **The floor's own contribution to the burn rose in step with the floor: about 90 AVAX a day for each nAVAX.** From the block sample, the chain used roughly the same gas every day at every new floor level: 82B, 93B and 89B gas/day at 5, 2.5 and 7.5 nAVAX (95% intervals overlap). So the part of the burn that comes from the base fee scaled almost exactly with the floor: **about 30 AVAX/day before Helicon, 242 at 2.5, 455 at 5 and 693 at 7.5** (95% intervals 184–316, 350–569 and 521–920; they don't overlap). Tips (priority fees) make up the rest. Tips are 90–96% of fees before Helicon and 57–68% after, and swing too much to show any effect of the floor (95% intervals span 2–4x). That is why the daily total burn is noisy, while the base-fee part tracks the floor cleanly.

8. **Who left: bots, in two waves.** From 300 random whole blocks per period (20,184 transactions, all with receipts):
   - **Wave 1 happened before Helicon and wasn't caused by the floor.** In August, 69% of all C-Chain transactions (about 1.55M a day) went to three contracts whose Routescan verified name is **XPower**. They switched on and off (almost none on 4–6 Aug and 20–25 Aug), which explains August's wild day-to-day swings. **XPower traffic stopped after 11 Sep, 11 days before Helicon went live,** and none appears in any later sample. Most of the drop from August's 2.2M tx/day happened then, with the floor still at 1 wei. These figures don't show *why* XPower stopped.
   - **Wave 2 came when the floor bound.** In the 10 days before Helicon, 40% of transactions were contract calls that emitted no event log, and 16% failed. Both are typical of bots probing or spamming. Once the floor reached 5 nAVAX, "no-log" calls fell from about 291K/day to 12K–35K/day, and failed transactions from about 118K/day to 28K–54K/day. The biggest pre-Helicon destinations were unverified contracts fed by one sender or a fixed set of senders (`0xceca…eec1`: 1 sender, 92K tx/day, empty function selector; `0x3317…e078`: 1 sender, 39K/day; `0x28d9…1c39`: exactly 100 senders, 106K/day). All three went to zero in every post-floor sample. The top 10 senders' share of transactions fell from 29% to 14–21%.
   - **Real use mostly stayed.** Contract calls that emit logs (such as token transfers) went from about 284K/day before to 186K–240K/day after. Plain AVAX transfers held at 25K–42K/day. Ordinary destinations kept their volume. A token behind `TransparentUpgradeableProxy` `0x9702…a8c7` (`transfer` calls) did 11K–21K/day in every period. USDC (`FiatTokenProxy`) is in the top 10 of every post-floor period. Some of the post-floor traffic is new: an oracle contract (`CompressedOracleV1`, `0xe844…3872`) had no transactions in any pre-Helicon sample, then about 11K/day at 5 nAVAX, 30K at 2.5 and 52K at 7.5.
   - Limits: labels are Routescan verified-contract names only. "Bot-like" is our reading of the patterns (single sender, no logs, empty selector), not proof of intent. Destinations that appear in no post-floor sample could still have a little traffic below what 300 blocks can detect.

## Before/after table (full UTC days only; transition days left out)

| Period | Days | Floor (nAVAX) | Tx/day (mean) | AVAX burned/day (mean / median) | USD burned/day (mean) | App fees/day (DefiLlama) | Chain share of app fees | AVAX price (mean) |
|---|---|---|---|---|---|---|---|---|
| Aug (pre-Helicon) | 31 | 1 wei | 2,228,642 | 510 / 430 | $3,547 | $271,240 | 1.31% | $6.82 |
| 1–21 Sep (pre-Helicon) | 21 | 1 wei | 1,300,430 | 695 / 574 | $5,868 | $299,477 | 1.96% | $7.94 |
| 12–21 Sep (last 10 days pre) | 10 | 1 wei | 719,652 | 823 / 704 | $7,487 | $306,478 | 2.44% | $8.35 |
| 28 Sep–18 Oct | 21 | **5** | 283,548 | 1,377 / 1,304 | $14,871 | $330,623 | 4.50% | $10.68 |
| 20 Oct–8 Nov | 20 | **2.5** | 297,067 | 1,155 / 827 | $10,040 | $263,047 | 3.82% | $8.79 |
| 11–25 Nov | 15 | **7.5** | 347,741 | 1,699 / 1,724 | $12,491 | $254,416 | 4.91% | $7.28 |

Left out: 22–27 Sep (ramp), 19 Oct (5 → 2.5), 9–10 Nov (2.5 → 7.5). Source file: `data/regimes.csv`. Day-level checks in the same file: 90% of days at 5 nAVAX, 60% at 2.5 and 100% at 7.5 burned more AVAX than the pre-Helicon median day. The 2.5 period is the weakest; its mean is lifted by one spike day (30 Oct, 6,158 AVAX, 27% of that period's burn).

## Caveats (read before quoting)

- **Correlation, not a controlled test.** Nobody randomised the floor. The up-down-up order (5 → 2.5 → 7.5) makes a simple time trend an unlikely explanation for the burn, but market events in the same weeks (volatility, MEV, one app's campaign) could still move both series.
- **Transactions were already falling before Helicon.** Daily tx fell from 2–3.9M in August to 0.5–1M in mid-September with the floor still at 1 wei. Pre-Helicon traffic swung wildly from day to day (0.73M to 3.92M in August), which looks like bots switching on and off. Any "the floor cut traffic by X%" claim depends on the baseline: −61% against the 10 days before, −87% against August. Use the 10-day baseline, or quote both.
- **Price.** AVAX jumped from about $7.9 to $10.9 around 22 Sep, then slid to $6.40 by 25 Nov. USD burn and the chain-share ratio carry this. The AVAX-denominated burn (finding 3) doesn't.
- **Partial month.** The 7.5 period has 15 days (11–25 Nov). November isn't over.
- **Tips dominate fees.** Every C-Chain fee (base fee + tip) is burned, so "burned" = "fees". Most of the burn is still tips, which follow MEV and arbitrage competition rather than the floor (finding 7). The floor-driven part (base fee × gas) is about 240–690 AVAX/day, roughly $1.5K–4.4K/day at late-November prices. It's real, but small next to app fees of $250K+/day.
- **Block sample size.** 300 blocks per period gives about 1,000 transactions per post-floor period. Shares are good to a few percentage points; small destinations can be missed. Sample-based tx/day lands within 1–11% of Routescan's counts (`est_tx_per_day_from_sample` vs `est_tx_per_day` in `data/who_summary.json`).
- **"App fees" are DefiLlama fees, not the Foundation's "protocol revenue".** Over Jan 2025–Aug 2026 DefiLlama totals $264.1M against the Foundation's $282.2M (−6.4%), and the month-by-month gap varies (see calibration). Ratios here are DefiLlama-based and won't match the Foundation's month by month.
- **Hourly sampling of the floor.** Changes were found from one header per ~3,600 blocks and then bisected to the exact block. A floor change that started and fully reversed within one hour would be missed. None is visible in the base fees.
- **Who-left labels** come only from Routescan's verified contract names. An unverified contract isn't named, and a label is not proof of intent.

## Cross-checks

| Check | Days | Total gap | Median daily gap | Worst day |
|---|---|---|---|---|
| AVAX burned: Routescan vs Avalanche metrics API (`feesPaid`) | 111 (to 19 Nov) | −0.01% | 0.16% | 0.81% |
| USD burned: Routescan × price vs DefiLlama chain fees | 117 | +0.46% | 1.7% | 59% (19 Aug; spikes land on different days) |
| Tx count: Routescan vs Avalanche metrics API (`txCount`) | 111 | −0.01% | 0.17% | 0.72% |
| AVAX price: DefiLlama (noon) vs CoinGecko (daily) | 117 | +0.21% | 1.35% | 13.6% |

Per period, Routescan and DefiLlama burns in USD agree within −4.2% to +2.1% (`data/crosscheck.json`).

**Why Routescan is the primary series.** On the 26 Nov pull, the Avalanche metrics API (`feesPaid`, `txCount`) matches Routescan to 0.01% over 111 days, including every post-Helicon day. It is used only as a cross-check because it stops at 19 Nov (it lags about a week), while Routescan runs to the last complete day.

## Calibration: free inputs vs the Foundation's published figures

| Figure | Foundation | Ours | Gap |
|---|---|---|---|
| C-Chain tx fees, Jan 2025–Aug 2026 ("The Price of a Transaction", 5 Nov 2026) | $9.6M | $9.53M (DefiLlama) / $9.75M (Routescan × price) | −0.7% / +1.6% |
| Protocol revenue, same window | $282.2M | $264.1M (DefiLlama app fees) | −6.4% |
| Fee ÷ revenue, same window | 3.39% | 3.61% (DefiLlama) / 3.69% (Routescan) | +0.2 to +0.3 pts |
| Fee ÷ revenue, Aug 2026 ("latest month") | 1.13% | 1.28% / 1.30% | +0.15 pts |
| Fee ÷ revenue, Jan 2025 | 5.79% | 3.11% / 3.12% | **−2.7 pts (doesn't match)** |
| Tx/day, Aug 2026 | 2.23M | 2,228,642 (Routescan) | match |
| Burned C-Chain fees since start of 2024 (GCI post, 12 Aug 2026) | ≈ $23.5M | $26.6M (Routescan, to 30 Jun 2026) / $27.3M (DefiLlama) | +13% to +16% |
| June 2026 burn vs June NGCP ($3.1M) | "≈3% of monthly NGCP" | $110–114K = 3.6–3.7% of $3.1M | close |

So the fee side reproduces within 2%, and the totals for the revenue side within 6.4%. Single months on the revenue side can be far off (Jan 2025), and the since-2024 burn comes out 13–16% higher than the Foundation's figure (their end date and price method aren't stated). Source file: `data/calibration.json`. The Foundation labels its figures as estimates. For these long windows, the Routescan × price figures use DefiLlama's daily price chart, which has gaps (142 of 608 days in Jan 2025–Aug 2026). Each gap takes the previous day's price, so they are less precise than the study-window series, which has a price for every day.

## Method

1. **Floor.** `floor.py` reads one C-Chain header about every hour (every 3,600 blocks) from 1 Aug: 2,703 headers. It finds every hour in which `minPriceExponent` changed, then bisects with `eth_getBlockByNumber` to the exact first block that left the old value and the first block that reached the new one. The formula `floor_wei = 2^(mpe / 2^58)` was fitted from the headers: 5 → 2.5 is a step of exactly 2^58 in the exponent, and 1,104 of 1,535 post-Helicon samples have a base fee exactly equal to the computed floor. Five samples sit up to 0.02% below it, all during ramps, because the base fee follows the parent block's floor.
2. **Daily series.** Routescan `dailytx` and `dailytxnfee` (AVAX), AVAX price at 12:00 UTC from DefiLlama's price API (no missing days), DefiLlama app fees (sum of every protocol on Avalanche, the chain's own gas fees excluded), DefiLlama chain fees, the Avalanche metrics API, and CoinGecko. Output: `data/daily.csv` (all columns) and `data/chart_daily.csv` (chart columns with 7-day centred means).
3. **Periods** are full UTC days at one floor level. Days when the floor was moving are left out. The pre-Helicon side is shown three ways (August, 1–21 Sep, last 10 days) because traffic was already falling.
4. **Chain share** = Σ(AVAX burned × that day's price) ÷ Σ(DefiLlama app fees) over the period.
5. **Who left.** `sample.py` draws 300 block numbers per period uniformly at random (seed 283), pulls each whole block with receipts, and `who.py` classifies every transaction. Sampling whole blocks evenly by block number gives an unbiased estimate of each class's share of all transactions in the period. Per-day figures scale the sampled shares by Routescan's tx/day.

## Sources

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
