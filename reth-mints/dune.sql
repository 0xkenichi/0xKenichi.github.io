-- Who actually mints rETH? Dune SQL (Trino) version of the core query in fetch.py + analyze.py.
-- Raw tables only (ethereum.logs, ethereum.transactions), so it doesn't depend on decoded-table names.
-- Window: 2026-08-22 00:00 UTC to 2026-11-20 00:00 UTC (edit the two dates below).
-- NOT YET RUN ON DUNE (no paid access). Expected output for this window, from the free RPC pipeline:
--   409 mints, 4,551.52 ETH gross (3,911.52 new deposits + 640.00 node-operator credit), 3,872.89 rETH.
--   Direct 311 / 3,208.65 ETH; credit 45 / 640.00; aggregators 5 / 343.84; smart wallets 10 / 205.14;
--   MetaMask staking 14 / 37.87; swap router 1 / 32.01; unlabelled 23 / 84.01.
-- Differences to expect: the Python pipeline also counts EOAs carrying EIP-7702 code used as tx.to and Safes found by
-- calling getThreshold()/VERSION(); here Safes come from safe_ethereum.safes and 7702 only as self-calls, and
-- contracts with a Dune label get "Labelled contract: <name>" where the Python version shows "unlabelled contract".
-- Each mint tx in this window has exactly one mint; if a tx ever holds several, check the rn = 1 pairing.
--
-- Contracts (resolved via RocketStorage 0x1d8f8f00cfa6758d7be78336684788fb0ee0fa46, getAddress(keccak256("contract.address"+name))):
--   rocketTokenRETH   0xae78736cd615f374d3085123a210448e74fc6393
--   rocketDepositPool 0xce15294273cfb9d9b628f4d61636623decdf4fdc  (same at start and end of window)
-- Event topics:
--   TokensMinted(address indexed to,uint256 amount,uint256 ethAmount,uint256 time)  0x6155cfd0fd028b0ca77e8495a60cbe563e8bce8611f0aad6fedbdaafc05d44a2
--   DepositReceived(address indexed from,uint256 amount,uint256 time)               0x7aa1a8eb998c779420645fc14513bf058edb347d95c2fc2e6845bdc22f888631
--   CreditWithdrawn(address indexed node,uint256 amount,uint256 time)               0x77982616940619ddbda4afe3675280fff7c605d31503336add3633fbea69d8ba
--     (Saturn 1: a node operator takes ETH credit as rETH via withdrawCredit(); mints rETH but adds no new ETH)

WITH params AS (
  SELECT TIMESTAMP '2026-08-22 00:00:00' AS t0, TIMESTAMP '2026-11-20 00:00:00' AS t1
),
mints AS (
  SELECT l.block_time, l.block_number, l.tx_hash, l.index AS log_index,
         varbinary_substring(l.topic1, 13, 20)                                 AS depositor,
         CAST(varbinary_to_uint256(varbinary_substring(l.data, 1, 32)) AS DOUBLE)  / 1e18      AS reth_minted,
         CAST(varbinary_to_uint256(varbinary_substring(l.data, 33, 32)) AS DOUBLE) / 1e18      AS eth_net
  FROM ethereum.logs l, params p
  WHERE l.contract_address = 0xae78736cd615f374d3085123a210448e74fc6393
    AND l.topic0 = 0x6155cfd0fd028b0ca77e8495a60cbe563e8bce8611f0aad6fedbdaafc05d44a2
    AND l.block_time >= p.t0 AND l.block_time < p.t1
),
dp_events AS (  -- the deposit-pool event emitted right after each mint in the same tx
  SELECT l.tx_hash, l.index AS log_index,
         CASE l.topic0 WHEN 0x7aa1a8eb998c779420645fc14513bf058edb347d95c2fc2e6845bdc22f888631 THEN 'deposit'
                       ELSE 'credit_withdrawal' END                              AS mint_path,
         CAST(varbinary_to_uint256(varbinary_substring(l.data, 1, 32)) AS DOUBLE) / 1e18        AS eth_gross
  FROM ethereum.logs l, params p
  WHERE l.contract_address = 0xce15294273cfb9d9b628f4d61636623decdf4fdc
    AND l.topic0 IN (0x7aa1a8eb998c779420645fc14513bf058edb347d95c2fc2e6845bdc22f888631, 0x77982616940619ddbda4afe3675280fff7c605d31503336add3633fbea69d8ba)
    AND l.block_time >= p.t0 AND l.block_time < p.t1
),
joined AS (
  SELECT m.*, e.mint_path, e.eth_gross,
         ROW_NUMBER() OVER (PARTITION BY m.tx_hash, m.log_index ORDER BY e.log_index) AS rn
  FROM mints m
  LEFT JOIN dp_events e ON e.tx_hash = m.tx_hash AND e.log_index > m.log_index
),
classified AS (
  SELECT j.block_time, j.tx_hash, j.depositor, j.reth_minted, j.eth_net,
         COALESCE(j.eth_gross, j.eth_net) AS eth_gross, COALESCE(j.mint_path, 'unmatched') AS mint_path,
         t."from" AS tx_from, t.to AS tx_to,
         CASE
           WHEN j.mint_path = 'credit_withdrawal'                       THEN 'Node operator credit withdrawal (no new ETH)'
           WHEN t.to = 0xce15294273cfb9d9b628f4d61636623decdf4fdc        THEN 'Direct deposit (EOA -> deposit pool)'
           WHEN t.to = 0x16d5a408e807db8ef7c578279beeee6b228f1c1c        THEN 'Rocket Pool swap router'
           WHEN t.to IN (0x9008d19f58aabd9ed0d60971565aa8510560ab41,   -- CoW Protocol: GPv2Settlement (Etherscan tag)
                         0x6131b5fae19ea4f9d964eac0408e4408b66337b5)   -- KyberSwap: Meta Aggregation Router v2 (Etherscan tag)
                                                                       THEN 'DEX aggregator / router'
           WHEN t.to = 0x1f6692e78dde07ff8da75769b6d7c716215bc7d0        THEN 'Wallet staking feature (MetaMask)'  -- Etherscan tag "MetaMask: Third Party Staking"
           WHEN t.to IN (0x5ff137d4b0fdcd49dca30c7cf57e578a026d2789,   -- ERC-4337 Entry Point 0.6.0
                         0x0000000071727de22e5e9d8baf0edac6f37da032)   -- ERC-4337 Entry Point 0.7.0
                OR s.address IS NOT NULL                               -- Safe (Dune spellbook safe_ethereum.safes)
                                                                       THEN 'Smart wallet (Safe / ERC-4337 / EIP-7702)'
           -- Add newly found aggregators/vaults here; EIP-7702 self-calls (t.to = t."from") also count as smart wallet:
           WHEN t.to = t."from"                                        THEN 'Smart wallet (Safe / ERC-4337 / EIP-7702)'
           WHEN COALESCE(l.name, '') <> ''                             THEN 'Labelled contract: ' || l.name
           ELSE 'Unlabelled contract'
         END AS entry_point
  FROM joined j
  JOIN ethereum.transactions t ON t.hash = j.tx_hash AND t.block_number = j.block_number
  LEFT JOIN safe_ethereum.safes s ON s.address = t.to
  LEFT JOIN (SELECT address, MAX(name) AS name FROM labels.addresses WHERE blockchain = 'ethereum' GROUP BY 1) l
         ON l.address = t.to
  WHERE j.rn = 1
)
-- 1) share by entry point
SELECT entry_point, COUNT(*) AS mints, SUM(eth_gross) AS eth, SUM(eth_gross) / SUM(SUM(eth_gross)) OVER () AS share_eth
FROM classified
GROUP BY 1
ORDER BY eth DESC;

-- 2) weekly trend (swap the final SELECT for this):
-- SELECT date_trunc('week', block_time) AS wk, entry_point, COUNT(*) AS mints, SUM(eth_gross) AS eth
-- FROM classified GROUP BY 1, 2 ORDER BY 1, 2;

-- 3) top 10 minting addresses (rETH recipient = TokensMinted.to):
-- SELECT depositor, COUNT(*) AS mints, SUM(eth_gross) AS eth FROM classified GROUP BY 1 ORDER BY eth DESC LIMIT 10;
