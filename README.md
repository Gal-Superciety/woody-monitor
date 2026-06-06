# woody-monitor
WOODY Monitor Bot – Telegram bot that tracks WOODY token swaps, big buys, big sells, liquidity changes and new holders on the MultiversX blockchain.

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

# Grup (nou)
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
