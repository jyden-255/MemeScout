# Can an LLM spot meme coins that collapse?

A small study on MemeScout's own data. MemeScout saved 113 timestamped reports (112 with data) between 3 July and 19 August 2026: 4,598 token-snapshot records covering 330 tokens. DeepSeek scored 108 of those tokens for "rug/dump risk". This study checks whether those scores were any good.

## Questions

1. **Is the LLM a consistent, grounded judge?** (`llm_audit.py`, no outcome data needed)
2. **Does DeepSeek's risk score predict which tokens actually collapsed**, and does it beat simple rules and models trained on the same market data? (`evaluate.py`, needs outcomes)

## How to run

```bash
pip install -r research/requirements.txt

python -m research.data                     # load + validate reports -> results/data_quality.md
python -m research.llm_audit                # consistency/drivers/grounding -> results/llm_audit.md
python -m research.evaluate --selftest random    # sanity check: should be ~0.5 everywhere
python -m research.evaluate --selftest planted   # sanity check: should find log_liquidity
python -m research.fetch_outcomes           # needs internet: what happened to each token
python -m research.evaluate                 # the real study -> results/study_results.md
```

## Method

- **Unit of analysis = token**, using its first sighting. The same coin appears in many snapshots, so splitting by row would leak (experiment E3 measures how much).
- **Label:** a token "collapsed" if, when outcomes were fetched, it had no trading pair, under $1,000 of liquidity, or a price below 10% of its first-seen price.
- **Predictors compared:** no-skill baseline, two one-line rules (low liquidity, newest pair), MemeScout's heuristic hype score, DeepSeek's risk score, logistic regression, gradient boosting.
- **Evaluation:** repeated stratified 5-fold cross-validation (5 seeds), ROC-AUC and PR-AUC, 95% bootstrap confidence intervals, and a paired bootstrap for model-vs-DeepSeek differences. E4 trains on July and tests on August.
- **Explainability:** permutation importance on held-out folds for the trained model, and an "imitation model" that explains what DeepSeek's scores depend on.

## Findings so far (from `llm_audit.py` on the real data)

- **Consistency:** the same token's risk score varies by a median of about 4 points across snapshots, compared with about 11 points between tokens, so DeepSeek is fairly stable. Scores only ever used 30–100.
- **What drives it:** market features alone explain about 40% of the variation in DeepSeek's risk score (R² ≈ 0.41, grouped CV). Liquidity, pair age and market cap matter most: thinner, newer and smaller coins get higher risk.
- **Agreement:** DeepSeek's hype score only weakly agrees with the heuristic hype score (Spearman ρ ≈ 0.22).
- **Grounding:** holder data was missing for 1,200 of 1,203 scored rows. DeepSeek said so in about 60% of cases, and made a holder/whale claim without data in about 2%.

Outcome-based results (does the risk score predict collapse?) are written to `results/study_results.md` after you run `fetch_outcomes`.

## Limitations

- Only 108 tokens have DeepSeek scores, so confidence intervals are wide.
- Outcomes are measured at a single later date (whenever `fetch_outcomes` runs), not at a fixed horizon after each sighting.
- MemeScout only sees coins that are already trending, so this says nothing about meme coins in general.
- Holder-concentration data is almost entirely missing, so the risk factor the prompt emphasises most could not be tested.
- Many comparisons are made, so one "significant" difference can appear by chance (the random-label self-test shows exactly this).
