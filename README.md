# SYNORA

SYNORA is an AI-powered restaurant operating system for POS, kitchen, inventory, CRM, analytics, and AI-assisted business management. The product targets independent and multi-branch restaurants, starting from a single table service flow: menu → tables → orders → kitchen display → payments, all tenant-scoped per restaurant. The backend is a FastAPI REST API with a real-time kitchen-display WebSocket; the frontend is a Next.js (App Router) application served in uz/ru/en locales at `synora.app`.

---

## Requirements

The project is developed and tested against these exact versions:

| Tool | Version | Used by |
|------|---------|---------|
| Python | **3.11.x** (3.11.9 in development; Docker image `python:3.11-slim`) | Backend |
| Node.js | **20+** (Docker image `node:20-alpine`; Node 24 works for local dev) | Frontend |
| Docker + Docker Compose | Docker 29.x, Compose v2 (v5.3.0 tested) | Full stack |
| PostgreSQL | **16** (compose image `postgres:16-alpine`) | Database |

Frontend pins Next.js **16.3.4** / React **19.2.8** via `package-lock.json`; backend pins every Python dependency exactly in `backend/requirements.txt`.

---

## Quick start (Docker)

The fastest way to run the whole stack (PostgreSQL + FastAPI + Next.js):

```bash
# 1. Clone and configure
cp .env.example backend/.env
#   (edit backend/.env and set a real JWT_SECRET_KEY —
#    generate one with: python -c "import secrets; print(secrets.token_urlsafe(64))")

# 2. Start everything
docker compose up --build

# 3. Open
open http://localhost:3000        # frontend (uz is the default locale)
open http://localhost:8000/api/docs # Swagger UI (only when DEBUG=true)
```

Five running services:

- `postgres` — PostgreSQL 16, host port `55432`, named volume for persistence.
- `backend` — FastAPI on host port `8000`. Runs Alembic migrations automatically at startup, then starts uvicorn (single worker — see Architecture decisions).
- `frontend` — Next.js (standalone build) on host port `3000`. Proxies `/api/*` and `/files/*` to the backend service over the Docker network (`http://backend:8000`).
- `minio` — MinIO S3-compatible object storage on host port `9000` (S3 API) and `9001` (web console). Provides `synora-uploads` bucket with public-read access for product images.
- `minio-init` — one-shot container that creates the bucket and sets download permissions, then exits.

`docker compose up` needs no manual steps beyond providing `backend/.env`. Shut down with `docker compose down` (add `-v` to also delete the Postgres and uploads volumes).

---

## Local development without Docker

Both paths work independently — the Docker stack and local dev are separate and can run side by side.

### Backend (FastAPI)

Requires Python 3.11 and a reachable PostgreSQL. For a local Postgres, either run the compose database alone (`docker compose up postgres`) or install your own on `localhost:5432` and adjust `DATABASE_URL`.

```bash
cd backend
python -m venv .venv
.venv\Scripts\activate          # Windows; on macOS/Linux: source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env            # if you haven't already; set DATABASE_URL / JWT_SECRET_KEY

alembic upgrade head            # apply migrations
uvicorn app.main:app --reload --port 8000
```

The app reads `backend/.env` automatically (pydantic-settings). The default `DATABASE_URL` points at `localhost:55432` — the port that `docker compose up postgres` exposes.

### Frontend (Next.js)

```bash
# from the repo root
npm install
npm run dev                     # http://localhost:3000
```

The dev server proxies `/api/*` (and `/files/*`) to the backend. By default `API_URL` is `http://localhost:8000`; override it for your shell if your backend runs elsewhere:

```bash
$env:API_URL="http://localhost:8000"   # PowerShell
# or
export API_URL=http://localhost:8000   # bash/zsh
```

---

## Environment variables

Only the backend reads a `.env` file; the frontend reads `API_URL` from its environment (set in `docker-compose.yml` or the shell). Source of truth: `backend/.env.example`, and a copy at the repo root (`.env.example`) for reference.

| Variable | Default | Required | Purpose |
|----------|---------|----------|---------|
| `APP_NAME` | `SYNORA API` | no | Service name shown in `/` and docs |
| `APP_ENV` | `dev` | yes | `dev` / `test` / `prod` — gates logging level and docs exposure |
| `DEBUG` | `true` | yes | When `true`, exposes `/api/docs`. Error responses never include stack traces (full detail stays in server logs); keep `false` in production to hide the docs |
| `DATABASE_URL` | `postgresql+asyncpg://synora:synora@localhost:55432/synora` | yes | Async SQLAlchemy URL. **`docker-compose` overrides this** with the container-network URL |
| `POSTGRES_USER` / `POSTGRES_PASSWORD` / `POSTGRES_DB` / `POSTGRES_PORT` | `synora` / `synora` / `synora` / `55432` | no | Used only by `docker-compose.yml`; also referenced by the backend entrypoint |
| `BACKEND_PORT` / `FRONTEND_PORT` | `8000` / `3000` | no | Host-side ports used by compose |
| `API_URL` | `http://localhost:8000` | no | Frontend backends to proxy `/api/*`. **Inside Docker compose it is set to `http://backend:8000`** |
| `JWT_SECRET_KEY` | `change-me` | **yes in prod** | HS256 signing key. Generate a 64-char urlsafe secret; never ship the default |
| `JWT_ALGORITHM` | `HS256` | no | JWT signing algorithm |
| `ACCESS_TOKEN_EXPIRE_MINUTES` | `30` | no | Access-token lifetime |
| `REFRESH_TOKEN_EXPIRE_DAYS` | `30` | no | Refresh-token lifetime (stored hashed) |
| `LOGIN_RATE_LIMIT_MAX_ATTEMPTS` | `5` | no | Failed logins before lockout |
| `LOGIN_RATE_LIMIT_WINDOW_SECONDS` | `900` | no | Sliding window for the above |
| `LOGIN_LOCKOUT_SECONDS` | `900` | no | Lockout duration after the limit |
| `REFRESH_COOKIE_SECURE` | `true` | no | Set `false` for plain-http local dev (must stay `true` in prod) |
| `CORS_ORIGINS` | `http://localhost:3000,http://127.0.0.1:3000` | no | Comma-separated allowed origins; no `*` in production |
| `UPLOAD_DIR` | `uploads` | no | Local disk folder for uploaded images (used as fallback when S3 is not configured) |
| `PUBLIC_APP_URL` | `http://localhost:3000` | no | Public-facing base URL; used in password-reset email links. Set to `https://<domain>` in production |
| `SMTP_HOST` | (empty = log-only mode) | no | SMTP server host for password-reset emails. Leave blank to log reset links instead of sending |
| `SMTP_PORT` | `587` | no | SMTP port |
| `SMTP_USER` | (empty) | no | SMTP login username |
| `SMTP_PASSWORD` | (empty) | no | SMTP login password |
| `SMTP_FROM_EMAIL` | `SYNORA <no-reply@synora.app>` | no | Sender address for password-reset emails |
| `SMTP_USE_TLS` | `true` | no | Enable STARTTLS on the SMTP connection |
| `PASSWORD_RESET_EXPIRE_MINUTES` | `45` | no | Lifetime of a password-reset token (minutes) |
| `S3_ENDPOINT` | (empty = local disk) | no | S3-compatible endpoint URL (e.g. `http://minio:9000`). Leave blank to use local disk |
| `S3_BUCKET` | (empty) | no | S3 bucket name for uploads |
| `S3_ACCESS_KEY` | (empty) | no | S3 access key ID |
| `S3_SECRET_KEY` | (empty) | no | S3 secret access key |
| `S3_REGION` | `us-east-1` | no | S3 bucket region |
| `S3_PUBLIC_URL_BASE` | (empty) | no | Public base URL for uploaded objects (e.g. `http://localhost:9000` in dev or `https://files.example.com` in prod) |
| `S3_USE_PATH_STYLE` | `true` | no | Use path-style S3 URLs (`/bucket/key`) instead of virtual-hosted (`bucket.s3.amazonaws.com`) |
| `PAYME_CHECKOUT_BASE_URL` | `https://test.paycom.uz` | no | Sandbox: `https://test.paycom.uz`. Live: `https://checkout.paycom.uz` |
| `PAYME_LOGIN` | (empty) | no | Payme Basic-auth login (usually `Paycom`) |
| `PAYME_KEY` | (empty) | no | Payme Basic-auth password (merchant key) |
| `PAYME_MERCHANT_ID` | (empty) | no | Payme cashier/merchant ID for checkout link paths |
| `PAYME_IS_TEST` | `true` | no | `true` = sandbox; `false` = live. In production (`APP_ENV=prod`) a configured key + `true` causes a startup error |

`docker-compose.yml` substitutes the `POSTGRES_*`, `BACKEND_PORT`, and `FRONTEND_PORT` values from your shell environment or the repo-root `.env` when present.

---

## Database & migrations

Migrations use Alembic against the async engine (`backend/alembic/env.py` reads `DATABASE_URL` from settings; all models import in `app/models`).

```bash
cd backend

# Create a new migration after changing a model
alembic revision --autogenerate -m "describe change"
#   — always review the generated file before committing

# Apply all pending migrations
alembic upgrade head

# Apply N steps / roll back one step
alembic upgrade +1
alembic downgrade -1
```

Inside Docker, migrations run automatically from `backend/entrypoint.sh` before uvicorn starts — you don't run `alembic` by hand against the container.

---

## Running tests

Backend (pytest, uses its own SQLite/aiosqlite database — no Postgres needed):

```bash
cd backend
pytest                      # full suite (119 tests)
```

Frontend type-check (as strict as CI gets today):

```bash
npx tsc --noEmit
```

There is no frontend unit-test framework yet (see Known limitations).

---

## API docs

Swagger UI: **`http://localhost:8000/api/docs`** (only visible when `DEBUG=true`). ReDoc is disabled; raw OpenAPI JSON is at `/openapi.json`.

All routes are versioned under `/api/v1` in `backend/app/api/v1/`. The frontend proxies `/api/*` same-origin, so browser requests can carry the httpOnly refresh cookie without CORS. Adding new endpoints = add a module in `app/api/v1/` and register it in `app/api/v1/api.py`.

---

## Project structure

```
backend/
  app/
    api/v1/          REST routers: auth, restaurants, menu, tables,
                     orders, payments, kitchen, uploads, health
    core/            config, logging, security (Argon2id + JWTs), tenancy docs
    database/        async engine/session, declarative Base + mixins
    models/          SQLAlchemy models (all tenant-scoped via restaurant_id)
    repositories/    TenantScopedRepository base + per-module repos
    schemas/         Pydantic request/response models
    services/        business logic (orders/kitchen/payments/auth/...)
    websocket/       kitchen WebSocket manager + routes (auth before accept)
    utils/           errors, in-memory rate limiters
  alembic/           migration scripts
  tests/             pytest suite (auth, isolation, RBAC, orders, payments, kitchen)
  requirements.txt

src/
  app/[locale]/      all routes under a next-intl locale segment (uz/ru/en)
  components/        marketing + dashboard components
  lib/api.ts         typed fetch client (in-memory access token + auto-refresh)
  lib/auth-context.tsx
  messages/          uz / ru / en translations
  proxy.ts           next-intl locale middleware
```

---

## Architecture decisions

These look unusual on purpose. Do not "fix" them without revisiting the reasoning.

- **Async SQLAlchemy + asyncpg, end to end.** FastAPI routes → services → repositories → ORM are all `async` on one `AsyncSession` per request. A synchronous ORM would force blocking calls in async handlers; keeping one stack avoids `MissingGreenlet`-style bugs. If a future module must use sync libraries, isolate them in their own worker/process, don't mix them into request handlers.

- **Argon2id password hashing.** `argon2-cffi`'s Argon2id (memory-hard, resistant to GPU cracking), chosen over bcrypt per the auth master plan. Never downgrade to md5/sha-family or plaintext.

- **Access token in memory, refresh token in an httpOnly cookie.** The client keeps the short-lived JWT only in memory (never localStorage — that's XSS-readable). The opaque refresh token travels exclusively in a `httpOnly` + `SameSite=Strict` + `Secure` cookie scoped to `/api/v1/auth`; the server stores only its SHA-256 hash. A stolen access token expires in 30 minutes; a stolen refresh cookie is useless without the cookie being delivered (XSS can't read it), and refresh tokens rotate on every use.

- **Tenant-scoped repository base (`core/tenancy.py` + `repositories/base.py`).** Every table carries `restaurant_id`; every tenant-scoped `get/list/update/delete` **requires** `restaurant_id` and applies it as the first WHERE clause. There is no public query without it, and cross-tenant access surfaces as HTTP 404 (never 403) so resource existence is never disclosed. New modules must inherit `TenantScopedRepository` — never hand-roll filters in routes.

- **RBAC as a data model, not hardcoded strings.** Permissions (`orders.read`, `menu.create`, …) and role templates (`OWNER`, `MANAGER`, `CASHIER`, `KITCHEN`, `WAITER`) live in DB tables seeded idempotently at startup; route decorators reference permission codes via `require_permission(...)`. New roles can be composed without redeploying code, and `perms` are baked into the JWT so authorization never needs a DB round-trip per request.

- **Money is `Decimal` / `Numeric(12,2)` everywhere.** Currency arithmetic is banker-safe at the DB and API layer; `float` is banned because binary floats can't represent decimal amounts exactly. The only money formatting on the frontend is display-only.

- **Idempotency-key requirement on order creation.** Order creation is the one operation that must never double-apply on a retry. Clients send an `Idempotency-Key` header; the server keys it to `(restaurant_id, key)` with a 24h window and returns the original order for repeats — the whole create (items, snapshots, totals, table claim, key row) is one transaction.

- **Single uvicorn worker locally.** The startup seed (global permissions/roles) and the in-memory rate limiters / WebSocket fan-out are single-process by design. Running more than one worker races the seed on a fresh DB and splits rate-limiting state. Scale out only after moving rate limits and the WS registry to Redis/an external store.

- **Broadcast only after commit.** Kitchen WebSocket events are emitted only after the driving DB transaction commits, so a client can never observe a change that rolls back.

---

## Known limitations / not-yet-built

Honest current state (nothing here is a bug; it is deliberately deferred scope):

- **Inventory & CRM & Analytics** — permission codes exist (`inventory.*`, `analytics.read`), but no modules, models, or pages exist yet.
- **QR / Telegram / Delivery / Online ordering entry points** — `source` is already an enum on orders (`POS|WAITER|QR|TELEGRAM|DELIVERY|ONLINE`) but only POS/WAITER are practiced today; no QR scanning or Telegram bot integration is wired.
- **Multi-instance WebSocket scaling** — `app/websocket/manager.py` is in-process memory; multiple replicas would not share connections. Same for the rate limiters.
- **Payment gateways (Click, Stripe, etc.)** — Payme integration is live and tested in sandbox; Click, Stripe and other gateways are not wired yet.
- **Branch-specific pricing** — `branch_price_overrides` is a documented extension point, not built.
- **AI features** — the marketing site describes AI capabilities; only the marketing/demo pages exist, no product AI.
- **Marketing pages** — real content now lives on `/features`, `/pricing`, `/about`, `/ai`, `/docs`, `/demo`, `/blog`, `/help`; `/pricing` annual toggle awaits a business decision; `/blog` shows a "coming soon" landing (no articles yet).
- **Frontend unit tests** — none yet; backend has pytest coverage, the frontend only has `tsc --noEmit`.
- **Login/register rate limiting** — login has a strict per-account+per-IP limiter; registration relies on the general per-IP limit only.
- **Cash-shift UI** — built (open/close in the Payments page), but closing is manual and optimistic-lock-gated; no shift-report export yet.
- **Production SMTP** — requires client-supplied SMTP credentials; without them, password-reset emails are logged only (development fallback).
- **S3 uploads** — MinIO wiring is complete for dev; production requires client-supplied S3 bucket and credentials.

---

## Production deployment

Production uses `docker-compose.prod.yml` which excludes host-side ports, adds Caddy as the TLS edge, and runs scheduled backups in a sidecar. The stack is validated with `docker compose -f docker-compose.prod.yml config`.

### Required client-supplied items

| Item | Purpose | How to set |
|------|---------|------------|
| Domain name | Caddy auto-provisions TLS certificates via Let's Encrypt | Set `DOMAIN` in `.env.prod` |
| SMTP credentials | Password-reset email delivery (real inbox, not log-only) | Set `SMTP_HOST`, `SMTP_PORT`, `SMTP_USER`, `SMTP_PASSWORD`, `SMTP_FROM_EMAIL` in `.env.prod` |
| Payme live merchant account | Accept real payments (sandbox is for development only) | Set `PAYME_LOGIN`, `PAYME_KEY`, `PAYME_MERCHANT_ID`, `PAYME_IS_TEST=false`, `PAYME_CHECKOUT_BASE_URL=https://checkout.paycom.uz` in `.env.prod` |
| JWT secret key | Token signing (must not be `change-me`) | Set `JWT_SECRET_KEY` — generate with `python -c "import secrets; print(secrets.token_urlsafe(64))"` |
| Object storage (optional) | Product images via S3-compatible storage | Set `S3_ENDPOINT`, `S3_BUCKET`, `S3_ACCESS_KEY`, `S3_SECRET_KEY`, `S3_PUBLIC_URL_BASE` in `.env.prod` |

### Deploy steps

```bash
# 1. Clone to the server and configure
cp .env.prod.example .env.prod
#   edit .env.prod — fill in every variable above
#   ensure deploy/Caddyfile matches your domain

# 2. Start the stack
docker compose -f docker-compose.prod.yml up -d --build

# 3. Verify
docker compose -f docker-compose.prod.yml logs -f backend   # watch migrations + startup
docker compose -f docker-compose.prod.yml ps                 # all 6 services healthy
curl -I https://<your-domain>                                 # Caddy TLS working
```

### Backup and restore

Backups run automatically inside the `backup` sidecar — a `pg_dump` gzip archive every `BACKUP_INTERVAL_SECONDS` (default 3600). Restoring is a single `pg_restore` against the running Postgres container.

```bash
# List available backups on the server
docker exec synora-backup ls /backups | head

# Restore from a specific backup
docker exec -i synora-postgres pg_restore -U synora -d synora --clean --if-exists \
  < <(docker exec synora-backup cat /backups/<filename>.dump.gz | gunzip)
```

Set `RETENTION_DAYS` in `.env.prod` to control how many days of backups are kept (default 7).

### Architecture summary (production)

```
Internet
  │
  ▼
Caddy (TLS + reverse proxy, port 443)
  ├── /api/*          → backend:8000
  ├── /files/*        → backend:8000 (local disk) or minio:9000 (S3)
  ├── /images/*       → minio:9000  (public-read bucket, strip_prefix)
  └── /*              → frontend:3000 (Next.js SSR)

postgres:5432        (no host port — internal only)
minio:9000           (internal S3 API)
minio:9001           (console — dev only, not exposed in prod)
backup               (pg_dump sidecar, writes to /backups volume)
```