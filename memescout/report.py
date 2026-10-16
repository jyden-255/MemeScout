"""Terminal output + timestamped JSON reports."""
import json
import os
import time

from rich.console import Console
from rich.table import Table

from .models import Coin

console = Console()


def _fmt_usd(x):
    if x is None:
        return "—"
    if x >= 1_000_000_000:
        return f"${x / 1e9:.2f}B"
    if x >= 1_000_000:
        return f"${x / 1e6:.2f}M"
    if x >= 1_000:
        return f"${x / 1e3:.1f}K"
    return f"${x:,.2f}"


def _fmt_price(x):
    if x is None:
        return "—"
    if x >= 1:
        return f"${x:,.4f}"
    return f"${x:.10f}".rstrip("0")


def _fmt_pct(x):
    if x is None:
        return "—"
    color = "green" if x >= 0 else "red"
    return f"[{color}]{x:+.1f}%[/{color}]"


def show(coins: list[Coin]) -> None:
    t = Table(title="MemeScout — hype board", header_style="bold")
    for col in ["#", "Symbol", "Chain", "Price", "1h", "24h", "Vol 24h",
                "Liq", "MCap", "Top10%", "Src", "Hype", "AI", "Risk"]:
        t.add_column(col, overflow="fold")
    for i, c in enumerate(coins, 1):
        t.add_row(
            str(i), c.symbol, c.chain,
            _fmt_price(c.price_usd), _fmt_pct(c.change_h1), _fmt_pct(c.change_h24),
            _fmt_usd(c.volume_h24), _fmt_usd(c.liquidity_usd), _fmt_usd(c.market_cap or c.fdv),
            "—" if c.top10_pct is None else f"{c.top10_pct:.0f}%",
            str(len(c.sources)),
            f"{c.hype_score:.0f}",
            "—" if c.ai_hype is None else str(c.ai_hype),
            "—" if c.ai_risk is None else str(c.ai_risk),
        )
    console.print(t)

    for c in coins:
        if c.ai_thesis or c.ai_flags:
            line = f"[bold]{c.symbol}[/bold]: {c.ai_thesis}"
            if c.ai_flags:
                line += f"  [red]⚑ {', '.join(c.ai_flags)}[/red]"
            console.print(line)


def save(coins: list[Coin], outdir: str = "reports") -> str:
    os.makedirs(outdir, exist_ok=True)
    ts = time.strftime("%Y%m%d-%H%M%S")
    path = os.path.join(outdir, f"memescout-{ts}.json")
    rows = [c.__dict__ | {"sources": sorted(c.sources)} for c in coins]
    with open(path, "w") as f:
        json.dump(rows, f, indent=2, default=str)
    console.print(f"\n[dim]Saved: {path}[/dim]")
    return path
