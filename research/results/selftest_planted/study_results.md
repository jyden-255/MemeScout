> **SELF-TEST (planted labels). These are FAKE outcomes used only to check the code works. Never report these numbers.**

# Study results: can an LLM spot meme coins that collapse?

Outcomes fetched: SELFTEST
Tokens with outcomes: 329 | collapsed: 184 (56%) | survived: 145
Label: no pair left, OR liquidity < $1,000, OR price < 10% of first-seen price.

## E1: All tokens

| Predictor | n | ROC-AUC | 95% CI | PR-AUC | SD across CV repeats |
| --- | --- | --- | --- | --- | --- |
| No-skill baseline | 329 | 0.500 | 0.500–0.500 | 0.559 |  |
| Rule: low liquidity | 329 | 0.679 | 0.621–0.742 | 0.648 |  |
| Rule: newest pair | 329 | 0.645 | 0.580–0.705 | 0.663 |  |
| Heuristic hype score | 329 | 0.551 | 0.487–0.612 | 0.582 |  |
| Logistic regression | 329 | 0.721 | 0.665–0.774 | 0.752 | 0.008 |
| Gradient boosting | 329 | 0.702 | 0.643–0.755 | 0.747 | 0.015 |

## E2: Head-to-head on the tokens DeepSeek scored

Same 108 tokens for every predictor, so the comparison is fair.

| Predictor | n | ROC-AUC | 95% CI | PR-AUC | SD across CV repeats |
| --- | --- | --- | --- | --- | --- |
| No-skill baseline | 108 | 0.500 | 0.500–0.500 | 0.602 |  |
| Rule: low liquidity | 108 | 0.757 | 0.653–0.850 | 0.760 |  |
| Rule: newest pair | 108 | 0.673 | 0.557–0.779 | 0.727 |  |
| Heuristic hype score | 108 | 0.473 | 0.353–0.583 | 0.578 |  |
| Logistic regression | 108 | 0.756 | 0.652–0.846 | 0.802 | 0.009 |
| Gradient boosting | 108 | 0.650 | 0.535–0.746 | 0.718 | 0.019 |
| DeepSeek risk score | 108 | 0.705 | 0.601–0.806 | 0.733 |  |

- Gradient boosting minus DeepSeek, ROC-AUC difference: -0.054 (95% CI -0.165 to +0.056; better in 17% of bootstrap samples)
- Logistic regression minus DeepSeek, ROC-AUC difference: +0.052 (95% CI -0.042 to +0.148; better in 86% of bootstrap samples)
- Rule: low liquidity minus DeepSeek, ROC-AUC difference: +0.052 (95% CI -0.029 to +0.137; better in 90% of bootstrap samples)

If a confidence interval includes 0, you cannot claim one is better.

## E3: Leakage demonstration (all snapshot rows)

Using every snapshot row (4,580 rows), the same coin appears many times.
- Random row split (LEAKY: same coin in train and test): ROC-AUC 0.990 ± 0.002
- Grouped split by token (honest): ROC-AUC 0.714 ± 0.065
The gap is how much a careless split would have overstated the model.

## E4: Train on July tokens, test on August tokens

Train 164 tokens, test 165 tokens.

- Logistic regression: ROC-AUC 0.677
- Gradient boosting: ROC-AUC 0.664
- Rule: low liquidity: ROC-AUC 0.632
- Heuristic hype score: ROC-AUC 0.578

## E5: What the gradient boosting model relies on

Permutation importance on held-out folds (drop in ROC-AUC when a feature is shuffled).

| feature | importance |
| --- | --- |
| log_liquidity | +0.154 ± 0.023 |
| log_mcap | +0.030 ± 0.029 |
| liq_to_mcap | +0.005 ± 0.014 |
| log_volume | +0.003 ± 0.012 |
| turnover | +0.002 ± 0.014 |
| in_gecko_trending | -0.000 ± 0.001 |
| n_sources | -0.001 ± 0.001 |
| has_paid_boost | -0.002 ± 0.003 |
| slog_change_h24 | -0.005 ± 0.009 |
| boost_total | -0.005 ± 0.015 |
| slog_change_h1 | -0.007 ± 0.014 |
| slog_change_h6 | -0.010 ± 0.030 |
| pair_age_h | -0.018 ± 0.021 |
| slog_change_m5 | -0.023 ± 0.019 |
