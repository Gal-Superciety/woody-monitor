import logging
import os
import random
import time
from typing import Optional, Dict, Any

import requests
from dotenv import load_dotenv
from telegram import (
    Update,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    InputFile,
)
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
# BASIC CONFIG
# =========================
TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "").strip()
PRIVATE_CHAT_ID = os.getenv("TELEGRAM_PRIVATE_CHAT_ID", "").strip()
GROUP_CHAT_ID = os.getenv("TELEGRAM_GROUP_CHAT_ID", "").strip()

WOODY_TOKEN_ID = os.getenv("WOODY_TOKEN_ID", "WOODY-5f9d9c").strip()
WEGLD_TOKEN_ID = os.getenv("WEGLD_TOKEN_ID", "WEGLD-bd4d79").strip()

PRICE_URL = os.getenv("PRICE_URL", "https://e-compass.io/token/WOODY-5f9d9c").strip()
CHART_URL = os.getenv("CHART_URL", PRICE_URL).strip()
TWITTER_URL = os.getenv("TWITTER_URL", "https://x.com/WOODY_EX").strip()
BUY_XEXCHANGE_URL = os.getenv("BUY_XEXCHANGE_URL", "https://xexchange.com").strip()
BUY_XOXNO_URL = os.getenv("BUY_XOXNO_URL", "https://xoxno.com").strip()

XEXCHANGE_POOL_ADDRESS = os.getenv(
    "XEXCHANGE_POOL_ADDRESS",
    "erd1qqqqqqqqqqqqqpgqvmgnk26tfvz6sj5yasw7p6yfvqpv628d2jpsnvmeaz",
).strip()

ONEDEX_POOL_ADDRESS = os.getenv("ONEDEX_POOL_ADDRESS", "").strip()

ONEDEX_BURN_ADDRESS = os.getenv(
    "ONEDEX_BURN_ADDRESS",
    "erd1deaddeaddeaddeaddeaddeaddeaddeaddeaddeaddeaddeaddeaqtv0gag",
).strip()

MVX_API = os.getenv("MVX_API", "https://api.multiversx.com").strip()

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
MIN_EGLD_ALERT = float(os.getenv("MIN_EGLD_ALERT", "0.2"))
BIG_ALERT_EGLD = float(os.getenv("BIG_ALERT_EGLD", "1"))
WHALE_ALERT_EGLD = float(os.getenv("WHALE_ALERT_EGLD", "3"))
SUPER_WHALE_ALERT_EGLD = float(os.getenv("SUPER_WHALE_ALERT_EGLD", "10"))

CHECK_INTERVAL_SECONDS = int(os.getenv("CHECK_INTERVAL_SECONDS", "30"))
GREETING_COOLDOWN_SECONDS = int(os.getenv("GREETING_COOLDOWN_SECONDS", "120"))
HOLDERS_CHECK_INTERVAL_SECONDS = int(os.getenv("HOLDERS_CHECK_INTERVAL_SECONDS", "180"))

# =========================
# LOGGING
# =========================
logging.basicConfig(
    format="%(asctime)s | %(levelname)s | %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger("WOODY_MONITOR")


# =========================
# RANDOM MESSAGES
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


def chat_targets() -> list[str]:
    targets = []
    if PRIVATE_CHAT_ID:
        targets.append(PRIVATE_CHAT_ID)
    if GROUP_CHAT_ID:
        targets.append(GROUP_CHAT_ID)
    return targets


def get_json(url: str) -> Optional[Any]:
    try:
        response = requests.get(url, timeout=20)
        response.raise_for_status()
        return response.json()
    except Exception as exc:
        logger.warning("GET JSON failed for %s -> %s", url, exc)
        return None


def get_pool_tokens(pool_address: str) -> Optional[list]:
    if not pool_address:
        return None
    url = f"{MVX_API}/accounts/{pool_address}/tokens"
    data = get_json(url)
    if isinstance(data, list):
        return data
    return None


def extract_balance(tokens: list, identifier: str) -> float:
    for token in tokens:
        if token.get("identifier") == identifier:
            balance = token.get("balance", "0")
            decimals = int(token.get("decimals", 18))
            try:
                return int(balance) / (10 ** decimals)
            except Exception:
                return 0.0
    return 0.0


def get_pool_state(pool_address: str) -> Optional[Dict[str, float]]:
    tokens = get_pool_tokens(pool_address)
    if not tokens:
        return None

    woody = extract_balance(tokens, WOODY_TOKEN_ID)
    wegld = extract_balance(tokens, WEGLD_TOKEN_ID)

    return {
        "woody": woody,
        "wegld": wegld,
    }


def detect_swap(previous: Dict[str, float], current: Dict[str, float]) -> Optional[Dict[str, float]]:
    if not previous or not current:
        return None

    prev_woody = safe_float(previous.get("woody"))
    prev_wegld = safe_float(previous.get("wegld"))
    curr_woody = safe_float(current.get("woody"))
    curr_wegld = safe_float(current.get("wegld"))

    if prev_woody == 0 or prev_wegld == 0 or curr_woody == 0 or curr_wegld == 0:
        return None

    woody_delta = curr_woody - prev_woody
    egld_delta = curr_wegld - prev_wegld

    # BUY = WOODY leaves pool, EGLD enters pool
    if woody_delta < 0 and egld_delta > 0:
        return {
            "type": "BUY",
            "woody": abs(woody_delta),
            "egld": abs(egld_delta),
        }

    # SELL = WOODY enters pool, EGLD leaves pool
    if woody_delta > 0 and egld_delta < 0:
        return {
            "type": "SELL",
            "woody": abs(woody_delta),
            "egld": abs(egld_delta),
        }

    return None


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
    lines = [
        "💧 *WOODY Liquidity*",
        "",
        "Main monitored pool:",
        f"• xExchange pool: `{XEXCHANGE_POOL_ADDRESS}`",
    ]

    if ONEDEX_POOL_ADDRESS:
        lines.append(f"• OneDex pool: `{ONEDEX_POOL_ADDRESS}`")
    else:
        lines.append("• OneDex pool: not configured")

    lines.extend([
        "",
        "🔒 OneDex LP burn wallet:",
        f"`{ONEDEX_BURN_ADDRESS}`",
        "",
        "Note: automatic liquidity alerts are currently disabled to avoid false signals.",
    ])

    return "\n".join(lines)


def format_holders_text(count: Optional[int]) -> str:
    if count is None:
        return "👥 *WOODY Holders*\n\nCould not fetch holders right now."

    return (
        "👥 *WOODY Holders*\n\n"
        f"Current holders: *{count}*"
    )


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
        "• Buy & sell activity\n"
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
            parse