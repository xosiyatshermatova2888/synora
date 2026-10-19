#!/usr/bin/env bash
# Prove that a backup can really be restored — before you need it.
#
# Dumps a RUNNING Postgres container, loads that dump into a brand-new throwaway
# Postgres container, and compares row counts of every table. Touches nothing
# that is running; the throwaway container is always removed.
#
#   ./scripts/test-restore.sh                        # dev stack (synora-postgres)
#   SRC_CONTAINER=synora-prod-postgres-1 ./scripts/test-restore.sh
#   ./scripts/test-restore.sh path/to/synora_xxx.sql.gz   # test a real backup file
set -euo pipefail

SRC_CONTAINER="${SRC_CONTAINER:-synora-postgres}"
SRC_USER="${SRC_USER:-synora}"
SRC_DB="${SRC_DB:-synora}"
FILE="${1:-}"
TMP_NAME="synora-restore-test-$$"
WORK="$(mktemp -d)"

cleanup() {
    docker rm -f "$TMP_NAME" >/dev/null 2>&1 || true
    rm -rf "$WORK"
}
trap cleanup EXIT

if [ -n "$FILE" ]; then
    [ -f "$FILE" ] || { echo "file not found: $FILE" >&2; exit 2; }
    cp "$FILE" "$WORK/dump.sql.gz"
else
    echo "1/4 dumping $SRC_CONTAINER/$SRC_DB ..."
    docker exec "$SRC_CONTAINER" pg_dump -U "$SRC_USER" -d "$SRC_DB" | gzip > "$WORK/dump.sql.gz"
fi
gzip -t "$WORK/dump.sql.gz"
echo "    dump: $(du -h "$WORK/dump.sql.gz" | cut -f1)"

echo "2/4 starting a throwaway Postgres ($TMP_NAME) ..."
docker run -d --name "$TMP_NAME" -e POSTGRES_USER=restore -e POSTGRES_PASSWORD=restore -e POSTGRES_DB=restore \
    postgres:16-alpine >/dev/null
for _ in $(seq 1 40); do
    docker exec "$TMP_NAME" pg_isready -U restore -d restore -q 2>/dev/null && break
    sleep 1
done
docker exec "$TMP_NAME" pg_isready -U restore -d restore -q || { echo "throwaway database did not start" >&2; exit 1; }
# Postgres restarts once during first init; wait until it answers a real query.
for _ in $(seq 1 20); do
    docker exec "$TMP_NAME" psql -U restore -d restore -tAc "select 1" >/dev/null 2>&1 && break
    sleep 1
done

echo "3/4 restoring into it ..."
# Dumps made by pg_dump (plain SQL) own objects by the SOURCE role; restore with
# --no-owner semantics by loading as the throwaway superuser and ignoring owner.
gzip -dc "$WORK/dump.sql.gz" | sed -e "/^ALTER .* OWNER TO /d" -e "/^SET default_table_access_method/d" \
    | docker exec -i "$TMP_NAME" psql -U restore -d restore -v ON_ERROR_STOP=1 -q >/dev/null

echo "4/4 comparing row counts ..."
COUNT_SQL="select table_name from information_schema.tables where table_schema='public' and table_type='BASE TABLE' order by 1"
TABLES="$(docker exec "$TMP_NAME" psql -U restore -d restore -tAc "$COUNT_SQL")"
[ -n "$TABLES" ] || { echo "FAIL: restored database has no tables" >&2; exit 1; }

fail=0
total=0
printf '    %-32s %10s %10s\n' TABLE RESTORED SOURCE
for table in $TABLES; do
    restored="$(docker exec "$TMP_NAME" psql -U restore -d restore -tAc "select count(*) from \"$table\"")"
    total=$((total + restored))
    if [ -z "$FILE" ]; then
        source_count="$(docker exec "$SRC_CONTAINER" psql -U "$SRC_USER" -d "$SRC_DB" -tAc "select count(*) from \"$table\"")"
        mark=""
        [ "$restored" = "$source_count" ] || { mark="  <-- MISMATCH"; fail=1; }
        printf '    %-32s %10s %10s%s\n' "$table" "$restored" "$source_count" "$mark"
    else
        printf '    %-32s %10s %10s\n' "$table" "$restored" "-"
    fi
done

version="$(docker exec "$TMP_NAME" psql -U restore -d restore -tAc "select version_num from alembic_version" 2>/dev/null || true)"
echo "    schema version (alembic): ${version:-<none>}"

if [ "$fail" -ne 0 ]; then
    echo "FAIL: restored data differs from the source." >&2
    exit 1
fi
if [ "$total" -eq 0 ]; then
    echo "FAIL: every table is empty — this backup contains no data." >&2
    exit 1
fi
echo "OK: the backup restores cleanly ($(echo "$TABLES" | wc -l | tr -d ' ') tables, $total rows)."
