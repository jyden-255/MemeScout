"""Fill each Coin's market metrics from DexScreener's token endpoint.

Accepts up to 30 comma-separated addresses per call, so the whole candidate
list usually costs 2-4 requests. For each token we keep its deepest-liquidity
pair as the canonical market.
"""
import time

from .config import DEFAULT_TIMEOUT, SESSION
from .models import Coin

TOKENS = "https://api.dexscreener.com/latest/dex/tokens/{addrs}"
BATCH = 25


def _f(x):
    try:
        return float(x)
    except (TypeError, ValueError):
        return None


def _apply(c: Coin, p: dict) -> None:
    base = p.get("baseToken") or {}
    c.symbol = base.get("symbol") or c.symbol
    c.name = base.get("name") or c.name
    c.price_usd = _f(p.get("priceUsd"))
    ch = p.get("priceChange") or {}
    c.change_m5 = _f(ch.get("m5"))
    c.change_h1 = _f(ch.get("h1"))
    c.change_h6 = _f(ch.get("h6"))
    c.change_h24 = _f(ch.get("h24"))
    c.volume_h24 = _f((p.get("volume") or {}).get("h24"))
    c.liquidity_usd = _f((p.get("liquidity") or {}).get("usd"))
    c.market_cap = _f(p.get("marketCap"))
    c.fdv = _f(p.get("fdv"))
    c.pair_created_at = p.get("pairCreatedAt")
    c.dex_url = p.get("url") or c.dex_url
    active = (p.get("boosts") or {}).get("active")
    if active:
        c.boost_total = max(c.boost_total, float(active))


def enrich(coins: list[Coin]) -> None:
    with_addr = [c for c in coins if c.address]
    for i in range(0, len(with_addr), BATCH):
        batch = with_addr[i:i + BATCH]
        index: dict[str, Coin] = {}
        for c in batch:
            index[c.address] = c
            index[c.address.lower()] = c
        try:
            r = SESSION.get(TOKENS.format(addrs=",".join(c.address for c in batch)), timeout=DEFAULT_TIMEOUT)
            r.raise_for_status()
            pairs = (r.json() or {}).get("pairs") or []
        except Exception as e:
            print(f"[enrich] batch failed: {e}")
            pairs = []

        best_liq: dict = {}
        for p in pairs:
            baddr = (p.get("baseToken") or {}).get("address") or ""
            c = index.get(baddr) or index.get(baddr.lower())
            if not c:
                continue
            if c.chain and c.chain != "cex" and (p.get("chainId") or "").lower() != c.chain:
                continue
            liq = _f((p.get("liquidity") or {}).get("usd")) or 0.0
            if liq <= best_liq.get(c.key, -1.0):
                continue
            best_liq[c.key] = liq
            _apply(c, p)
        time.sleep(0.4)
