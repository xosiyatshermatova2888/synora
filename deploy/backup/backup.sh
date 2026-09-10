#!/bin/sh
set -eu

export PGPASSWORD="${POSTGRES_PASSWORD:?POSTGRES_PASSWORD is required}"
HOST="${POSTGRES_HOST:-postgres}"
USER="${POSTGRES_USER:?POSTGRES_USER is required}"
DB="${POSTGRES_DB:?POSTGRES_DB is required}"
INTERVAL="${BACKUP_INTERVAL_SECONDS:-86400}"
RETENTION_DAYS="${RETENTION_DAYS:-14}"
BACKUP_DIR=/backups

log() { echo "[backup $(date -u +%FT%TZ)] $*"; }

while true; do
    mkdir -p "$BACKUP_DIR"
    TS="$(date -u +%F_%H%M)"
    FILE="$BACKUP_DIR/synora_${TS}.sql.gz"

    log "starting pg_dump of $DB (host $HOST)"
    if pg_dump -h "$HOST" -U "$USER" -d "$DB" | gzip > "$FILE.tmp"; then
        mv "$FILE.tmp" "$FILE"
        SIZE=$(du -h "$FILE" | cut -f1)
        log "backup complete: $FILE ($SIZE)"
    else
        rm -f "$FILE.tmp"
        log "backup FAILED for $DB — will retry in $INTERVAL seconds"
    fi

    # Prune backups older than the retention window.
    find "$BACKUP_DIR" -name 'synora_*.sql.gz' -mtime "+${RETENTION_DAYS}" -delete

    sleep "$INTERVAL"
done