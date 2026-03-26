import json
import logging
import os
import random
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
USDC_TOKEN_ID = os.getenv("USDC_TOKEN_ID", "USDC-c76f1f").strip()  # modifică dacă ai alt identifier
MEX_TOKEN_ID = os.getenv("MEX_TOKEN_ID", "").strip()
BOBER_TOKEN_ID = os.getenv("BOBER_TOKEN_ID", "").strip()
JEX_TOKEN_ID = os.getenv("JEX_TOKEN_ID", "").strip()

PRICE_URL = os.getenv("PRICE_URL", "https://e-compass.io/token/WOODY-5f9d9c").strip()
CHART_URL = os.getenv("CHART_URL", PRICE_URL).strip()
TWITTER_URL = os.getenv("TWITTER_URL", "https://x.com/WOODY_EX").strip()
BUY_XEXCHANGE_URL = os.getenv("BUY_XEXCHANGE_URL", "https://xexchange.com").strip()
BUY_XOXNO_URL = os.getenv("BUY_XOXNO_URL", "https://xoxno.com").strip()

# Pools
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
    "",
).strip()

WOODY_MEX_POOL_ADDRESS = os.getenv(
    "WOODY_MEX_POOL_ADDRESS",
    "",
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

# Images
BANNER_IMAGE = os.getenv("BANNER_IMAGE", "banner.png").strip()
BUY_IMAGE = os.getenv("BUY_IMAGE", "buy.png").strip()
SELL_IMAGE = os.getenv("SELL_IMAGE", "sell.png").strip()
BIG_BUY_IMAGE = os.getenv("BIG_BUY_IMAGE", "big_buy.png").strip()
BIG_SELL_IMAGE = os.getenv("BIG_SELL_IMAGE", "big_sell.png").strip()
NEW_HOLDER_IMAGE = os.getenv("NEW_HOLDER_IMAGE", "new_holder.png").strip()
WHALE_BUY_IMAGE = os.getenv("WHALE_BUY_IMAGE", "whale_buy.png").strip()
SUPER_WHALE_IMAGE = os.getenv("SUPER_WHALE_IMAGE", "super_whale.png").strip()

# Thresholds
SWAP_MIN_WOODY = float(os.getenv("SWAP_MIN_WOODY", "10000"))
SWAP_MIN_EGLD = float(os.getenv("SWAP_MIN_EGLD", "0.2"))
BIG_ALERT_EGLD = float(os.getenv("BIG_ALERT_EGLD", "1"))
WHALE_ALERT_EGLD = float(os.getenv("WHALE_ALERT_EGLD", "3"))
SUPER_WHALE_ALERT_EGLD = float(os.getenv("SUPER_WHALE_ALERT_EGLD", "10"))

CHECK_INTERVAL_SECONDS = int(os.getenv("CHECK_INTERVAL_SECONDS", "20"))
GREETING_COOLDOWN_SECONDS = int(os.getenv("GREETING_COOLDOWN_SECONDS", "120"))
HOLDERS_CHECK_INTERVAL_SECONDS = int(os.getenv("HOLDERS_CHECK_INTERVAL_SECONDS", "180"))

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
# RANDOM TEXTS
# =========================
GREETING_REPLIES = [
    "👋 Welcome to the WOODY community!",
    "🪶 Glad to see you here in WOODY.",
    "☀️ GM! Welcome to WOODY.",
    "🚀 Welcome! The WOODY ecosystem keeps growing.",
    "🔥 Another legend just said hello in WOODY.",
]

WELCOME_NEW_MEMBER_MESSAGES = [
    "🪶 Welcome to the WOODY community!\n\nStay tuned for updates, trades and ecosystem news.",
    "🚀 A new WOODY has landed!\n\nWelcome to the community.",
    "👋 Welcome! WOODY Monitor is watching the ecosystem 24/7.",
    "🔥 Great to have you here!\n\nYou’re now part of the WOODY community.",
]

BUY_ALERT_TITLES = [
    "🟢 WOODY BUY ALERT",
    "🚀 Fresh WOODY buy detected!",
    "🔥 Someone just grabbed more WOODY!",
]

SELL_ALERT_TITLES = [
    "🔴 WOODY SELL ALERT",
    "⚠️ WOODY sell detected!",
    "📉 A WOODY sell just happened!",
]

BIG_BUY_TITLES = [
    "🚨 WOODY BIG BUY",
    "🔥 BIG BUY DETECTED",
    "💚 STRONG BUY MOMENTUM",
]

BIG_SELL_TITLES = [
    "💥 WOODY BIG SELL",
    "⚠️ BIG SELL DETECTED",
    "🔻 HEAVY SELL PRESSURE",
]

WHALE_BUY_TITLES = [
    "🐋 WOODY WHALE BUY",
    "🌊 WHALE ALERT",
    "🚀 MAJOR ACCUMULATION DETECTED",
]

WHALE_SELL_TITLES = [
    "🐋 WOODY WHALE SELL",
    "🌊 WHALE SELL ALERT",
    "⚠️ LARGE SELL PRESSURE DETECTED",
]

SUPER_WHALE_TITLES = [
    "👑 WOODY SUPER WHALE",
    "🚀 LEGENDARY BUY DETECTED",
    "💎 MONSTER ACCUMULATION ALERT",
]

# =========================
# GLOBALS
# =========================
last_known_holders = None
pending_holder_value = None

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
    if len(addr) < 12:
        return addr
    return f"{addr[:8]}...{addr[-6:]}"


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
        seen = seen[-1500:]
        save_json_file(SEEN_TX_FILE, seen)


def has_seen_tx(tx_hash: str) -> bool:
    seen = load_json_file(SEEN_TX_FILE, [])
    return tx_hash in seen


def log_large_swap(entry: dict) -> None:
    rows = load_json_file(SWAP_LOG_FILE, [])
    rows.append(entry)
    rows = rows[-500:]
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
    greetings = {
        "hello", "hi", "hey", "gm", "good morning", "salut", "buna", "bună"
    }
    return value in greetings


def choose_title(event_type: str, egld_amount: float) -> str:
    if event_type == "BUY":
        if egld_amount >= SUPER_WHALE_ALERT_EGLD:
            return random.choice(SUPER_WHALE_TITLES)
        if egld_amount >= WHALE_ALERT_EGLD:
            return random.choice(WHALE_BUY_TITLES)
        if egld_amount >= BIG_ALERT_EGLD:
            return random.choice(BIG_BUY_TITLES)
        return random.choice(BUY_ALERT_TITLES)

    if egld_amount >= WHALE_ALERT_EGLD:
        return random.choice(WHALE_SELL_TITLES)
    if egld_amount >= BIG_ALERT_EGLD:
        return random.choice(BIG_SELL_TITLES)
    return random.choice(SELL_ALERT_TITLES)


def choose_image(event_type: str, egld_amount: float) -> str:
    if event_type == "BUY":
        if egld_amount >= SUPER_WHALE_ALERT_EGLD:
            return SUPER_WHALE_IMAGE
        if egld_amount >= WHALE_ALERT_EGLD:
            return WHALE_BUY_IMAGE
        if egld_amount >= BIG_ALERT_EGLD:
            return BIG_BUY_IMAGE
        return BUY_IMAGE

    if egld_amount >= BIG_ALERT_EGLD:
        return BIG_SELL_IMAGE
    return SELL_IMAGE


def format_liquidity_text() -> str:
    pools = [
        f"• xExchange pool: `{XEXCHANGE_POOL_ADDRESS}`",
        f"• OneDex pool: `{ONEDEX_POOL_ADDRESS}`" if ONEDEX_POOL_ADDRESS else "• OneDex pool: not configured",
    ]
    if WOODY_USDC_POOL_ADDRESS:
        pools.append(f"• WOODY/USDC pool: `{WOODY_USDC_POOL_ADDRESS}`")
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
        "",
        "Note: auto-liquidity alerts are disabled to avoid false signals.",
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
        [
            InlineKeyboardButton("𝕏 Twitter", url=TWITTER_URL),
        ],
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
        "• Swap activity\n"
        "• Big buys and whale alerts\n\n"
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

            logger.info("[OK] Sent alert to %s", target)
        except Exception as exc:
            logger.warning("[ALERT ERROR] %s -> %s", target, exc)


def normalize_amount(raw: Any, decimals: int) -> float:
    try:
        return int(str(raw)) / (10 ** decimals)
    except Exception:
        return safe_float(raw)


def get_tx_hash(tx_data: dict) -> str:
    return (
        tx_data.get("txHash")
        or tx_data.get("txHashString")
        or tx_data.get("hash")
        or tx_data.get("originalTxHash")
        or ""
    )


def fetch_pool_transactions(pool_address: str, size: int = 20) -> List[dict]:
    if not pool_address:
        return []

    url = f"{MVX_API}/accounts/{pool_address}/transactions"
    params = {
        "status": "success",
        "withOperations": "true",
        "size": size,
    }
    data = get_json(url, params=params)
    return data if isinstance(data, list) else []


def parse_operations_for_pool(
    tx_data: dict,
    pool_address: str,
    pair_token_id: str,
) -> Tuple[Optional[str], str, float, float]:
    """
    Return:
    (tx_type, wallet, woody_amount, pair_amount)

    tx_type in: BUY / SELL / SWAP / None
    """
    operations = tx_data.get("operations", [])
    if not isinstance(operations, list) or not operations:
        return None, "unknown", 0.0, 0.0

    user_wallet = tx_data.get("sender", "") or "unknown"

    woody_out = 0.0
    woody_in = 0.0
    pair_out = 0.0
    pair_in = 0.0

    found_woody = False
    found_pair = False

    for op in operations:
        token_id = op.get("identifier") or op.get("tokenIdentifier") or ""
        raw_value = op.get("value", "0")
        decimals = int(op.get("decimals", 18))
        amount = normalize_amount(raw_value, decimals)

        op_sender = op.get("sender", "") or ""
        op_receiver = op.get("receiver", "") or ""

        # caută un wallet real, diferit de pool și de adrese tehnice
        for addr in [op_sender, op_receiver]:
            if (
                addr
                and addr != pool_address
                and not addr.startswith("erd1qqqqqqqqqqqqqpgq")
            ):
                user_wallet = addr

        if token_id == WOODY_TOKEN_ID:
            found_woody = True
            if op_sender == pool_address:
                woody_out += amount
            if op_receiver == pool_address:
                woody_in += amount

        if pair_token_id and token_id == pair_token_id:
            found_pair = True
            if op_sender == pool_address:
                pair_out += amount
            if op_receiver == pool_address:
                pair_in += amount

    woody_amount = max(woody_out, woody_in)
    pair_amount = max(pair_in, pair_out)

    # filtru strict: fără WOODY > 0, fără alertă
    if not found_woody or woody_amount <= 0:
        return None, user_wallet, 0.0, 0.0

    # filtru strict: fără pair token > 0, fără alertă
    if pair_token_id and (not found_pair or pair_amount <= 0):
        return None, user_wallet, woody_amount, 0.0

    if woody_out > 0 and pair_in > 0:
        return "BUY", user_wallet, woody_out, pair_in

    if woody_in > 0 and pair_out > 0:
        return "SELL", user_wallet, woody_in, pair_out

    if woody_amount > 0 and pair_amount > 0:
        return "SWAP", user_wallet, woody_amount, pair_amount

    return None, user_wallet, woody_amount, pair_amount


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
        f"Swap filters:\n"
        f"• Min WOODY: *{SWAP_MIN_WOODY:,.0f}*\n"
        f"• Min EGLD: *{SWAP_MIN_EGLD}*\n\n"
        f"Big alerts: *≥ {BIG_ALERT_EGLD} EGLD*\n"
        f"Whale alerts: *≥ {WHALE_ALERT_EGLD} EGLD*\n"
        f"Super whale: *≥ {SUPER_WHALE_ALERT_EGLD} EGLD*"
    )
    await update.message.reply_text(text, parse_mode=ParseMode.MARKDOWN)


async def id_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_text(f"Chat ID: {update.effective_chat.id}")


async def menu_callbacks(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()

    if query.data == "price":
        text = "💰 *WOODY Price*\n\nOpen the official chart / price source below."
        keyboard = InlineKeyboardMarkup(
            [[InlineKeyboardButton("📈 Open Price", url=PRICE_URL)]]
        )
        await query.message.reply_text(text, parse_mode=ParseMode.MARKDOWN, reply_markup=keyboard)

    elif query.data == "liquidity":
        await query.message.reply_text(
            format_liquidity_text(),
            parse_mode=ParseMode.MARKDOWN,
        )

    elif query.data == "holders":
        holders = get_holders_count()
        await query.message.reply_text(
            format_holders_text(holders),
            parse_mode=ParseMode.MARKDOWN,
        )

    elif query.data == "chart":
        text = "📈 *WOODY Chart*\n\nOpen the chart below."
        keyboard = InlineKeyboardMarkup(
            [[InlineKeyboardButton("📊 Open Chart", url=CHART_URL)]]
        )
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
    await update.message.reply_text(random.choice(GREETING_REPLIES))


async def welcome_new_members(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not update.message or not update.message.new_chat_members:
        return

    for member in update.message.new_chat_members:
        if member.is_bot:
            continue
        await update.message.reply_text(random.choice(WELCOME_NEW_MEMBER_MESSAGES))


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


async def process_pool_swaps(
    context: ContextTypes.DEFAULT_TYPE,
    pool_address: str,
    dex_name: str,
    pair_name: str,
    pair_token_id: str,
    is_egld_pair: bool = False,
) -> None:
    txs = fetch_pool_transactions(pool_address, size=20)
    if not txs:
        return

    for tx in reversed(txs):
        tx_hash = get_tx_hash(tx)
        if not tx_hash:
            continue

        if has_seen_tx(tx_hash):
            continue

        tx_type, wallet, woody_amount, pair_amount = parse_operations_for_pool(
            tx,
            pool_address,
            pair_token_id,
        )

        # dacă nu există WOODY real în tranzacție, ignoră complet
        if tx_type is None or woody_amount <= 0 or pair_amount <= 0:
            add_seen_tx(tx_hash)
            continue

        # pentru pair EGLD/WEGLD filtrăm și după pragul de EGLD
        if is_egld_pair:
            if woody_amount < SWAP_MIN_WOODY and pair_amount < SWAP_MIN_EGLD:
                add_seen_tx(tx_hash)
                continue
            egld_amount = pair_amount
        else:
            # pentru non-EGLD, filtrăm doar după WOODY
            if woody_amount < SWAP_MIN_WOODY:
                add_seen_tx(tx_hash)
                continue
            egld_amount = 0.0

        title = choose_title("BUY" if tx_type == "BUY" else "SELL", egld_amount)
        image = choose_image("BUY" if tx_type == "BUY" else "SELL", egld_amount)

        if is_egld_pair:
            value_line = f"💰 EGLD: {pair_amount:.6f}"
        else:
            value_line = f"💰 {pair_name.split('/')[-1].strip()}: {pair_amount:,.6f}"

        caption = (
            f"{title}\n\n"
            f"🔁 Type: {tx_type}\n"
            f"👤 Wallet: {short_wallet(wallet)}\n"
            f"🪙 WOODY: {woody_amount:,.2f}\n"
            f"{value_line}\n"
            f"💱 Pair: {pair_name}\n"
            f"🏦 DEX: {dex_name}\n"
            f"🔗 https://explorer.multiversx.com/transactions/{tx_hash}"
        )

        await send_alert_to_targets(context, image, caption)

        log_large_swap(
            {
                "txHash": tx_hash,
                "type": tx_type,
                "wallet": wallet,
                "woody": woody_amount,
                "pairAmount": pair_amount,
                "pair": pair_name,
                "pairToken": pair_token_id,
                "dex": dex_name,
                "timestamp": tx.get("timestamp"),
                "explorer": f"https://explorer.multiversx.com/transactions/{tx_hash}",
            }
        )

        add_seen_tx(tx_hash)


async def check_swaps(context: ContextTypes.DEFAULT_TYPE) -> None:
    logger.info("Checking swaps...")

    if XEXCHANGE_POOL_ADDRESS:
        await process_pool_swaps(
            context=context,
            pool_address=XEXCHANGE_POOL_ADDRESS,
            dex_name="xExchange",
            pair_name="WOODY / EGLD",
            pair_token_id=WEGLD_TOKEN_ID,
            is_egld_pair=True,
        )

    if ONEDEX_POOL_ADDRESS:
        await process_pool_swaps(
            context=context,
            pool_address=ONEDEX_POOL_ADDRESS,
            dex_name="OneDex",
            pair_name="WOODY / EGLD",
            pair_token_id=WEGLD_TOKEN_ID,
            is_egld_pair=True,
        )

    if WOODY_USDC_POOL_ADDRESS:
        await process_pool_swaps(
            context=context,
            pool_address=WOODY_USDC_POOL_ADDRESS,
            dex_name="xExchange / Aggregator",
            pair_name="WOODY / USDC",
            pair_token_id=USDC_TOKEN_ID,
            is_egld_pair=False,
        )

    if WOODY_MEX_POOL_ADDRESS and MEX_TOKEN_ID:
        await process_pool_swaps(
            context=context,
            pool_address=WOODY_MEX_POOL_ADDRESS,
            dex_name="xExchange",
            pair_name="WOODY / MEX",
            pair_token_id=MEX_TOKEN_ID,
            is_egld_pair=False,
        )

    if WOODY_BOBER_POOL_ADDRESS and BOBER_TOKEN_ID:
        await process_pool_swaps(
            context=context,
            pool_address=WOODY_BOBER_POOL_ADDRESS,
            dex_name="JEX / Other",
            pair_name="WOODY / BOBER",
            pair_token_id=BOBER_TOKEN_ID,
            is_egld_pair=False,
        )

    if WOODY_JEX_POOL_ADDRESS and JEX_TOKEN_ID:
        await process_pool_swaps(
            context=context,
            pool_address=WOODY_JEX_POOL_ADDRESS,
            dex_name="JEX / Other",
            pair_name="WOODY / JEX",
            pair_token_id=JEX_TOKEN_ID,
            is_egld_pair=False,
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
    app.job_queue.run_repeating(
        check_new_holders,
        interval=HOLDERS_CHECK_INTERVAL_SECONDS,
        first=20,
    )

    logger.info("WOODY Monitor Bot started...")
    app.run_polling(drop_pending_updates=True)


if __name__ == "__main__":
    main()
