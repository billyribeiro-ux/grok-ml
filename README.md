# Aether / grok-ml

Market Intelligence Brain — day-trading tops/bottoms decoder (ML + self-learning design).

## Repo contents
- `scripts/` — FMP Ultimate + Databento download pipelines
- `docs/` — architecture notes, dashboard prompt, data status
- Data lives on external LaCie: `/Volumes/LaCie/Aether/` (not in git)

## Setup
```bash
python3 -m venv .venv
source .venv/bin/activate
pip install requests pandas pyarrow python-dotenv tqdm databento
cp .env.example .env   # add API keys
```

## Remote
https://github.com/billyribeiro-ux/grok-ml.git
