"""The one data structure everything passes around."""
from dataclasses import dataclass, field
from typing import Optional


@dataclass
class Coin:
    chain: str                      # "solana", "ethereum", "base", "bsc", or "cex" if unknown
    address: str                    # mint / contract address ("" if unknown)
    symbol: str
    name: str = ""
    sources: set = field(default_factory=set)   # which discovery feeds flagged it
    boost_total: float = 0.0                    # DexScreener paid-boost points (a literal hype-spend signal)

    # market metrics (filled by enrich.py, or CoinGecko for CEX-only coins)
    price_usd: Optional[float] = None
    change_m5: Optional[float] = None
    change_h1: Optional[float] = None
    change_h6: Optional[float] = None
    change_h24: Optional[float] = None
    volume_h24: Optional[float] = None
    liquidity_usd: Optional[float] = None
    market_cap: Optional[float] = None
    fdv: Optional[float] = None
    pair_created_at: Optional[int] = None       # ms epoch
    dex_url: str = ""

    # holder concentration (Solana only for now, via public RPC)
    top1_pct: Optional[float] = None
    top10_pct: Optional[float] = None
    top20_pct: Optional[float] = None
    top10_ex1_pct: Optional[float] = None       # top 2-11, i.e. excluding the LP-ish whale slot

    # scoring
    hype_score: float = 0.0                     # local heuristic pre-rank
    ai_hype: Optional[int] = None               # DeepSeek 0-100
    ai_risk: Optional[int] = None               # DeepSeek 0-100 (100 = near-certain rug/dump)
    ai_flags: list = field(default_factory=list)
    ai_thesis: str = ""

    @property
    def key(self):
        return (self.chain, self.address or self.symbol.lower())

    def merge(self, other: "Coin") -> None:
        """Fold a duplicate discovery of the same token into this one."""
        self.sources |= other.sources
        self.boost_total = max(self.boost_total, other.boost_total)
        if self.symbol in ("", "?") and other.symbol not in ("", "?"):
            self.symbol = other.symbol
        if not self.name and other.name:
            self.name = other.name
        if not self.address and other.address:
            self.address = other.address
        for attr in ("price_usd", "market_cap", "volume_h24", "change_h24"):
            if getattr(self, attr) is None and getattr(other, attr) is not None:
                setattr(self, attr, getattr(other, attr))
