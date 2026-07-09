# woody-monitor

WOODY Monitor Bot – Telegram bot that tracks WOODY token swaps, big buys, big sells, liquidity changes and new holders on the MultiversX blockchain.

## Installation & Setup

1. **Clonează repository-ul și intră în proiect.**
   ```bash
   git clone <repo-url>
   cd woody-monitor
   ```
2. **Creează un mediu Python izolat.**
   ```bash
   python3 -m venv .venv
   source .venv/bin/activate
   ```
3. **Instalează dependențele.**
   ```bash
   pip install -r requirements.txt
   ```
4. **Creează configurația locală.**
   ```bash
   cp .env.example .env
   ```
5. **Editează `.env`.** Setează obligatoriu `TELEGRAM_BOT_TOKEN` și, pentru meniul privat complet, `ADMIN_TELEGRAM_ID`. Completează `TELEGRAM_PRIVATE_CHAT_ID` și/sau `TELEGRAM_GROUP_CHAT_ID` în funcție de unde vrei alertele.
6. **Pornește botul.**
   ```bash
   python main.py
   ```
7. **Verifică runtime-ul în Telegram.** Rulează `/status` ca admin ca să confirmi conexiunea, destinațiile de alerte și eventualele avertizări.

## Docker

Repository-ul include un `Dockerfile` multi-stage și un `.dockerignore` pentru rulare containerizată sigură prin variabile de mediu.

### Variantă recomandată

1. Creează `.env` din `.env.example` și completează secretele.
2. Construiește imaginea:
   ```bash
   docker build -t woody-monitor .
   ```
3. Rulează containerul:
   ```bash
   docker run --rm --env-file .env -p 8080:8080 -v "$(pwd)/data:/app/data" woody-monitor
   ```

### `.dockerignore`

Build-ul Docker folosește `.dockerignore` pentru a exclude secretele locale, fișierele Git, cache-urile Python, documentația și directoarele de editor din contextul trimis către daemon. Verifică acest fișier înainte de build ca să nu incluzi accidental `.env` sau alte fișiere locale sensibile în imagine.

### Dockerfile recomandat

Repository-ul include un `Dockerfile` multi-stage care:
- instalează dependențele într-un virtualenv separat în etapa `builder`;
- copiază virtualenv-ul în imaginea finală `python:3.12-slim`;
- rulează aplicația cu user non-root `app`;
- creează `/app/data` pentru fișiere persistente, recomandat de montat ca volum.

```dockerfile
# syntax=docker/dockerfile:1

FROM python:3.12-slim AS builder

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

RUN python -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

COPY requirements.txt .
RUN pip install --upgrade pip \
    && pip install -r requirements.txt

FROM python:3.12-slim AS runtime

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PATH="/opt/venv/bin:$PATH" \
    DATA_DIR=/app/data

WORKDIR /app

RUN addgroup --system app \
    && adduser --system --ingroup app --home /app app \
    && mkdir -p /app/data \
    && chown -R app:app /app

COPY --from=builder /opt/venv /opt/venv
COPY --chown=app:app . .

USER app

EXPOSE 8080

CMD ["python", "main.py"]
```

### Notă pentru Docker Compose

Când se adaugă `docker-compose.yml`, montează `./data` ca volum persistent și pasează `.env` prin `env_file`. Expune portul `PUBLIC_STATUS_PORT` dacă folosești endpoint-ul public de status.

## Environment variables

Toate variabilele cunoscute sunt listate în `.env.example`. Cele mai importante sunt:

| Variabilă | Descriere |
| --- | --- |
| `TELEGRAM_BOT_TOKEN` | Tokenul botului Telegram primit de la BotFather. Obligatoriu. |
| `ADMIN_TELEGRAM_ID` | User ID Telegram care primește meniul privat complet de administrare. |
| `TELEGRAM_PRIVATE_CHAT_ID` | Chat ID pentru alerte private. Necesită `ENABLE_PRIVATE_ALERTS=true`. |
| `TELEGRAM_GROUP_CHAT_ID` | Chat ID pentru grup/supergroup. De obicei începe cu `-100`. Necesită `ENABLE_GROUP_ALERTS=true`. |
| `ENABLE_PRIVATE_ALERTS` | Activează/dezactivează trimiterea alertelor în privat (`true`/`false`). |
| `ENABLE_GROUP_ALERTS` | Activează/dezactivează trimiterea alertelor în grup (`true`/`false`). |
| `MVX_API` | Endpoint REST MultiversX folosit pentru tranzacții, tokenuri, conturi și VM queries. |
| `WS_URL` | Endpoint WebSocket MultiversX pentru evenimente live. |
| `COINGECKO_EGLD_API`, `BINANCE_EGLD_PRICE_API`, `COINBASE_EGLD_SPOT_API` | Surse pentru prețul EGLD/USD și fallback-uri. |
| `WOODY_TOKEN_ID`, `WEGLD_TOKEN_ID`, `USDC_TOKEN_HINT`, `JEX_TOKEN_ID`, `MEX_TOKEN_ID`, `BOBER_TOKEN_ID`, `ONE_TOKEN_ID` | Identificatori de token folosiți pentru clasificare, prețuri și context de piață. |
| `ROUTER_ADDRESS` | Adresa routerului DEX tratată ca adresă tehnică. |
| `XEXCHANGE_POOL_ADDRESS`, `ONEDEX_POOL_ADDRESS`, `WOODY_USDC_POOL_ADDRESS`, `WOODY_BOBER_POOL_ADDRESS`, `WOODY_JEX_POOL_ADDRESS`, `WOODY_MEX_POOL_ADDRESS`, `WOODY_OLV_POOL_ADDRESS` | Adresele pool-urilor monitorizate pentru preț, lichiditate și LP snapshots. |
| `XEXCHANGE_LP_TOKEN_ID` | LP token ID manual pentru WOODY/EGLD xExchange; util când autodetectarea prin VM query nu este disponibilă. |
| `ONEDEX_BURN_ADDRESS` | Adresă tehnică/burn OneDex ignorată în clasificări. |
| `EXTRA_TECHNICAL_ADDRESSES` | Listă separată prin virgule cu adrese tehnice suplimentare de exclus din detecția walleturilor reale. |
| `PRICE_URL`, `CHART_URL`, `TWITTER_URL`, `BUY_XEXCHANGE_URL`, `BUY_XOXNO_URL` | Linkuri afișate în meniuri și mesaje Telegram. |
| `BANNER_IMAGE`, `BUY_IMAGE`, `SELL_IMAGE`, `BIG_BUY_IMAGE`, `BIG_SELL_IMAGE`, `NEW_HOLDER_IMAGE` | Fișiere imagine folosite în alerte și meniuri. |
| `MIN_ALERT_USD`, `BIG_ALERT_USD`, `WHALE_ALERT_USD`, `SUPER_WHALE_ALERT_USD` | Praguri USD pentru alerte normale, mari, whale și super-whale. |
| `ROOT_SETTLE_SECONDS`, `ROOT_MAX_AGE_SECONDS`, `ROOT_PROCESSING_CONCURRENCY` | Controlează agregarea și procesarea tranzacțiilor root. |
| `CHECK_HOLDERS_INTERVAL`, `WS_RECONNECT_DELAY`, `API_TIMEOUT_SECONDS` | Interval pentru verificarea holderilor, delay de reconectare WebSocket și timeout HTTP. |
| `PRICE_TTL_SECONDS`, `POOL_SNAPSHOT_TTL_SECONDS`, `EGLD_PRICE_SOFT_TTL_SECONDS`, `EGLD_PRICE_HARD_TTL_SECONDS`, `TX_DETAILS_CACHE_TTL_SECONDS` | TTL-uri pentru cache-uri de preț, pool, EGLD și detalii tranzacții. |
| `LP_HOLDERS_PAGE_SIZE`, `LP_HOLDERS_MAX_PAGES` | Paginarea citirii holderilor LP din API. |
| `LP_SNAPSHOT_CHECK_INTERVAL`, `LP_SNAPSHOT_FILE`, `LP_REWARDS_FILE`, `LP_EXPORT_REWARD_POOL_EGLD` | Configurarea snapshot-urilor LP, fișierului de recompense și fondului implicit pentru export CSV. |
| `GLOBAL_LP_DUST_EGLD` | Prag minim EGLD estimat sub care pozițiile LP globale sunt ignorate ca dust. |
| `DATA_DIR`, `LAST_ALERTS_FILE`, `TOP_VOLUME_FILE`, `VOLUME_HISTORY_FILE`, `ROOT_CACHE_FILE` | Locații pentru date persistente locale. |
| `PUBLIC_STATUS_FILE`, `PUBLIC_STATUS_INTERVAL`, `PUBLIC_STATUS_HOST`, `PUBLIC_STATUS_PORT`, `PORT` | Configurarea statusului public HTTP/JSON; `PORT` este util pe platforme PaaS, iar `PUBLIC_STATUS_PORT` are prioritate. |

## Alerte și în grupul de Telegram (nu doar privat)

Botul suportă trimiterea alertelor în **două destinații în paralel**: chat privat și grup.

Setează variabilele de mediu astfel:

```env
# Token bot
TELEGRAM_BOT_TOKEN=...

# Admin Telegram user id (private full menu)
ADMIN_TELEGRAM_ID=123456789

# Chat privat (opțional)
TELEGRAM_PRIVATE_CHAT_ID=123456789
ENABLE_PRIVATE_ALERTS=true

# Grup
TELEGRAM_GROUP_CHAT_ID=-1001234567890
ENABLE_GROUP_ALERTS=true
```

### Pași rapizi

1. Adaugă botul în grupul de Telegram.
2. Dă-i dreptul de a trimite mesaje în grup.
3. Ia `chat_id`-ul grupului (de regulă începe cu `-100...`).
4. Pune valorile în `.env` și repornește botul.

### Verificare în runtime

La pornire, comanda `/status` îți arată dacă sunt active:
- `Private alerts: ON/OFF`
- `Group alerts: ON/OFF`

Dacă `Group alerts` e `OFF`, verifică:
- `ENABLE_GROUP_ALERTS=true`
- `TELEGRAM_GROUP_CHAT_ID` setat corect
- botul este prezent în grup și nu e restricționat.

## Meniuri separate (public vs admin)

### Grup public (`group` / `supergroup`)
Meniul afișează doar:
- 💰 Price
- 💧 Liquidity
- 🪙 LP Holders
- 🏆 LP Leaderboard
- 📸 LP Snapshots
- 🎁 LP Rewards
- 📄 LP Export
- 👥 Holders
- 📊 Chart
- 🛒 Buy
- 🤖 Bot Status

Sunt ascunse din meniu (dar păstrate în cod): Top Holders, Last Buy/Sell, Volume 24h, Top Volume, Pools, Diagnostics și alte opțiuni tehnice.

### Privat admin (`private` + `user_id == ADMIN_TELEGRAM_ID`)
Adminul vede meniul complet, cu toate butoanele existente.

### Privat non-admin (`private` + alt `user_id`)
Utilizatorii non-admin văd meniul public simplificat.

## Monitorizare LP holders WOODY/EGLD xExchange

Botul poate monitoriza holderii LP pentru pool-ul WOODY/EGLD de pe xExchange:

```text
erd1qqqqqqqqqqqqqpgqvmgnk26tfvz6sj5yasw7p6yfvqpv628d2jpsnvmeaz
```

### Comenzi Telegram
- `/lp_holders` — afișează holderii LP, cantitatea de LP deținută și valoarea estimată în EGLD.
- `/lp_leaderboard` — afișează clasamentul lunar după media LP din snapshot-urile lunii curente.
- `/lp_snapshots` — listează snapshot-urile salvate pentru luna curentă și programul automat de snapshot.
- `/lp_rewards X` — calculează distribuția proporțională pentru un fond lunar de `X` EGLD, fără să trimită EGLD automat. Exemplu: `/lp_rewards 5`.
- `/lp_export` — generează CSV cu wallet address, LP mediu lunar, procent din total și recompensa calculată în EGLD.

### Snapshot-uri automate
Botul salvează snapshot-uri automat în `data/lp_snapshots.json` pe:
- data de 1 a lunii;
- data de 15 a lunii;
- ultima zi a lunii.

Fiecare snapshot include data, wallet address, cantitatea de LP token și valoarea estimată în EGLD.

### Configurare opțională
```env
# Dacă autodetectarea LP token-ului prin VM query nu este disponibilă, setează manual identificatorul LP:
XEXCHANGE_LP_TOKEN_ID=...

# Frecvența jobului care verifică dacă trebuie salvat snapshot-ul:
LP_SNAPSHOT_CHECK_INTERVAL=3600

# Dimensiunea paginilor pentru citirea holderilor LP:
LP_HOLDERS_PAGE_SIZE=100
LP_HOLDERS_MAX_PAGES=20
```
