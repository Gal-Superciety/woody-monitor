import os
import asyncio
import logging
import requests
import socketio
from dotenv import load_dotenv
from telegram import Bot

# ================= LOAD ENV =================
load_dotenv()

BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
CHAT_ID = os.getenv("TELEGRAM_PRIVATE_CHAT_ID")

MVX_API = os.getenv("MVX_API")
POOL = os.getenv("XEXCHANGE_POOL_ADDRESS")

WOODY = os.getenv("WOODY_TOKEN_ID")
WEGLD = os.getenv("WEGLD_TOKEN_ID")

MIN_ALERT_USD = float(os.getenv("MIN_ALERT_USD", 2))

bot = Bot(token=BOT_TOKEN)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("WOODY_MONITOR")

# ================= SOCKET =================
sio = socketio.AsyncClient(
    reconnection=True,
    reconnection_attempts=1000,
    reconnection_delay=5
)

last_seen_tx = set()

# ================= TELEGRAM =================
async def send(msg):
    try:
        await bot.send_message(chat_id=CHAT_ID, text=msg)
    except Exception as e:
        logger.error(f"Telegram error: {e}")

# ================= PRICE =================
def get_egld_price():
    try:
        r = requests.get(f"{MVX_API}/economics", timeout=5).json()
        return float(r.get("price", 0))
    except:
        return 0

# ================= FETCH TX =================
def get_latest_swaps():
    try:
        url = f"{MVX_API}/transactions?size=10&receiver={POOL}&status=success"
        return requests.get(url, timeout=5).json()
    except:
        return []

# ================= PARSER =================
def parse_tx(tx):
    try:
        tx_hash = tx["txHash"]
        logs = tx.get("logs", {})
        events = logs.get("events", [])

        bought = 0
        sold = 0

        for ev in events:
            data = ev.get("data", "")
            if not data:
                continue

            try:
                decoded = bytes.fromhex(data).decode()
            except:
                continue

            # Detect amounts
            if WOODY in decoded:
                parts = decoded.split("@")
                for p in parts:
                    if p.isdigit():
                        bought += int(p)

            if WEGLD in decoded:
                parts = decoded.split("@")
                for p in parts:
                    if p.isdigit():
                        sold += int(p)

        return tx_hash, bought, sold

    except:
        return None, 0, 0

# ================= ANALYZE =================
async def analyze():
    egld_price = get_egld_price()
    txs = get_latest_swaps()

    for tx in txs:
        tx_hash, bought, sold = parse_tx(tx)

        if not tx_hash or tx_hash in last_seen_tx:
            continue

        last_seen_tx.add(tx_hash)

        # Normalize values
        bought = bought / 10**18
        sold = sold / 10**18

        usd = sold * egld_price

        if usd < MIN_ALERT_USD:
            continue

        if sold > 0 and bought > 0:
            msg = f"🟢 BUY WOODY\n💰 {sold:.4f} EGLD (~${usd:.2f})"
            await send(msg)

        elif sold > 0:
            msg = f"🔴 SELL WOODY\n💰 {sold:.4f} EGLD (~${usd:.2f})"
            await send(msg)

# ================= SOCKET EVENTS =================
@sio.event
async def connect():
    logger.info("Connected to MultiversX WS")

@sio.event
async def disconnect():
    logger.warning("Disconnected from WS")

@sio.on("transactions")
async def on_tx(data):
    await analyze()

# ================= MAIN LOOP =================
async def main():
    logger.info("WOODY MONITOR STARTED")

    while True:
        try:
            await sio.connect("https://socket-api-ovh.multiversx.com")
            await sio.wait()
        except Exception as e:
            logger.error(f"Reconnect error: {e}")
            await asyncio.sleep(5)

if __name__ == "__main__":
    asyncio.run(main())
