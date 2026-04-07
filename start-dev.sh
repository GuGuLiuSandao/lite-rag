#!/usr/bin/env sh
set -eu

SCRIPT_DIR=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
cd "$SCRIPT_DIR"

BACKEND_PORT="${LITE_RAG_API_PORT:-8000}"
BACKEND_HOST="${LITE_RAG_API_HOST:-127.0.0.1}"
FRONTEND_PORT="${VITE_PORT:-5173}"
FRONTEND_HOST="${VITE_HOST:-127.0.0.1}"

BACKEND_PID=""
FRONTEND_PID=""

require_command() {
  if ! command -v "$1" >/dev/null 2>&1; then
    echo "Missing required command: $1" >&2
    exit 1
  fi
}

kill_port_processes() {
  port="$1"
  label="$2"
  pids=$(lsof -ti tcp:"$port" 2>/dev/null || true)
  if [ -n "$pids" ]; then
    echo "Releasing $label port $port"
    kill $pids 2>/dev/null || true
    sleep 1
  fi
}

ensure_frontend_env() {
  if [ ! -f "web/.env" ]; then
    cp "web/.env.example" "web/.env"
  fi
}

ensure_frontend_deps() {
  if [ ! -d "web/node_modules" ]; then
    echo "Installing frontend dependencies..."
    (
      cd "web"
      npm install
    )
  fi
}

cleanup() {
  echo ""
  echo "Stopping services..."
  if [ -n "$BACKEND_PID" ]; then
    kill "$BACKEND_PID" 2>/dev/null || true
  fi
  if [ -n "$FRONTEND_PID" ]; then
    kill "$FRONTEND_PID" 2>/dev/null || true
  fi
}

trap cleanup INT TERM EXIT

require_command lsof
require_command npm
require_command lite-rag-api

ensure_frontend_env
ensure_frontend_deps

kill_port_processes "$BACKEND_PORT" "backend"
kill_port_processes "$FRONTEND_PORT" "frontend"

echo "Starting backend: http://$BACKEND_HOST:$BACKEND_PORT"
lite-rag-api &
BACKEND_PID=$!

echo "Starting frontend: http://$FRONTEND_HOST:$FRONTEND_PORT"
(
  cd "web"
  npm run dev -- --host "$FRONTEND_HOST" --port "$FRONTEND_PORT"
) &
FRONTEND_PID=$!

echo ""
echo "Backend:  http://$BACKEND_HOST:$BACKEND_PORT"
echo "Frontend: http://$FRONTEND_HOST:$FRONTEND_PORT"
echo "Press Ctrl+C to stop both services"

wait "$BACKEND_PID" "$FRONTEND_PID"
