# SYNORA — serverga joylash (production) qo'llanmasi

Bu qo'llanma SYNORA'ni internetdagi serverga qanday joylashni, mavjud ma'lumotlarni
(Shirin taom) kompyuterdan serverga qanday ko'chirishni, chek printerni qanday
ulashni va zaxira nusxalarni qanday boshqarishni tushuntiradi.

> **Qisqasi:** VPS + domen → `scripts/gen-env.sh` → `docker compose up` → ma'lumotni
> ko'chirish → restoran kompyuterida print agent. Hammasi ~1–2 soat.

---

## 0. Nima kerak

| Narsa | Izoh |
|---|---|
| **VPS (server)** | Ubuntu 22.04/24.04, kamida 2 vCPU, 4 GB RAM, 40 GB disk. Arzon tarif yetadi. |
| **Domen** | Masalan `synora.uz`. Telegram bot va HTTPS uchun **shart** (Telegram faqat `https://` manzilga yuboradi). |
| **Restoran kompyuteri** | Printer bilan bir Wi-Fi/LAN'da; faqat chek chiqarish uchun (Windows/Mac/Linux, Python 3.8+). |
| **SYNORA to'lov kartasi** | Restoranlar obuna to'lovini shu kartaga o'tkazadi. |

Server restoran ichida bo'lishi shart emas — chek chiqarish **print agent** orqali ishlaydi (4-bo'lim).

---

## 1. Server tayyorlash

1. VPS yarating, `root` yoki sudo-foydalanuvchi sifatida SSH bilan kiring.
2. Domenning **A yozuvi**ni server IP manziliga yo'naltiring (`synora.uz → 203.0.113.10`).
   Bu **docker compose up'dan oldin** bajarilishi kerak — aks holda HTTPS sertifikat olinmaydi.
3. Docker o'rnating:
   ```bash
   curl -fsSL https://get.docker.com | sh
   ```
4. Xavfsizlik devori — faqat SSH, 80 va 443 ochiq:
   ```bash
   ufw allow OpenSSH && ufw allow 80/tcp && ufw allow 443/tcp && ufw --force enable
   ```
   Postgres, MinIO va backend portlari **tashqariga ochilmaydi** (faqat Caddy kirish eshigi).
5. Loyiha fayllarini serverga qo'ying (`git clone` yoki `scp -r`), masalan `/opt/synora`.

## 2. Sozlash va ishga tushirish

```bash
cd /opt/synora
./scripts/gen-env.sh synora.uz        # .env.prod ni YANGI maxfiy kalitlar bilan yaratadi
nano .env.prod                         # quyidagi 3 ta qiymatni to'ldiring
```

`.env.prod` da qo'lda to'ldiriladiganlar:

- `SYNORA_PAYMENT_CARD`, `SYNORA_PAYMENT_HOLDER` — obuna to'lovi kartasi. **Bo'sh qoldirmang va soxta raqam yozmang**: bu karta restoranlarga ko'rsatiladi.
- `WAITER_RESTAURANT_SLUG=shirin-taom` — ofitsiant ilovasi (PIN bilan kirish) qaysi restoranga tegishli ekanini belgilaydi.
- `PAYME_*` — faqat Payme ishlatsangiz. **Ishlatmasangiz `PAYME_KEY` bo'sh qolsin** (har qanday qiymat Payme'ni yoqib yuboradi).

Ishga tushirish:

```bash
docker compose -f docker-compose.prod.yml --env-file .env.prod up -d --build
docker compose -f docker-compose.prod.yml --env-file .env.prod ps     # hammasi Up/healthy bo'lishi kerak
curl -s https://synora.uz/api/v1/health/ready                            # {"status":"ready"}
```

Birinchi ishga tushishda baza migratsiyalari avtomatik bajariladi, sertifikatni Caddy o'zi oladi va yangilaydi.

**O'zingizni platforma administratori qiling** (obuna to'lovlarini tasdiqlash uchun). Avval sayt orqali
oddiy ro'yxatdan o'ting (yoki Shirin taom egasining login'ini ishlating), keyin:

```bash
docker compose -f docker-compose.prod.yml --env-file .env.prod exec backend \
    python -m app.cli make-platform-admin <login>
```

Chiqib-kirgandan keyin menyuda **Platforma** bo'limi paydo bo'ladi. Bu huquqni faqat shu buyruq beradi — API orqali berib bo'lmaydi.

## 3. Mavjud ma'lumotlarni kompyuterdan serverga ko'chirish

Hozir Shirin taom ma'lumotlari (menyu, buyurtmalar, xodimlar, Telegram bot sozlamasi) kompyuteringizdagi
Docker'da turibdi. Ularni ko'chirish:

**Kompyuterda (Git Bash / WSL'da):**

```bash
docker exec synora-postgres pg_dump -U synora -d synora | gzip > synora_dump.sql.gz
docker exec synora-minio tar -czf - -C /data . > uploads.tar.gz       # menyu rasmlari
scp synora_dump.sql.gz uploads.tar.gz user@synora.uz:/opt/synora/
```

**Serverda:**

```bash
cd /opt/synora
./scripts/restore.sh synora_dump.sql.gz uploads.tar.gz
```

Muhim:

1. **Kompyuterdagi SYNORA'ni to'xtating** (`docker compose down`). Bitta Telegram bot ikki joyda bir vaqtda
   ishlay olmaydi: kompyuterdagi "polling" bilan serverdagi "webhook" bir-biriga xalaqit beradi.
2. Server ishga tushganda **har bir ulangan bot avtomatik** `https://synora.uz` ga qayta ulanadi
   (qo'lda hech narsa qilish shart emas). Tekshirish: botga `/start` yuboring.
3. Rasm manzillari (`/uploads/...`) kompyuterdagi bilan bir xil, shuning uchun menyu rasmlari o'zgarishsiz ishlaydi.
4. Eski sinov restoranlari ham ko'chadi. Keraksizlarini ko'chirishdan oldin kompyuterdagi bazadan o'chiring.

Mavjud (ko'chirilgan) restoranlar **Business tarifida, muddatsiz** bo'ladi — ular uchun hech narsa o'zgarmaydi.
Yangi ro'yxatdan o'tganlar 14 kunlik Pro sinov oladi.

## 4. Chek printer (print agent)

Internetdagi server restoran ichidagi `192.168.x.x` printerga to'g'ridan-to'g'ri ulana olmaydi. Shuning uchun
restoranda kichik dastur (**print agent**) ishlaydi: u serverdan "chop etiladigan narsa bormi?" deb so'raydi
(faqat tashqariga chiquvchi HTTPS — routerda hech narsa ochish shart emas), chekni LAN printerga yuboradi.

1. **Printer IP'sini toping.** Restoran Wi-Fi'siga ulangan Windows kompyuterda:
   ```
   powershell -ExecutionPolicy Bypass -File scripts\find-printer.ps1
   ```
   Skript tarmoqdagi 9100-portli qurilmalarni ro'yxatlaydi. Topilmasa — printerning o'z-o'zini tekshirish
   varag'ini chiqaring (odatda FEED tugmasini bosib turib yoqiladi), unda IP yozilgan.
   Routerda printerga **doimiy (static) IP** bering, aks holda qayta yoqilganda manzil o'zgarishi mumkin.
2. SYNORA → **Sozlamalar → Chek printerlar → Qo'shish**: IP, port 9100, **Ulanish usuli: "Print agent orqali"**.
3. Shu bo'limda filial uchun **"Token yaratish"** tugmasini bosing. Token **faqat bir marta** ko'rsatiladi — nusxalab oling.
4. Restoran kompyuterida (Python o'rnatilgan bo'lishi kerak) `scripts/print_agent.py` faylini qo'ying va ishga tushiring:
   ```
   python print_agent.py --server https://synora.uz --token pa_XXXXXXXX
   ```
5. Sozlamalarda **"Agent ulangan"** yozuvi paydo bo'ladi. "Sinov cheki" tugmasi bilan tekshiring.
6. Kompyuter yoqilganda avtomatik ishlashi uchun (Windows):
   ```
   schtasks /Create /SC ONLOGON /TN "SynoraPrintAgent" /TR "python C:\synora\print_agent.py --server https://synora.uz --token pa_XXXXXXXX"
   ```

Agent o'chiq bo'lsa cheklar navbatda kutadi va agent qaytgach chiqadi (6 soatdan eskilari bekor qilinadi).
Token yo'qolsa — yangisini yarating, eskisi darhol ishlamay qoladi.

## 5. Zaxira nusxa (backup)

- **Avtomatik:** `backup` konteyneri har kuni baza (`synora_*.sql.gz`) va rasmlar (`uploads_*.tar.gz`) nusxasini
  Docker volume'ga yozadi, 14 kundan eskilarini o'chiradi.
- **Qo'lda** (xavfli o'zgarishdan oldin): `./scripts/backup.sh` → `./backups/` papkasiga.
- **Serverdan tashqariga ko'chiring!** Server disk bilan birga yo'qolsa, shu diskdagi zaxira ham yo'qoladi.
  Masalan, o'z kompyuteringizdan haftada bir: `scp user@synora.uz:/opt/synora/backups/*.gz .`
- **Tiklash:** `./scripts/restore.sh <baza.sql.gz> [rasmlar.tar.gz]` (mavjud bazani **o'chirib** o'rniga qo'yadi).
- **Zaxira haqiqatan tiklanishini tekshiring** (oyiga bir marta): `./scripts/test-restore.sh <baza.sql.gz>` —
  vaqtinchalik Postgres ochib, nusxani tiklaydi va jadvallardagi qatorlar sonini solishtiradi.

## 6. Kuzatuv

`deploy/uptime.sh` saytning ishlayotganini tekshiradi (chiqish kodi 0 = hammasi joyida). Crontab:

```
*/5 * * * * SYNORA_UPTIME_URL=https://synora.uz /opt/synora/deploy/uptime.sh >> /var/log/synora-uptime.log 2>&1
```

yoki bepul UptimeRobot'da `https://synora.uz/api/v1/health/ready` manzilini kuzating.
Loglar: `docker compose -f docker-compose.prod.yml --env-file .env.prod logs -f backend`.

## 7. Yangilash va orqaga qaytish

```bash
./scripts/backup.sh                                                       # 1) avval zaxira
git pull   # yoki yangi fayllarni scp qiling
docker compose -f docker-compose.prod.yml --env-file .env.prod up -d --build   # 2) yangilash (migratsiya avtomatik)
```

Muammo bo'lsa: `./scripts/restore.sh` bilan 1-qadamdagi zaxirani qaytaring va oldingi versiya fayllari bilan qayta `up -d --build`.

## 8. Obuna to'lovlari qanday ishlaydi

1. Restoran egasi **Obuna** bo'limida tarifni tanlaydi → SYNORA kartasi va summa ko'rsatiladi.
2. Karta orqali o'tkazma qiladi va **chek rasmini** yuklaydi.
3. Siz **Platforma → To'lovlar** bo'limida chekni ko'rib, **Tasdiqlash** yoki **Rad etish** bosasiz.
4. Tasdiqlangach tarif darhol faollashadi (muddat shu paytdan, yoki muddat tugamagan bo'lsa uning ustiga 1 oy/1 yil qo'shiladi).
5. Muddat tugasa: **7 kun imtiyoz** (hammasi ishlaydi, ogohlantirish chiqadi), keyin tizim **faqat ko'rish** rejimiga o'tadi
   (yangi buyurtma, jumladan Telegram/QR orqali ham, qabul qilinmaydi) — to'lov qilingach darhol tiklanadi.

Qo'lda o'zgartirish (sovg'a muddat, sinovni uzaytirish): **Platforma → Restoranlar → O'zgartirish**.

## 9. Xavfsizlik ro'yxati

- [ ] `.env.prod` faqat serverda, `chmod 600`, git'ga qo'shilmagan.
- [ ] SSH uchun parol o'rniga kalit; `ufw` faqat 22/80/443.
- [ ] **Telegram bot tokeni chatda ochiq yozilgan bo'lsa**, @BotFather → `/revoke` bilan yangisini oling va Sozlamalardan qayta ulang.
- [ ] Zaxira nusxalar serverdan tashqarida ham saqlanadi va `test-restore.sh` bilan sinab ko'rilgan.
- [ ] Platforma administratori faqat ishonchli odam(lar)da.

## 10. Muammolar

| Alomat | Sabab / yechim |
|---|---|
| Sayt `https` da ochilmaydi | A yozuvi serverga yo'naltirilmagan yoki 80/443 yopiq. `docker compose ... logs caddy` ni ko'ring. |
| Bot javob bermaydi | Kompyuterdagi SYNORA hali yoqiq (polling bilan to'qnashadi) yoki `PUBLIC_APP_URL` `https://` emas. Backend logida "telegram webhook registered" qatori bo'lishi kerak. |
| Chek chiqmaydi | Sozlamalarda "Agent ulangan" ko'rinyaptimi? Restoran kompyuteridagi agent oynasida xato bormi? Printer IP o'zgarmaganmi? |
| "Obuna muddati tugagan" (402) | Obuna sahifasida to'lov qiling yoki Platforma'dan muddatni uzaytiring. |
| Rasmlar ko'rinmaydi | `uploads.tar.gz` tiklanganini va `/uploads/...` manzili ochilishini tekshiring. |
