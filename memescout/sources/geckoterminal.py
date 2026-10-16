"""GeckoTerminal public API — trending pools per network. Overlap with the
other feeds is the point: a coin showing up in 2-3 independent trend lists is
a much stronger hype signal than topping any single one.
"""
import time

from ..config import DEFAULT_TIMEOUT, SESSION
from ..models import Coin

TRENDING = "https://api.geckoterminal.com/api/v2/networks/{net}/trending_pools"

NET_MAP = {"ethereum": "eth"}  # our name -> GeckoTerminal network slug

# Base tokens that are really the quote side of a pool (skip them)
DENYLIST = {
    "So11111111111111111111111111111111111111112",   # wSOL
    "EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v",  # USDC (Solana)
    "Es9vMFrzaCERmJfrF4H2FYD4KCoNkY11McCe8BenwNYB",  # USDT (Solana)
    "0xc02aaa39b223fe8d0a0e5c4f27ead9083c756cc2",    # WETH
}


def fetch_trending(networks: list[str]) -> list[Coin]:
    out: list[Coin] = []
    for net in networks or ["solana"]:
        gt_net = NET_MAP.get(net, net)
        try:
            r = SESSION.get(TRENDING.format(net=gt_net), timeout=DEFAULT_TIMEOUT)
            r.raise_for_status()
            pools = r.json().get("data") or []
        except Exception as e:
            print(f"[geckoterminal] {net} failed: {e}")
            continue
        for pool in pools:
            rel = ((pool.get("relationships") or {}).get("base_token") or {}).get("data") or {}
            tid = rel.get("id") or ""                      # e.g. "solana_<mint>"
            addr = tid.split("_", 1)[1] if "_" in tid else ""
            if not addr or addr in DENYLIST:
                continue
            name = ((pool.get("attributes") or {}).get("name") or "").split("/")[0].strip()
            out.append(Coin(chain=net, address=addr, symbol=name or "?",
                            sources={"geckoterminal:trending"}))
        time.sleep(1.0)
    return out
