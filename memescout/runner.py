"""Shared MemeScout pipeline used by the CLI and web UI."""
from dataclasses import dataclass
from typing import Callable

from . import enrich, evaluator, fixtures, holders, hype, report
from .models import Coin
from .sources import coingecko, dexscreener, geckoterminal


LogFn = Callable[[str], None]


@dataclass
class RunOptions:
    networks: str = "solana"
    top: int = 12
    min_liquidity: float = 10_000
    all_trending: bool = False
    no_llm: bool = False
    demo: bool = False
    coingecko_limit: int = 10
    skip_holders: bool = False
    llm_timeout: int = 45
    ai_top: int = 12

    @property
    def network_list(self) -> list[str]:
        return [n.strip().lower() for n in self.networks.split(",") if n.strip()]


@dataclass
class RunResult:
    coins: list[Coin]
    report_path: str
    ai_ran: bool


def dedupe(coins: list[Coin]) -> list[Coin]:
    seen: dict = {}
    for c in coins:
        if c.key in seen:
            seen[c.key].merge(c)
        else:
            seen[c.key] = c
    return list(seen.values())


def run_pipeline(options: RunOptions, log: LogFn = print) -> RunResult:
    nets = options.network_list

    if options.demo:
        log("demo mode - synthetic data, no live requests")
        coins = fixtures.demo_coins()
    else:
        log("1/5 discovering candidates")
        coins: list[Coin] = []
        log("   DexScreener boosts/profiles")
        coins += dexscreener.fetch_hyped(nets)
        log(f"   {len(coins)} candidates after DexScreener")
        log("   GeckoTerminal trending pools")
        coins += geckoterminal.fetch_trending(nets)
        log(f"   {len(coins)} candidates after GeckoTerminal")
        if options.coingecko_limit > 0:
            log(f"   CoinGecko trending searches (limit {options.coingecko_limit})")
            coins += coingecko.fetch_trending(
                nets,
                limit=options.coingecko_limit,
                meme_only=not options.all_trending,
            )
        else:
            log("   CoinGecko skipped")
        coins = dedupe(coins)
        log(f"   {len(coins)} unique candidates")

        log("2/5 enriching market data (DexScreener)")
        enrich.enrich(coins)

    coins = [c for c in coins if c.price_usd is not None]
    if options.min_liquidity > 0:
        coins = [
            c for c in coins
            if c.liquidity_usd is None or c.liquidity_usd >= options.min_liquidity
        ]

    for c in coins:
        c.hype_score = hype.score(c)
    coins.sort(key=lambda c: c.hype_score, reverse=True)
    coins = coins[: options.top]

    if not options.demo and not options.skip_holders:
        log("3/5 holder concentration (Solana RPC)")
        holders.add_holder_stats(coins)
    elif options.skip_holders:
        log("3/5 holder concentration skipped")

    ai_ran = False
    if options.no_llm:
        log("4/5 DeepSeek pass skipped")
    else:
        ai_count = max(0, min(options.ai_top, len(coins)))
        log(f"4/5 DeepSeek evaluation (top {ai_count})")
        ai_ran = evaluator.evaluate(coins[:ai_count], log=log, timeout=options.llm_timeout)
        if ai_ran:
            scored = coins[:ai_count]
            rest = coins[ai_count:]
            scored.sort(
                key=lambda c: (c.ai_hype if c.ai_hype is not None else -1, c.hype_score),
                reverse=True,
            )
            coins = scored + rest
        else:
            log("   DeepSeek did not return scores; showing heuristic ranking")

    log("5/5 saving report")
    path = report.save(coins)
    return RunResult(coins=coins, report_path=path, ai_ran=ai_ran)
