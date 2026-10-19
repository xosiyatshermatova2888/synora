#!/bin/sh
set -eu

export PGPASSWORD="${POSTGRES_PASSWORD:?POSTGRES_PASSWORD is required}"
HOST="${POSTGRES_HOST:-postgres}"
USER="${POSTGRES_USER:?POSTGRES_USER is required}"
DB="${POSTGRES_DB:?POSTGRES_DB is required}"
INTERVAL="${BACKUP_INTERVAL_SECONDS:-86400}"
RETENTION_DAYS="${RETENTION_DAYS:-14}"
BACKUP_DIR=/backups
UPLOADS_DIR=/minio-data   # read-only mount of the MinIO volume (optional)

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

    # Uploaded images (menu photos, payment receipts) live in MinIO, not in the
    # database — back them up too, or a restore brings back empty pictures.
    if [ -d "$UPLOADS_DIR" ]; then
        UFILE="$BACKUP_DIR/uploads_${TS}.tar.gz"
        if tar -czf "$UFILE.tmp" -C "$UPLOADS_DIR" . 2>/dev/null; then
            mv "$UFILE.tmp" "$UFILE"
            log "uploads backup complete: $UFILE ($(du -h "$UFILE" | cut -f1))"
        else
            rm -f "$UFILE.tmp"
            log "uploads backup FAILED"
        fi
    fi

    # Prune backups older than the retention window.
    find "$BACKUP_DIR" \( -name 'synora_*.sql.gz' -o -name 'uploads_*.tar.gz' \) -mtime "+${RETENTION_DAYS}" -delete

    sleep "$INTERVAL"
done
