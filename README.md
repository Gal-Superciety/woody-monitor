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


### Hatom Stage-2 liquidation eligibility alerts (independent of profit)

The Hatom watcher scans every `HATOM_WATCH_INTERVAL_SECONDS=90` seconds.
When a borrower passes the fresh on-chain Stage-2 liquidation preflight,
a private Telegram alert is sent **regardless of whether the modeled
profit is positive, negative, below $0.25 or unavailable**. Only
risk-only Stage-1 positions remain silent.

The eligible-borrower notifier checks approximately every 180 seconds,
sends up to two positions per message and permanently records
notified borrower addresses across future scans and restarts. The optional DEX-min output estimate
is attached where available; errors never suppress a valid Stage-2
eligibility notification. The saved `HATOM_ALERT_*` thresholds still
support informative profitability classification but are NOT a
notification gate.

Use `/hatom_report` to see a recent risk-scan report with negative
scenarios and `/hatom_profit` for a fresh per-borrower estimate.
The three automatic daily Hatom digest messages have been disabled
so that the bot only proactively notifies confirmed eligible positions.
There are no wallet signatures or liquidation transactions.

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

### Micro-liquidation profit estimation

The on-demand Hatom calculator can still show modeled net surplus down
to cents, including negative values. A result of +$0.25 USD or higher
is a useful reference target for *manual evaluation*, but not a minimum
for Telegram eligibility notifications, and not executable profit.
Even a small failed or unexpectedly expensive transaction can wipe
out gains from many successful micro-liquidations.

### XOXNO Lending MultiversX watch — private, no wallet

XOXNO's lending protocol is separate from Hatom. This integration uses
the publicly documented `GET /lending/leaderboard/liquidate` to discover
candidates, then confirms `canBeLiquidated` on the official MultiversX
Controller. It alerts every newly confirmed eligible **account NFT**,
whether the optional price scenario is a profit, a loss or UNKNOWN.

The main loop runs every 240 seconds and sends at most two positions per
batch, with a minimum 240-second gap between batches and permanent
persistent deduplication per account NFT. The alert includes the owner
address and a `/xoxno_profit XLEND-...` command to manually re-price.
A fresh verified eligible account is alerted *before* the optional
valuation pass so that a failed/slow DEX quote cannot silence the alert.

Separate on-demand `/xoxno_scan` and `/xoxno_report` reports still
show negative, positive, below-target and UNKNOWN outcomes. The
optional profit calculator prices up to six of the confirmed accounts
per cycle in rotation. No routine daily report is automatically sent
when there is no eligible candidate.

XOXNO Stellar positions are not included. This is strictly
read-only MultiversX; no keys, no broadcasts and no automatic execution.

### XOXNO manual liquidation profit calculator

Private command: `/xoxno_profit XLEND-18dc6f-eb` (replace the account NFT
with a current candidate from `/xoxno_scan`). Alternatively reply directly
to a private XOXNO eligibility alert with `/xoxno_profit`.
Without an argument or replied alert, the command looks up one current
on-chain-confirmed candidate from the public XOXNO leaderboard.

The calculator always rechecks live `canBeLiquidated` on the deployed XOXNO
MultiversX Controller; it cannot use an outdated alert to assume eligibility.
It reads `/lending/account/{nonce}/positions` for debt token discovery and
`getBorrowAmountForToken` on-chain for current amounts/decimals. It tests
three repay sizes (full, half and quarter) for up to three debt token types
via the protocol's read-only `liquidationEstimations` view.

The official `LiquidationEstimate` supplies seized fungible payments,
protocol fees, refunds, maximum repay value and bonus. We conservatively
subtract protocol fees from seized amounts, net any debt refunds, request
live XOXNO Swap exact-input min-output routes for each collateral asset,
convert the output into the repayment token's USD reference value and
subtract **assumed** gas plus an extra safety buffer (>= USD 0.50 or 1%).
Only a COMPLETE decoded protocol estimate and valid DEX quotes produce
a numerical net scenario. If any required field, price, token metadata,
route or ABI decode is absent or invalid, it returns `NOT VERIFIED`.

Default assumptions: `XOXNO_GAS_UNITS_ASSUMED=180000000`,
`XOXNO_SAFETY_BPS=100`, `XOXNO_SAFETY_USD=0.50`. The estimated
profit model is compared against the previously chosen `USD 0.25` floor,
but **neither the gas assumption nor the live DEX min-out guarantees an
executed profit**. Public token USD prices have no independently verified
timestamp, a swap route can expire and a full liquidation+swap execution
has not been simulated. Treat a positive scenario as a *candidate for
manual independent verification*, not approval to trade.

The on-demand `/xoxno_profit` command lets the administrator
recheck an individual NFT; `/xoxno_scan` and `/xoxno_report`
show negative, below-threshold, positive and unpriceable results.
Automatic eligibility alerts do not require a profit estimate.
No wallet, signing, funds, broadcasting or automatic liquidation is implemented.

### Current private notification rule (10 November 2026)

**Continuous scanning, notifications only for newly confirmed
liquidatable positions.** Both protocols alert even when their
best available profit scenario is negative or unpriceable. No
routine risk-only or empty scan messages are scheduled.

| Protocol | Scanning | Alert trigger | Duplicate limit |
| --- | --- | --- | --- |
| Hatom | ~90 sec | Fresh contract-confirmed Stage-2 liquidation eligibility | Max 2 positions per 3-minute batch, each borrower notified once |
| XOXNO MVX | ~240 sec | Fresh contract-confirmed `canBeLiquidated` for an XLEND NFT | Max 2 NFTs per 4-minute batch, each NFT notified once |

The existing private commands `/hatom_report`, `/hatom_profit`,
`/xoxno_report`, `/xoxno_scan`, `/xoxno_profit` remain available.
Profit thresholds and market valuations are INFORMATION ONLY;
the user will decide whether to attempt manual liquidation.
An eligible account may not have a profitable execution, and
other liquidators or changing prices may invalidate the opportunity.

### Permanent one-time notification history (10 November 2026)

The bot **never automatically repeats an eligibility alert for the same
Hatom borrower address** or the same **XOXNO account NFT** while the
persistent Railway Volume remains intact. This replaces the previous
12-hour deduplication expiration. Other newly eligible addresses and
different XOXNO lending account NFTs still trigger their own one-time
notifications (even if two XOXNO NFTs belong to the same owner wallet).

Hatom stores notified borrower keys in
`DATA_DIR/hatom_stage_notifications.json`; XOXNO stores NFT keys in
`DATA_DIR/xoxno_lending_alerts.json`. The files are preserved across
normal application restarts and are not pruned for age. Legacy keys
already expired and removed by *older* deployments cannot be recovered.

To minimize duplicate attempts if Telegram times out after receiving a
message, a notification is **reserved on disk before Telegram is called**.
This is at-most-once delivery, not a guarantee that Telegram delivered it:
a crash or network error after reservation can lose an alert rather than
retry it. Manual `/hatom_report`, `/hatom_profit`,
`/xoxno_scan` and `/xoxno_profit` still allow fresh checks.
If the historical file is corrupted or cannot be saved, automatic
notification is suppressed instead of silently clearing the deduplication
history. Restoring a Railway Volume from an older snapshot can naturally
restore an older alert history.

### Owner-approved second Telegram user for Hatom/XOXNO (private read-only)

WOODY Monitor supports additional **private read-only** liquidation watchers
(up to five). Authorization is by numeric **Telegram user ID**, not a
displayed name, mutable @username, or MultiversX `erd1...` wallet. The
username is stored only as an optional label. The new participant must
first open the WOODY Monitor bot in Telegram and press **Start**.

The existing administrator sends `/liquidation_invite` to WOODY Monitor
in their **private chat**. The bot returns a strong one-time invitation
valid for 24 hours as `/liquidation_join SECRET_TOKEN`. The owner privately
sends it to the intended participant (for example @CosminRussu). That
person enters the command in their own private Telegram chat with the bot.
**Possession of the code grants the slot**; never send it to a public group.
The bot stores only the SHA-256 hash of the one-time secret in Railway.

After joining, the owner and subscriber each receive **future** private
Hatom and XOXNO liquidation-eligibility alerts. The subscriber may use
`/hatom_status`, `/hatom_scan`, `/hatom_report`, `/hatom_profit`,
`/xoxno_status`, `/xoxno_scan`, `/xoxno_report`, `/xoxno_profit`.
Each private command replies to its own requester; `/hatom_report` no longer
accidentally sends a subscriber's report to the owner. Existing alerts
that were already deduplicated are not replayed retroactively.

Owner-only commands: `/liquidation_invite` (generate 24-hour invitation),
`/liquidation_users` (view approved IDs), `/liquidation_remove 123456789`
(revoke someone), `/hatom_test` and `/hatom_dryrun`. The subscriber can
unsubscribe with `/liquidation_leave`. No subscriber gets control of bot
administration, Railway, wallets, keys, automatic execution, or group alerts.

Membership and invite digests persist in
`DATA_DIR/liquidation_subscribers.json` on the worker's mounted volume.
The bot individually sends alerts to both private recipients, so a blocked
subscriber does not interrupt attempts to deliver to the owner.
Successful deployment itself does **not** enroll a named Telegram account.
The owner must issue the invite, send it privately, and the person must join.
