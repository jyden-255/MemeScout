"""Load, clean and validate MemeScout's saved reports.

Every run of MemeScout writes reports/memescout-<YYYYMMDD-HHMMSS>.json, a
list of coins with market data and (for the top N) DeepSeek's scores. This
module turns all of those files into one tidy pandas DataFrame:
one row = one coin seen in one snapshot.

Key cleaning decisions (each one is something you should be able to explain):

1. Timestamps. The filename time is Sydney local time (AEST, UTC+10 in
   July-August), but pair_created_at is a UTC epoch in milliseconds.
   Mixing them naively makes every coin look 10 hours older than it is.
   We convert snapshots to UTC first. (Evidence: with a +10h correction the
   youngest pair is ~0 hours old at first sighting, never negative.)
2. Missing values are kept as NaN, not filled with 0. A missing liquidity
   figure is "unknown", not "zero liquidity", and filling it with 0 would
   invent a strong (and false) risk signal.
3. Extreme values are real in this market (+500,000% in an hour happens),
   so we never delete them. Instead, features use log transforms or
   signed-log transforms so one wild coin can't dominate a model.
4. The unit of analysis for prediction is the TOKEN, not the row: the same
   coin appears in many snapshots, so rows are not independent.
"""
from __future__ import annotations

import glob
import json
import os
from typing import Iterable

import numpy as np
import pandas as pd

SNAPSHOT_TZ = "Australia/Sydney"
HERE = os.path.dirname(os.path.abspath(__file__))
DEFAULT_REPORTS = os.path.join(HERE, "..", "reports")

NUMERIC = ["boost_total", "price_usd", "change_m5", "change_h1", "change_h6",
           "change_h24", "volume_h24", "liquidity_usd", "market_cap", "fdv",
           "top1_pct", "top10_pct", "top20_pct", "top10_ex1_pct",
           "hype_score", "ai_hype", "ai_risk"]

# Features available at the moment a coin is first seen. Nothing here may
# use information from the future (that would be leakage).
FEATURES = ["log_liquidity", "log_volume", "log_mcap", "turnover",
            "liq_to_mcap", "pair_age_h", "slog_change_m5", "slog_change_h1",
            "slog_change_h6", "slog_change_h24", "boost_total", "n_sources",
            "in_gecko_trending", "has_paid_boost"]


def _snapshot_time(path: str) -> pd.Timestamp:
    stamp = os.path.basename(path).split("memescout-")[1][:15]
    local = pd.to_datetime(stamp, format="%Y%m%d-%H%M%S").tz_localize(SNAPSHOT_TZ)
    return local.tz_convert("UTC")


def load_reports(reports_dir: str = DEFAULT_REPORTS) -> pd.DataFrame:
    files = sorted(glob.glob(os.path.join(reports_dir, "memescout-*.json")))
    if not files:
        raise FileNotFoundError(f"No reports found in {reports_dir}")
    rows = []
    for f in files:
        with open(f) as fh:
            coins = json.load(fh)
        snap = _snapshot_time(f)
        for rank, c in enumerate(coins):
            c = dict(c)
            c["snapshot_utc"] = snap
            c["report_file"] = os.path.basename(f)
            c["rank_in_report"] = rank
            rows.append(c)
    df = pd.DataFrame(rows)
    for col in NUMERIC:
        if col in df:
            df[col] = pd.to_numeric(df[col], errors="coerce")
    df["sources"] = df["sources"].apply(lambda s: list(s) if isinstance(s, list) else [])
    return df


def _slog(x: pd.Series) -> pd.Series:
    """Signed log: keeps the sign of a % change but squashes huge values."""
    return np.sign(x) * np.log1p(np.abs(x))


def add_features(df: pd.DataFrame) -> pd.DataFrame:
    out = df.copy()
    out["log_liquidity"] = np.log10(out["liquidity_usd"] + 1)
    out["log_volume"] = np.log10(out["volume_h24"] + 1)
    mcap = out["market_cap"].where(out["market_cap"] > 0, out["fdv"])
    out["log_mcap"] = np.log10(mcap + 1)
    out["turnover"] = np.log1p(out["volume_h24"] / out["liquidity_usd"])
    out["liq_to_mcap"] = out["liquidity_usd"] / mcap
    created = pd.to_datetime(out["pair_created_at"], unit="ms", utc=True)
    out["pair_age_h"] = (out["snapshot_utc"] - created).dt.total_seconds() / 3600
    for k in ["m5", "h1", "h6", "h24"]:
        out[f"slog_change_{k}"] = _slog(out[f"change_{k}"])
    out["n_sources"] = out["sources"].apply(len)
    out["in_gecko_trending"] = out["sources"].apply(
        lambda s: any(x.startswith("geckoterminal") for x in s)).astype(int)
    out["has_paid_boost"] = out["sources"].apply(
        lambda s: any("boost" in x for x in s)).astype(int)
    return out


def first_sightings(df: pd.DataFrame) -> pd.DataFrame:
    """One row per token: the first time MemeScout saw it."""
    return (df.sort_values(["snapshot_utc", "rank_in_report"])
              .groupby(["chain", "address"], as_index=False).first())


def first_scored(df: pd.DataFrame) -> pd.DataFrame:
    """One row per token: the first time DeepSeek scored it."""
    scored = df[df["ai_risk"].notna()]
    return (scored.sort_values(["snapshot_utc", "rank_in_report"])
                  .groupby(["chain", "address"], as_index=False).first())


def validate(df: pd.DataFrame) -> list[str]:
    """Data checks written like unit tests. Returns a list of problems found
    (an empty list means every check passed). Fatal problems raise."""
    problems = []
    assert len(df) > 0, "no rows loaded"
    assert df["address"].notna().all(), "every row needs a token address"
    dupes = df.duplicated(["address", "snapshot_utc"]).sum()
    assert dupes == 0, f"{dupes} duplicate (token, snapshot) rows"
    assert (df["price_usd"].dropna() > 0).all(), "prices must be positive"
    for col in ["ai_risk", "ai_hype", "hype_score"]:
        v = df[col].dropna()
        assert v.between(0, 100).all(), f"{col} outside 0-100"
    ages = add_features(df)["pair_age_h"].dropna()
    if (ages < -0.5).any():
        problems.append(f"{(ages < -0.5).sum()} rows have a pair created AFTER "
                        "the snapshot: timezone handling is wrong")
    miss = df[NUMERIC].isna().mean()
    for col, frac in miss.items():
        if frac > 0.2:
            problems.append(f"{col}: {frac:.0%} missing")
    return problems


def quality_report(df: pd.DataFrame) -> str:
    f = add_features(df)
    tok = first_sightings(df)
    lines = ["# MemeScout data quality report", ""]
    lines.append(f"- Reports (snapshots): {df['report_file'].nunique()}")
    lines.append(f"- Rows (token x snapshot): {len(df):,}")
    lines.append(f"- Unique tokens: {len(tok):,}")
    lines.append(f"- Date range (UTC): {df['snapshot_utc'].min():%Y-%m-%d %H:%M} to "
                 f"{df['snapshot_utc'].max():%Y-%m-%d %H:%M}")
    lines.append(f"- Snapshots per collection day: " + ", ".join(
        f"{d}: {n}" for d, n in df.groupby(df['snapshot_utc'].dt.tz_convert(SNAPSHOT_TZ).dt.date)['report_file'].nunique().items()))
    lines.append(f"- Chains: " + ", ".join(f"{k} {v}" for k, v in df['chain'].value_counts().items()))
    lines.append(f"- Tokens DeepSeek scored at least once: {df.loc[df.ai_risk.notna(), 'address'].nunique()}")
    lines.append("")
    lines.append("## Missing values (share of rows)")
    lines.append("")
    lines.append("| column | missing |")
    lines.append("| --- | --- |")
    for col, frac in df[NUMERIC].isna().mean().sort_values(ascending=False).items():
        lines.append(f"| {col} | {frac:.1%} |")
    lines.append("")
    lines.append("## Extreme values (kept, then log-transformed)")
    lines.append("")
    for col in ["change_h1", "change_h24", "volume_h24", "market_cap"]:
        v = df[col].dropna()
        lines.append(f"- {col}: median {v.median():,.1f}, 99th percentile {v.quantile(.99):,.1f}, max {v.max():,.1f}")
    lines.append("")
    lines.append(f"- Pair age at first sighting (hours): median {f.groupby('address')['pair_age_h'].min().median():.1f}")
    probs = validate(df)
    lines.append("")
    lines.append("## Validation")
    lines.append("")
    lines.append("All fatal checks passed (no duplicates, positive prices, scores in 0-100).")
    for p in probs:
        lines.append(f"- Warning: {p}")
    return "\n".join(lines) + "\n"


if __name__ == "__main__":
    data = load_reports()
    report = quality_report(data)
    out = os.path.join(HERE, "results", "data_quality.md")
    os.makedirs(os.path.dirname(out), exist_ok=True)
    with open(out, "w") as fh:
        fh.write(report)
    print(report)
    print(f"Saved to {out}")
