import json
import logging
import os
import time
from collections import defaultdict
from typing import Any, Dict, List, Optional, Tuple

import requests
import socketio
from dotenv import load_dotenv
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, InputFile, Update
from telegram.constants import ParseMode
from telegram.ext import (
    Application,
    CallbackQueryHandler,
    CommandHandler,
    ContextTypes,
    MessageHandler,
    filters,
)

load_dotenv()

# =========================
# CONFIG
# =========================
TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "").strip()
PRIVATE_CHAT_ID = os.getenv("TELEGRAM_PRIVATE_CHAT_ID", "").strip()
GROUP_CHAT_ID = os.getenv("TELEGRAM_GROUP_CHAT_ID", "").strip()

MVX_API = os.getenv("MVX_API", "https://api.multiversx.com").strip()
WOODY_TOKEN_ID = os.getenv("WOODY_TOKEN_ID", "WOODY-5f9d9c").strip()
WEGLD_TOKEN_ID = os.getenv("WEGLD_TOKEN_ID", "WEGLD-bd4d79").strip()

PRICE_URL = os.getenv("PRICE_URL", "https://e-compass.io/token/WOODY-5f9d9c").strip()
CHART_URL = os.getenv("CHART_URL", PRICE_URL).strip()
TWITTER_URL = os.getenv("TWITTER_URL", "https://x.com/WOODY_EX").strip()
BUY_XEXCHANGE_URL = os.getenv("BUY_XEXCHANGE_URL", "https://xexchange.com").strip()
BUY_XOXNO_URL = os.getenv("BUY_XOXNO_URL", "https://xoxno.com").strip()

XEXCHANGE_POOL_ADDRESS = os.getenv(
    "XEXCHANGE_POOL_ADDRESS",
    "erd1qqqqqqqqqqqqqpgqq66xk9gfr4esuhem3jru86wg5hvp33a62jps2fy57p",
).strip()
ONEDEX_POOL_ADDRESS = os.getenv(
    "ONEDEX_POOL_ADDRESS",
    "erd1qqqqqqqqqqqqqpgqqz6vp9y50ep867vnr296mqf3dduh6guvmvlsu3sujc",
).strip()
WOODY_USDC_POOL_ADDRESS = os.getenv(
    "WOODY_USDC_POOL_ADDRESS",
    "erd1qqqqqqqqqqqqqpgqjhy8hut0d9rzwqlz37e5nsmlj2rch6vd2jpss7a69j",
).strip()
WOODY_BOBER_POOL_ADDRESS = os.getenv(
    "WOODY_BOBER_POOL_ADDRESS",
    "erd1qqqqqqqqqqqqqpgqvq8vtfn26fdezjm07a7yjqtgn3h02af86avs9vf6kw",
).strip()
WOODY_JEX_POOL_ADDRESS = os.getenv(
    "WOODY_JEX_POOL_ADDRESS",
    "erd1qqqqqqqqqqqqqpgqdz5vj73j7h2velx83xwrad6zz82q2njr6avsrkua0n",
).strip()

ONEDEX_BURN_ADDRESS = os.getenv(
    "ONEDEX_BURN_ADDRESS",
    "erd1deaddeaddeaddeaddeaddeaddeaddeaddeaddeaddeaddeaddeaqtv0gag",
).strip()

BANNER_IMAGE = os.getenv("BANNER_IMAGE", "banner.png").strip()
BUY_IMAGE = os.getenv("BUY_IMAGE", "buy.png").strip()
SELL_IMAGE = os.getenv("SELL_IMAGE", "sell.png").strip()
LIQUIDITY_IMAGE = os.getenv("LIQUIDITY_IMAGE", "liquidity.png").strip()
NEW_HOLDER_IMAGE = os.getenv("NEW_HOLDER_IMAGE", "new_holder.png").strip()

SWAP_MIN_USD = float(os.getenv("SWAP_MIN_USD", "2"))

HOLDERS_CHECK_INTERVAL_SECONDS = int(os.getenv("HOLDERS_CHECK_INTERVAL_SECONDS", "180"))
GREETING_COOLDOWN_SECONDS = int(os.getenv("GREETING_COOLDOWN_SECONDS", "120"))

SEEN_TX_FILE = os.getenv("SEEN_TX_FILE", "seen_swaps.json").strip()
SWAP_LOG_FILE = os.getenv("SWAP_LOG_FILE", "large_swaps.json").strip()

# =========================
# LOGGING
# =========================
logging.basicConfig(
    format="%(asctime)s | %(levelname)s | %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger("WOODY_MONITOR_WS")

# =========================
# GLOBALS
# =========================
KNOWN_POOL_ADDRESSES = {
    XEXCHANGE_POOL_ADDRESS,
    ONEDEX_POOL_ADDRESS,
    WOODY_USDC_POOL_ADDRESS,
    WOODY_BOBER_POOL_ADDRESS,
    WOODY_JEX_POOL_ADDRESS,
}
KNOWN_POOL_ADDRESSES = {x for x in KNOWN_POOL_ADDRESSES if x}

TOKEN_PRICE_CACHE: Dict[str, Dict[str, float]] = {}
TOKEN_PRICE_CACHE_TTL = 60

last_known_holders = None
pending_holder_value = None

GREETING_REPLIES = [
    "👋 Welcome to the WOODY community!",
    "🪶 Glad to see you here in WOODY.",
    "☀️ GM! Welcome to WOODY.",
    "🚀 Welcome! The WOODY ecosystem keeps growing.",
]

WELCOME_NEW_MEMBER_MESSAGES = [
    "🪶 Welcome to the WOODY community!\n\nStay tuned for updates, trades and ecosystem news.",
    "🚀 A new WOODY has landed!\n\nWelcome to the community.",
    "👋 Welcome! WOODY Monitor is watching the ecosystem 24/7.",
]

# tx assembly buffers
TX_BUFFER: Dict[str, Dict[str, Any]] = {}
TX_BUFFER_LAST_UPDATE: Dict[str, float] = {}
TX_BUFFER_TTL_SECONDS = 4.0


# =========================
# HELPERS
# =========================
def require_token() -> None:
    if not TOKEN:
        raise ValueError("TELEGRAM_BOT_TOKEN is missing from environment variables")


def file_exists(path: str) -> bool:
    return bool(path) and os.path.exists(path)


def safe_float(value: Any) -> float:
    try:
        return float(value)
    except Exception:
        return 0.0


def short_wallet(addr: str) -> str:
    if not addr:
        return "unknown"
    if len(addr) < 18:
        return addr
    return f"{addr[:10]}...{addr[-8:]}"


def normalize_amount(raw: Any, decimals: int) -> float:
    try:
        return int(str(raw)) / (10 ** decimals)
    except Exception:
        return safe_float(raw)


def chat_targets() -> List[str]:
    targets = []
    if PRIVATE_CHAT_ID:
        targets.append(PRIVATE_CHAT_ID)
    if GROUP_CHAT_ID:
        targets.append(GROUP_CHAT_ID)
    return targets


def get_json(url: str, params: Optional[dict] = None) -> Optional[Any]:
    try:
        response = requests.get(url, params=params, timeout=25)
        response.raise_for_status()
        return response.json()
    except Exception as exc:
        logger.warning("GET JSON failed for %s -> %s", url, exc)
        return None


def load_json_file(path: str, default: Any) -> Any:
    if not os.path.exists(path):
        return default
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return default


def save_json_file(path: str, data: Any) -> None:
    try:
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
    except Exception as exc:
        logger.warning("Could not save %s -> %s", path, exc)


def add_seen_tx(tx_hash: str) -> None:
    seen = load_json_file(SEEN_TX_FILE, [])
    if tx_hash not in seen:
        seen.append(tx_hash)
        seen = seen[-5000:]
        save_json_file(SEEN_TX_FILE, seen)


def has_seen_tx(tx_hash: str) -> bool:
    seen = load_json_file(SEEN_TX_FILE, [])
    return tx_hash in seen


def log_large_swap(entry: dict) -> None:
    rows = load_json_file(SWAP_LOG_FILE, [])
    rows.append(entry)
    rows = rows[-2000:]
    save_json_file(SWAP_LOG_FILE, rows)


def get_token_usd_price(token_id: str) -> float:
    if not token_id:
        return 0.0

    token_id = token_id.strip()
    now_ts = time.time()

    cached = TOKEN_PRICE_CACHE.get(token_id)
    if cached and now_ts - cached.get("ts", 0) < TOKEN_PRICE_CACHE_TTL:
        return cached.get("price", 0.0)

    url = f"{MVX_API}/tokens/{token_id}"
    data = get_json(url)

    price = 0.0
    if isinstance(data, dict):
        for key in ("price", "usdPrice", "priceUsd", "priceUSD"):
            if data.get(key) is not None:
                price = safe_float(data.get(key))
                break

    TOKEN_PRICE_CACHE[token_id] = {"price": price, "ts": now_ts}
    return price


def get_holders_count() -> Optional[int]:
    url = f"{MVX_API}/tokens/{WOODY_TOKEN_ID}"
    data = get_json(url)
    if not isinstance(data, dict):
        return None

    accounts = data.get("accounts")
    if isinstance(accounts, int):
        return accounts

    try:
        return int(accounts)
    except Exception:
        return None


# =========================
# TELEGRAM MENU
# =========================
def main_menu_keyboard() -> InlineKeyboardMarkup:
    keyboard = [
        [
            InlineKeyboardButton("💰 Price", callback_data="price"),
            InlineKeyboardButton("💧 Liquidity", callback_data="liquidity"),
        ],
        [
            InlineKeyboardButton("👥 Holders", callback_data="holders"),
            InlineKeyboardButton("📈 Chart", callback_data="chart"),
        ],
        [
            InlineKeyboardButton("🟢 Buy xExchange", url=BUY_XEXCHANGE_URL),
            InlineKeyboardButton("🟢 Buy XOXNO", url=BUY_XOXNO_URL),
        ],
        [InlineKeyboardButton("𝕏 Twitter", url=TWITTER_URL)],
    ]
    return InlineKeyboardMarkup(keyboard)


def start_caption() -> str:
    return (
        "🪶 *Welcome to WOODY Monitor*\n\n"
        "Live transaction tracking for the WOODY ecosystem.\n\n"
        "This bot monitors:\n"
        "• Price\n"
        "• Liquidity status\n"
        "• Holders\n"
        "• Real-time WOODY transfers\n"
        "• Buy / Sell / Liquidity alerts\n\n"
        "Choose an option below 👇"
    )


async def send_start_menu(chat_id: int, context: ContextTypes.DEFAULT_TYPE) -> None:
    caption = start_caption()
    keyboard = main_menu_keyboard()

    if file_exists(BANNER_IMAGE):
        with open(BANNER_IMAGE, "rb") as photo:
            await context.bot.send_photo(
                chat_id=chat_id,
                photo=InputFile(photo),
                caption=caption,
                parse_mode=ParseMode.MARKDOWN,
                reply_markup=keyboard,
            )
    else:
        await context.bot.send_message(
            chat_id=chat_id,
            text=caption,
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=keyboard,
        )


def format_liquidity_text() -> str:
    return (
        "💧 *WOODY Liquidity*\n\n"
        f"• xExchange pool: `{XEXCHANGE_POOL_ADDRESS}`\n"
        f"• OneDex pool: `{ONEDEX_POOL_ADDRESS}`\n"
        f"• WOODY / USDC pool: `{WOODY_USDC_POOL_ADDRESS}`\n\n"
        f"🔒 OneDex LP burn wallet:\n`{ONEDEX_BURN_ADDRESS}`"
    )


def format_holders_text(count: Optional[int]) -> str:
    if count is None:
        return "👥 *WOODY Holders*\n\nCould not fetch holders right now."
    return f"👥 *WOODY Holders*\n\nCurrent holders: *{count}*"


async def send_alert_to_targets(
    context: ContextTypes.DEFAULT_TYPE,
    image_path: str,
    caption: str,
) -> None:
    for target in chat_targets():
        try:
            if file_exists(image_path):
                with open(image_path, "rb") as photo:
                    await context.bot.send_photo(
                        chat_id=target,
                        photo=InputFile(photo),
                        caption=caption,
                    )
            else:
                await context.bot.send_message(chat_id=target, text=caption)
        except Exception as exc:
            logger.warning("[ALERT ERROR] %s -> %s", target, exc)


# =========================
# WS + TX PARSING
# =========================
def get_ws_url() -> str:
    cfg = get_json(f"{MVX_API}/websocket/config")
    if not isinstance(cfg, dict) or not cfg.get("url"):
        raise RuntimeError("Could not fetch MultiversX websocket config")
    return f"https://{cfg['url']}"
    

def merge_same_tokens(items: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    merged: Dict[str, float] = defaultdict(float)
    for item in items:
        merged[item["token"]] += safe_float(item["amount"])
    return [{"token": token, "amount": amount} for token, amount in merged.items()]


def extract_transfers_from_action_args(entry: dict) -> List[Dict[str, Any]]:
    transfers = []
    action = entry.get("action") or {}
    arguments = action.get("arguments") or {}
    inner = arguments.get("transfers") or []

    for tr in inner:
        token = tr.get("token") or tr.get("identifier")
        decimals = int(tr.get("decimals", 18))
        value = tr.get("value", "0")
        amount = normalize_amount(value, decimals)
        if token:
            transfers.append({"token": token, "amount": amount})
    return transfers


def detect_pair_and_dex(entry: dict, sent_items: List[Dict[str, Any]], received_items: List[Dict[str, Any]]) -> Tuple[str, str]:
    sender = entry.get("sender", "")
    receiver = entry.get("receiver", "")

    dex = "Aggregator"
    if sender == WOODY_USDC_POOL_ADDRESS or receiver == WOODY_USDC_POOL_ADDRESS:
        dex = "xExchange / USDC"
    elif sender == XEXCHANGE_POOL_ADDRESS or receiver == XEXCHANGE_POOL_ADDRESS:
        dex = "xExchange"
    elif sender == ONEDEX_POOL_ADDRESS or receiver == ONEDEX_POOL_ADDRESS:
        dex = "OneDex"
    elif sender == WOODY_BOBER_POOL_ADDRESS or receiver == WOODY_BOBER_POOL_ADDRESS:
        dex = "Other / BOBER"
    elif sender == WOODY_JEX_POOL_ADDRESS or receiver == WOODY_JEX_POOL_ADDRESS:
        dex = "Other / JEX"

    quote = "?"
    for item in sent_items + received_items:
        if item["token"] != WOODY_TOKEN_ID:
            quote = item["token"]
            break

    return f"WOODY / {quote}", dex


def classify_aggregated_tx(entry: dict) -> Optional[Dict[str, Any]]:
    tx_hash = entry.get("originalTxHash") or entry.get("txHash")
    if not tx_hash:
        return None

    sent_items = merge_same_tokens(entry.get("sent_items", []))
    received_items = merge_same_tokens(entry.get("received_items", []))

    sent_tokens = {x["token"] for x in sent_items}
    received_tokens = {x["token"] for x in received_items}

    woody_sent = WOODY_TOKEN_ID in sent_tokens
    woody_received = WOODY_TOKEN_ID in received_tokens

    lp_received = any("WOODY" in x["token"] and ("LP" in x["token"].upper() or "WEGLD" in x["token"]) for x in received_items)

    tx_type = None
    if woody_received and not woody_sent:
        tx_type = "BUY"
    elif woody_sent and not woody_received:
        tx_type = "SELL"
    elif woody_sent and lp_received:
        tx_type = "LIQUIDITY"
    else:
        return None

    woody_amount = 0.0
    if tx_type == "BUY":
        for item in received_items:
            if item["token"] == WOODY_TOKEN_ID:
                woody_amount = safe_float(item["amount"])
                break
    else:
        for item in sent_items:
            if item["token"] == WOODY_TOKEN_ID:
                woody_amount = safe_float(item["amount"])
                break

    if tx_type == "BUY":
        quote_candidates = [x for x in sent_items if x["token"] != WOODY_TOKEN_ID]
    elif tx_type == "SELL":
        quote_candidates = [x for x in received_items if x["token"] != WOODY_TOKEN_ID]
    else:
        quote_candidates = [x for x in sent_items if x["token"] != WOODY_TOKEN_ID]

    quote_token = "?"
    quote_amount = 0.0
    if quote_candidates:
        quote_candidates.sort(key=lambda x: safe_float(x["amount"]), reverse=True)
        quote_token = quote_candidates[0]["token"]
        quote_amount = safe_float(quote_candidates[0]["amount"])

    swap_usd_value = 0.0
    if "USDC" in quote_token.upper():
        swap_usd_value = quote_amount
    else:
        price = get_token_usd_price(quote_token)
        if price > 0:
            swap_usd_value = quote_amount * price

    pair, dex = detect_pair_and_dex(entry, sent_items, received_items)

    return {
        "tx_hash": tx_hash,
        "type": tx_type,
        "woody_amount": woody_amount,
        "quote_token": quote_token,
        "quote_amount": quote_amount,
        "swap_usd_value": swap_usd_value,
        "pair": pair,
        "dex": dex,
        "sender": entry.get("sender", ""),
        "receiver": entry.get("receiver", ""),
        "function": entry.get("function") or ((entry.get("action") or {}).get("name")) or "transfer",
        "sent_items": sent_items,
        "received_items": received_items,
        "timestamp": entry.get("timestamp"),
    }


def build_message(parsed: Dict[str, Any]) -> str:
    explorer = f"https://explorer.multiversx.com/transactions/{parsed['tx_hash']}"

    sent_block = "\n".join(
        f"{item['amount']:,.6f} {item['token']}" for item in parsed["sent_items"]
    ) or "-"

    received_block = "\n".join(
        f"{item['amount']:,.6f} {item['token']}" for item in parsed["received_items"]
    ) or "-"

    if parsed["type"] == "BUY":
        title = "🟢 WOODY BUY ALERT"
    elif parsed["type"] == "SELL":
        title = "🔴 WOODY SELL ALERT"
    else:
        title = "💧 WOODY LIQUIDITY ADDED"

    return (
        f"{title}\n\n"
        f"🔁 Transaction: `{short_wallet(parsed['tx_hash'])}`\n"
        f"📤 From: `{short_wallet(parsed['sender'])}`\n"
        f"📥 To: `{short_wallet(parsed['receiver'])}`\n"
        f"🧩 Data: `{parsed['function']}`\n\n"
        f"⬅️ Sent:\n{sent_block}\n\n"
        f"➡️ Received:\n{received_block}\n\n"
        f"🪶 WOODY: {parsed['woody_amount']:,.2f}\n"
        f"💵 Quote: {parsed['quote_amount']:,.6f} {parsed['quote_token']}\n"
        f"💲 Swap value: ${parsed['swap_usd_value']:,.2f}\n"
        f"💱 Pair: {parsed['pair']}\n"
        f"🏦 DEX: {parsed['dex']}\n"
        f"🔗 {explorer}"
    )


def choose_image(tx_type: str) -> str:
    if tx_type == "BUY":
        return BUY_IMAGE
    if tx_type == "SELL":
        return SELL_IMAGE
    return LIQUIDITY_IMAGE


# =========================
# TELEGRAM HANDLERS
# =========================
async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await send_start_menu(update.effective_chat.id, context)


async def status_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    text = (
        "✅ *WOODY Monitor is running*\n\n"
        f"Live source: *MultiversX WebSocket*\n"
        f"Filter token: *{WOODY_TOKEN_ID}*\n"
        f"Min swap value: *${SWAP_MIN_USD}*"
    )
    await update.message.reply_text(text, parse_mode=ParseMode.MARKDOWN)


async def id_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_text(f"Chat ID: {update.effective_chat.id}")


async def menu_callbacks(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()

    if query.data == "price":
        keyboard = InlineKeyboardMarkup([[InlineKeyboardButton("📈 Open Price", url=PRICE_URL)]])
        await query.message.reply_text("💰 *WOODY Price*", parse_mode=ParseMode.MARKDOWN, reply_markup=keyboard)

    elif query.data == "liquidity":
        await query.message.reply_text(format_liquidity_text(), parse_mode=ParseMode.MARKDOWN)

    elif query.data == "holders":
        holders = get_holders_count()
        await query.message.reply_text(format_holders_text(holders), parse_mode=ParseMode.MARKDOWN)

    elif query.data == "chart":
        keyboard = InlineKeyboardMarkup([[InlineKeyboardButton("📊 Open Chart", url=CHART_URL)]])
        await query.message.reply_text("📈 *WOODY Chart*", parse_mode=ParseMode.MARKDOWN, reply_markup=keyboard)


async def greeting_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not update.message or not update.message.text:
        return

    text = update.message.text.strip().lower()
    if text.startswith("/"):
        return

    if text not in {"hello", "hi", "hey", "gm", "good morning", "salut", "buna", "bună"}:
        return

    now = int(time.time())
    last_ts = context.application.bot_data.get("last_greet_ts", 0)
    if now - last_ts < GREETING_COOLDOWN_SECONDS:
        return

    context.application.bot_data["last_greet_ts"] = now
    await update.message.reply_text(GREETING_REPLIES[now % len(GREETING_REPLIES)])


async def welcome_new_members(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not update.message or not update.message.new_chat_members:
        return

    for member in update.message.new_chat_members:
        if member.is_bot:
            continue
        await update.message.reply_text(
            WELCOME_NEW_MEMBER_MESSAGES[int(time.time()) % len(WELCOME_NEW_MEMBER_MESSAGES)]
        )


# =========================
# HOLDERS JOB
# =========================
async def check_new_holders(context: ContextTypes.DEFAULT_TYPE):
    global last_known_holders
    global pending_holder_value

    holders = get_holders_count()
    if holders is None:
        return

    if last_known_holders is None:
        last_known_holders = holders
        return

    if holders > last_known_holders:
        if pending_holder_value is None:
            pending_holder_value = holders
            return

        if holders == pending_holder_value:
            added = holders - last_known_holders
            caption = (
                f"👤 WOODY NEW HOLDER\n\n"
                f"Added holders: +{added}\n"
                f"Total holders: {holders}"
            )
            await send_alert_to_targets(context, NEW_HOLDER_IMAGE, caption)
            last_known_holders = holders
            pending_holder_value = None
    else:
        pending_holder_value = None


# =========================
# WEBSOCKET WORKER
# =========================
class WoofyWsWorker:
    def __init__(self, application: Application):
        self.app = application
        self.sio = socketio.Client(
            reconnection=True,
            reconnection_attempts=0,
            reconnection_delay=1,
            logger=False,
            engineio_logger=False,
            ssl_verify=True,
        )
        self.ws_url = ""
        self.context = None

        @self.sio.event
        def connect():
            logger.info("WebSocket connected")
            payload = {"token": WOODY_TOKEN_ID}
            self.sio.emit("subscribeCustomTransfers", payload)
            logger.info("Subscribed to custom transfers for %s", WOODY_TOKEN_ID)

        @self.sio.event
        def disconnect():
            logger.warning("WebSocket disconnected")

        @self.sio.on("error")
        def on_error(data):
            logger.warning("WebSocket server error: %s", data)

        @self.sio.on("customTransferUpdate")
        def on_custom_transfer_update(data):
            try:
                self.handle_transfer_update(data)
            except Exception as exc:
                logger.exception("handle_transfer_update failed: %s", exc)

    def handle_transfer_update(self, data: dict) -> None:
        transfers = data.get("transfers", [])
        for entry in transfers:
            tx_hash = entry.get("originalTxHash") or entry.get("txHash")
            if not tx_hash:
                continue

            # first boot protection
            if not self.app.bot_data.get("ws_initialized"):
                add_seen_tx(tx_hash)
                continue

            sent_items = []
            received_items = []

            action_transfers = extract_transfers_from_action_args(entry)
            sender = entry.get("sender", "")
            receiver = entry.get("receiver", "")

            for tr in action_transfers:
                token = tr["token"]
                amount = tr["amount"]
                if sender and sender not in KNOWN_POOL_ADDRESSES:
                    sent_items.append({"token": token, "amount": amount})
                else:
                    received_items.append({"token": token, "amount": amount})

            # fallback direct current token
            if not action_transfers:
                action = entry.get("action") or {}
                arguments = action.get("arguments") or {}
                token = None
                decimals = 18
                value = "0"

                inner = arguments.get("transfers") or []
                if inner:
                    tr = inner[0]
                    token = tr.get("token") or tr.get("identifier")
                    decimals = int(tr.get("decimals", 18))
                    value = tr.get("value", "0")

                if token:
                    amount = normalize_amount(value, decimals)
                    if sender and sender not in KNOWN_POOL_ADDRESSES:
                        sent_items.append({"token": token, "amount": amount})
                    else:
                        received_items.append({"token": token, "amount": amount})

            bucket = TX_BUFFER.setdefault(tx_hash, {
                "txHash": entry.get("txHash"),
                "originalTxHash": entry.get("originalTxHash"),
                "sender": sender,
                "receiver": receiver,
                "function": entry.get("function"),
                "action": entry.get("action"),
                "timestamp": entry.get("timestamp"),
                "sent_items": [],
                "received_items": [],
            })

            bucket["sent_items"].extend(sent_items)
            bucket["received_items"].extend(received_items)
            TX_BUFFER_LAST_UPDATE[tx_hash] = time.time()

        # after first packet batch, enable live mode
        if not self.app.bot_data.get("ws_initialized"):
            self.app.bot_data["ws_initialized"] = True
            logger.info("Initial WS sync complete. Old transfers skipped.")

        self.flush_ready_transactions()

    def flush_ready_transactions(self) -> None:
        now_ts = time.time()
        ready_hashes = [
            tx_hash for tx_hash, ts in TX_BUFFER_LAST_UPDATE.items()
            if now_ts - ts >= TX_BUFFER_TTL_SECONDS
        ]

        for tx_hash in ready_hashes:
            if has_seen_tx(tx_hash):
                TX_BUFFER.pop(tx_hash, None)
                TX_BUFFER_LAST_UPDATE.pop(tx_hash, None)
                continue

            entry = TX_BUFFER.pop(tx_hash, None)
            TX_BUFFER_LAST_UPDATE.pop(tx_hash, None)

            if not entry:
                continue

            add_seen_tx(tx_hash)

            parsed = classify_aggregated_tx(entry)
            if not parsed:
                continue

            if parsed["swap_usd_value"] < SWAP_MIN_USD:
                continue

            caption = build_message(parsed)
            image = choose_image(parsed["type"])

            self.app.create_task(send_alert_to_targets(self.context, image, caption))

            log_large_swap(
                {
                    "txHash": parsed["tx_hash"],
                    "type": parsed["type"],
                    "woody_amount": parsed["woody_amount"],
                    "quote_token": parsed["quote_token"],
                    "quote_amount": parsed["quote_amount"],
                    "swap_usd_value": parsed["swap_usd_value"],
                    "pair": parsed["pair"],
                    "dex": parsed["dex"],
                    "timestamp": parsed["timestamp"],
                }
            )

    async def start(self, context: ContextTypes.DEFAULT_TYPE) -> None:
        self.context = context
        self.ws_url = get_ws_url()
        logger.info("Resolved WebSocket cluster: %s", self.ws_url)

        def _connect():
            self.sio.connect(
                self.ws_url,
                socketio_path="/ws/subscription",
                transports=["websocket"],
                wait_timeout=20,
            )
            self.sio.wait()

        import threading
        thread = threading.Thread(target=_connect, daemon=True)
        thread.start()


# =========================
# MAIN
# =========================
async def bootstrap_ws(context: ContextTypes.DEFAULT_TYPE):
    if context.application.bot_data.get("ws_worker_started"):
        return
    worker = WoofyWsWorker(context.application)
    context.application.bot_data["ws_worker"] = worker
    context.application.bot_data["ws_worker_started"] = True
    await worker.start(context)


def main() -> None:
    require_token()

    app = Application.builder().token(TOKEN).build()

    app.add_handler(CommandHandler("start", start_command))
    app.add_handler(CommandHandler("status", status_command))
    app.add_handler(CommandHandler("id", id_command))
    app.add_handler(CallbackQueryHandler(menu_callbacks))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, greeting_handler))
    app.add_handler(MessageHandler(filters.StatusUpdate.NEW_CHAT_MEMBERS, welcome_new_members))

    if app.job_queue is None:
        raise RuntimeError("JobQueue is missing. Install python-telegram-bot[job-queue].")

    app.job_queue.run_once(bootstrap_ws, when=3)
    app.job_queue.run_repeating(check_new_holders, interval=HOLDERS_CHECK_INTERVAL_SECONDS, first=20)

    logger.info("WOODY Monitor WebSocket Bot started...")
    app.run_polling(drop_pending_updates=True)


if __name__ == "__main__":
    main()
