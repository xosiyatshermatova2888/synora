#!/usr/bin/env bash
# Create .env.prod for a new server with freshly generated secrets.
#
#   ./scripts/gen-env.sh synora.example.uz
#
# Refuses to overwrite an existing .env.prod (it holds your live secrets).
set -euo pipefail

DOMAIN="${1:-}"
if [ -z "$DOMAIN" ]; then
    echo "usage: $0 <domain>      e.g. $0 synora.example.uz" >&2
    exit 2
fi
case "$DOMAIN" in
    http*|*/*) echo "give the bare domain, without https:// or a path" >&2; exit 2 ;;
esac

cd "$(dirname "$0")/.."
OUT="${ENV_OUT:-.env.prod}"
if [ -e "$OUT" ]; then
    echo "$OUT already exists — not overwriting. Delete it first if you really want new secrets." >&2
    exit 1
fi
command -v openssl >/dev/null || { echo "openssl is required" >&2; exit 1; }

# URL/shell-safe random strings (no / + = so they survive .env parsing and URLs).
rand() { openssl rand -base64 "$1" | tr -d '/+=\n' | cut -c1-"$2"; }

JWT="$(rand 96 80)"
PG_PASS="$(rand 48 32)"
MINIO_PASS="$(rand 48 32)"

cp .env.prod.example "$OUT"
# `|` as the sed delimiter: none of the generated values contain it.
sed -i \
    -e "s|^DOMAIN=.*|DOMAIN=${DOMAIN}|" \
    -e "s|^PUBLIC_APP_URL=.*|PUBLIC_APP_URL=https://${DOMAIN}|" \
    -e "s|^CORS_ORIGINS=.*|CORS_ORIGINS=https://${DOMAIN}|" \
    -e "s|^POSTGRES_PASSWORD=.*|POSTGRES_PASSWORD=${PG_PASS}|" \
    -e "s|^JWT_SECRET_KEY=.*|JWT_SECRET_KEY=${JWT}|" \
    -e "s|^MINIO_ROOT_PASSWORD=.*|MINIO_ROOT_PASSWORD=${MINIO_PASS}|" \
    "$OUT"
chmod 600 "$OUT"

echo "Wrote $OUT for https://${DOMAIN} (permissions 600)."
echo
echo "Still to fill in by hand:"
echo "  - SYNORA_PAYMENT_CARD / SYNORA_PAYMENT_HOLDER   (card restaurants pay you to)"
echo "  - WAITER_RESTAURANT_SLUG                        (e.g. shirin-taom)"
echo "  - PAYME_*                                       (only if you use Payme)"
echo
echo "Then:  docker compose -f docker-compose.prod.yml --env-file .env.prod up -d --build"
