#!/usr/bin/env bash
# Aleph dev startup — brings up all 3 servers in tmux panes.
# Usage:  ./start.sh
# Requires: tmux, node/pnpm, python3 with venvs already set up.

set -e
REPO="$(cd "$(dirname "$0")" && pwd)"

# ── helper: kill any existing process on a port ─────────────────────────────
kill_port() {
  local port=$1
  lsof -ti tcp:"$port" | xargs kill -9 2>/dev/null || true
}

kill_port 3000
kill_port 8000
kill_port 8010

# ── start all 3 in tmux ─────────────────────────────────────────────────────
SESSION="aleph"

tmux new-session -d -s "$SESSION" -x 220 -y 50 2>/dev/null || true
tmux rename-window -t "$SESSION:0" "aleph"

# Pane 0 — Next.js (port 3000)
tmux send-keys -t "$SESSION:0" "cd '$REPO/web' && pnpm dev" Enter

# Pane 1 — MLX search server (port 8000)
tmux split-window -t "$SESSION:0" -v
tmux send-keys -t "$SESSION:0.1" "cd '$REPO/search' && source .venv/bin/activate && python3 server.py" Enter

# Pane 2 — Claude API server (port 8010)
tmux split-window -t "$SESSION:0" -h
tmux send-keys -t "$SESSION:0.2" "cd '$REPO/apps/api' && source .venv/bin/activate && uvicorn aleph_api.main:app --host 0.0.0.0 --port 8010 --reload" Enter

# ── attach ───────────────────────────────────────────────────────────────────
echo "All 3 servers starting in tmux session '$SESSION'."
echo "  port 3000  →  Next.js frontend"
echo "  port 8000  →  MLX search server"
echo "  port 8010  →  Claude/custom API"
echo ""
echo "Run:  tmux attach -t $SESSION"
echo "Or open http://localhost:3000 — it'll be live in ~10 seconds."

tmux attach -t "$SESSION"
