# Data directory

Market data is **not** stored in git (too large).

## Primary store (source of truth)

```
/Volumes/LaCie/Aether/data/raw/
  fmp/           ← all FMP archives
  databento/     ← all Databento paid data
  PROTECT_DO_NOT_DELETE/
```

**Keep LaCie mounted** whenever downloading or syncing.

## Project pointers (symlinks)

| Path | Points to |
|------|-----------|
| `data/fmp` | `/Volumes/LaCie/Aether/data/raw/fmp` |
| `data/databento` | `/Volumes/LaCie/Aether/data/raw/databento` |

SSD backups (if present) are named `*_ssd_backup_KEEP` — **do not delete** until you are sure LaCie has everything.

## Sync helper

```bash
# Re-sync SSD backups → LaCie and fix symlinks
python scripts/ensure_lacie_sync.py
```

Rules:
1. Never delete Databento `.dbn.zst` or FMP archives on LaCie
2. New downloads must write to LaCie paths (scripts prefer LaCie when mounted)
3. `fmp_eod_bulk_parallel.py` **refuses** to run if LaCie is missing
