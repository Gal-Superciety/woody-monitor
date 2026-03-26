import os
import time
import json
import logging
import threading
import queue
import requests
import socketio
from dotenv import load_dotenv
from telegram.ext import Application, CommandHandler, ContextTypes

load_dotenv()

# =========================
# CONFIG
# =========================
TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
CHAT_ID = os.getenv("TELEGRAM_GROUP_CHAT_ID")

MVX_API = "https://api.multiversx.com"
WOODY_TOKEN = "WOODY-5f9d9c"

MIN_USD = 2

# =========================
# LOGGING
# =========================
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("WOODY")

# =========================
# QUEUE
# =========================
ALERT_QUEUE = queue.Queue()

# =========================
# HELPERS
# =========================
def short(addr):
    if not addr:
        return "unknown"
    return addr[:8] + "..." + addr[-6:]


def get_ws_url():
    try:
        data = requests.get(f"{MVX_API}/websocket/config").json()
        return f"https://{data['url']}"
    except:
        return None


def get_tx(tx_hash):
    try:
        url = f"{MVX_API}/transactions/{tx_hash}?withOperations=true"
        return requests.get(url).json()
    except:
        return None


def normalize(value, decimals):
    try:
        return int(value) / (10 ** decimals)
    except:
        return 0


# =========================
# PARSER SIMPLU (FOARTE IMPORTANT)
# =========================
def parse_tx(tx):
    ops = tx.get("operations", [])
    woody_in = 0
    woody_out = 0
    usdc = 0
    wallet = None

    for op in ops:
        token = op.get("identifier")
        amount = normalize(op.get("value", "0"), op.get("decimals", 18))

        if token == WOODY_TOKEN:
            if op.get("action") == "transfer":
                if op.get("receiver"):
                    woody_in += amount
                    wallet = op.get("receiver")
                if op.get("sender"):
                    woody_out += amount
                    wallet = op.get("sender")

        if "USDC" in str(token):
            usdc += amount

    if woody_in > 0 and usdc > 0:
        return "BUY", woody_in, usdc, wallet

    if woody_out > 0 and usdc > 0:
        return "SELL", woody_out, usdc, wallet

    return None


# =========================
# BUILD MESSAGE
# =========================
def build(tx_hash, parsed):
    typ, woody, usd, wallet = parsed

    return f"""
{'🟢 BUY' if typ=='BUY' else '🔴 SELL'}

Wallet: {short(wallet)}
WOODY: {woody:,.0f}
Value: ${usd:.2f}

https://explorer.multiversx.com/transactions/{tx_hash}
"""


# =========================
# WEBSOCKET
# =========================
def ws_worker():
    while True:
        try:
            url = get_ws_url()
            logger.info("WS URL: %s", url)

            sio = socketio.Client()

            @sio.event
            def connect():
                logger.info("WS CONNECTED ✅")
                sio.emit("subscribeCustomTransfers", {"token": WOODY_TOKEN})
                logger.info("SUBSCRIBED TO WOODY")

            @sio.on("customTransferUpdate")
            def event(data):
                logger.info("WS EVENT RAW: %s", data)

                transfers = data.get("transfers", [])

                for t in transfers:
                    tx_hash = t.get("txHash")

                    if not tx_hash:
                        continue

                    logger.info("TX HASH: %s", tx_hash)

                    tx = get_tx(tx_hash)

                    logger.info("TX DATA: %s", tx)

                    if not tx:
                        continue

                    parsed = parse_tx(tx)

                    logger.info("PARSED: %s", parsed)

                    if not parsed:
                        continue

                    if parsed[2] < MIN_USD:
                        logger.info("SKIP <2 USD")
                        continue

                    msg = build(tx_hash, parsed)
                    ALERT_QUEUE.put(msg)

            sio.connect(url, socketio_path="/ws/subscription")
            sio.wait()

        except Exception as e:
            logger.error("WS ERROR: %s", e)
            time.sleep(5)


# =========================
# TELEGRAM
# =========================
async def start(update, context):
    await update.message.reply_text("WOODY Monitor active")


async def status(update, context):
    await update.message.reply_text("Bot running ✅")


async def sender(context: ContextTypes.DEFAULT_TYPE):
    while not ALERT_QUEUE.empty():
        msg = ALERT_QUEUE.get()

        try:
            await context.bot.send_message(
                chat_id=CHAT_ID,
                text=msg
            )
        except Exception as e:
            logger.error("SEND ERROR: %s", e)


# =========================
# MAIN
# =========================
def main():
    threading.Thread(target=ws_worker, daemon=True).start()

    app = Application.builder().token(TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("status", status))

    app.job_queue.run_repeating(sender, interval=1)

    logger.info("BOT STARTED 🚀")
    app.run_polling()


if __name__ == "__main__":
    main()
