"""Synthetic sample data for `--demo` mode: exercises the whole pipeline
(filtering, scoring, ranking, reporting, and DeepSeek if a key is set)
without touching any live API. All addresses/symbols are fake.
"""
import time

from .models import Coin


def _ms_ago(days: float) -> int:
    return int((time.time() - days * 86_400) * 1000)


def demo_coins() -> list[Coin]:
    a = Coin("solana", "DemoMint1111111111111111111111111111111111A", "WIFCAT",
             name="wif cat (demo)",
             sources={"dexscreener:boost-top", "geckoterminal:trending"}, boost_total=300)
    a.price_usd, a.change_m5, a.change_h1, a.change_h6, a.change_h24 = 0.0021, 2.1, 18.0, 44.0, 160.0
    a.volume_h24, a.liquidity_usd, a.market_cap = 2_400_000, 180_000, 2_100_000
    a.pair_created_at = _ms_ago(2)
    a.top1_pct, a.top10_pct, a.top20_pct, a.top10_ex1_pct = 22.0, 41.0, 52.0, 19.0

    b = Coin("solana", "DemoMint1111111111111111111111111111111111B", "GROKDOG",
             name="grok dog (demo)", sources={"dexscreener:boost-new"}, boost_total=50)
    b.price_usd, b.change_m5, b.change_h1, b.change_h6, b.change_h24 = 0.0000087, 35.0, 240.0, 310.0, 900.0
    b.volume_h24, b.liquidity_usd, b.market_cap = 900_000, 12_000, 850_000
    b.pair_created_at = _ms_ago(0.4)
    b.top1_pct, b.top10_pct, b.top20_pct, b.top10_ex1_pct = 31.0, 78.0, 86.0, 47.0

    c = Coin("solana", "DemoMint1111111111111111111111111111111111C", "PEPE26",
             name="pepe 2026 (demo)",
             sources={"coingecko:trending", "dexscreener:profile", "geckoterminal:trending"})
    c.price_usd, c.change_m5, c.change_h1, c.change_h6, c.change_h24 = 0.014, -0.5, 3.2, 9.0, 25.0
    c.volume_h24, c.liquidity_usd, c.market_cap = 6_800_000, 1_400_000, 38_000_000
    c.pair_created_at = _ms_ago(40)
    c.top1_pct, c.top10_pct, c.top20_pct, c.top10_ex1_pct = 12.0, 24.0, 31.0, 12.0

    d = Coin("base", "0xdemo00000000000000000000000000000000000d", "MOONCHAD",
             name="moonchad (demo)", sources={"geckoterminal:trending"})
    d.price_usd, d.change_h1, d.change_h24 = 0.00042, -6.0, -18.0
    d.volume_h24, d.liquidity_usd, d.market_cap = 140_000, 95_000, 600_000
    d.pair_created_at = _ms_ago(9)

    e = Coin("cex", "", "DOGGO", name="doggo (demo)", sources={"coingecko:trending"})
    e.price_usd, e.change_h24 = 0.087, 12.0
    e.volume_h24, e.market_cap = 55_000_000, 1_200_000_000

    f = Coin("solana", "DemoMint1111111111111111111111111111111111F", "RUGLET",
             name="ruglet (demo)", sources={"dexscreener:boost-new"}, boost_total=10)
    f.price_usd, f.change_h1, f.change_h24 = 0.0000004, 4.0, 20.0
    f.volume_h24, f.liquidity_usd, f.market_cap = 9_000, 6_000, 40_000  # fails default liq filter
    f.pair_created_at = _ms_ago(0.1)

    return [a, b, c, d, e, f]
