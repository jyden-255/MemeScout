"""Environment config + a shared requests session with sane retries."""
import os

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

USER_AGENT = "memescout/0.1 (personal research tool)"
DEFAULT_TIMEOUT = (5, 25)

DEEPSEEK_API_KEY = os.getenv("DEEPSEEK_API_KEY", "")
DEEPSEEK_BASE_URL = os.getenv("DEEPSEEK_BASE_URL", "https://api.deepseek.com")
DEEPSEEK_MODEL = os.getenv("DEEPSEEK_MODEL", "deepseek-chat")

# Optional free "demo" key from CoinGecko raises your rate limit. Works without it.
COINGECKO_API_KEY = os.getenv("COINGECKO_API_KEY", "")

# Any Solana RPC works; a free Helius/QuickNode endpoint is faster than the public one.
SOLANA_RPC_URL = os.getenv("SOLANA_RPC_URL", "https://api.mainnet-beta.solana.com")


def make_session() -> requests.Session:
    s = requests.Session()
    retry = Retry(
        total=2,
        connect=0,
        read=1,
        status=2,
        backoff_factor=1.5,
        status_forcelist=[429, 500, 502, 503, 504],
        allowed_methods=["GET", "POST"],
    )
    s.mount("https://", HTTPAdapter(max_retries=retry))
    s.headers.update({"User-Agent": USER_AGENT, "Accept": "application/json"})
    return s


SESSION = make_session()
