#!/bin/sh
# Starts the sandbox portal (internal only) and the executor (public).
set -e
PORT="${PORT:-7860}"
# Citizen links must point at the public address. Set CIVIC_PUBLIC_URL explicitly in production;
# on Hugging Face Spaces, SPACE_HOST is used when it is present.
if [ -z "$CIVIC_PUBLIC_URL" ]; then
  if [ -n "$SPACE_HOST" ]; then CIVIC_PUBLIC_URL="https://$SPACE_HOST"; else CIVIC_PUBLIC_URL="http://localhost:$PORT"; fi
fi
export CIVIC_PUBLIC_URL
mkdir -p "${CIVIC_DATA_DIR:-/tmp/civic-data}"

SANDBOX_PORT="$(echo "${SANDBOX_URL:-http://127.0.0.1:7861}" | sed 's/.*://')"
uv run --no-sync uvicorn sandbox_portal.app:app --host 127.0.0.1 --port "$SANDBOX_PORT" --log-level warning &

exec uv run --no-sync uvicorn executor.api:app --host 0.0.0.0 --port "$PORT" --proxy-headers --forwarded-allow-ips='*'
