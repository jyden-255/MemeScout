"""Main study: can an LLM spot meme coins that collapse?

Compares several ways of predicting whether a token collapsed after
MemeScout first saw it:

  - No-skill baseline (always predict the base rate)
  - Simple rules: "low liquidity is risky", "brand-new pair is risky"
  - MemeScout's heuristic hype score
  - DeepSeek's risk score (only on the 108 tokens DeepSeek scored)
  - Logistic regression trained on market features
  - Gradient boosting trained on market features

Experiment design (be ready to explain every line of this):
  * One row per TOKEN (its first sighting), so no coin is in both train and
    test. Experiment E3 shows what goes wrong if you ignore this.
  * Repeated stratified 5-fold cross-validation (5 repeats, fixed seeds):
    every token gets an out-of-fold prediction from a model that never saw
    it. Results are reported as mean +/- SD across repeats.
  * 95% bootstrap confidence intervals for every predictor, plus a paired
    bootstrap for "is model X really better than DeepSeek?".
  * ROC-AUC (ranking quality) AND PR-AUC (better when classes are uneven).
  * E4 trains only on July tokens and tests on August tokens, to check the
    model still works on a later period (markets drift).

Usage:
    python -m research.evaluate                   # needs research/outcomes.csv
    python -m research.evaluate --selftest random # sanity check: labels are coin flips
    python -m research.evaluate --selftest planted  # sanity check: a known signal is planted
"""
from __future__ import annotations

import argparse
import os

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from sklearn.base import clone
from sklearn.ensemble import HistGradientBoostingClassifier
from sklearn.impute import SimpleImputer
from sklearn.inspection import permutation_importance
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import average_precision_score, roc_auc_score
from sklearn.model_selection import GroupKFold, KFold, StratifiedKFold
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler

from .data import FEATURES, add_features, first_scored, first_sightings, load_reports

HERE = os.path.dirname(os.path.abspath(__file__))
OUTCOMES = os.path.join(HERE, "outcomes.csv")

# Label definition. A token "collapsed" if, when outcomes were fetched:
#   - it has no trading pair on DexScreener any more, OR
#   - its best pool has under $1,000 liquidity (effectively untradeable), OR
#   - its price is below 10% of the price when MemeScout first saw it.
DEAD_LIQUIDITY_USD = 1_000
DEAD_PRICE_RATIO = 0.10

SEEDS = [0, 1, 2, 3, 4]
N_SPLITS = 5
N_BOOT = 2000


# ----------------------------------------------------------------- data ---

def build_dataset(outcomes: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    rows = add_features(load_reports())
    tokens = first_sightings(rows)
    o = outcomes[~outcomes["fetch_failed"].astype(bool)]
    d = tokens.merge(o, on=["chain", "address"], how="inner")
    ratio = d["price_now"] / d["price_usd"]
    d["price_ratio"] = ratio
    d["collapsed"] = ((~d["found"].astype(bool))
                      | (d["liquidity_now"].fillna(0) < DEAD_LIQUIDITY_USD)
                      | (ratio < DEAD_PRICE_RATIO)).astype(int)
    # DeepSeek's first risk score for each token (NaN if never scored)
    ds = first_scored(rows)[["chain", "address", "ai_risk", "ai_hype"]]
    d = d.drop(columns=["ai_risk", "ai_hype"]).merge(ds, on=["chain", "address"], how="left")
    labelled_rows = rows.merge(d[["chain", "address", "collapsed"]], on=["chain", "address"])
    return d.reset_index(drop=True), labelled_rows


def synthetic_outcomes(mode: str, seed: int = 7) -> pd.DataFrame:
    """Fake outcomes for SELF-TESTS ONLY. Never report these as results."""
    rng = np.random.default_rng(seed)
    t = add_features(first_sightings(load_reports()))
    t = t[t["chain"] != "cex"]
    if mode == "random":
        dead = rng.random(len(t)) < 0.6
    else:  # planted: low liquidity truly causes collapse, plus noise
        z = -(t["log_liquidity"].fillna(t["log_liquidity"].median()) - t["log_liquidity"].median())
        p = 1 / (1 + np.exp(-(0.4 + 4.0 * z)))
        dead = rng.random(len(t)) < p
    return pd.DataFrame({
        "chain": t["chain"], "address": t["address"], "fetched_at_utc": "SELFTEST",
        "found": ~dead, "fetch_failed": False,
        "price_now": t["price_usd"].values, "liquidity_now": np.where(dead, 0.0, 50_000.0),
        "volume_h24_now": np.nan, "market_cap_now": np.nan})


# --------------------------------------------------------------- models ---

def models() -> dict:
    return {
        "Logistic regression": make_pipeline(
            SimpleImputer(strategy="median", add_indicator=True),
            StandardScaler(),
            LogisticRegression(C=1.0, class_weight="balanced", max_iter=2000)),
        "Gradient boosting": HistGradientBoostingClassifier(
            max_iter=200, learning_rate=0.05, max_leaf_nodes=15,
            min_samples_leaf=10, class_weight="balanced", random_state=0),
    }


def rule_scores(d: pd.DataFrame) -> dict:
    """Fixed scoring rules: higher score = more likely to collapse."""
    liq = d["log_liquidity"].fillna(d["log_liquidity"].min())  # unknown liquidity treated as worst case
    age = d["pair_age_h"].fillna(d["pair_age_h"].median())
    return {
        "Rule: low liquidity": -liq.values,
        "Rule: newest pair": -age.values,
        "Heuristic hype score": d["hype_score"].values,
    }


def oof_predictions(model, X: pd.DataFrame, y: np.ndarray, seed: int) -> np.ndarray:
    pred = np.zeros(len(y))
    skf = StratifiedKFold(n_splits=N_SPLITS, shuffle=True, random_state=seed)
    for tr, te in skf.split(X, y):
        m = clone(model)
        if hasattr(m, "random_state"):
            m.set_params(random_state=seed)
        m.fit(X.iloc[tr], y[tr])
        pred[te] = m.predict_proba(X.iloc[te])[:, 1]
    return pred


# -------------------------------------------------------------- metrics ---

def bootstrap_ci(y, s, metric, rng, n=N_BOOT):
    vals = []
    idx = np.arange(len(y))
    for _ in range(n):
        b = rng.choice(idx, len(idx), replace=True)
        if y[b].min() == y[b].max():
            continue
        vals.append(metric(y[b], s[b]))
    return np.percentile(vals, [2.5, 97.5])


def paired_diff(y, s1, s2, rng, n=N_BOOT):
    """Bootstrap the AUC difference s1 - s2 on the same resampled tokens."""
    diffs = []
    idx = np.arange(len(y))
    for _ in range(n):
        b = rng.choice(idx, len(idx), replace=True)
        if y[b].min() == y[b].max():
            continue
        diffs.append(roc_auc_score(y[b], s1[b]) - roc_auc_score(y[b], s2[b]))
    diffs = np.array(diffs)
    return diffs.mean(), np.percentile(diffs, [2.5, 97.5]), (diffs > 0).mean()


def score_table(y, scores: dict, per_repeat: dict, rng) -> pd.DataFrame:
    out = []
    for name, s in scores.items():
        ok = ~np.isnan(s)
        yy, ss = y[ok], s[ok]
        auc = roc_auc_score(yy, ss)
        ap = average_precision_score(yy, ss)
        lo, hi = bootstrap_ci(yy, ss, roc_auc_score, rng)
        row = {"predictor": name, "n": int(ok.sum()), "roc_auc": auc,
               "auc_ci_low": lo, "auc_ci_high": hi, "pr_auc": ap}
        if name in per_repeat:
            reps = [roc_auc_score(yy, r[ok]) for r in per_repeat[name]]
            row["auc_repeat_sd"] = float(np.std(reps))
        out.append(row)
    base = y.mean()
    out.insert(0, {"predictor": "No-skill baseline", "n": len(y), "roc_auc": 0.5,
                   "auc_ci_low": 0.5, "auc_ci_high": 0.5, "pr_auc": base})
    return pd.DataFrame(out)


# ---------------------------------------------------------- experiments ---

def run(outcomes: pd.DataFrame, out_dir: str, banner: str = "") -> str:
    os.makedirs(out_dir, exist_ok=True)
    rng = np.random.default_rng(12345)
    d, labelled_rows = build_dataset(outcomes)
    y = d["collapsed"].values
    X = d[FEATURES]
    L = []
    if banner:
        L += [f"> **{banner}**", ""]
    L += ["# Study results: can an LLM spot meme coins that collapse?", "",
          f"Outcomes fetched: {outcomes['fetched_at_utc'].iloc[0]}",
          f"Tokens with outcomes: {len(d)} | collapsed: {y.sum()} ({y.mean():.0%}) | "
          f"survived: {(1 - y).sum()}",
          f"Label: no pair left, OR liquidity < ${DEAD_LIQUIDITY_USD:,}, OR price < "
          f"{DEAD_PRICE_RATIO:.0%} of first-seen price.", ""]
    if min(y.sum(), (1 - y).sum()) < 15:
        L += ["**Warning: fewer than 15 tokens in one class. Treat every number below as "
              "very uncertain.**", ""]

    # E1/E2: all predictors, out-of-fold
    per_repeat = {name: [oof_predictions(m, X, y, s) for s in SEEDS]
                  for name, m in models().items()}
    scores = rule_scores(d)
    for name, reps in per_repeat.items():
        scores[name] = np.mean(reps, axis=0)
    scores["DeepSeek risk score"] = d["ai_risk"].values.astype(float)

    full = {k: v for k, v in scores.items() if k != "DeepSeek risk score"}
    t1 = score_table(y, full, per_repeat, rng)
    L += ["## E1: All tokens", "", _md(t1), ""]

    sub = ~np.isnan(scores["DeepSeek risk score"])
    t2 = score_table(y[sub], {k: v[sub] for k, v in scores.items()},
                     {k: [r[sub] for r in v] for k, v in per_repeat.items()}, rng)
    L += ["## E2: Head-to-head on the tokens DeepSeek scored", "",
          f"Same {sub.sum()} tokens for every predictor, so the comparison is fair.", "",
          _md(t2), ""]
    if y[sub].min() != y[sub].max():
        for name in ["Gradient boosting", "Logistic regression", "Rule: low liquidity"]:
            mean, (lo, hi), p = paired_diff(y[sub], scores[name][sub],
                                            scores["DeepSeek risk score"][sub], rng)
            L.append(f"- {name} minus DeepSeek, ROC-AUC difference: {mean:+.3f} "
                     f"(95% CI {lo:+.3f} to {hi:+.3f}; better in {p:.0%} of bootstrap samples)")
        L += ["", "If a confidence interval includes 0, you cannot claim one is better.", ""]

    # E3: leakage demonstration
    Xr, yr, gr = labelled_rows[FEATURES], labelled_rows["collapsed"].values, labelled_rows["address"].values
    gb = models()["Gradient boosting"]
    leak, honest = [], []
    for tr, te in KFold(5, shuffle=True, random_state=0).split(Xr):
        m = clone(gb).fit(Xr.iloc[tr], yr[tr])
        leak.append(roc_auc_score(yr[te], m.predict_proba(Xr.iloc[te])[:, 1]))
    for tr, te in GroupKFold(5).split(Xr, yr, gr):
        m = clone(gb).fit(Xr.iloc[tr], yr[tr])
        honest.append(roc_auc_score(yr[te], m.predict_proba(Xr.iloc[te])[:, 1]))
    L += ["## E3: Leakage demonstration (all snapshot rows)", "",
          f"Using every snapshot row ({len(yr):,} rows), the same coin appears many times.",
          f"- Random row split (LEAKY: same coin in train and test): ROC-AUC {np.mean(leak):.3f} ± {np.std(leak):.3f}",
          f"- Grouped split by token (honest): ROC-AUC {np.mean(honest):.3f} ± {np.std(honest):.3f}",
          "The gap is how much a careless split would have overstated the model.", ""]

    # E4: temporal generalisation
    month = d["snapshot_utc"].dt.month
    tr, te = (month == 7).values, (month == 8).values
    if tr.sum() > 20 and te.sum() > 20 and y[tr].min() != y[tr].max() and y[te].min() != y[te].max():
        L += ["## E4: Train on July tokens, test on August tokens", "",
              f"Train {tr.sum()} tokens, test {te.sum()} tokens.", ""]
        for name, m in models().items():
            mm = clone(m).fit(X[tr], y[tr])
            L.append(f"- {name}: ROC-AUC {roc_auc_score(y[te], mm.predict_proba(X[te])[:, 1]):.3f}")
        rs = rule_scores(d)
        for name in ["Rule: low liquidity", "Heuristic hype score"]:
            L.append(f"- {name}: ROC-AUC {roc_auc_score(y[te], rs[name][te]):.3f}")
        L.append("")

    # E5: permutation importance for gradient boosting (held-out folds)
    imps = []
    for tr_i, te_i in StratifiedKFold(5, shuffle=True, random_state=0).split(X, y):
        m = clone(gb).fit(X.iloc[tr_i], y[tr_i])
        pi = permutation_importance(m, X.iloc[te_i], y[te_i], scoring="roc_auc",
                                    n_repeats=10, random_state=0)
        imps.append(pi.importances_mean)
    imp = pd.DataFrame(imps, columns=FEATURES)
    imp = pd.DataFrame({"mean": imp.mean(), "sd": imp.std()}).sort_values("mean", ascending=False)
    L += ["## E5: What the gradient boosting model relies on", "",
          "Permutation importance on held-out folds (drop in ROC-AUC when a feature is shuffled).", "",
          "| feature | importance |", "| --- | --- |"]
    L += [f"| {f} | {r['mean']:+.3f} ± {r['sd']:.3f} |" for f, r in imp.iterrows()]

    _plots(t2 if sub.sum() >= 20 else t1, imp, out_dir)
    text = "\n".join(L) + "\n"
    with open(os.path.join(out_dir, "study_results.md"), "w") as fh:
        fh.write(text)
    return text


def _md(t: pd.DataFrame) -> str:
    cols = ["predictor", "n", "roc_auc", "auc_ci_low", "auc_ci_high", "pr_auc"]
    if "auc_repeat_sd" in t:
        cols.append("auc_repeat_sd")
    t = t[cols].copy()
    head = "| Predictor | n | ROC-AUC | 95% CI | PR-AUC | SD across CV repeats |"
    lines = [head, "| --- | --- | --- | --- | --- | --- |"]
    for _, r in t.iterrows():
        sd = r.get("auc_repeat_sd")
        sd_s = f"{sd:.3f}" if isinstance(sd, float) and not np.isnan(sd) else ""
        lines.append(f"| {r.predictor} | {r.n} | {r.roc_auc:.3f} | "
                     f"{r.auc_ci_low:.3f}–{r.auc_ci_high:.3f} | {r.pr_auc:.3f} | {sd_s} |")
    return "\n".join(lines)


def _plots(t: pd.DataFrame, imp: pd.DataFrame, out_dir: str) -> None:
    t = t.sort_values("roc_auc")
    fig, ax = plt.subplots(figsize=(7, 4.5))
    err = np.array([t.roc_auc - t.auc_ci_low, t.auc_ci_high - t.roc_auc])
    colors = ["#c0504d" if "DeepSeek" in p else "#3b6ea5" for p in t.predictor]
    ax.barh(t.predictor, t.roc_auc, xerr=err, color=colors, ecolor="#555")
    ax.axvline(0.5, color="#888", ls="--", lw=1)
    ax.set_xlim(0.3, 1.0)
    ax.set_xlabel("ROC-AUC (0.5 = coin flip), with 95% bootstrap CI")
    ax.set_title("Predicting which meme coins collapse")
    fig.tight_layout()
    fig.savefig(os.path.join(out_dir, "auc_comparison.png"), dpi=150)
    plt.close(fig)

    top = imp.head(8)[::-1]
    fig, ax = plt.subplots(figsize=(7, 4.5))
    ax.barh(top.index, top["mean"], xerr=top["sd"], color="#3b6ea5", ecolor="#555")
    ax.set_xlabel("Drop in ROC-AUC when shuffled (held-out folds)")
    ax.set_title("What the gradient boosting model relies on")
    fig.tight_layout()
    fig.savefig(os.path.join(out_dir, "model_importance.png"), dpi=150)
    plt.close(fig)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--selftest", choices=["random", "planted"])
    args = ap.parse_args()
    if args.selftest:
        out = os.path.join(HERE, "results", f"selftest_{args.selftest}")
        text = run(synthetic_outcomes(args.selftest), out,
                   banner=f"SELF-TEST ({args.selftest} labels). These are FAKE outcomes used only "
                          "to check the code works. Never report these numbers.")
    else:
        if not os.path.exists(OUTCOMES):
            raise SystemExit("No research/outcomes.csv yet. Run: python -m research.fetch_outcomes")
        out = os.path.join(HERE, "results")
        text = run(pd.read_csv(OUTCOMES), out)
    print(text)
    print(f"Saved to {out}")


if __name__ == "__main__":
    main()
