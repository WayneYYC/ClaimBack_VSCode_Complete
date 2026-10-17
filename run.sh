#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")"
if [ ! -d .venv ]; then python3 -m venv .venv; fi
source .venv/bin/activate
if [ ! -f .venv/.claimback_dependencies_installed ]; then
  python -m pip install -r requirements.txt
  touch .venv/.claimback_dependencies_installed
fi
if [ ! -f .env ]; then cp .env.example .env; fi
exec python -m uvicorn backend.app:app --reload --host 127.0.0.1 --port 8000
