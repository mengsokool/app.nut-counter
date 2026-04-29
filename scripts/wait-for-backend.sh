#!/usr/bin/env sh
set -eu

url="${1:-http://127.0.0.1:8787/api/status}"
timeout_seconds="${2:-45}"
started_at="$(date +%s)"

while :; do
  if command -v curl >/dev/null 2>&1 && curl -fsS "$url" >/dev/null 2>&1; then
    exit 0
  fi

  now="$(date +%s)"
  if [ "$((now - started_at))" -ge "$timeout_seconds" ]; then
    echo "Timed out waiting for $url" >&2
    exit 1
  fi

  sleep 1
done
