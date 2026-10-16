"""DeepSeek evaluation layer.

Sends one batched request with compact per-coin JSON and asks for structured
verdicts back (JSON mode). DeepSeek's API is OpenAI-compatible:
POST {base}/chat/completions with a Bearer key.
"""
import json
from typing import Callable

from .config import DEEPSEEK_API_KEY, DEEPSEEK_BASE_URL, DEEPSEEK_MODEL, DEFAULT_TIMEOUT, SESSION
from .models import Coin


LogFn = Callable[[str], None]

SYSTEM = (
    "You are a blunt, skeptical meme-coin analyst. You receive market and holder "
    "data for tokens currently trending across public sources. Score each one. "
    "Reply with JSON only — no prose, no markdown fences."
)

INSTRUCTIONS = """For each coin in COINS, produce one object with:
- "address": echo the address you were given
- "symbol": echo the symbol
- "ai_hype": integer 0-100 — genuine attention/momentum. Reward multi-source presence and sustained volume; don't reward a lone vertical candle.
- "risk": integer 0-100 — 100 means near-certain rug or dump. Weigh: extreme holder concentration (top10_excl_top1_pct is the honest whale number, since the #1 account is usually the LP vault), thin liquidity relative to market cap, a brand-new pair, and parabolic 1h moves.
- "red_flags": up to 4 short strings
- "thesis": one sentence, max 140 chars, plain description of what the data says (no advice, no "buy/sell")

Return exactly this shape and nothing else:
{"evaluations": [{...}, {...}]}"""


def _int(x):
    try:
        return int(round(float(x)))
    except (TypeError, ValueError):
        return None


def evaluate(coins: list[Coin], log: LogFn = print, timeout: int = 45) -> bool:
    """Annotate coins in place. Returns True if the LLM pass succeeded."""
    if not DEEPSEEK_API_KEY:
        log("[deepseek] DEEPSEEK_API_KEY not set - skipping AI evaluation")
        return False
    if not coins:
        log("[deepseek] no coins to score - skipping AI evaluation")
        return False

    payload = [{
        "symbol": c.symbol,
        "address": c.address,
        "chain": c.chain,
        "sources": sorted(c.sources),
        "dexscreener_boost_points": c.boost_total,
        "price_usd": c.price_usd,
        "pct_change": {"m5": c.change_m5, "h1": c.change_h1, "h6": c.change_h6, "h24": c.change_h24},
        "volume_24h_usd": c.volume_h24,
        "liquidity_usd": c.liquidity_usd,
        "market_cap_usd": c.market_cap or c.fdv,
        "pair_created_at_ms": c.pair_created_at,
        "holders": {
            "top1_pct": c.top1_pct,
            "top10_pct": c.top10_pct,
            "top20_pct": c.top20_pct,
            "top10_excl_top1_pct": c.top10_ex1_pct,
        },
    } for c in coins]

    body = {
        "model": DEEPSEEK_MODEL,
        "messages": [
            {"role": "system", "content": SYSTEM},
            {"role": "user", "content": INSTRUCTIONS + "\n\nCOINS:\n" + json.dumps(payload, default=str)},
        ],
        "response_format": {"type": "json_object"},
        "temperature": 0.3,
        "max_tokens": 2400,
    }

    try:
        r = SESSION.post(
            f"{DEEPSEEK_BASE_URL.rstrip('/')}/chat/completions",
            headers={"Authorization": f"Bearer {DEEPSEEK_API_KEY}"},
            json=body,
            timeout=(DEFAULT_TIMEOUT[0], timeout),
        )
        r.raise_for_status()
        text = r.json()["choices"][0]["message"]["content"]
    except Exception as e:
        log(f"[deepseek] request failed: {e}")
        return False

    text = text.strip()
    if text.startswith("```"):  # belt-and-braces even in JSON mode
        text = text.strip("`")
        text = text[4:] if text.startswith("json") else text

    try:
        evals = json.loads(text).get("evaluations") or []
    except json.JSONDecodeError as e:
        log(f"[deepseek] could not parse response as JSON: {e}")
        return False

    by_addr = {str(e.get("address")): e for e in evals if e.get("address")}
    by_sym = {str(e.get("symbol", "")).upper(): e for e in evals}
    for c in coins:
        e = by_addr.get(c.address) or by_sym.get(c.symbol.upper())
        if not e:
            continue
        c.ai_hype = _int(e.get("ai_hype"))
        c.ai_risk = _int(e.get("risk"))
        c.ai_flags = [str(x) for x in (e.get("red_flags") or [])][:4]
        c.ai_thesis = str(e.get("thesis") or "")[:200]
    log(f"[deepseek] scored {len(evals)} coins")
    return True
