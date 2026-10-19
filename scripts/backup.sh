#!/usr/bin/env bash
# One-off backup of the PRODUCTION stack to ./backups on the server:
#   - synora_<time>.sql.gz   full database dump
#   - uploads_<time>.tar.gz  uploaded images (menu photos, payment receipts)
#
# (The `backup` container already does this every night into a Docker volume;
# use this script before risky changes, or to copy backups off the server.)
#
#   ./scripts/backup.sh
set -euo pipefail

cd "$(dirname "$0")/.."
COMPOSE=(docker compose -f docker-compose.prod.yml --env-file .env.prod)
OUT="${BACKUP_OUT:-./backups}"
TS="$(date -u +%F_%H%M%S)"
mkdir -p "$OUT"

echo "Dumping database ..."
"${COMPOSE[@]}" exec -T postgres sh -c 'pg_dump -U "$POSTGRES_USER" -d "$POSTGRES_DB"' | gzip > "$OUT/synora_${TS}.sql.gz"

echo "Archiving uploads ..."
"${COMPOSE[@]}" exec -T minio sh -c 'tar -czf - -C /data .' > "$OUT/uploads_${TS}.tar.gz"

# A truncated/empty file would silently pass for a backup — verify both.
gzip -t "$OUT/synora_${TS}.sql.gz"
gzip -t "$OUT/uploads_${TS}.tar.gz"
[ "$(gzip -dc "$OUT/synora_${TS}.sql.gz" | wc -c)" -gt 1000 ] || { echo "database dump looks empty!" >&2; exit 1; }

ls -lh "$OUT/synora_${TS}.sql.gz" "$OUT/uploads_${TS}.tar.gz"
echo "OK. Copy these off the server (e.g. scp) — a backup on the same disk dies with the disk."
