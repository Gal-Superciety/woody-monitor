import os
import asyncio
import logging
import requests
import socketio
from dotenv import load_dotenv
from telegram import Bot

load_dotenv()

BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "").strip()
CHAT_ID = os.getenv("TELEGRAM_PRIVATE_CHAT_ID", "").strip()

MVX_API = os.getenv("MVX_API", "https://api.multiversx.com").strip()
WS_URL = os.getenv("WS_URL", "https://socket-api-ovh.multiversx.com").strip()

POOL = os.getenv("XEXCHANGE_POOL_ADDRESS", "").strip()
WOODY = os.getenv("WOODY_TOKEN_ID", "WOODY-5f9d9c").strip()
WEGLD = os.getenv("WEGLD_TOKEN_ID", "WEGLD-bd4d79").strip()

MIN_ALERT_USD = float(os.getenv("MIN_ALERT_USD", "2"))

logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(levelname)s | %(message)s")
logger = logging.getLogger("WOODY_MONITOR")

if not BOT_TOKEN:
    raise ValueError("Missing TELEGRAM_BOT_TOKEN")
if not CHAT_ID:
    raise ValueError("Missing TELEGRAM_PRIVATE_CHAT_ID")

bot = Bot(token=BOT_TOKEN)

sio = socketio.AsyncClient(
    reconnection=True,
    reconnection_attempts=1000,
    reconnection_delay=5,
)

last_seen_tx = set()


async def send(msg: str) -> None:
    try:
        await bot.send_message(chat_id=CHAT_ID, text=msg)
        logger.info("Telegram alert sent")
    except Exception as e:
        logger.error(f"Telegram error: {e}")


def get_egld_price() -> float:
    try:
        r = requests.get(f"{MVX_API}/economics", timeout=10)
        r.raise_for_status()
        data = r.json()
        return float(data.get("price", 0))
    except Exception as e:
        logger.warning(f"Could not fetch EGLD price: {e}")
        return 0.0


def get_latest_pool_txs():
    try:
        url = f"{MVX_API}/transactions"
        params = {
            "receiver": POOL,
            "status": "success",
            "size": 15,
            "withLogs": "true",
        }
        r = requests.get(url, params=params, timeout=15)
        r.raise_for_status()
        data = r.json()
        return data if isinstance(data, list) else []
    except Exception as e:
        logger.warning(f"Could not fetch tx list: {e}")
        return []


def parse_tx(tx):
    try:
        tx_hash = tx.get("txHash") or tx.get("hash")
        if not tx_hash:
            return None

        logs = tx.get("logs") or {}
        events = logs.get("events") or []

        woody_found = False
        wegld_found = False

        for ev in events:
            identifier = str(ev.get("identifier") or "")
            topics = ev.get("topics") or []
            data = str(ev.get("data") or "")

            raw = f"{identifier} {' '.join(str(x) for x in topics)} {data}"

            if WOODY in raw:
                woody_found = True
            if WEGLD in raw:
                wegld_found = True

        if not woody_found:
            return None

        return {
            "tx_hash": tx_hash,
            "is_buy_like": wegld_found and woody_found,
        }
    except Exception as e:
        logger.warning(f"parse_tx failed: {e}")
        return None


async def analyze_latest_swaps(trigger_reason: str = "manual") -> None:
    logger.info("Analyze triggered: %s", trigger_reason)

    egld_price = get_egld_price()
    txs = get_latest_pool_txs()

    if not txs:
        logger.info("No txs fetched")
        return

    for tx in txs:
        parsed = parse_tx(tx)
        if not parsed:
            continue

        tx_hash = parsed["tx_hash"]
        if tx_hash in last_seen_tx:
            continue

        last_seen_tx.add(tx_hash)

        explorer = f"https://explorer.multiversx.com/transactions/{tx_hash}"
        tx_type = "BUY/SELL activity"
        usd_text = f"EGLD price now: ${egld_price:.2f}" if egld_price > 0 else "EGLD price unavailable"

        msg = (
            f"🪶 WOODY activity detected\n\n"
            f"Type: {tx_type}\n"
            f"{usd_text}\n"
            f"Pool: {POOL}\n"
            f"Tx: {explorer}"
        )
        await send(msg)


@sio.event
async def connect():
    logger.info("Connected to MultiversX WS")

    try:
        # subscribe pe token
        await sio.emit("subscribeCustomTransfers", {"token": WOODY})
        logger.info("Subscribed custom transfers for token: %s", WOODY)
    except Exception as e:
        logger.warning(f"Token subscribe failed: {e}")

    try:
        # subscribe pe pool
        await sio.emit("subscribeCustomTransfers", {"address": POOL})
        logger.info("Subscribed custom transfers for pool: %s", POOL)
    except Exception as e:
        logger.warning(f"Pool subscribe failed: {e}")


@sio.event
async def disconnect():
    logger.warning("Disconnected from WS")


@sio.on("customTransferUpdate")
async def on_custom_transfer_update(data):
    logger.info("customTransferUpdate received")
    await analyze_latest_swaps("customTransferUpdate")


async def periodic_poll():
    while True:
        try:
            await analyze_latest_swaps("periodic")
        except Exception as e:
            logger.error(f"periodic_poll error: {e}")
        await asyncio.sleep(15)


async def main():
    logger.info("WOODY MONITOR STARTED")

    poll_task = asyncio.create_task(periodic_poll())

    while True:
        try:
            await sio.connect(WS_URL, socketio_path="/ws/subscription", transports=["websocket"])
            await sio.wait()
        except Exception as e:
            logger.error(f"Reconnect error: {e}")
            await asyncio.sleep(5)

    await poll_task


if __name__ == "__main__":
    asyncio.run(main())
