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
- 👥 Holders
- 📊 Chart
- 🛒 Buy
- 🤖 Bot Status

Sunt ascunse din meniu (dar păstrate în cod): Top Holders, Last Buy/Sell, Volume 24h, Top Volume, Pools, Diagnostics și alte opțiuni tehnice.

### Privat admin (`private` + `user_id == ADMIN_TELEGRAM_ID`)
Adminul vede meniul complet, cu toate butoanele existente.

### Privat non-admin (`private` + alt `user_id`)
Utilizatorii non-admin văd meniul public simplificat.
