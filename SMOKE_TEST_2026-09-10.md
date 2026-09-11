# SYNORA — Smoke-test hisoboti (2026-09-10)

## Natija: ✅ hammasi yashil

### 1. Avtomatik testlar
| Tekshiruv | Natija |
|---|---|
| Backend `pytest` | **119 passed** (1m52s) |
| Frontend `npx tsc --noEmit` | **0 xato** (exit 0) |

### 2. Docker stack (ishlab turibdi)
| Servis | Holat |
|---|---|
| synora-postgres | healthy (55432) |
| synora-backend | healthy (8000) |
| synora-minio | healthy (9000/9001) |
| synora-frontend | up (3000) |

- `GET /api/v1/health` → `{"status":"ok"}`
- Frontend proxy `localhost:3000/api/v1/health` → backend'ga to'g'ri o'tyapti

### 3. To'liq biznes-oqim (API orqali, real so'rovlar)
1. **Register** → restoran + "Main Branch" avtomatik yaratildi, JWT qaytdi ✅
2. **Menu** → kategoriya + mahsulot (`45000.00` UZS, Decimal) ✅
3. **Table** → stol yaratildi ✅
4. **Order** (`Idempotency-Key` bilan) → `subtotal/total = 90000.00`, stol `OCCUPIED` bo'ldi ✅
5. **Idempotency replay** → aynan o'sha buyurtma qaytdi (dublikat yo'q) ✅
6. **Kitchen** → `PENDING → NEW → PREPARING → READY → SERVED`, ticket board'da ko'rindi ✅
7. **Cash shift** → ochildi (`OPEN`) ✅
8. **Payment** (CASH, to'liq summa) → `status: PAID`, buyurtma avtomatik `COMPLETED` ✅

### 4. Marketing sahifalar
`/uz`, `/uz/features`, `/uz/pricing`, `/uz/login`, `/ru`, `/en/about` — hammasi `200`

## Kichik kuzatuvlar (blocker emas)
- `GET /api/v1/kitchen/tickets` `?branch_id=` query param talab qiladi (xato emas, shunday ishlangan).
- `DRAFT` holatidagi buyurtmani to'lasa `COMPLETED` ga o'tmaydi (faqat `OPEN → COMPLETED` ruxsat). Buyurtma avval `OPEN` bo'lishi kerak. Frontend buni to'g'ri boshqaradimi — tekshirish kerak.
- `/uz/dashboard/*` unauth holatda ham `200` qaytaradi (himoya client-side `DashboardGuard` da). SSR-guard yo'q.

## Keyingi qadam
Backend to'liq ishlaydi. Endi: **register/onboarding frontend sahifasi** (backend `/auth/register` tayyor, UI yo'q).
