# Multi-strategy data vision

## Products (same data lake, different models later)

| Machine | Horizon | Primary data |
|---------|---------|----------------|
| **Aether day-trader** | Intraday tops/bottoms | 1m/5m, microstructure (Databento), VIX, flow |
| **Swing trader** | Multi-day–weeks | EOD bulk, fundamentals, earnings, ratings, PE sector |
| **Small-cap scanner** | IWM / Russell 2000 | Full IWM holdings EOD + screener table + denser tape on top names |
| **Future products** | TBD | Same archive; feature-select per strategy |

**Rule:** Download ≠ use. Archive everything before FMP expiry (2026-07-12). Each model chooses features later.

## Live / paper execution (later)

- **Charles Schwab Developer API** for live quotes, orders, simulator when ready.
- Historical training = FMP + Databento archive on disk.
- Do not mix live keys into git; use `.env` only.

## Storage

| Store | Role |
|-------|------|
| **LaCie #1** (`/Volumes/LaCie/Aether`) | Primary hot archive for training |
| **LaCie #2** | Overflow when #1 fills; mirror critical folders |
| **iCloud 2TB** | Cold backup of compressed archives (not for high-IOPS training) |
| **Internal SSD** | Code only (`~/Desktop/grok-ml`) |

## Layout

```
/Volumes/LaCie/Aether/data/raw/fmp/
  universe/  iwm_russell2000/  sector_etfs/  vix_internals/
  market_internals/  ultimate/  batches/  plan_catalog/  archive_expiry/
/Volumes/LaCie/Aether/data/raw/databento/purchased_v2/
```
