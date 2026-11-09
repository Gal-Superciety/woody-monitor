# woody-monitor

WOODY Monitor Bot – Telegram bot that tracks WOODY token swaps, big buys, big sells, liquidity changes and new holders on the MultiversX blockchain.

## Installation & Setup

1. **Clonează repository-ul și intră în proiect.**
   ```bash
   git clone <repo-url>
   cd woody-monitor
   ```
2. **Creează un mediu Python izolat.** Necesită Python 3.10 sau mai nou; producția Docker folosește Python 3.12.
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
| `ENABLE_COMMUNITY_WELCOME` | Trimite un mesaj când utilizatori noi intră într-un grup sau supergrup. |
| `ENABLE_MORNING_BRIEF`, `MORNING_BRIEF_CHAT_ID`, `MORNING_BRIEF_HOUR`, `MORNING_BRIEF_TIMEZONE` | Raport de piață zilnic; implicit la 09:00 Europe/Berlin în `TELEGRAM_GROUP_CHAT_ID`. |
| `COINGECKO_DAILY_MARKET_API`, `COINGECKO_GLOBAL_MARKET_API` | Sursele CoinGecko pentru variațiile pe 24h și indicatorii globali. |
| `tzdata` | Baza IANA folosită pentru programarea corectă a orei locale și a schimbării de oră în medii Docker minimale. |
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
| `WOODY_APP_URL` | Destinația redirectului de la domeniul tehnic Railway către Command Center public. |

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

## Private Hatom Watch (experimental, read-only)

Hatom monitoring has **one destination only**: the administrator's private
Telegram chat determined from `ADMIN_TELEGRAM_ID`. It never sends Hatom
alerts to `TELEGRAM_GROUP_CHAT_ID`, even when WOODY group alerts are on.

Admin-only Telegram commands: `/hatom_status`, `/hatom_test`, `/hatom_scan`.
The admin menu also has a **Hatom Watch (Private)** status button.
Other users and group chats cannot use these commands.

To enable, configure:
```env
ENABLE_HATOM_WATCH=true
HATOM_OPPORTUNITIES_URL=https://your-trusted-observer.example/positions
HATOM_WATCH_INTERVAL_SECONDS=60
HATOM_MAX_SOURCE_AGE_SECONDS=120
HATOM_ALERT_COOLDOWN_SECONDS=900
```

The JSON endpoint must be a validated, independent Hatom borrower indexer.
Hatom does not document a public list of all risky positions, so monitoring
is **disabled by default** until such a source is connected. The endpoint
returns a JSON object with `updated_at` and a `positions` array. Each
position has `borrower` (full MultiversX bech32 address),
`health_factor`, `debt_token`, `collateral_token`, and optionally
`borrow_usd` and `max_repay_usd`. Either per-position or top-level
`updated_at` must be a recent ISO-8601 timestamp or UNIX seconds.

Entries older than the configured freshness limit, malformed data, and
healthy positions are ignored. The monitor sends at most five alerts per
poll and deduplicates within a cooldown period. Alerts are **not proof of
a profitable or executable liquidation**: positions and prices must be
validated on-chain immediately before trading. It **never** sends
transactions or touches wallet keys.

See Hatom's official [liquidation documentation](https://docs.hatom.com/getting-started/hatoms-ecosystem/lending-protocol/liquidation).
Run offline tests with `python -m unittest tests.test_hatom_liquidations`.


### Native Hatom mainnet scanner (no external feed)

Set the following variables on Railway to request **read-only** smart
contract scanning. It never signs transactions, and Hatom messages go only
to `ADMIN_TELEGRAM_ID` (a Telegram private chat, never the WOODY group).

```env
ENABLE_HATOM_WATCH=true
HATOM_WATCH_SOURCE=onchain
HATOM_ONCHAIN_BATCH_SIZE=15
HATOM_WATCH_INTERVAL_SECONDS=60
```

The code calls `https://gateway.multiversx.com/vm-values/query`
directly with Hatom's documented mainnet Controller
`erd1qqqqqqqqqqqqqpgqxp28qpnv7rfcmk6qrgxgw5uf2fnp84ar78ssqdk6hr`.

Sequence: `getWhitelistedMarkets`, periodic `getMarketMembers`,
`isRisky`, `getAccountMarkets`, `getCurrentAccountBorrowAmount`,
`getAccountTokens`, and `liquidateBorrowAllowed` (small probe
amount, view-only). Scan batches are capped at 100 wallets per poll, with
a default of 15. The index gradually discovers participating addresses.
If a view fails, nothing is sent; we do not invent portfolio values.

**Limitations:** Verification against the live mainnet query responses is
still required. A positive risk/allow check is an indicative on-chain
signal, not a profitable opportunity. This monitor does not evaluate
borrow-market decimal precision, close factors, gas, routing, or slippage
for actual execution. It does not liquidate. In particular,
`getMarketMembers` may be expensive for very large markets, and a
production low-latency liquidator would require a dedicated event indexer.

Offline unit tests: `pytest tests/test_hatom_onchain.py tests/test_hatom_liquidations.py`.

Primary references:
* https://docs.hatom.com/getting-started/hatoms-ecosystem/lending-protocol/networks
* https://github.com/HatomProtocol/hatom-sc-proxies
* https://docs.multiversx.com/sdk-and-tools/rest-api/virtual-machine/

### Important: Unpriced liquidation alerts are suppressed

As of November 2026, the Hatom on-chain scanner validates risk indicators
but **does not provide executable net-profit quotes**. All automatic
liquidation alerts are therefore blocked, including signals from optional
external feeds. A positive `isRisky` / `liquidateBorrowAllowed` result
is not proof of profit. Scans may continue for private diagnostic status,
but they will not message the admin about unpriced positions.

Before restoring real profit alerts, implement and test token decimal
resolution, actual repay limits, oracle freshness, seize amounts, current
DEX liquidation routes, slippage, fees, and a configurable minimum **net**
profit margin. Deduplicate by borrower and best executable collateral/debt
route. Keep liquidation execution disabled until separately authorized.

### Hatom Watch: quiet scans and private risk digests

Set `ENABLE_HATOM_WATCH=true` with `HATOM_WATCH_SOURCE=onchain`
to run *read-only* checks every `HATOM_WATCH_INTERVAL_SECONDS=90`
seconds. These checks **never send per-position alerts**.

By default, at most one private digest runs at **09:00, 15:00, 21:00
Europe/Berlin** (`HATOM_DIGEST_HOURS_BERLIN=9,15,21`). The digest
is skipped if no recent position passes an additional fresh Hatom
`isRisky` and tiny-repayment `liquidateBorrowAllowed` view check.
An administrator may request an immediate **private** snapshot with
`/hatom_report`, which does not increase the scheduled message count.
The bot deduplicates multiple debt/collateral markets of one borrower.

**No verified profitable liquidation is available yet.** A positive
`isRisky` and minimum-repayment view check are **only risk indicators**.
Accurate repay caps, token decimals, oracle prices, seized collateral
quotes, swap slippage, gas and net profit must be computed and tested
before any notification may truthfully claim a profit. No trades are
executed. All Hatom reports target ONLY `ADMIN_TELEGRAM_ID` in a
private chat, never the WOODY Telegram group.

### Two-stage Hatom alerts — November 2026

Stage 1 (risk): continuous read-only scans; at most three private risk summaries
daily at 09:00, 15:00 and 21:00 Europe/Berlin. Multiple debt/collateral
pairs for the same borrower are grouped.

Stage 2 (protocol liquidation eligibility): the Hatom Controller identifies a
risky account with nonzero borrowed funds and collateral; before promotion,
the monitor checks a significant proposed repayment (25% of current debt,
capped by the live market close factor), a nonzero `tokensToSeize` result,
nonzero conversion from Hatom tokens to underlying collateral, and enough
cash in the collateral money market. These contract view checks are
**not** a transaction simulation and do not guarantee on-chain execution.

Stage 2 notifications are private to `ADMIN_TELEGRAM_ID`, limited globally to
**one batched message per hour** containing at most **two accounts** and a
**12-hour per-borrower cooldown**. A fresh Hatom recheck is required before
each batch; a temporary on-disk cooldown record is saved under `DATA_DIR`
so reconnects/redeployments do not reset the global rate limit.

The bot still **cannot verify whether a liquidation generates positive net
profit**: USD-equivalent token prices, exact swap routes and slippage, gas and
validator competition remain unavailable. The alert explicitly says so.
The bot **never signs or executes any liquidation**. A future profit-only
filter must first validate net profit before attaching a "profit-positive"
label. No Hatom messages go to the WOODY group.

### Hatom reference-price scenario calculator (read-only)

A stage-2 notification, and the admin-only `/hatom_profit` command,
can now report token quantities and USD values when **all** required
metadata is available.

Calculation process:
1. Read Hatom money-market `getUnderlyingId` for the debt and collateral.
2. Fetch underlying token decimals and indicative USD prices via
   `https://api.multiversx.com/tokens/{identifier}` (EGLD is read from
   `/economics`), and network minimum gas price from MultiversX Gateway.
3. Convert exact Hatom raw repay/underlying amounts to human token amounts.
4. Calculate the reference **gross** USD spread, then subtract **assumed**
   swap loss (default 1.5%) and **assumed** gas units (default 60 million).
   The scenario uses `HATOM_GAS_UNITS_ASSUMED` and
   `HATOM_SWAP_LOSS_BPS_ASSUMED` from the environment.

**Important:** The estimated scenario net is NOT an executable trade quote.
Token USD prices can be stale, Hatom may change between checks, and swap
routing/price impact, hToken redemption, exact execution gas, congestion
and other liquidators are unverified. No price snapshot timestamp is
available from the current public token API. An unavailable token price
or metadata is reported as `unavailable`, never synthesized. No automatic
trades, private keys, or wallet funding are involved. Until a validated
live route and transaction simulation are available, **no scenario may be
labeled verified profit**, regardless of its sign.

Only the configured Telegram administrator receives Hatom reports. Stage-1
scheduled risk digests and the stage-2 one-per-hour anti-spam restriction
remain unchanged. The `/hatom_profit` command is an on-demand private
recheck of recently cached stage-2 positions, not a request to execute.

### Hatom DEX minimum-output quote integration

The stage-2 calculator also reads a **public, exact-input XOXNO MultiversX
DEX aggregator quote** from `https://swap.xoxno.com/api/v1/quote` using
the underlying collateral amount to be redeemed. It validates the input
and output token identifiers, exact input base units, nonzero output,
minimum output (after slippage), and actual path presence. `EGLD` is
represented as `WEGLD-bd4d79` for quoting; the required wrap/redeem
transaction costs are *not* fully simulated.

When an exact-input DEX quote exists, the bot additionally reports:
- Live DEX minimum-output USD equivalent (using public API token price)
- Estimated DEX route surplus after repaying the debt and **assumed gas**
- Route count (information only)

This can be more informative than the simple reference-price spread,
but does not include exact Hatom liquidation execution gas, the cost
of hToken redemption/wrap, market changes, competing liquidators,
or a transactional atomicity guarantee. The result is explicitly
**NOT AN EXECUTABLE OR VERIFIED PROFIT QUOTE**. DEX quote failures
fall back to the reference-price scenario with the failure reason.
Never execute from a chat message without a fresh independent check.

See [the public MultiversX aggregator API](https://swap.xoxno.com/)
and [MultiversX Token API](https://api.multiversx.com/).

### Hatom cache and historical Telegram alert recheck

The admin-only `/hatom_profit` command can now restore recently scanned
Stage-2 positions from `$DATA_DIR/hatom_candidates.json` when `DATA_DIR`
points to the worker's mounted persistent Railway volume (`/app/data`).
Only public borrower/market addresses and observations are stored.
Entries expire within 12 hours, and all on-chain risk, debt, collateral
and liquidation eligibility checks must run again before USD valuation.

To analyze a Hatom alert created before the cache existed, reply to
that old private Telegram message with `/hatom_profit`, or use
`/hatom_profit erd1...` with a public borrower address. The bot parses
borrower addresses from numbered risk digests and older Stage-2 alerts;
it never reuses old repayment amounts without reconfirming contract state.
At most three borrower addresses are examined per command. This does not
sign or execute any blockchain transactions. If the position is no
longer eligible, the bot says so rather than manufacturing a profit quote.


### Hatom priority alerts: positive indicative DEX scenarios only

Stage-1 scheduled risk digests stay unchanged. Stage-2 stays rate limited to
one private batch per hour, maximum two wallets per message, same borrower
at most once per 12 hours **after a successful alert**.

The notifier filters out ALL other Stage-2 candidates and requires:
1. A freshly reconfirmed Hatom on-chain liquidation preflight.
2. A valid XOXNO exact-input route with strictly positive minimum output,
   received within `HATOM_ALERT_MAX_QUOTE_AGE_SECONDS=60`.
3. A strictly positive repayment; `HATOM_ALERT_MIN_REPAY_USD=0` removes the additional minimum-capital floor.
4. The DEX minimum-output reference USD value minus the debt repayment and
   *assumed* gas, minus an **additional** conservative buffer equal to
   the greater of 1% of the repayment or USD 0.50 (unchanged safety reserve).
5. At least `HATOM_ALERT_MIN_NET_USD=0.25` remains after that buffer.

Relevant variables: `HATOM_ALERT_MIN_REPAY_USD`,
`HATOM_ALERT_MIN_NET_USD`, `HATOM_ALERT_SAFETY_BUFFER_BPS`,
`HATOM_ALERT_SAFETY_BUFFER_USD`,
`HATOM_ALERT_MAX_QUOTE_AGE_SECONDS`. Invalid settings fail closed.

If these conditions are NOT met, no Stage-2 Telegram alert is sent.
On-demand `/hatom_profit` still explains positive *or negative* indicative
scenarios for eligible positions. An indicative profit screen is **not
evidence of an executable liquidation**: end-to-end signing, redemption,
wrap/unwrap, gas and competition still need separate simulation.
No transactions or wallet keys are used. Alerts go to the private admin
chat exclusively.


### Hatom Stage 3: isolated read-only liquidation dry-run

New administrator-only command: `/hatom_dryrun`. Reply to a private
Hatom Stage-2 alert with that command, or use `/hatom_dryrun erd1...`
with a borrower address. The bot always refreshes the account's Hatom
borrowed amounts, risk status and collateral before testing.

It builds unsigned draft calldata for the Hatom market `liquidateBorrow`
endpoint: an `ESDTTransfer` for fungible token debts, or a direct EGLD
payment for EGLD debt. **No keys, signing, transactions or funds.**

Optionally set `HATOM_SIMULATION_SENDER` to the *public address* of an
account you control. This enables **isolated** mainnet gas estimation
and simulation; this setting is NOT a seed phrase or a private key.
The code uses only allowlisted read-only endpoints:
`GET /network/config`, `GET /address/{sender}`,
`POST /transaction/cost`, and
`POST /transaction/simulate?checkSignature=false`.
The latter uses a dummy zero signature and never broadcasts.

Without a public simulation sender, the command clearly reports that
the gas/outcome could not be tested. With an unfunded sender, the network
may reject the simulation for missing EGLD or borrowed tokens.

Important: these queries can simulate only the isolated liquidation
call, NOT the entire liquidation → hToken redemption → optional wrap
→ DEX swap pipeline in one atomic state transition. Same-shard
limitations, other liquidators, timing and gas mean an isolated success
is NOT a verified profitable trade. This monitor retains read-only
mode, Stage-1 digests and positive-indicative Stage-2 alert filtering.

Reference: https://docs.multiversx.com/sdk-and-tools/rest-api/transactions/

### Micro-liquidation alerts and cumulative gains

Alerts now include positions with as little as USD 0.25 **modeled positive
surplus AFTER** subtracting the quoted DEX minimum return, the assumed
gas cost, and an *extra* safety buffer (at least USD 0.50 or 1% of debt).
There is no arbitrary repayment-size floor. This lets smaller, genuinely
positive *indicative* opportunities surface.

These are **NOT verified or guaranteed profits**: liquidation may revert,
a route may expire, redemptions may cost additional gas, and failed attempts
can erase the small modeled gains. The monitor does not submit trades,
compound gains or provide profit statistics based on unexecuted alerts.
Never fund a bot solely on the basis of these scenarios.


### XOXNO Lending MultiversX watch — private, no wallet

XOXNO's MultiversX lending protocol is a distinct money market from Hatom.
The public XOXNO SDK documents a liquidation candidate feed:
`GET https://api.xoxno.com/lending/leaderboard/liquidate`. This public
endpoint returned HTTP 200 with an empty array when tested on 9 Nov 2026.
A candidate may appear whenever an account's collateral becomes insufficient.

New private commands: `/xoxno_status` (status) and `/xoxno_scan` (immediate
read-only lookup). Optional 240-second background monitoring is enabled by
`ENABLE_XOXNO_LENDING_WATCH=true`. Only administrator DMs are used; no group
messages. Automatic private eligibility alerts are capped at one batch/hour,
two accounts/batch, and 12h duplicate suppression by account NFT. Alert
state is stored in `DATA_DIR/xoxno_lending_alerts.json` to persist restarts.

The API feed is treated as discovery ONLY. Each candidate must have an
`XLEND-18dc6f` MultiversX account NFT, a positive borrowed balance and
a parseable owner wallet. The watcher converts the account NFT nonce
from hexadecimal and checks `canBeLiquidated` on the published XOXNO
MultiversX Controller address from `XOXNO/rs-lending/networks.json`:
`erd1qqqqqqqqqqqqqpgqyq9mwxkq7zelkupafta5ah95pw6362j745qsk5mdzw`.
A missing response, false response, unexpected schema or network failure
fails closed; the bot sends no inferred liquidation opportunities.

**Eligibility is NOT profit**: the Controller health-factor view does NOT
establish a viable repayment, collateral seize, DEX route, gas cost or net
surplus. XOXNO's `liquidationEstimations` view exists for a later stage
but requires a correctly encoded per-debt repayment plan and the returned
collateral payments must be valued and quoted at the DEX.

Accordingly the XOXNO private alert is deliberately labeled NOT A PROFIT
ALERT, and it DOES NOT apply Hatom's USD 0.25 modeled-profit gate. No
signatures, fees, wallet keys, transactions, network broadcasts or
automatic liquidations are triggered. To obtain actual profits, a further
reviewed profit quote + complete gas/swap simulation is needed.

XOXNO also offers Stellar lending, but this integration is intentionally
MultiversX-only and does not mix the two account or liquidation formats.

Sources: https://github.com/XOXNO/rs-lending and
https://sdk.xoxno.com/.
