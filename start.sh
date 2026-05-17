#!/usr/bin/env bash
# Aleph dev startup — brings up all 3 servers in tmux panes.
# Usage:  ./start.sh
# Requires: lsof, npm, python3 with venvs already set up (tmux optional).

set -e
REPO="$(cd "$(dirname "$0")" && pwd)"

# ── helper: kill any existing process on a port ─────────────────────────────
kill_port() {
  local port=$1
  lsof -ti tcp:"$port" | xargs kill -9 2>/dev/null || true
}

wait_port() {
  local port=$1
  local name=$2
  local log=$3
  local tries=20
  for _ in $(seq 1 "$tries"); do
    if lsof -ti tcp:"$port" >/dev/null 2>&1; then
      return 0
    fi
    sleep 0.5
  done
  echo "Error: $name did not bind to port $port. Check $log." >&2
  return 1
}

kill_port 3000
kill_port 3001
kill_port 8000
kill_port 8010

# ── start all 3 in tmux ─────────────────────────────────────────────────────
SESSION="aleph"

if ! command -v tmux >/dev/null 2>&1; then
  echo "tmux not found; starting servers in the background."
  nohup bash -lc "cd '$REPO/web' && npm run dev -- --hostname 0.0.0.0 --port 3000" \
    > "$REPO/.aleph-web.log" 2>&1 &
  nohup bash -lc "cd '$REPO/search' && source .venv/bin/activate && python3 server.py" \
    > "$REPO/.aleph-mlx.log" 2>&1 &
  nohup bash -lc "cd '$REPO/apps/api' && source .venv/bin/activate && ALEPH_MLX_SEARCH_URL=http://127.0.0.1:8000/search uvicorn aleph_api.main:app --host 0.0.0.0 --port 8010 --reload" \
    > "$REPO/.aleph-api.log" 2>&1 &

  wait_port 3000 "Next.js frontend" "$REPO/.aleph-web.log"
  wait_port 8000 "MLX search server" "$REPO/.aleph-mlx.log"
  wait_port 8010 "Aleph API" "$REPO/.aleph-api.log"

  echo "All 3 servers starting in the background."
  echo "  port 3000  ->  Next.js frontend"
  echo "  port 8000  ->  MLX search server"
  echo "  port 8010  ->  Aleph API"
  echo ""
  echo "Logs:"
  echo "  $REPO/.aleph-web.log"
  echo "  $REPO/.aleph-mlx.log"
  echo "  $REPO/.aleph-api.log"
  echo ""
  echo "Open http://localhost:3000 once startup completes."
  exit 0
fi

tmux new-session -d -s "$SESSION" -x 220 -y 50 2>/dev/null || true
tmux rename-window -t "$SESSION:0" "aleph"

# Pane 0 — Next.js frontend (port 3000)
tmux send-keys -t "$SESSION:0" "cd '$REPO/web' && npm run dev -- --hostname 0.0.0.0 --port 3000" Enter

# Pane 1 — MLX search server (port 8000)
tmux split-window -t "$SESSION:0" -v
tmux send-keys -t "$SESSION:0.1" "cd '$REPO/search' && source .venv/bin/activate && python3 server.py" Enter

# Pane 2 — Aleph API server (port 8010)
tmux split-window -t "$SESSION:0" -h
tmux send-keys -t "$SESSION:0.2" "cd '$REPO/apps/api' && source .venv/bin/activate && ALEPH_MLX_SEARCH_URL=http://127.0.0.1:8000/search uvicorn aleph_api.main:app --host 0.0.0.0 --port 8010 --reload" Enter

# ── attach ───────────────────────────────────────────────────────────────────
echo "All 3 servers starting in tmux session '$SESSION'."
echo "  port 3000  →  Next.js frontend"
echo "  port 8000  →  MLX search server"
echo "  port 8010  →  Aleph API"
echo ""
echo "Run:  tmux attach -t $SESSION"
echo "Or open http://localhost:3000 — it'll be live in ~10 seconds."

tmux attach -t "$SESSION"
