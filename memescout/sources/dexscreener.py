"""DexScreener public API (https://docs.dexscreener.com) — no key required.

Boosted tokens are people literally paying DexScreener for visibility, which
makes them one of the most honest "hype" signals available. Rate limit on
these endpoints is 60 req/min, so we sleep between calls.
"""
import time

from ..config import DEFAULT_TIMEOUT, SESSION
from ..models import Coin

BOOSTS_TOP = "https://api.dexscreener.com/token-boosts/top/v1"
BOOSTS_LATEST = "https://api.dexscreener.com/token-boosts/latest/v1"
PROFILES_LATEST = "https://api.dexscreener.com/token-profiles/latest/v1"


def _get_list(url: str) -> list:
    r = SESSION.get(url, timeout=DEFAULT_TIMEOUT)
    r.raise_for_status()
    data = r.json()
    if isinstance(data, dict):  # be defensive about wrapper objects
        data = data.get("data") or data.get("tokens") or []
    return data or []


def fetch_hyped(networks: list[str]) -> list[Coin]:
    feeds = [
        (BOOSTS_TOP, "dexscreener:boost-top"),
        (BOOSTS_LATEST, "dexscreener:boost-new"),
        (PROFILES_LATEST, "dexscreener:profile"),
    ]
    coins: list[Coin] = []
    for url, src in feeds:
        try:
            for row in _get_list(url):
                chain = (row.get("chainId") or "").lower()
                addr = row.get("tokenAddress") or ""
                if not addr or (networks and chain not in networks):
                    continue
                coins.append(Coin(
                    chain=chain,
                    address=addr,
                    symbol="?",  # boosts feed has no symbol; enrichment fills it
                    name=(row.get("description") or "")[:60],
                    sources={src},
                    boost_total=float(row.get("totalAmount") or row.get("amount") or 0),
                ))
        except Exception as e:
            print(f"[dexscreener] {src} failed: {e}")
        time.sleep(1.1)
    return coins
