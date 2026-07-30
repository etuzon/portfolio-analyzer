#!/usr/bin/env sh
set -eu

mkdir -p /app/certs /app/data

if [ ! -f /app/certs/server.key ] || [ ! -f /app/certs/server.crt ]; then
  openssl req -x509 -newkey rsa:2048 -nodes \
    -keyout /app/certs/server.key \
    -out /app/certs/server.crt \
    -days 365 \
    -subj "/CN=localhost" >/dev/null 2>&1
fi

exec uvicorn app.main:app \
  --host 0.0.0.0 \
  --port 6443 \
  --ssl-keyfile /app/certs/server.key \
  --ssl-certfile /app/certs/server.crt

