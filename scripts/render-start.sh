#!/usr/bin/env bash
set -euo pipefail

cd /srv/backend

python -m alembic upgrade head
python -m app.seed

python -m uvicorn app.main:app --host 127.0.0.1 --port 8000 &
api_pid=$!

caddy run --config /etc/caddy/Caddyfile --adapter caddyfile &
proxy_pid=$!

stop_processes() {
    kill -TERM "$api_pid" "$proxy_pid" 2>/dev/null || true
    wait "$api_pid" "$proxy_pid" 2>/dev/null || true
}

trap stop_processes EXIT INT TERM

wait -n "$api_pid" "$proxy_pid"

