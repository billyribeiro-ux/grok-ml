#!/usr/bin/env bash
# Local Aether Python backend (status / research API).
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"
if [[ -f .venv/bin/activate ]]; then
  # shellcheck disable=SC1091
  source .venv/bin/activate
fi
export PYTHONUNBUFFERED=1
export PYTHONPATH="${ROOT}/packages${PYTHONPATH:+:$PYTHONPATH}"
exec python -m aether.dev_server --host 127.0.0.1 --port "${AETHER_API_PORT:-8787}"
