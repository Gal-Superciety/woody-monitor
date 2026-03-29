import asyncio
import json
import logging
import os
import websockets
from telegram import Bot
from dotenv import load_dotenv

# ------------------ CONFIG ------------------
load_dotenv()

TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
CHAT_ID = int(os.getenv("TELEGRAM_PRIVATE_CHAT_ID"))

WOODY_TOKEN = "WOODY-5f9d9c"

WS_URL = "wss://socket-api-ovh.multiversx.com"

# --------------------------------------------

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("WOODY_MONITOR")

bot = Bot(token=TOKEN)

# ------------------ ALERT ------------------

async def send_alert(text):
    try:
        await bot.send_message(chat_id=CHAT_ID, text=text)
    except Exception as e:
        logger.error(f"Telegram error: {e}")

# ------------------ PARSER ------------------

def parse_transfer(transfer):
    try:
        token = transfer.get("token", "")
        value = int(transfer.get("value", "0"))

        if value == 0:
            return None

        value = value / (10 ** 18)

        sender = transfer.get("sender", "")[:8]
        receiver = transfer.get("receiver", "")[:8]

        return {
            "token": token,
            "value": value,
            "from": sender,
            "to": receiver
        }

    except Exception as e:
        logger.error(f"Parse error: {e}")
        return None

# ------------------ HANDLER ------------------

async def handle_event(data):
    try:
        transfers = data.get("data", {}).get("transfers", [])

        if not transfers:
            return

        woody_found = False
        parsed = []

        for t in transfers:
            p = parse_transfer(t)
            if not p:
                continue

            parsed.append(p)

            if p["token"] == WOODY_TOKEN:
                woody_found = True

        if not woody_found:
            return

        # 🔥 trimitem TOT, fara filtrare
        msg = "🔥 WOODY ACTIVITY DETECTED\n\n"

        for p in parsed:
            msg += f"{p['token']} | {p['value']:.4f}\n"
            msg += f"{p['from']} → {p['to']}\n\n"

        logger.info("ALERT TRIGGERED")
        await send_alert(msg)

    except Exception as e:
        logger.error(f"Handler error: {e}")

# ------------------ WS ------------------

async def listen():
    async with websockets.connect(WS_URL) as ws:
        logger.info("Connected to MultiversX WS")

        # subscribe
        await ws.send(json.dumps({
            "type": "subscribe",
            "payload": {
                "channel": "customTransferUpdate"
            }
        }))

        logger.info("Subscribed to transfers")

        while True:
            try:
                msg = await ws.recv()
                data = json.loads(msg)

                if data.get("type") == "customTransferUpdate":
                    await handle_event(data)

            except Exception as e:
                logger.error(f"WS error: {e}")
                await asyncio.sleep(2)

# ------------------ MAIN ------------------

async def main():
    logger.info("WOODY MONITOR STARTED")
    await listen()

if __name__ == "__main__":
    asyncio.run(main())
