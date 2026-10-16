# MemeScout

Finds the meme coins getting real attention right now, pulls their market and holder stats, and has DeepSeek score each one for hype and rug risk. Terminal table out, plus a timestamped JSON report you can feed into anything else.

## How it works

```
discover  →  dedupe  →  enrich  →  filter + pre-rank  →  holder stats  →  DeepSeek  →  report
(3 feeds)              (DexScreener)  (heuristic 0-100)   (Solana RPC)    (JSON verdicts)
```

**Discovery** merges three independent public feeds — a coin appearing in two or three of them is a far stronger hype signal than topping any single one:

| Feed | What it captures | Key needed |
|---|---|---|
| DexScreener boosts (`token-boosts/top`, `latest`) | People literally paying for visibility — hype spend | No |
| GeckoTerminal trending pools | On-chain trading attention per network | No |
| CoinGecko trending searches | Retail search attention (filtered to meme category) | No (free demo key optional) |

**Enrichment** batch-queries DexScreener's token endpoint (30 addresses per call) for price, 5m/1h/6h/24h change, volume, liquidity, market cap/FDV and pair age, keeping each token's deepest-liquidity pair.

**Holder stats** come straight from Solana RPC (`getTokenLargestAccounts` + `getTokenSupply`) — no indexer key needed. You get top-1 / top-10 / top-20 concentration as % of supply, plus **top10-excluding-top1**, which is usually the honest whale number because the #1 account is almost always the liquidity pool or bonding-curve vault, not a person. A *total holder count* isn't available from plain RPC; if you want it, get a free Helius or Birdeye key and add one call in `holders.py` — that's the drop-in spot.

**DeepSeek** gets one batched request with compact JSON per coin and returns structured verdicts in JSON mode: `ai_hype` 0-100, `risk` 0-100, up to 4 red flags, and a one-line thesis. No key set → the tool still runs and ranks on the local heuristic.

## Why APIs instead of scraping HTML or Twitter/X

The sites you'd want to scrape (DexScreener, GeckoTerminal, CoinGecko) all publish free documented APIs, which are faster, stabler, and won't break every time a div changes. Scraping X specifically violates their ToS and their anti-bot walls kill unauthenticated scrapers within minutes; the official API's cheapest useful tier is paid. The boost/trending feeds above are decent proxies for social hype anyway, since they're driven by user attention. If you later get X API access, add a `sources/x.py` that returns `list[Coin]` and append it in `main.py` — the pipeline doesn't care where candidates come from.

## Setup

```bash
pip install -r requirements.txt
cp .env.example .env        # put your DeepSeek key in
```

## Usage

```bash
python3 -m memescout.web                          # local web UI
python -m memescout.main                          # live run, Solana focus
python -m memescout.main --networks solana,base   # multi-chain discovery
python -m memescout.main --top 15 --min-liquidity 25000
python -m memescout.main --top 50 --ai-top 12       # show more, AI-score first 12
python -m memescout.main --all-trending           # don't filter CoinGecko to meme-only
python -m memescout.main --no-llm                 # heuristic ranking only
python -m memescout.main --demo --no-llm          # offline smoke test, no network
```

The web UI defaults to showing 50 coins while DeepSeek scores the first 12.
Raise "DeepSeek coins" when you want more AI verdicts; raise "Coins to show"
when you mainly want a broader heuristic board.

Reports land in `reports/memescout-<timestamp>.json` with every field per coin.

## Local hype heuristic (pre-rank)

Only the top `--top` coins are sent to DeepSeek, ranked by a cheap 0-100 score: multi-source consensus (up to 40), boost spend (15), 24h volume ÷ liquidity turnover (20), 1h+24h momentum (15), pair newness (10).

## Notes and knobs

- Public Solana RPC is slow-ish and rate-limited; a free Helius/QuickNode URL in `SOLANA_RPC_URL` speeds up the holder pass a lot.
- Keyless CoinGecko allows ~30 calls/min, hence the sleeps; a free demo key in `COINGECKO_API_KEY` loosens that.
- Endpoints are current as of the docs at build time; if one drifts, each source is isolated in its own file under `memescout/sources/`.
- Cron it (`0 * * * *`) and diff consecutive JSON reports to catch coins *entering* the hype set — that's usually more interesting than the standings themselves.

## Disclaimer

Meme coins are lottery tickets with extra steps: most go to zero, liquidity can be pulled at any time, and holder data can be obfuscated across wallets. This tool surfaces and summarizes public data; it is not financial advice.

## Research: does the LLM's risk score actually work?

`research/` contains a study on MemeScout's own saved reports: it audits DeepSeek's scores for consistency and grounding, then tests whether its risk score predicts which tokens collapsed, against simple rules and trained models. See [research/README.md](research/README.md).
