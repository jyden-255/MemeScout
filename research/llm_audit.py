"""Audit DeepSeek's scores: can we trust the LLM as a risk analyst?

This needs no outcome data. It asks four questions of the scores DeepSeek
already produced:

  A1 Consistency  - does the same coin get a similar risk score each time?
  A2 Drivers      - which market features explain DeepSeek's risk score?
                    (we train a model to imitate the LLM, then explain it)
  A3 Agreement    - does DeepSeek's hype score agree with the simple
                    heuristic hype score?
  A4 Grounding    - the prompt tells DeepSeek to weigh holder concentration,
                    but that data is almost always missing. Does DeepSeek
                    still cite holder/whale problems it cannot have seen?

Run:  python -m research.llm_audit
"""
from __future__ import annotations

import os
import re

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from scipy.stats import spearmanr
from sklearn.ensemble import HistGradientBoostingRegressor
from sklearn.inspection import permutation_importance
from sklearn.model_selection import GroupKFold

from .data import FEATURES, add_features, load_reports

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "results")
SEED = 42

HOLDER_WORDS = re.compile(r"holder|whale|concentrat|top ?10|top ?1\b|supply", re.I)
MISSING_WORDS = re.compile(r"\bno\b|missing|unknown|unavailable|n/?a\b|lack|not (?:available|provided)|absent", re.I)


def consistency(scored: pd.DataFrame) -> dict:
    """Compare variation WITHIN a token (same coin, different snapshots)
    against variation BETWEEN tokens. If the LLM is consistent, within-token
    spread should be much smaller than between-token spread."""
    g = scored.groupby("address")["ai_risk"]
    multi = g.filter(lambda s: len(s) >= 3)
    within = scored[scored["address"].isin(multi.index.map(scored["address"]))]
    within_sd = within.groupby("address")["ai_risk"].std(ddof=0)
    token_means = scored.groupby("address")["ai_risk"].mean()
    # Same-day check: market data moves between days, so also look at
    # repeat scores taken on the same calendar day.
    s = scored.copy()
    s["day"] = s["snapshot_utc"].dt.date
    same_day = s.groupby(["address", "day"])["ai_risk"].agg(["std", "count"])
    same_day = same_day[same_day["count"] >= 2]
    return {
        "tokens_scored_3plus": int(within_sd.size),
        "median_within_token_sd": float(within_sd.median()),
        "mean_within_token_sd": float(within_sd.mean()),
        "max_within_token_sd": float(within_sd.max()),
        "between_token_sd": float(token_means.std(ddof=0)),
        "same_day_pairs": int(len(same_day)),
        "same_day_median_sd": float(same_day["std"].median()) if len(same_day) else float("nan"),
        "risk_range": (int(scored["ai_risk"].min()), int(scored["ai_risk"].max())),
    }


def drivers(scored: pd.DataFrame) -> tuple[pd.DataFrame, float, pd.Series]:
    """Train a model to predict DeepSeek's risk score from the market
    features it was shown, using GroupKFold so the same coin is never in
    both train and test. Then use permutation importance on held-out folds
    to see which features the imitation model (and so the LLM) relies on."""
    X = scored[FEATURES]
    y = scored["ai_risk"]
    groups = scored["address"]
    gkf = GroupKFold(n_splits=5)
    r2s, imps = [], []
    for tr, te in gkf.split(X, y, groups):
        m = HistGradientBoostingRegressor(max_iter=200, learning_rate=0.05,
                                          max_leaf_nodes=15, random_state=SEED)
        m.fit(X.iloc[tr], y.iloc[tr])
        r2s.append(m.score(X.iloc[te], y.iloc[te]))
        pi = permutation_importance(m, X.iloc[te], y.iloc[te], n_repeats=10,
                                    random_state=SEED, scoring="r2")
        imps.append(pi.importances_mean)
    imp = pd.DataFrame(imps, columns=FEATURES)
    summary = pd.DataFrame({"importance_mean": imp.mean(), "importance_sd": imp.std()})
    summary = summary.sort_values("importance_mean", ascending=False)
    corr = pd.Series({f: spearmanr(scored[f], y, nan_policy="omit").statistic
                      for f in FEATURES}).sort_values()
    return summary, float(np.mean(r2s)), corr


def grounding(scored: pd.DataFrame) -> dict:
    """Count risk flags that mention holders/whales/concentration on rows
    where DeepSeek was given NO holder data at all."""
    no_holder = scored[scored["top10_pct"].isna() & scored["top1_pct"].isna()]
    flags = no_holder["ai_flags"].apply(lambda fl: fl if isinstance(fl, list) else [])
    theses = no_holder["ai_thesis"].fillna("")

    def acknowledges(text: str) -> bool:
        # "no holder data", "whale data missing", "concentration unknown"
        return bool(HOLDER_WORDS.search(text)) and bool(MISSING_WORDS.search(text))

    def claims(text: str) -> bool:
        # mentions holders but does NOT say the data is missing,
        # e.g. "high whale concentration": a claim it had no data for
        return bool(HOLDER_WORDS.search(text)) and not MISSING_WORDS.search(text)

    ack = flags.apply(lambda fl: any(acknowledges(x) for x in fl)) | theses.apply(acknowledges)
    claim_flags = flags.apply(lambda fl: [x for x in fl if claims(x)])
    claim_thesis = theses.apply(claims)
    claimed = claim_flags.apply(bool) | claim_thesis
    examples = []
    for fl, th in zip(claim_flags[claimed], theses[claimed]):
        examples.append(fl[0] if fl else th)
    all_flags = pd.Series([x.lower() for fl in scored["ai_flags"].dropna() for x in fl])
    n = len(no_holder)
    return {
        "rows_without_holder_data": int(n),
        "rows_with_holder_data": int(len(scored) - n),
        "rows_acknowledging_missing": int(ack.sum()),
        "share_acknowledging_missing": float(ack.mean()) if n else 0.0,
        "rows_claiming_anyway": int(claimed.sum()),
        "share_claiming_anyway": float(claimed.mean()) if n else 0.0,
        "examples": list(dict.fromkeys(examples))[:6],
        "top_flags": all_flags.value_counts().head(10),
    }


def main() -> None:
    os.makedirs(OUT, exist_ok=True)
    df = add_features(load_reports())
    scored = df[df["ai_risk"].notna()].copy()

    c = consistency(scored)
    imp, r2, corr = drivers(scored)
    rho_hype, p_hype = spearmanr(scored["ai_hype"], scored["hype_score"])
    rho_rh, p_rh = spearmanr(scored["ai_risk"], scored["ai_hype"])
    g = grounding(scored)

    # Figure: what DeepSeek's risk score depends on
    fig, ax = plt.subplots(figsize=(7, 4.5))
    top = imp.head(8)[::-1]
    ax.barh(top.index, top["importance_mean"], xerr=top["importance_sd"],
            color="#3b6ea5", ecolor="#555")
    ax.set_xlabel("Drop in R² when the feature is shuffled (held-out folds)")
    ax.set_title("What DeepSeek's risk score depends on")
    fig.tight_layout()
    fig.savefig(os.path.join(OUT, "llm_risk_drivers.png"), dpi=150)
    plt.close(fig)

    L = ["# DeepSeek score audit", "",
         f"Scored rows: {len(scored):,} across {scored['address'].nunique()} tokens.", "",
         "## A1 Consistency", "",
         f"- Tokens scored 3+ times: {c['tokens_scored_3plus']}",
         f"- Spread of risk score for the SAME token (median SD): {c['median_within_token_sd']:.1f} points "
         f"(mean {c['mean_within_token_sd']:.1f}, worst {c['max_within_token_sd']:.1f})",
         f"- Spread BETWEEN tokens (SD of token averages): {c['between_token_sd']:.1f} points",
         f"- Same-day repeat scores: {c['same_day_pairs']} token-days, median SD {c['same_day_median_sd']:.1f}",
         f"- Risk scores used the range {c['risk_range'][0]}-{c['risk_range'][1]}", "",
         "## A2 What drives the risk score", "",
         f"An imitation model (gradient boosting, GroupKFold by token) explains "
         f"R² = {r2:.2f} of the variation in DeepSeek's risk score from market features alone.", "",
         "| feature | permutation importance (mean ± sd) | Spearman correlation with risk |",
         "| --- | --- | --- |"]
    for f, row in imp.iterrows():
        L.append(f"| {f} | {row.importance_mean:.3f} ± {row.importance_sd:.3f} | {corr[f]:+.2f} |")
    L += ["", "## A3 Agreement with the heuristic", "",
          f"- DeepSeek hype vs heuristic hype score: Spearman ρ = {rho_hype:.2f} (p = {p_hype:.2g})",
          f"- DeepSeek risk vs DeepSeek hype: Spearman ρ = {rho_rh:.2f} (p = {p_rh:.2g})", "",
          "## A4 Grounding: citing data it did not have", "",
          f"- Scored rows with no holder data: {g['rows_without_holder_data']:,} "
          f"(rows with holder data: {g['rows_with_holder_data']})",
          f"- Rows where DeepSeek correctly said holder data was missing: "
          f"{g['rows_acknowledging_missing']} ({g['share_acknowledging_missing']:.1%})",
          f"- Rows where DeepSeek made a holder/whale/supply claim WITHOUT saying data was missing: "
          f"{g['rows_claiming_anyway']} ({g['share_claiming_anyway']:.1%})"]
    if g["examples"]:
        L.append("- Examples of those claims (check each by hand: some may be reasonable, "
                 "e.g. inferred from market cap): " + "; ".join(f'"{e}"' for e in g["examples"]))
    L += ["", "Most common red flags:", ""]
    for flag, n in g["top_flags"].items():
        L.append(f"- {flag}: {n}")
    text = "\n".join(L) + "\n"
    with open(os.path.join(OUT, "llm_audit.md"), "w") as fh:
        fh.write(text)
    print(text)
    print("Saved results/llm_audit.md and results/llm_risk_drivers.png")


if __name__ == "__main__":
    main()
