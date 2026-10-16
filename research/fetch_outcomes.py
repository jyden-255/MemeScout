"""Fetch what happened to every token MemeScout ever saw.

Queries DexScreener's free public token endpoint (no API key) for each
token's CURRENT price and liquidity, so we can label which coins collapsed
after MemeScout first saw them. Run it on your own machine (it needs
internet), then run the study:

    python -m research.fetch_outcomes
    python -m research.evaluate

Output: research/outcomes.csv (one row per token). Re-running overwrites it,
and the fetch time is recorded so your results always say WHEN outcomes
were measured.
"""
from __future__ import annotations

import os
import time
from datetime import datetime, timezone

import pandas as pd
import requests

from .data import first_sightings, load_reports

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "outcomes.csv")
URL = "https://api.dexscreener.com/latest/dex/tokens/{addrs}"
BATCH = 25  # same batch size as memescout/enrich.py


def _f(x):
    try:
        return float(x)
    except (TypeError, ValueError):
        return None


def fetch(tokens: pd.DataFrame) -> pd.DataFrame:
    session = requests.Session()
    session.headers["User-Agent"] = "memescout-research/0.1"
    fetched_at = datetime.now(timezone.utc).isoformat(timespec="seconds")
    results = {}
    rows = tokens[tokens["chain"] != "cex"][["chain", "address"]].drop_duplicates()
    addrs = rows["address"].tolist()
    chain_of = dict(zip(rows["address"], rows["chain"]))
    for i in range(0, len(addrs), BATCH):
        batch = addrs[i:i + BATCH]
        for attempt in range(3):
            try:
                r = session.get(URL.format(addrs=",".join(batch)), timeout=30)
                if r.status_code == 429:
                    time.sleep(5 * (attempt + 1))
                    continue
                r.raise_for_status()
                pairs = (r.json() or {}).get("pairs") or []
                break
            except requests.RequestException as e:
                print(f"  batch {i // BATCH + 1} attempt {attempt + 1} failed: {e}")
                time.sleep(3)
        else:
            print(f"  giving up on batch {i // BATCH + 1}; those tokens are marked fetch_failed")
            for a in batch:
                results[a] = {"fetch_failed": True}
            continue
        # keep the deepest-liquidity pair on the right chain, like enrich.py
        for p in pairs:
            a = (p.get("baseToken") or {}).get("address") or ""
            if a not in chain_of or (p.get("chainId") or "").lower() != chain_of[a]:
                continue
            liq = _f((p.get("liquidity") or {}).get("usd")) or 0.0
            if a in results and (results[a].get("liquidity_now") or 0) >= liq:
                continue
            results[a] = {
                "price_now": _f(p.get("priceUsd")),
                "liquidity_now": liq,
                "volume_h24_now": _f((p.get("volume") or {}).get("h24")),
                "market_cap_now": _f(p.get("marketCap")),
            }
        print(f"  batch {i // BATCH + 1}/{(len(addrs) - 1) // BATCH + 1}: {len(pairs)} pairs")
        time.sleep(0.5)
    out = []
    for a in addrs:
        r = results.get(a, {})
        out.append({"chain": chain_of[a], "address": a, "fetched_at_utc": fetched_at,
                    "found": bool(r) and not r.get("fetch_failed"),
                    "fetch_failed": bool(r.get("fetch_failed")),
                    **{k: r.get(k) for k in ["price_now", "liquidity_now",
                                             "volume_h24_now", "market_cap_now"]}})
    return pd.DataFrame(out)


def main() -> None:
    tokens = first_sightings(load_reports())
    print(f"Fetching current data for {len(tokens)} tokens from DexScreener...")
    df = fetch(tokens)
    df.to_csv(OUT, index=False)
    print(f"Saved {OUT}")
    print(f"  found on DexScreener: {df['found'].sum()} / {len(df)}")
    print(f"  not found (delisted or no pairs): {(~df['found'] & ~df['fetch_failed']).sum()}")
    print(f"  fetch failed (re-run later): {df['fetch_failed'].sum()}")


if __name__ == "__main__":
    main()
