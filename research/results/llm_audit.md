# DeepSeek score audit

Scored rows: 1,203 across 108 tokens.

## A1 Consistency

- Tokens scored 3+ times: 79
- Spread of risk score for the SAME token (median SD): 4.2 points (mean 4.3, worst 12.7)
- Spread BETWEEN tokens (SD of token averages): 11.3 points
- Same-day repeat scores: 91 token-days, median SD 4.3
- Risk scores used the range 30-100

## A2 What drives the risk score

An imitation model (gradient boosting, GroupKFold by token) explains R² = 0.41 of the variation in DeepSeek's risk score from market features alone.

| feature | permutation importance (mean ± sd) | Spearman correlation with risk |
| --- | --- | --- |
| log_liquidity | 0.176 ± 0.178 | -0.56 |
| pair_age_h | 0.148 ± 0.372 | -0.55 |
| slog_change_h1 | 0.089 ± 0.070 | -0.04 |
| log_mcap | 0.071 ± 0.028 | -0.64 |
| slog_change_h24 | 0.043 ± 0.044 | -0.20 |
| turnover | 0.032 ± 0.022 | +0.18 |
| log_volume | 0.028 ± 0.047 | -0.26 |
| n_sources | 0.018 ± 0.013 | +0.09 |
| slog_change_h6 | 0.012 ± 0.029 | +0.09 |
| slog_change_m5 | 0.002 ± 0.028 | -0.06 |
| has_paid_boost | -0.000 ± 0.000 | +0.05 |
| boost_total | -0.002 ± 0.008 | -0.16 |
| liq_to_mcap | -0.003 ± 0.027 | +0.51 |
| in_gecko_trending | -0.010 ± 0.192 | -0.21 |

## A3 Agreement with the heuristic

- DeepSeek hype vs heuristic hype score: Spearman ρ = 0.22 (p = 1.8e-14)
- DeepSeek risk vs DeepSeek hype: Spearman ρ = -0.41 (p = 2.8e-49)

## A4 Grounding: citing data it did not have

- Scored rows with no holder data: 1,200 (rows with holder data: 3)
- Rows where DeepSeek correctly said holder data was missing: 720 (60.0%)
- Rows where DeepSeek made a holder/whale/supply claim WITHOUT saying data was missing: 24 (2.0%)
- Examples of those claims (check each by hand: some may be reasonable, e.g. inferred from market cap): "whale risk"; "Stable price action with decent volume but still early and opaque holder distribution."

Most common red flags:

- new pair: 520
- low liquidity: 473
- no holder data: 427
- whale data missing: 189
- very low liquidity: 75
- moderate liquidity: 63
- low volume: 63
- very new pair: 62
- whale concentration unknown: 60
- low liquidity/mcap ratio: 46
