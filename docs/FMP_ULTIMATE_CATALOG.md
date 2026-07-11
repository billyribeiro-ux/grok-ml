# FMP Ultimate plan — full product surface (user-provided)

This is the complete catalog of what the Ultimate plan exposes.  
Download status is tracked by `scripts/fmp_download_plan_catalog.py` into  
`/Volumes/LaCie/Aether/data/raw/fmp/plan_catalog/`.

## Categories
- Company Information & Directory
- Financial Statements & Growth
- DCF / Valuations
- SEC Filings
- Fundraisers / Crowdfunding
- Quotes (stock, ETF, MF, commodity, crypto, forex, index) + batch
- Market Performance (sector/industry, PE, movers)
- Market Hours
- Charts (light/full, unadjusted, dividend-adjusted, 1m–4h)
- News (all verticals)
- Analyst (estimates, ratings, targets, grades)
- Earnings / Dividends / Splits / IPOs / Transcripts
- Form 13F / Institutional
- Senate & House disclosures
- Insider Trades
- ETF & Mutual Funds
- COT
- Economics
- ESG
- Technical Indicators
- Indexes / Commodity / Crypto / Forex
- **Bulk** CSV dumps (profile, ratings, DCF, scores, metrics, peers, EOD, statements, …)

## Already partially covered by earlier pipelines
- Core OHLCV universe, VIX, sectors, IWM holdings, ultimate enrichment, batches, market_internals

## Honest gaps on stable API (404 / empty when probed)
- Some alias paths differ from marketing names (`stock-screener` vs `company-screener`)
- A few bulk endpoints require specific params or return empty
- Classic TICK/TRIN not provided as symbols
