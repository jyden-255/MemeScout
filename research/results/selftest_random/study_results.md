> **SELF-TEST (random labels). These are FAKE outcomes used only to check the code works. Never report these numbers.**

# Study results: can an LLM spot meme coins that collapse?

Outcomes fetched: SELFTEST
Tokens with outcomes: 329 | collapsed: 189 (57%) | survived: 140
Label: no pair left, OR liquidity < $1,000, OR price < 10% of first-seen price.

## E1: All tokens

| Predictor | n | ROC-AUC | 95% CI | PR-AUC | SD across CV repeats |
| --- | --- | --- | --- | --- | --- |
| No-skill baseline | 329 | 0.500 | 0.500–0.500 | 0.574 |  |
| Rule: low liquidity | 329 | 0.521 | 0.459–0.584 | 0.588 |  |
| Rule: newest pair | 329 | 0.548 | 0.485–0.611 | 0.603 |  |
| Heuristic hype score | 329 | 0.547 | 0.485–0.613 | 0.620 |  |
| Logistic regression | 329 | 0.456 | 0.392–0.521 | 0.541 | 0.027 |
| Gradient boosting | 329 | 0.464 | 0.400–0.526 | 0.569 | 0.016 |

## E2: Head-to-head on the tokens DeepSeek scored

Same 108 tokens for every predictor, so the comparison is fair.

| Predictor | n | ROC-AUC | 95% CI | PR-AUC | SD across CV repeats |
| --- | --- | --- | --- | --- | --- |
| No-skill baseline | 108 | 0.500 | 0.500–0.500 | 0.639 |  |
| Rule: low liquidity | 108 | 0.479 | 0.368–0.590 | 0.638 |  |
| Rule: newest pair | 108 | 0.546 | 0.429–0.664 | 0.659 |  |
| Heuristic hype score | 108 | 0.479 | 0.367–0.588 | 0.657 |  |
| Logistic regression | 108 | 0.447 | 0.339–0.565 | 0.631 | 0.045 |
| Gradient boosting | 108 | 0.392 | 0.281–0.507 | 0.585 | 0.041 |
| DeepSeek risk score | 108 | 0.575 | 0.450–0.685 | 0.682 |  |

- Gradient boosting minus DeepSeek, ROC-AUC difference: -0.184 (95% CI -0.324 to -0.039; better in 1% of bootstrap samples)
- Logistic regression minus DeepSeek, ROC-AUC difference: -0.129 (95% CI -0.280 to +0.016; better in 4% of bootstrap samples)
- Rule: low liquidity minus DeepSeek, ROC-AUC difference: -0.096 (95% CI -0.189 to -0.007; better in 2% of bootstrap samples)

If a confidence interval includes 0, you cannot claim one is better.

## E3: Leakage demonstration (all snapshot rows)

Using every snapshot row (4,580 rows), the same coin appears many times.
- Random row split (LEAKY: same coin in train and test): ROC-AUC 0.986 ± 0.004
- Grouped split by token (honest): ROC-AUC 0.434 ± 0.034
The gap is how much a careless split would have overstated the model.

## E4: Train on July tokens, test on August tokens

Train 164 tokens, test 165 tokens.

- Logistic regression: ROC-AUC 0.476
- Gradient boosting: ROC-AUC 0.430
- Rule: low liquidity: ROC-AUC 0.494
- Heuristic hype score: ROC-AUC 0.547

## E5: What the gradient boosting model relies on

Permutation importance on held-out folds (drop in ROC-AUC when a feature is shuffled).

| feature | importance |
| --- | --- |
| log_mcap | +0.019 ± 0.013 |
| boost_total | +0.006 ± 0.011 |
| slog_change_h1 | +0.001 ± 0.037 |
| has_paid_boost | -0.000 ± 0.002 |
| in_gecko_trending | -0.001 ± 0.001 |
| turnover | -0.003 ± 0.016 |
| n_sources | -0.004 ± 0.005 |
| slog_change_m5 | -0.004 ± 0.030 |
| log_liquidity | -0.004 ± 0.019 |
| slog_change_h6 | -0.006 ± 0.012 |
| log_volume | -0.007 ± 0.027 |
| slog_change_h24 | -0.011 ± 0.024 |
| pair_age_h | -0.015 ± 0.018 |
| liq_to_mcap | -0.015 ± 0.048 |
