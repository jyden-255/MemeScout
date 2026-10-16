"""CoinGecko public API — trending = the top-15 most searched coins right now,
which is retail attention in its purest form. We then pull each coin's detail
page to get its category (meme filter) and contract address so it can join the
on-chain pipeline.

Public (keyless) limit is roughly 30 calls/min, hence the sleeps. A free demo
key in COINGECKO_API_KEY raises that.
"""
import time

from ..config import COINGECKO_API_KEY, DEFAULT_TIMEOUT, SESSION
from ..models import Coin

TRENDING = "https://api.coingecko.com/api/v3/search/trending"
COIN = ("https://api.coingecko.com/api/v3/coins/{id}"
        "?localization=false&tickers=false&market_data=true"
        "&community_data=false&developer_data=false&sparkline=false")

# CoinGecko platform key -> DexScreener chainId
PLATFORM_MAP = {
    "solana": "solana",
    "base": "base",
    "ethereum": "ethereum",
    "binance-smart-chain": "bsc",
    "arbitrum-one": "arbitrum",
}


def _headers() -> dict:
    return {"x-cg-demo-api-key": COINGECKO_API_KEY} if COINGECKO_API_KEY else {}


def fetch_trending(networks: list[str], limit: int = 10, meme_only: bool = True) -> list[Coin]:
    out: list[Coin] = []
    try:
        r = SESSION.get(TRENDING, headers=_headers(), timeout=DEFAULT_TIMEOUT)
        r.raise_for_status()
        items = [x.get("item") or {} for x in (r.json().get("coins") or [])][:limit]
    except Exception as e:
        print(f"[coingecko] trending failed: {e}")
        return out

    for it in items:
        cid = it.get("id")
        if not cid:
            continue
        time.sleep(2.2)  # stay under the keyless rate limit
        try:
            r = SESSION.get(COIN.format(id=cid), headers=_headers(), timeout=DEFAULT_TIMEOUT)
            r.raise_for_status()
            d = r.json()
        except Exception as e:
            print(f"[coingecko] {cid} failed: {e}")
            continue

        cats = [str(c).lower() for c in (d.get("categories") or []) if c]
        if meme_only and not any("meme" in c for c in cats):
            continue

        platforms = {k.lower(): v for k, v in (d.get("platforms") or {}).items() if v}
        chain, addr = "", ""
        for cg_key, ds_chain in PLATFORM_MAP.items():
            if cg_key in platforms:
                chain, addr = ds_chain, platforms[cg_key]
                break

        md = d.get("market_data") or {}
        c = Coin(
            chain=chain or "cex",
            address=addr,
            symbol=(d.get("symbol") or "").upper(),
            name=d.get("name") or "",
            sources={"coingecko:trending"},
        )
        c.price_usd = (md.get("current_price") or {}).get("usd")
        c.market_cap = (md.get("market_cap") or {}).get("usd")
        c.volume_h24 = (md.get("total_volume") or {}).get("usd")
        c.change_h24 = md.get("price_change_percentage_24h")
        out.append(c)
    return out
