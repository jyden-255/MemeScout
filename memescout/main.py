"""MemeScout CLI.

    python -m memescout.main                    # live run, Solana focus
    python -m memescout.main --networks solana,base --top 15
    python -m memescout.main --demo --no-llm    # offline smoke test
"""
import argparse

from .report import console
from . import report
from .runner import RunOptions, run_pipeline


def run() -> None:
    ap = argparse.ArgumentParser(
        prog="memescout",
        description="Find trending meme coins from public APIs, pull market + holder stats, "
                    "and have DeepSeek score them.")
    ap.add_argument("--networks", default="solana",
                    help="comma list for on-chain discovery: solana,ethereum,base,bsc (default: solana)")
    ap.add_argument("--top", type=int, default=12, help="how many coins to show/analyze (default 12)")
    ap.add_argument("--min-liquidity", type=float, default=10_000,
                    help="drop pairs below this USD liquidity (default 10000; 0 disables)")
    ap.add_argument("--all-trending", action="store_true",
                    help="include non-meme CoinGecko trending coins too")
    ap.add_argument("--no-llm", action="store_true", help="skip the DeepSeek pass")
    ap.add_argument("--demo", action="store_true", help="run offline on bundled sample data")
    ap.add_argument("--coingecko-limit", type=int, default=10,
                    help="how many CoinGecko trending coins to inspect (default 10; 0 skips)")
    ap.add_argument("--skip-holders", action="store_true",
                    help="skip Solana holder concentration checks")
    ap.add_argument("--llm-timeout", type=int, default=45,
                    help="DeepSeek request timeout in seconds (default 45)")
    ap.add_argument("--ai-top", type=int, default=12,
                    help="how many of the shown coins DeepSeek should score (default 12)")
    args = ap.parse_args()
    options = RunOptions(
        networks=args.networks,
        top=args.top,
        min_liquidity=args.min_liquidity,
        all_trending=args.all_trending,
        no_llm=args.no_llm,
        demo=args.demo,
        coingecko_limit=args.coingecko_limit,
        skip_holders=args.skip_holders,
        llm_timeout=args.llm_timeout,
        ai_top=args.ai_top,
    )
    result = run_pipeline(options, log=console.print)
    console.print()
    report.show(result.coins)
    console.print("[dim]Meme coins are extremely volatile and most go to zero. "
                  "This is a research tool, not financial advice.[/dim]")


if __name__ == "__main__":
    run()
