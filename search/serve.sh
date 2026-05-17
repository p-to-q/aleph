#!/usr/bin/env bash
# Aleph live backend, one command (Scheme A: Mac + cloudflared tunnel).
#
#   bash search/serve.sh
#
# Starts search/server.py, opens a public cloudflared tunnel, wires the local
# frontend (web/.env.local) automatically, and prints the value to paste into
# Vercel. Keep this terminal open during the demo; Ctrl+C stops everything.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PY="${ALEPH_PY:-python3}"
PORT=8000
ENVFILE="$ROOT/web/.env.local"
CFLOG="$(mktemp -t aleph_cf.XXXXXX)"
SRVLOG="$ROOT/.aleph_server.log"
SRV=""
CF=""

cleanup() { [ -n "$CF" ] && kill "$CF" 2>/dev/null || true
            [ -n "$SRV" ] && kill "$SRV" 2>/dev/null || true; }
trap cleanup EXIT INT TERM

# 0. preflight
"$PY" "$ROOT/search/preflight.py" || { echo "[serve] preflight failed"; exit 1; }
command -v cloudflared >/dev/null 2>&1 || { echo "[serve] cloudflared not found → run: brew install cloudflared"; exit 1; }

# 1. backend (reuse if already healthy)
if curl -sf "http://localhost:$PORT/health" >/dev/null 2>&1; then
  echo "[serve] backend already running on :$PORT — reusing"
else
  echo "[serve] starting backend (server.py) — first run loads the model …"
  "$PY" -u "$ROOT/search/server.py" > "$SRVLOG" 2>&1 &
  SRV=$!
  for _ in $(seq 1 90); do
    curl -sf "http://localhost:$PORT/health" >/dev/null 2>&1 && break
    sleep 1
  done
  curl -sf "http://localhost:$PORT/health" >/dev/null 2>&1 \
    || { echo "[serve] backend failed to warm — see $SRVLOG"; exit 1; }
  echo "[serve] backend warm on :$PORT"
fi

# 2. public tunnel
echo "[serve] opening cloudflared quick tunnel …"
cloudflared tunnel --url "http://localhost:$PORT" > "$CFLOG" 2>&1 &
CF=$!
URL=""
for _ in $(seq 1 40); do
  URL="$(grep -Eo 'https://[a-z0-9-]+\.trycloudflare\.com' "$CFLOG" | head -1 || true)"
  [ -n "$URL" ] && break
  sleep 1
done
[ -n "$URL" ] || { echo "[serve] tunnel URL not found — see $CFLOG"; exit 1; }

# 3. wire local frontend + print the Vercel value
printf 'NEXT_PUBLIC_SEARCH_API=%s/search\n' "$URL" > "$ENVFILE"

cat <<EOF

================ Aleph live backend is up ================
 tunnel        : $URL
 health        : $URL/health
 local wired → : $ENVFILE   (restart 'npm run dev' to pick it up)

 Deployed site (Vercel → Settings → Environment Variables, then redeploy):
   NEXT_PUBLIC_SEARCH_API=$URL/search

 Quick-tunnel URLs change every run. Keep this window open during the demo.
 Ctrl+C stops the backend + tunnel.
==========================================================
EOF

wait "$CF"
