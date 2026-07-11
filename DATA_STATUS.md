# Aether data status

**As of:** 2026-07-10 (Friday after US close)  
**FMP Ultimate expires:** ~2026-07-12 (Sunday)  
**Next US session:** 2026-07-13 (Monday) — **no more FMP market data after sub dies**

## Intent

Friday 2026-07-10 is the **last real session** we can archive under Ultimate.  
Not “one EOD snapshot” — **max bandwidth burn** of everything useful before Sunday.

Primary store: `/Volumes/LaCie/Aether/data/raw/fmp/`  
Never store paid Databento / FMP archives only on the Mac internal drive.

## Done (verified)

| Dataset | Path | Notes |
|--------|------|--------|
| EOD session freeze 2026-07-10 | `eod_2026-07-10/` | 514 OK / 0 fail, ~266 MB (bulk, quotes, charts, breadth, news) |
| Ultimate core pack | `ultimate/` | manifest_done |
| Plan catalog | `plan_catalog/` | ~1.2G, 2424 ok |
| Batch engine | `batches/` | calendars, enrichment, multi-TF OHLCV |
| IWM ~1972 holdings | `iwm_russell2000/` | EOD + screener + top 1m/5m; run_done |
| Universe core | `universe/` | longs + inverses |
| Friday EOD bulk day | `archive_expiry/eod_bulk/2026-07-10.csv` | full market ~59k rows |

## Running overnight / weekend (pre-expiry)

| Job | Log | Output |
|-----|-----|--------|
| **Parallel 5y eod-bulk** (~1326 weekdays) | `logs/eod_bulk_parallel.log` | `archive_expiry/eod_bulk/` |
| Max remaining bulk/FX/crypto/dirs | `logs/archive_max_remaining.log` | `archive_expiry/` |
| Sector ETFs (LaCie) | `logs/sector_etfs.log` | `sector_etfs/` |
| VIX + vol complex (LaCie) | `logs/vix_internals.log` | `vix_internals/` |
| Market internals | `logs/market_internals.log` | `market_internals/` |

Scripts: `scripts/fmp_eod_bulk_parallel.py`, `scripts/fmp_archive_max_remaining.py`,  
`scripts/fmp_eod_snapshot_20260710.py`, etc.

## Honest gaps

- Classic NYSE TICK / TRIN / ADD / equity PCR (`^CPC`) **not on this FMP plan**
- Databento microstructure: separate budget track; not part of FMP expiry burn
- Sector/VIX briefly wrote to Mac `data/fmp/` (disk ~99%); **synced to LaCie**, scripts fixed to prefer LaCie

## After Monday 2026-07-13

FMP historical archive on LaCie is the freeze. Live quotes → Schwab (later) or free/paid replacements.  
Do not assume Ultimate still answers after 2026-07-12.
