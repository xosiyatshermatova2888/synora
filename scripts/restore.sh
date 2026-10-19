#!/usr/bin/env bash
# Restore a backup into the PRODUCTION stack. DESTRUCTIVE: replaces the live
# database (and, if given, the uploaded images).
#
#   ./scripts/restore.sh synora_2026-10-12_0300.sql.gz [uploads_2026-10-12_0300.tar.gz]
#
# Use it to (a) recover from a disaster, or (b) move a restaurant's data from
# another machine (e.g. the PC it ran on) to a new server.
set -euo pipefail

DUMP="${1:-}"
UPLOADS="${2:-}"
if [ -z "$DUMP" ] || [ ! -f "$DUMP" ]; then
    echo "usage: $0 <database.sql.gz> [uploads.tar.gz]" >&2
    exit 2
fi
[ -z "$UPLOADS" ] || [ -f "$UPLOADS" ] || { echo "uploads archive not found: $UPLOADS" >&2; exit 2; }
gzip -t "$DUMP"

cd "$(dirname "$0")/.."
COMPOSE=(docker compose -f docker-compose.prod.yml --env-file .env.prod)

if [ "${3:-}" != "--yes" ]; then
    echo "This will ERASE the current production database and replace it with:"
    echo "    $DUMP"
    [ -z "$UPLOADS" ] || echo "    $UPLOADS (images)"
    read -r -p "Type 'restore' to continue: " answer
    [ "$answer" = "restore" ] || { echo "aborted"; exit 1; }
fi

echo "Stopping the application (database stays up) ..."
"${COMPOSE[@]}" stop backend frontend caddy

echo "Recreating the database ..."
"${COMPOSE[@]}" exec -T postgres sh -c 'dropdb -U "$POSTGRES_USER" --if-exists --force "$POSTGRES_DB" && createdb -U "$POSTGRES_USER" "$POSTGRES_DB"'

echo "Loading the dump ..."
gzip -dc "$DUMP" | "${COMPOSE[@]}" exec -T postgres sh -c 'psql -U "$POSTGRES_USER" -d "$POSTGRES_DB" -v ON_ERROR_STOP=1 -q' >/dev/null

if [ -n "$UPLOADS" ]; then
    echo "Restoring uploaded images ..."
    "${COMPOSE[@]}" exec -T minio sh -c 'cd /data && tar -xzf - ' < "$UPLOADS"
fi

echo "Starting everything (the backend applies any newer migrations and re-registers Telegram webhooks) ..."
"${COMPOSE[@]}" up -d
echo "Restore finished."
