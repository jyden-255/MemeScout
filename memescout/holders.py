"""Holder concentration straight from Solana RPC — no indexer key required.

getTokenLargestAccounts returns the 20 biggest *token accounts* for a mint.
Divide by total supply and you get concentration:

  top1_pct       what the single biggest account holds
  top10_pct      biggest 10 combined
  top20_pct      biggest 20 combined
  top10_ex1_pct  accounts 2-11 combined

Caveat: for DEX-traded tokens the #1 account is very often the liquidity pool
or bonding-curve vault, not a person. That's why top10_ex1_pct exists — it's
usually the better "whale risk" number. A *total* holder count needs an
indexer (Helius / Birdeye / Solscan Pro); see README for the drop-in spot.
"""
import time

from .config import DEFAULT_TIMEOUT, SESSION, SOLANA_RPC_URL
from .models import Coin


def _rpc(method: str, params: list):
    r = SESSION.post(
        SOLANA_RPC_URL,
        json={"jsonrpc": "2.0", "id": 1, "method": method, "params": params},
        timeout=DEFAULT_TIMEOUT,
    )
    r.raise_for_status()
    j = r.json()
    if "error" in j:
        raise RuntimeError(j["error"])
    return j["result"]


def add_holder_stats(coins: list[Coin], pause: float = 0.8) -> None:
    for c in coins:
        if c.chain != "solana" or not c.address:
            continue
        try:
            supply = _rpc("getTokenSupply", [c.address])["value"]
            total = float(supply.get("uiAmount") or 0)
            if total <= 0:
                continue
            largest = _rpc("getTokenLargestAccounts", [c.address])["value"]
            amts = sorted((float(a.get("uiAmount") or 0) for a in largest), reverse=True)
            if not amts:
                continue
            c.top1_pct = round(100 * amts[0] / total, 2)
            c.top10_pct = round(100 * sum(amts[:10]) / total, 2)
            c.top20_pct = round(100 * sum(amts[:20]) / total, 2)
            c.top10_ex1_pct = round(100 * sum(amts[1:11]) / total, 2)
        except Exception as e:
            print(f"[holders] {c.symbol} ({c.address[:6]}…): {e}")
        time.sleep(pause)  # be polite to the public RPC
