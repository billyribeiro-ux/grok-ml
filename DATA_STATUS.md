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

## History depth (explicit)

| Layer | Range | Notes |
|-------|-------|--------|
| **Full-market eod-bulk** | **2019-01-01 → 2026-07-10** | ~1960 weekdays; primary scanner history |
| Core deep history (per symbol) | 2019-01-01 → 2026-07-10 | after eod-bulk; `deep_history_2019/` |
| Earlier packs (ultimate/IWM/etc.) | mostly ~5y (~2021+) | still useful; eod-bulk covers older marketwide |

Why 2019: pre-COVID → COVID crash → recovery → 2022 bear → AI regime.  
2020 alone is not enough for “how regimes changed.”

## Running overnight / weekend (pre-expiry)

| Job | Log | Output |
|-----|-----|--------|
| **Parallel eod-bulk 2019→2026-07-10** | `logs/eod_bulk_parallel.log` | `archive_expiry/eod_bulk/` |
| Deep core history (queued after eod) | `logs/deep_history_2019.log` | `deep_history_2019/` |
| Max remaining bulk/FX/crypto/dirs | `logs/archive_max_remaining.log` | `archive_expiry/` (done) |
| Sector / VIX / internals (queued) | respective logs | LaCie paths |

Env: `FMP_EOD_START=2019-01-01` `FMP_EOD_END=2026-07-10` `FMP_EOD_WORKERS=3` `FMP_EOD_RPS=2.5`

Scripts: `scripts/fmp_eod_bulk_parallel.py`, `scripts/fmp_core_deep_history.py`,  
`scripts/fmp_archive_max_remaining.py`, `scripts/fmp_eod_snapshot_20260710.py`, etc.

## Honest gaps

- Classic NYSE TICK / TRIN / ADD / equity PCR (`^CPC`) **not on this FMP plan**
- Databento microstructure: separate budget track; not part of FMP expiry burn
- Sector/VIX briefly wrote to Mac `data/fmp/` (disk ~99%); **synced to LaCie**, scripts fixed to prefer LaCie

## After Monday 2026-07-13

FMP historical archive on LaCie is the freeze. Live quotes → Schwab (later) or free/paid replacements.  
Do not assume Ultimate still answers after 2026-07-12.
