# Who actually mints rETH? Results

**Window:** 22 Aug 2026 00:00 UTC to 20 Nov 2026 00:00 UTC (90 days), Ethereum blocks 25,806,959 to 26,452,577.
**Data pulled:** 20 Nov 2026, from free public JSON-RPC endpoints (publicnode, Tenderly public gateway, MEV Blocker). No API keys and no paid services.
**Reproduce:** `python3 -I fetch.py && python3 -I crosscheck.py && python3 -I analyze.py && python3 -I report.py` (Python 3.9 standard library only).

## Headline findings

1. **Minting is small and lumpy.** 409 mints created 3,872.89 rETH against 4,551.52 ETH over 90 days. 3,911.52 ETH of that was new user deposits. The other 640 ETH was node operators taking existing ETH credit as rETH (Saturn 1 `withdrawCredit`), which brings no new ETH in.
2. **Almost all of it is people calling `deposit()` themselves.** EOAs sending a transaction straight to the deposit pool account for 311 mints and 3,208.65 ETH. That is 70.5% of all minted ETH and 82.0% of new-deposit ETH.
3. **Whales drive the total.** The top 10 rETH recipients took 70.4% of minted ETH. One address (an EOA now running MetaMask's EIP-7702 delegator) minted 1,125 ETH in 3 deposits, 24.7% of the total. Seven direct deposits of 100 ETH or more add up to 2,391 ETH. The median direct deposit was 0.56 ETH, and 185 of the 311 direct deposits were under 1 ETH.
4. **Rocket Pool's own swap router barely mints.** It made 1 mint (32.01 ETH, 0.7%) in 90 days. Aggregators made 5 (343.84 ETH, 7.6%), and 4 of those came through CoW Protocol's settlement contract (338.44 ETH). Safe, ERC-4337 and EIP-7702 smart wallets made 10 (205.14 ETH, 4.5%). MetaMask's staking contract made 14 (37.87 ETH, 0.8%). Unlabelled contracts made 23 (84.01 ETH, 1.8%), led by one unverified contract `0x8f5835e9…5cb7` (16 mints). No mint came through a labelled vault or yield protocol.
5. **The trend is up sharply at the end of the window.** The last two buckets (7–19 Nov) hold 2,506.7 of the 4,551.5 ETH, 55% of the 90-day total, mostly from direct deposits.
6. **The market supplies far more rETH than minting does.** Tracked DEX venues paid out about 22,531 rETH, roughly 5.8 times the 3,873 rETH minted. This is gross outflow and includes arbitrage, so it overstates real buying. Meanwhile 20,901 rETH was burned, and rETH supply fell 17,028 rETH (−5.3%).

## Cross-check result

- **rocketscan.io** could not be used. On 20 Nov 2026 the domain had no A record ("could not resolve host").
- **Rocket Pool's own API** (`https://api.rocketpool.net/mainnet/payload`, fetched 20 Nov 2026) publishes queue and staking stats but no mint or rETH-supply history, so it can't be compared with a 90-day mint total.
- **On-chain supply reconciliation (exact):** rETH `totalSupply()` at block 25,806,958 minus `totalSupply()` at block 26,452,577 matches minted minus burned to within 2e-11 rETH, which is floating-point rounding. That gap is zero to the wei. So no mint or burn event in the window is missing from the pull.
- **Independent indexer (Routescan): exact match.** `crosscheck.py` re-pulled the same three event streams for the same blocks from Routescan's keyless Etherscan-compatible API (api.routescan.io), which is a separate indexer from the RPC nodes. It found 409 mints, 3,872.890887 rETH, 4,549.241930 ETH net, 364 deposits worth 3,911.517689 ETH and 45 credit withdrawals worth 640 ETH. The gap is 0 on every figure. (Blockscout's API was tried first but rate-limited this IP with HTTP 429 on 20 Nov. It is still available with `python3 -I crosscheck.py blockscout`.)

## Method

1. **Addresses** were resolved on-chain through RocketStorage `0x1d8f8f00cfa6758d7be78336684788fb0ee0fa46`, using `getAddress(keccak256("contract.address" + name))`:
   - `rocketTokenRETH` = `0xae78736cd615f374d3085123a210448e74fc6393`. This equals the expected address.
   - `rocketDepositPool` = `0xce15294273cfb9d9b628f4d61636623decdf4fdc`. The address was identical at the first block, the last block and today, so no older deposit pool version was active in the window. RocketStorage at the start block confirms `contract.name` = "rocketDepositPool" and `contract.exists` = true. Its verified source on Blockscout is `RocketDepositPool`, solc 0.8.30.
2. **Mints** are rETH `TokensMinted(to, amount, ethAmount, time)` logs, pulled in 10,000-block `eth_getLogs` chunks with retries.
3. **Mint path.** Every mint is followed in the same transaction by one deposit-pool event. `DepositReceived(from, amount, time)` comes from `deposit()` and marks new ETH; 364 mints had one. `CreditWithdrawn(node, amount, time)` comes from Saturn 1's `withdrawCredit()`, where a node operator takes ETH credit as rETH; 45 mints had one, from 41 nodes. All 409 mints paired with one of the two. The verified source shows both paths call `rocketTokenRETH.mint(amount − fee, recipient)`.
4. **Entry point** is the mint transaction's `to`, fetched with `eth_getTransactionByHash`:
   - `to` = deposit pool means a direct deposit. The signer is an EOA, though it may now carry EIP-7702 code.
   - `to` = `0x16d5…1c1c` means the Rocket Pool swap router (Etherscan tag "Rocket Pool: Swap Router").
   - A contract with a public Etherscan name tag for an aggregator means "DEX aggregator / router" (CoW Protocol GPv2Settlement, KyberSwap Meta Aggregation Router v2).
   - ERC-4337 EntryPoints (Etherscan tags "Entry Point 0.6.0" and "Entry Point 0.7.0"), contracts where `getThreshold()` and `VERSION()` both answer (Safe), and EOAs with EIP-7702 delegation code (`0xef0100…`) used as `to` all count as a smart wallet.
   - The MetaMask staking contract is its own category (Etherscan tag "MetaMask: Third Party Staking").
   - Anything else is an "unlabelled contract".
5. **Labels** come only from a public Etherscan name tag (the address page title) or a Blockscout verified contract name. Each one's source is listed in the tables, and nothing was named by hand. The category mapping for tagged contracts is in `categories.json`.
6. **DEX contrast** is rETH paid out by:
   - the Uniswap v3 rETH/WETH pools at all four fee tiers, resolved through `UniswapV3Factory.getPool` (`0x1f98…f984`), using Swap events where the rETH delta is negative;
   - the Uniswap v2 pair, resolved through `getPair`;
   - Balancer v2 Vault `0xba12…f2c8` Swap events with tokenOut = rETH, across all pools;
   - rETH Transfer events out of the Uniswap v4 PoolManager and the Balancer v3 Vault.
7. **Weekly** buckets are 7 days from 22 Aug. The last bucket, 14–19 Nov, is 6 days. Mint times come from the event's own timestamp. DEX times are interpolated from daily block samples, so they are accurate to minutes.

<!-- AUTO:START -->
### Totals

| Metric | Value | Method |
|---|---|---|
| Mints (TokensMinted events) | 409 in 409 txs | rETH `TokensMinted` logs, blocks 25806959–26452577 |
| rETH minted | 3,872.8909 | sum of `amount` |
| ETH behind mints (gross) | 4,551.5177 | DepositReceived / CreditWithdrawn `amount` |
| …of which new user deposits | 3,911.5177 ETH in 364 mints | `DepositReceived` |
| …of which node-operator credit taken as rETH | 640.0000 ETH in 45 mints | `CreditWithdrawn` |
| ETH credited to rETH (net of deposit fee) | 4,549.2419 | TokensMinted `ethAmount` |
| Deposit fee | 2.2758 ETH | gross − net |
| Distinct rETH recipients / tx senders | 283 / 312 | TokensMinted `to` / tx `from` |
| Mints not paired with a deposit-pool event | 0 | — |

### Share by entry point

| Entry point | Mints | ETH | Share of ETH | Share of mints |
|---|---|---|---|---|
| Direct deposit (EOA -> deposit pool) | 311 | 3,208.65 | 70.5% | 76.0% |
| Node operator credit withdrawal (no new ETH) | 45 | 640.00 | 14.1% | 11.0% |
| Rocket Pool swap router | 1 | 32.01 | 0.7% | 0.2% |
| DEX aggregator / router | 5 | 343.84 | 7.6% | 1.2% |
| Smart wallet (Safe / ERC-4337 / EIP-7702) | 10 | 205.14 | 4.5% | 2.4% |
| Wallet staking feature (MetaMask) | 14 | 37.87 | 0.8% | 3.4% |
| Vault or other protocol | 0 | 0.00 | 0.0% | 0.0% |
| Unlabelled contract | 23 | 84.01 | 1.8% | 5.6% |

### Every non-direct entry point (tx `to`)

| Address | Label | Category | Mints | ETH | Label source |
|---|---|---|---|---|---|
| `0x9008d19f58aabd9ed0d60971565aa8510560ab41` | CoW Protocol: GPv2Settlement | DEX aggregator / router | 4 | 338.44 | Etherscan name tag (etherscan.io/address/0x9008d19f58aabd9ed0d60971565aa8510560ab41) |
| `0x9953f65e00ce71d7aa5a3f7889f63fee0f1ba63c` | SafeProxy | Smart wallet (Safe / ERC-4337 / EIP-7702) | 4 | 178.46 | Blockscout verified contract name (eth.blockscout.com/address/0x9953f65e00ce71d7aa5a3f7889f63fee0f1ba63c) |
| `0x8f5835e9d756c9bd934bce527157a4b0ef3c5cb7` | unlabelled contract | Unlabelled contract | 16 | 79.48 | none found |
| `0x1f6692e78dde07ff8da75769b6d7c716215bc7d0` | MetaMask: Third Party Staking | Wallet staking feature (MetaMask) | 14 | 37.87 | Etherscan name tag (etherscan.io/address/0x1f6692e78dde07ff8da75769b6d7c716215bc7d0) |
| `0x16d5a408e807db8ef7c578279beeee6b228f1c1c` | Rocket Pool: Swap Router | Rocket Pool swap router | 1 | 32.01 | Etherscan name tag (etherscan.io/address/0x16d5a408e807db8ef7c578279beeee6b228f1c1c) |
| `0x5ff137d4b0fdcd49dca30c7cf57e578a026d2789` | Entry Point 0.6.0 | Smart wallet (Safe / ERC-4337 / EIP-7702) | 2 | 16.00 | Etherscan name tag (etherscan.io/address/0x5ff137d4b0fdcd49dca30c7cf57e578a026d2789) |
| `0xfd314504b868c716ce409c7eb999d4b7e240e96e` | Safe v1.5.0 (threshold 1) | Smart wallet (Safe / ERC-4337 / EIP-7702) | 1 | 6.27 | on-chain: getThreshold() and VERSION() answer at this address |
| `0x6131b5fae19ea4f9d964eac0408e4408b66337b5` | KyberSwap: Meta Aggregation Router v2 | DEX aggregator / router | 1 | 5.40 | Etherscan name tag (etherscan.io/address/0x6131b5fae19ea4f9d964eac0408e4408b66337b5) |
| `0xff0000000674ffb069f73038b0a54c7937552088` | unlabelled contract | Unlabelled contract | 5 | 4.51 | none found |
| `0x20dc966e61e77fce62e271d5357b32476ef8f3fd` | GnosisSafeProxy | Smart wallet (Safe / ERC-4337 / EIP-7702) | 1 | 4.31 | Blockscout verified contract name (eth.blockscout.com/address/0x20dc966e61e77fce62e271d5357b32476ef8f3fd) |
| `0x0000000071727de22e5e9d8baf0edac6f37da032` | Entry Point 0.7.0 | Smart wallet (Safe / ERC-4337 / EIP-7702) | 1 | 0.08 | Etherscan name tag (etherscan.io/address/0x0000000071727de22e5e9d8baf0edac6f37da032) |
| `0xd0a9a5f6b129e8ce82943025e20c1ae0e6f016e1` | Safe v1.3.0 (threshold 1) | Smart wallet (Safe / ERC-4337 / EIP-7702) | 1 | 0.02 | on-chain: getThreshold() and VERSION() answer at this address |
| `0xbc1d9760bd6ca468ca9fb5ff2cfbeac35d86c973` | unlabelled contract | Unlabelled contract | 1 | 0.01 | none found |
| `0x2fd983c453753eeae26079553bc1032a863a2186` | unlabelled contract | Unlabelled contract | 1 | 0.01 | none found |

### Top 10 minting addresses (rETH recipient)

| # | Address | Label | Main path | Mints | ETH | Share |
|---|---|---|---|---|---|---|
| 1 | `0x6ea486a3426563e23023125f18867117878f0ea7` | EOA, EIP-7702 delegated to 0x63c0c19a… (MetaMask: EIP-7702 Delegator) | Direct deposit (EOA -> deposit pool) | 3 | 1,125.00 | 24.7% |
| 2 | `0xccede65d51037f557afe45e6fc5bbfcaf4fd9998` | EOA (no public tag) | Direct deposit (EOA -> deposit pool) | 1 | 700.00 | 15.4% |
| 3 | `0xaddc26a3854feabfd20d6bf658254088d83a425a` | MainnetSettler | DEX aggregator / router | 3 | 327.84 | 7.2% |
| 4 | `0xce8d037748fa151a1ca6d18138066ce61d1022a6` | EOA (no public tag) | Direct deposit (EOA -> deposit pool) | 1 | 271.00 | 6.0% |
| 5 | `0x4938412d8cac27cf2a9e1a900c881cc437e4bbed` | EOA (no public tag) | Node operator credit withdrawal (no new ETH) | 7 | 224.00 | 4.9% |
| 6 | `0xde53bcda6527d2aa15ec733352c8d393c2e0ec99` | SafeProxy | Smart wallet (Safe / ERC-4337 / EIP-7702) | 4 | 178.46 | 3.9% |
| 7 | `0x0e59e76bc1ce90fb8fdb857a0efc9122546f15b7` | EOA (no public tag) | Direct deposit (EOA -> deposit pool) | 1 | 100.00 | 2.2% |
| 8 | `0x0f61d61ffdf741a87d506c55c2c5bd3f76d3b2b5` | EOA (no public tag) | Direct deposit (EOA -> deposit pool) | 1 | 100.00 | 2.2% |
| 9 | `0x6996e087b7b138d9f655f663b7e3f2dc95b532ea` | EOA (no public tag) | Direct deposit (EOA -> deposit pool) | 1 | 100.00 | 2.2% |
| 10 | `0xa31b59c9a7ecacd682da37898716681ce02cb188` | EOA (no public tag) | Node operator credit withdrawal (no new ETH) | 2 | 80.00 | 1.8% |

Top 10 together: 70.4% of ETH behind mints.

### Weekly (7-day buckets from 22 Aug; last bucket 6 days)

| Week | Mints | ETH (gross) | of which direct | rETH minted | rETH out of tracked DEX venues | rETH burned |
|---|---|---|---|---|---|---|
| 22 Aug–28 Aug | 44 | 122.8 | 62.4 | 104.8 | 1,795.5 | 417.0 |
| 29 Aug–04 Sep | 34 | 82.2 | 34.2 | 70.2 | 5,219.8 | 2,497.2 |
| 05 Sep–11 Sep | 29 | 143.5 | 127.8 | 122.5 | 1,563.1 | 457.3 |
| 12 Sep–18 Sep | 24 | 148.8 | 60.8 | 126.9 | 1,120.5 | 459.5 |
| 19 Sep–25 Sep | 21 | 51.9 | 51.3 | 44.3 | 1,820.7 | 444.7 |
| 26 Sep–02 Oct | 28 | 196.2 | 145.5 | 167.2 | 1,692.7 | 438.1 |
| 03 Oct–09 Oct | 22 | 124.6 | 28.2 | 106.1 | 1,943.3 | 917.5 |
| 10 Oct–16 Oct | 15 | 162.1 | 24.5 | 138.0 | 2,555.3 | 775.5 |
| 17 Oct–23 Oct | 28 | 464.8 | 409.1 | 395.7 | 1,690.2 | 5,474.8 |
| 24 Oct–30 Oct | 37 | 334.5 | 16.2 | 284.7 | 604.0 | 1,716.0 |
| 31 Oct–06 Nov | 49 | 213.4 | 143.2 | 181.5 | 246.3 | 843.5 |
| 07 Nov–13 Nov | 38 | 1,044.9 | 821.7 | 888.4 | 485.1 | 2,490.6 |
| 14 Nov–19 Nov | 40 | 1,461.8 | 1,283.8 | 1,242.5 | 1,794.7 | 3,969.6 |

### rETH out of DEX venues (contrast; approximate)

| Venue | Address / how resolved | Events | rETH out |
|---|---|---|---|
| Uniswap v3 rETH/WETH 0.01% | `0x553e9c493678d8606d6a5ba284643db2110df823` (UniswapV3Factory.getPool(rETH, WETH, 100)) | 13193 | 10,170.09 |
| Uniswap v4 PoolManager (rETH Transfer out, approx.) | `0x000000000004444c5dc75cb358380d2e3de08a90` (Etherscan tag: Uniswap V4: Pool Manager) | 5910 | 7,692.83 |
| Balancer v3 Vault (rETH Transfer out, approx.) | `0xba1333333333a1ba1108e8412f11850a5c319ba9` (Etherscan tag: Balancer V3: Vault) | 964 | 4,206.35 |
| Uniswap v3 rETH/WETH 0.05% | `0xa4e0faa58465a2d369aa21b3e42d43374c6f9613` (UniswapV3Factory.getPool(rETH, WETH, 500)) | 619 | 460.19 |
| Balancer v2 (all pools, tokenOut=rETH) | `0xba12222222228d8ba445958a75a0704d566bf2c8` Vault, Swap events with tokenOut = rETH | 361 | 1.63 |
| Uniswap v3 rETH/WETH 0.30% | `0xf0e02cf61b31260fd5ae527d58be16312bda59b1` (UniswapV3Factory.getPool(rETH, WETH, 3000)) | 15 | 0.09 |
| Uniswap v2 rETH/WETH | `0xe4f719c11fc5ab883e32068df99962985645e860` (UniswapV2Factory.getPair(rETH, WETH)) | 5 | 0.00 |
| **Total** | | 21067 events in 20015 txs | **22,531.18** |

rETH out of DEX venues ÷ rETH minted = 5.82×. 11 DEX events sit inside a mint transaction; 727 txs have more than one rETH outflow (multi-hop or arbitrage).

### Checks

| Check | Result |
|---|---|
| rETH totalSupply, block 25806958 → 26452577 | 320,042.274964 → 303,013.831413 (-17028.443551) |
| Minted − burned (16998 TokensBurned events, 20,901.334438 rETH burned) | -17028.443551 |
| Gap (supply change − (minted − burned)) | -2.18e-11 rETH (float rounding) |
| Routescan indexer vs RPC: mint_events | 409 vs 409 (gap 0) |
| Routescan indexer vs RPC: reth_minted | 3872.890887097072 vs 3872.890887097072 (gap 0.0) |
| Routescan indexer vs RPC: eth_net | 4549.241930440514 vs 4549.241930440514 (gap 0.0) |
| Routescan indexer vs RPC: deposit_received_events | 364 vs 364 (gap 0) |
| Routescan indexer vs RPC: eth_deposited_gross | 3911.5176892851564 vs 3911.5176892851564 (gap 0.0) |
| Routescan indexer vs RPC: credit_withdrawn_events | 45 vs 45 (gap 0) |
| Routescan indexer vs RPC: credit_withdrawn_eth | 640.0 vs 640.0 (gap 0.0) |
<!-- AUTO:END -->

## Caveats

- **"Direct" can't see the front-end.** A wallet or website that builds a plain `deposit()` call from the user's own EOA looks identical to a user doing it by hand. That includes stake.rocketpool.net when it routes to the deposit pool rather than the swap router. Attributing mints to front-ends would need calldata or referral data, which `deposit()` doesn't carry.
- **EIP-7702 status is today's code.** The top minter's delegation to MetaMask's EIP-7702 delegator was read at the latest block and may not have existed at mint time. It doesn't change the category, because a transaction sent to the deposit pool is direct either way.
- **The aggregator count is a floor.** Only contracts with a public tag are called aggregators. `0x8f5835e9…5cb7` (16 mints, about 154k transactions, unverified on Etherscan) and three other unlabelled contracts could be routers or bots. They stay "unlabelled contract" until a public label exists.
- **The DEX numbers are gross outflows, not net buying.** Arbitrage between pools, multi-hop routes and, for Uniswap v4 and Balancer v3, liquidity withdrawals all count. Curve, other DEXs, OTC and CEX flows aren't covered. Treat ~5.8× as "the market moved several times more rETH than minting created", not as a precise demand ratio.
- **Uniswap v3 volume dipped late in the window.** The v3 rETH/WETH pools paid out about 800–1,460 rETH a week until 23 Oct. That fell to 26 and 40 rETH in the two weeks from 24 Oct to 6 Nov, then recovered to 201 and 643. Some of that flow may have moved to venues counted here only approximately (v4, Balancer v3) or not at all. This wasn't investigated.
- **Blockscout labels.** Blockscout's address API returned errors (HTTP 500/429) for 17 of 41 addresses during the run. Those addresses fall back to the Etherscan tag, or show as unlabelled.
- **Context, not part of the analysis.** Rocket Pool's API (fetched 20 Nov 2026) reports `megapoolQueueTotal` 672, `megapoolQueueBorrowedEth` 18,816 and `depositPoolBalance` 4.34 ETH. Demand from node operators is waiting on rETH-side ETH. That is why the mint path matters.

## Dune version

`dune.sql` reproduces the core query on `ethereum.logs` and `ethereum.transactions`, plus `safe_ethereum.safes` and `labels.addresses` for classification. **It has not been run on Dune** because there was no paid access. Table and column names follow Dune's documented raw schema, so check the first run against the totals above (409 mints, 4,551.52 ETH).

## Files

- `fetch.py`, `rpclib.py`: data pull (stdlib keccak, JSON-RPC client)
- `crosscheck.py`: independent indexer re-pull (Routescan; Blockscout optional)
- `analyze.py`, `categories.json`: classification and aggregates → `data/results.json`
- `report.py`: `index.html` and the tables in this file
- `data/mints.csv` (one row per mint), `data/dex_buys.csv`, `data/burns.csv`, `data/addresses.csv`, `data/meta.json`
