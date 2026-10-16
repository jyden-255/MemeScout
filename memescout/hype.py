"""Cheap local pre-rank (0-100) so we only spend DeepSeek tokens on the top N.

Components:
  - multi-source consensus (appearing in 2+ independent trend feeds)
  - paid boost spend on DexScreener
  - 24h volume relative to liquidity (turnover = real trading interest)
  - price momentum (1h + 24h)
  - pair newness (fresh pairs are where meme hype lives)
"""
import time

from .models import Coin


def score(c: Coin) -> float:
    s = 0.0
    s += min(40.0, 20.0 * len(c.sources))

    if c.boost_total:
        s += min(15.0, c.boost_total / 40.0)

    if c.volume_h24 and c.liquidity_usd and c.liquidity_usd > 0:
        s += min(20.0, 4.0 * (c.volume_h24 / c.liquidity_usd))

    momentum = 0.0
    if c.change_h1 is not None:
        momentum += abs(c.change_h1) / 5.0
    if c.change_h24 is not None:
        momentum += abs(c.change_h24) / 25.0
    s += min(15.0, momentum)

    if c.pair_created_at:
        age_days = (time.time() * 1000 - c.pair_created_at) / 86_400_000
        if age_days < 3:
            s += 10.0
        elif age_days < 14:
            s += 5.0

    return round(min(100.0, s), 1)
