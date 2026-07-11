# Aether data status

## Canonical root (external LaCie)

```
/Volumes/LaCie/Aether/
├── README.txt
├── config/
│   ├── paths.json
│   └── universe.json
├── data/
│   ├── raw/
│   │   ├── fmp/
│   │   │   ├── universe/        # core + inverses
│   │   │   ├── vix_internals/
│   │   │   ├── sector_etfs/
│   │   │   └── enrichment/
│   │   └── databento/
│   │       ├── purchased/
│   │       └── quotes/
│   ├── processed/
│   │   ├── features/
│   │   ├── labels/
│   │   └── datasets/
│   ├── models/
│   │   ├── checkpoints/
│   │   └── exports/
│   ├── signals/
│   └── backtests/
└── logs/
    ├── downloads/
    └── training/
```

## Local project links

| Local path | Target |
|------------|--------|
| `~/Desktop/grok-ml/Aether-data` | `/Volumes/LaCie/Aether` |
| `~/Desktop/grok-ml/data/databento` | `/Volumes/LaCie/Aether/data/raw/databento` |
| `~/Desktop/grok-ml/data/fmp` | Active FMP download workdir (mirrored to LaCie) |

**Keep LaCie mounted** when downloading or training.

## Note

Older path `/Volumes/LaCie/aether-data` is **retired**. Use **`/Volumes/LaCie/Aether`** only.
