# Aether / grok-ml

Market Intelligence Brain — day-trading tops/bottoms decoder (ML + self-learning design).

## Repo contents
- `packages/aether/` — **engine spine (F0/F1)**: paths, integrity, loaders, daily features, feature store
- `scripts/` — FMP Ultimate + Databento download pipelines
- `docs/` — Mars-grade vision, theoretical ceiling, V∞ architecture
- Data lives on external LaCie: `/Volumes/LaCie/Aether/` (not in git)

## Design docs (read in order)
1. `docs/AETHER_MARS_GRADE_VISION.md`
2. `docs/AETHER_ENGINE_THEORETICAL_CEILING.md`
3. `docs/AETHER_ENGINE_V_INFINITY.md`

## Setup
```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
pip install requests tqdm databento   # download scripts
cp .env.example .env   # add API keys
```

## F0 / F1 (engine spine)
Requires LaCie mounted at `/Volumes/LaCie/Aether`.

```bash
# F0 — integrity inventory → LaCie data/processed/integrity/
python -m aether.cli integrity

# F1 — daily features for core symbols from eod-bulk → feature store
python -m aether.cli f1 --start 2018-01-01 --end 2026-07-10

# unit tests (no LaCie required)
pytest -q

# offline engine flight (mock data — no LaCie, no downloads)
python -m aether.cli engine-flight

# real LaCie eod-bulk flight (requires mount)
python -m aether.cli lacie-flight --symbols SPY,QQQ,IWM,SQQQ,SH --start 2018-01-01 --end 2026-07-10

# monorepo (pnpm) — frontend + backend together
pnpm install
pnpm dev:all
# front  → http://127.0.0.1:5173  (SvelteKit cockpit)
# back   → http://127.0.0.1:8787  (Python status/research API)
#   curl http://127.0.0.1:8787/health
#   curl http://127.0.0.1:8787/api/status

# or separately:
pnpm dev:front
pnpm dev:backend
```


### Engine (data-pluggable)
- `packages/aether/engine/` — money (cents), data protocol, mock + LaCie sources,
  labels, regime state, logistic scorer, scored policy, risk governor,
  execution costs, paper backtest, walk-forward pipeline, telemetry
- `apps/cockpit/` — Svelte 5 / SvelteKit mission control (reads latest flight JSON)

### Chief-architect mode
Build continues without waiting on download agents. Data plugs in when ready.

Processed output (LaCie, not git):
- `/Volumes/LaCie/Aether/data/processed/feature_store/`
- `/Volumes/LaCie/Aether/data/processed/integrity/`

## Remote
https://github.com/billyribeiro-ux/grok-ml.git
