# MemeScout data quality report

- Reports (snapshots): 112
- Rows (token x snapshot): 4,598
- Unique tokens: 330
- Date range (UTC): 2026-07-03 07:35 to 2026-08-19 04:51
- Snapshots per collection day: 2026-07-03: 47, 2026-07-07: 12, 2026-07-14: 1, 2026-08-13: 27, 2026-08-18: 14, 2026-08-19: 11
- Chains: solana 4563, cex 18, base 12, ethereum 5
- Tokens DeepSeek scored at least once: 108

## Missing values (share of rows)

| column | missing |
| --- | --- |
| top10_ex1_pct | 99.5% |
| top10_pct | 99.5% |
| top20_pct | 99.5% |
| top1_pct | 99.5% |
| ai_hype | 73.8% |
| ai_risk | 73.8% |
| liquidity_usd | 22.3% |
| change_m5 | 9.2% |
| fdv | 1.2% |
| change_h1 | 0.8% |
| change_h6 | 0.7% |
| boost_total | 0.0% |
| price_usd | 0.0% |
| market_cap | 0.0% |
| volume_h24 | 0.0% |
| change_h24 | 0.0% |
| hype_score | 0.0% |

## Extreme values (kept, then log-transformed)

- change_h1: median 0.2, 99th percentile 696.0, max 525,869.0
- change_h24: median 79.9, 99th percentile 3,350.8, max 592,625.0
- volume_h24: median 450,697.4, 99th percentile 17,347,273.0, max 104,059,720.0
- market_cap: median 150,166.5, 99th percentile 376,390,093.2, max 313,663,334,330.0

- Pair age at first sighting (hours): median 6.7

## Validation

All fatal checks passed (no duplicates, positive prices, scores in 0-100).
- Warning: liquidity_usd: 22% missing
- Warning: top1_pct: 99% missing
- Warning: top10_pct: 99% missing
- Warning: top20_pct: 99% missing
- Warning: top10_ex1_pct: 99% missing
- Warning: ai_hype: 74% missing
- Warning: ai_risk: 74% missing
