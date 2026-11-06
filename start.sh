#!/usr/bin/env bash
# One-command local run on Linux/Mac. By default: SQLite database + mock AI (no Postgres, Docker or API key needed).
# To use Supabase, put its connection string and keys in backend/.env (see docs/SUPABASE_SETUP.md) and run it again.
# Needs: uv (installs Python 3.11 for you) and Node.js 18+.   Usage:  ./start.sh
set -euo pipefail
cd "$(dirname "$0")"
ROOT=$(pwd)

command -v uv >/dev/null || { echo "uv is missing. Install it:  curl -LsSf https://astral.sh/uv/install.sh | sh  (then open a new terminal)"; exit 1; }
command -v npm >/dev/null || { echo "Node.js is missing. See the README (Linux install steps)."; exit 1; }

echo "==> Backend: Python 3.11 environment + packages"
cd "$ROOT/backend"
[ -d .venv ] || uv venv --python 3.11 .venv
echo "    downloading Python packages (about 100 MB, can take several minutes the first time)..."
uv pip install --python .venv/bin/python -r requirements.txt
if [ ! -f .env ]; then
  sed 's#^DATABASE_URL=.*#DATABASE_URL=sqlite:///./recruiter.db#' .env.example > .env
  echo "    created backend/.env (SQLite, mock AI)"
fi

DB_URL=$(grep -E '^DATABASE_URL=' .env | head -1 | cut -d= -f2-)
if [[ "$DB_URL" != sqlite* ]]; then
  echo "==> Checking your database and keys (backend/.env)"
  .venv/bin/python -m scripts.check_setup || { echo; echo "Fix the problems above in backend/.env, then run ./start.sh again."; exit 1; }
fi

echo "==> Database tables + demo data"
.venv/bin/alembic upgrade head
# demo data is added once per database (so switching to Supabase seeds it too)
DB_KEY=$(printf '%s' "$DB_URL" | sha256sum | cut -c1-16)
if ! grep -qx "$DB_KEY" .seeded 2>/dev/null; then
  echo "    adding demo accounts and sample candidates..."
  if .venv/bin/python -m scripts.seed --reset > seed.log 2>&1; then echo "$DB_KEY" >> .seeded
  else tail -20 seed.log; echo "Adding demo data failed (full log: backend/seed.log)"; exit 1; fi
fi

echo "==> Frontend packages"
cd "$ROOT/web"
[ -f .env ] || cp .env.example .env
if [ ! -d node_modules ]; then
  echo "    downloading JavaScript packages (can take a few minutes the first time)..."
  npm install --no-audit --no-fund
fi

echo "==> Starting backend on http://localhost:8000 and frontend on http://localhost:5173"
cd "$ROOT/backend"
.venv/bin/uvicorn app.main:app --port 8000 &
BACKEND=$!
trap 'kill $BACKEND 2>/dev/null' EXIT
cd "$ROOT/web"
echo
echo "    Open http://localhost:5173   (password for all demo accounts: Demo1234)"
echo "    recruiter@demo.com  |  candidate5@demo.com (live interview)"
echo "    Press Ctrl+C to stop."
echo
npm run dev -- --port 5173 --strictPort
