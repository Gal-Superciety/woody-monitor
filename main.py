import json
import logging
import os
import time
from typing import Any, Dict, List, Optional, Tuple

import requests
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

WOODY_MEX_POOL_ADDRESS = os.getenv("WOODY_MEX_POOL_ADDRESS", "").strip()

WOODY_BOBER_POOL_ADDRESS = os.getenv(
    "WOODY_BOBER_POOL_ADDRESS",
    "erd1qqqqqqqqqqqqqpgqvq8vtfn26fdezjm07a7yjqtgn3h02af86avs9vf6kw",
).strip()

WOODY_JEX_POOL_ADDRESS = os.getenv(
    "WOODY_JEX_POOL_ADDRESS",
    "erd1qqqqqqqqqqqqqpgqdz5vj73j7h2velx83xwrad6zz82q2njr6avsrkua0n",
).strip()

WOODY_USDC_POOL_ADDRESS = os.getenv(
    "WOODY_USDC_POOL_ADDRESS",
    "erd1qqqqqqqqqqqqqpgqjhy8hut0d9rzwqlz37e5nsmlj2rch6vd2jpss7a69j",
).strip()

ONEDEX_BURN_ADDRESS = os.getenv(
    "ONEDEX_BURN_ADDRESS",
    "erd1deaddeaddeaddeaddeaddeaddeaddeaddeaddeaddeaddeaddeaqtv0gag",
).strip()

# Images
BANNER_IMAGE = os.getenv("BANNER_IMAGE", "banner.png").strip()
BUY_IMAGE = os.getenv("BUY_IMAGE", "buy.png").strip()
SELL_IMAGE = os.getenv("SELL_IMAGE", "sell.png").strip()
BIG_BUY_IMAGE = os.getenv("BIG_BUY_IMAGE", "big_buy.png").strip()
BIG_SELL_IMAGE = os.getenv("BIG_SELL_IMAGE", "big_sell.png").strip()
NEW_HOLDER_IMAGE = os.getenv("NEW_HOLDER_IMAGE", "new_holder.png").strip()
WHALE_BUY_IMAGE = os.getenv("WHALE_BUY_IMAGE", "whale_buy.png").strip()
SUPER_WHALE_IMAGE = os.getenv("SUPER_WHALE_IMAGE", "super_whale.png").strip()
LIQUIDITY_IMAGE = os.getenv("LIQUIDITY_IMAGE", "liquidity.png").strip()

# Thresholds
SWAP_MIN_USD = float(os.getenv("SWAP_MIN_USD", "2"))
BIG_ALERT_USD = float(os.getenv("BIG_ALERT_USD", "25"))
WHALE_ALERT_USD = float(os.getenv("WHALE_ALERT_USD", "100"))
SUPER_WHALE_ALERT_USD = float(os.getenv("SUPER_WHALE_ALERT_USD", "500"))

# Intervals
CHECK_INTERVAL_SECONDS = int(os.getenv("CHECK_INTERVAL_SECONDS", "20"))
GREETING_COOLDOWN_SECONDS = int(os.getenv("GREETING_COOLDOWN_SECONDS", "120"))
HOLDERS_CHECK_INTERVAL_SECONDS = int(os.getenv("HOLDERS_CHECK_INTERVAL_SECONDS", "180"))

# Local storage
SEEN_TX_FILE = os.getenv("SEEN_TX_FILE", "seen_swaps.json").strip()
SWAP_LOG_FILE = os.getenv("SWAP_LOG_FILE", "large_swaps.json").strip()

# =========================
# LOGGING
# =========================
logging.basicConfig(
    format="%(asctime)s | %(levelname)s | %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger("WOODY_MONITOR")

# =========================
# STATIC TEXT
# =========================
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

# =========================
# GLOBALS
# =========================
last_known_holders = None
pending_holder_value = None

KNOWN_POOL_ADDRESSES = {
    XEXCHANGE_POOL_ADDRESS,
    ONEDEX_POOL_ADDRESS,
    WOODY_MEX_POOL_ADDRESS,
    WOODY_BOBER_POOL_ADDRESS,
    WOODY_JEX_POOL_ADDRESS,
    WOODY_USDC_POOL_ADDRESS,
}
KNOWN_POOL_ADDRESSES = {x for x in KNOWN_POOL_ADDRESSES if x}

TOKEN_PRICE_CACHE: Dict[str, Dict[str, float]] = {}
TOKEN_PRICE_CACHE_TTL = 60


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
        seen = seen[-3000:]
        save_json_file(SEEN_TX_FILE, seen)


def has_seen_tx(tx_hash: str) -> bool:
    seen = load_json_file(SEEN_TX_FILE, [])
    return tx_hash in seen


def log_large_swap(entry: dict) -> None:
    rows = load_json_file(SWAP_LOG_FILE, [])
    rows.append(entry)
    rows = rows[-1500:]
    save_json_file(SWAP_LOG_FILE, rows)


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


def greeting_detected(text: str) -> bool:
    value = text.lower().strip()
    greetings = {"hello", "hi", "hey", "gm", "good morning", "salut", "buna", "bună"}
    return value in greetings


def normalize_amount(raw: Any, decimals: int) -> float:
    try:
        return int(str(raw)) / (10 ** decimals)
    except Exception:
        return safe_float(raw)


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


def get_swap_usd_value(parsed: Dict[str, Any]) -> float:
    quote_token = (parsed.get("quote_token") or "").strip()
    quote_amount = safe_float(parsed.get("quote_amount", 0.0))

    if quote_amount <= 0 or not quote_token:
        return 0.0

    if "USDC" in quote_token.upper():
        return quote_amount

    token_price = get_token_usd_price(quote_token)
    if token_price > 0:
        return quote_amount * token_price

    return 0.0


def choose_title(tx_type: str, swap_usd_value: float) -> str:
    if tx_type == "BUY":
        if swap_usd_value >= SUPER_WHALE_ALERT_USD:
            return "👑 WOODY SUPER WHALE BUY"
        if swap_usd_value >= WHALE_ALERT_USD:
            return "🐋 WOODY WHALE BUY"
        if swap_usd_value >= BIG_ALERT_USD:
            return "🚨 WOODY BIG BUY"
        return "🟢 WOODY BUY ALERT"

    if tx_type == "SELL":
        if swap_usd_value >= WHALE_ALERT_USD:
            return "🐋 WOODY WHALE SELL"
        if swap_usd_value >= BIG_ALERT_USD:
            return "💥 WOODY BIG SELL"
        return "🔴 WOODY SELL ALERT"

    return "💧 WOODY LIQUIDITY ADDED"


def choose_image(tx_type: str, swap_usd_value: float) -> str:
    if tx_type == "BUY":
        if swap_usd_value >= SUPER_WHALE_ALERT_USD:
            return SUPER_WHALE_IMAGE
        if swap_usd_value >= WHALE_ALERT_USD:
            return WHALE_BUY_IMAGE
        if swap_usd_value >= BIG_ALERT_USD:
            return BIG_BUY_IMAGE
        return BUY_IMAGE

    if tx_type == "SELL":
        if swap_usd_value >= BIG_ALERT_USD:
            return BIG_SELL_IMAGE
        return SELL_IMAGE

    return LIQUIDITY_IMAGE


def format_liquidity_text() -> str:
    pools = [
        f"• xExchange pool: `{XEXCHANGE_POOL_ADDRESS}`",
        f"• OneDex pool: `{ONEDEX_POOL_ADDRESS}`",
        f"• WOODY/USDC pool: `{WOODY_USDC_POOL_ADDRESS}`",
    ]
    if WOODY_MEX_POOL_ADDRESS:
        pools.append(f"• WOODY/MEX pool: `{WOODY_MEX_POOL_ADDRESS}`")
    if WOODY_BOBER_POOL_ADDRESS:
        pools.append(f"• WOODY/BOBER pool: `{WOODY_BOBER_POOL_ADDRESS}`")
    if WOODY_JEX_POOL_ADDRESS:
        pools.append(f"• WOODY/JEX pool: `{WOODY_JEX_POOL_ADDRESS}`")

    lines = [
        "💧 *WOODY Liquidity*",
        "",
        *pools,
        "",
        "🔒 OneDex LP burn wallet:",
        f"`{ONEDEX_BURN_ADDRESS}`",
    ]
    return "\n".join(lines)


def format_holders_text(count: Optional[int]) -> str:
    if count is None:
        return "👥 *WOODY Holders*\n\nCould not fetch holders right now."
    return f"👥 *WOODY Holders*\n\nCurrent holders: *{count}*"


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
        "The real-time tracker for the WOODY ecosystem.\n\n"
        "This bot monitors:\n"
        "• Price\n"
        "• Liquidity status\n"
        "• Holders\n"
        "• Token swaps\n"
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


def fetch_recent_woody_transactions(size: int = 30) -> List[dict]:
    url = f"{MVX_API}/transactions"
    params = {
        "status": "success",
        "token": WOODY_TOKEN_ID,
        "withOperations": "true",
        "size": size,
    }
    data = get_json(url, params=params)
    if isinstance(data, list):
        return data
    return []


def choose_user_wallet(tx: dict) -> str:
    sender = tx.get("sender", "")
    receiver = tx.get("receiver", "")

    if sender and sender not in KNOWN_POOL_ADDRESSES:
        return sender
    if receiver and receiver not in KNOWN_POOL_ADDRESSES:
        return receiver

    operations = tx.get("operations", [])
    for op in operations:
        for field in ("sender", "receiver"):
            addr = op.get(field, "")
            if addr and addr not in KNOWN_POOL_ADDRESSES and not addr.startswith("erd1qqqqqqqqqqqqqpgq"):
                return addr

    return sender or receiver or "unknown"


def detect_pair_and_dex(tx: dict) -> Tuple[str, str]:
    operations = tx.get("operations", [])
    pair = "WOODY / ?"
    dex = "Aggregator"

    addresses = set()
    for op in operations:
        if op.get("sender"):
            addresses.add(op["sender"])
        if op.get("receiver"):
            addresses.add(op["receiver"])

    if WOODY_USDC_POOL_ADDRESS in addresses:
        dex = "xExchange / USDC"
    elif XEXCHANGE_POOL_ADDRESS in addresses:
        dex = "xExchange"
    elif ONEDEX_POOL_ADDRESS in addresses:
        dex = "OneDex"
    elif WOODY_BOBER_POOL_ADDRESS in addresses:
        dex = "JEX / Other"
    elif WOODY_JEX_POOL_ADDRESS in addresses:
        dex = "JEX / Other"

    quote_tokens = []
    for op in operations:
        ident = (op.get("identifier") or op.get("tokenIdentifier") or "").strip()
        if ident and ident != WOODY_TOKEN_ID:
            quote_tokens.append(ident)

    quote = quote_tokens[0] if quote_tokens else "?"
    pair = f"WOODY / {quote}"
    return pair, dex


def parse_tx_from_wallet_perspective(tx: dict) -> Optional[Dict[str, Any]]:
    operations = tx.get("operations", [])
    if not operations:
        return None

    wallet = choose_user_wallet(tx)

    woody_in = 0.0
    woody_out = 0.0
    quote_in = 0.0
    quote_out = 0.0
    quote_token = None

    for op in operations:
        token_id = (op.get("identifier") or op.get("tokenIdentifier") or "").strip()
        decimals = int(op.get("decimals", 18))
        amount = normalize_amount(op.get("value", "0"), decimals)
        op_sender = op.get("sender", "")
        op_receiver = op.get("receiver", "")

        if token_id == WOODY_TOKEN_ID:
            if op_receiver == wallet:
                woody_in += amount
            if op_sender == wallet:
                woody_out += amount
        else:
            if token_id:
                quote_token = token_id
            if op_receiver == wallet:
                quote_in += amount
            if op_sender == wallet:
                quote_out += amount

    pair, dex = detect_pair_and_dex(tx)

    tx_type = None
    woody_amount = 0.0
    quote_amount = 0.0

    if woody_in > 0 and quote_out > 0:
        tx_type = "BUY"
        woody_amount = woody_in
        quote_amount = quote_out
    elif woody_out > 0 and quote_in > 0:
        tx_type = "SELL"
        woody_amount = woody_out
        quote_amount = quote_in
    elif woody_out > 0 and quote_out > 0:
        tx_type = "LIQUIDITY"
        woody_amount = woody_out
        quote_amount = quote_out
    else:
        return None

    return {
        "wallet": wallet,
        "type": tx_type,
        "woody_amount": woody_amount,
        "quote_amount": quote_amount,
        "quote_token": quote_token or "?",
        "pair": pair,
        "dex": dex,
    }


def should_alert(parsed: Dict[str, Any]) -> bool:
    swap_usd_value = get_swap_usd_value(parsed)
    return swap_usd_value >= SWAP_MIN_USD


def build_swap_message(tx: dict, parsed: Dict[str, Any]) -> str:
    tx_hash = tx.get("txHash") or tx.get("hash") or ""
    explorer = f"https://explorer.multiversx.com/transactions/{tx_hash}"
    swap_usd_value = get_swap_usd_value(parsed)

    return (
        f"{choose_title(parsed['type'], swap_usd_value)}\n\n"
        f"🔁 Type: {parsed['type']}\n"
        f"👤 Wallet: {short_wallet(parsed['wallet'])}\n"
        f"🪙 WOODY: {parsed['woody_amount']:,.2f}\n"
        f"💵 Quote: {parsed['quote_amount']:,.6f} {parsed['quote_token']}\n"
        f"💲 Swap value: ${swap_usd_value:,.2f}\n"
        f"💱 Pair: {parsed['pair']}\n"
        f"🏦 DEX: {parsed['dex']}\n"
        f"🔗 {explorer}"
    )


# =========================
# TELEGRAM HANDLERS
# =========================
async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await send_start_menu(update.effective_chat.id, context)


async def status_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    text = (
        "✅ *WOODY Monitor is running*\n\n"
        f"Private alerts: *{'YES' if PRIVATE_CHAT_ID else 'NO'}*\n"
        f"Group alerts: *{'YES' if GROUP_CHAT_ID else 'NO'}*\n\n"
        f"Universal swap filter:\n"
        f"• Min swap value: *${SWAP_MIN_USD}*\n\n"
        f"Big alert: *≥ ${BIG_ALERT_USD}*\n"
        f"Whale alert: *≥ ${WHALE_ALERT_USD}*\n"
        f"Super whale: *≥ ${SUPER_WHALE_ALERT_USD}*"
    )
    await update.message.reply_text(text, parse_mode=ParseMode.MARKDOWN)


async def id_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_text(f"Chat ID: {update.effective_chat.id}")


async def menu_callbacks(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()

    if query.data == "price":
        text = "💰 *WOODY Price*\n\nOpen the official chart / price source below."
        keyboard = InlineKeyboardMarkup([[InlineKeyboardButton("📈 Open Price", url=PRICE_URL)]])
        await query.message.reply_text(text, parse_mode=ParseMode.MARKDOWN, reply_markup=keyboard)

    elif query.data == "liquidity":
        await query.message.reply_text(format_liquidity_text(), parse_mode=ParseMode.MARKDOWN)

    elif query.data == "holders":
        holders = get_holders_count()
        await query.message.reply_text(format_holders_text(holders), parse_mode=ParseMode.MARKDOWN)

    elif query.data == "chart":
        text = "📈 *WOODY Chart*\n\nOpen the chart below."
        keyboard = InlineKeyboardMarkup([[InlineKeyboardButton("📊 Open Chart", url=CHART_URL)]])
        await query.message.reply_text(text, parse_mode=ParseMode.MARKDOWN, reply_markup=keyboard)


async def greeting_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not update.message or not update.message.text:
        return

    text = update.message.text.strip()
    if text.startswith("/"):
        return

    if not greeting_detected(text):
        return

    now = int(time.time())
    last_ts = context.application.bot_data.get("last_greet_ts", 0)

    if now - last_ts < GREETING_COOLDOWN_SECONDS:
        return

    context.application.bot_data["last_greet_ts"] = now
    await update.message.reply_text(GREETING_REPLIES[int(now) % len(GREETING_REPLIES)])


async def welcome_new_members(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not update.message or not update.message.new_chat_members:
        return

    for member in update.message.new_chat_members:
        if member.is_bot:
            continue
        await update.message.reply_text(WELCOME_NEW_MEMBER_MESSAGES[int(time.time()) % len(WELCOME_NEW_MEMBER_MESSAGES)])


# =========================
# BACKGROUND JOBS
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


async def check_swaps(context: ContextTypes.DEFAULT_TYPE) -> None:
    logger.info("Checking WOODY token transactions...")

    txs = fetch_recent_woody_transactions(size=30)
    if not txs:
        return

    # prima sincronizare: marcheaza ce exista deja, fara sa trimita spam
    if not context.application.bot_data.get("swaps_initialized"):
        for tx in txs:
            tx_hash = tx.get("txHash") or tx.get("hash")
            if tx_hash:
                add_seen_tx(tx_hash)
        context.application.bot_data["swaps_initialized"] = True
        logger.info("Initial swap sync complete. Old transactions skipped.")
        return

    for tx in reversed(txs):
        tx_hash = tx.get("txHash") or tx.get("hash")
        if not tx_hash:
            continue

        if has_seen_tx(tx_hash):
            continue

        add_seen_tx(tx_hash)

        parsed = parse_tx_from_wallet_perspective(tx)
        if not parsed:
            continue

        if not should_alert(parsed):
            continue

        swap_usd_value = get_swap_usd_value(parsed)
        image = choose_image(parsed["type"], swap_usd_value)
        caption = build_swap_message(tx, parsed)

        await send_alert_to_targets(context, image, caption)

        log_large_swap(
            {
                "txHash": tx_hash,
                "wallet": parsed["wallet"],
                "type": parsed["type"],
                "woody": parsed["woody_amount"],
                "quote_amount": parsed["quote_amount"],
                "quote_token": parsed["quote_token"],
                "swap_usd_value": swap_usd_value,
                "pair": parsed["pair"],
                "dex": parsed["dex"],
                "timestamp": tx.get("timestamp"),
                "explorer": f"https://explorer.multiversx.com/transactions/{tx_hash}",
            }
        )


# =========================
# MAIN
# =========================
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

    app.job_queue.run_repeating(check_swaps, interval=CHECK_INTERVAL_SECONDS, first=10)
    app.job_queue.run_repeating(check_new_holders, interval=HOLDERS_CHECK_INTERVAL_SECONDS, first=20)

    logger.info("WOODY Monitor Bot started...")
    app.run_polling(drop_pending_updates=True)


if __name__ == "__main__":
    main()
