import json
import logging
import os
import random
import time
from datetime import datetime, time as dt_time
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

ALERT_COOLDOWN_SECONDS = int(os.getenv("ALERT_COOLDOWN_SECONDS", "60"))
STATE_FILE = os.getenv("STATE_FILE", "state.json").strip()

DAILY_RECAP_HOUR = int(os.getenv("DAILY_RECAP_HOUR", "23"))
DAILY_RECAP_MINUTE = int(os.getenv("DAILY_RECAP_MINUTE", "0"))

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
# GLOBAL HOLDER MEMORY
# =========================
last_known_holders = None
pending_holder_value = None


# =========================
# STATE
# =========================
def default_state() -> dict:
    return {
        "xexchange_prev": None,
        "onedex_prev": None,
        "last_greet_ts": 0,
        "last_swap_scan_ts": 0,
        "last_holders_scan_ts": 0,
        "last_alert_ts": 0,
        "last_alert_signature": "",
        "last_alert": None,
        "last_buy": None,
        "last_sell": None,
        "last_known_holders": None,
        "pending_holder_value": None,
        "daily_stats": {
            "buy_count": 0,
            "sell_count": 0,
            "biggest_buy_egld": 0.0,
            "biggest_sell_egld": 0.0,
            "biggest_buy_caption": "",
            "biggest_sell_caption": "",
            "holders_start": None,
            "holders_current": None,
            "last_reset_date": datetime.utcnow().strftime("%Y-%m-%d"),
        },
    }


def load_state() -> dict:
    if not STATE_FILE or not os.path.exists(STATE_FILE):
        return default_state()

    try:
        with open(STATE_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)

        state = default_state()
        state.update(data)

        if "daily_stats" not in state or not isinstance(state["daily_stats"], dict):
            state["daily_stats"] = default_state()["daily_stats"]

        return state
    except Exception as exc:
        logger.warning("Could not load state file: %s", exc)
        return default_state()


def save_state(state: dict) -> None:
    try:
        with open(STATE_FILE, "w", encoding="utf-8") as f:
            json.dump(state, f, indent=2, ensure_ascii=False)
    except Exception as exc:
        logger.warning("Could not save state file: %s", exc)


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


def now_text() -> str:
    return datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S UTC")


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


def alert_level_label(egld_amount: float) -> str:
    if egld_amount >= SUPER_WHALE_ALERT_EGLD:
        return "SUPER WHALE"
    if egld_amount >= WHALE_ALERT_EGLD:
        return "WHALE"
    if egld_amount >= BIG_ALERT_EGLD:
        return "BIG"
    return "NORMAL"


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


def format_thresholds_text() -> str:
    return (
        "🎯 *WOODY Alert Thresholds*\n\n"
        f"• Normal alert: *≥ {MIN_EGLD_ALERT} EGLD*\n"
        f"• Big alert: *≥ {BIG_ALERT_EGLD} EGLD*\n"
        f"• Whale alert: *≥ {WHALE_ALERT_EGLD} EGLD*\n"
        f"• Super whale alert: *≥ {SUPER_WHALE_ALERT_EGLD} EGLD*\n"
        f"• Alert cooldown: *{ALERT_COOLDOWN_SECONDS}s*"
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
            InlineKeyboardButton("📊 Stats", callback_data="stats"),
            InlineKeyboardButton("🎯 Thresholds", callback_data="thresholds"),
        ],
        [
            InlineKeyboardButton("🔄 Refresh", callback_data="refresh"),
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
        "• Big buys and whale alerts\n"
        "• Daily recap\n\n"
        "Choose an option below 👇"
    )


def format_last_alert_text(item: Optional[dict], label: str) -> str:
    if not item:
        return f"{label}: none"
    return (
        f"{label}: {item.get('type', 'N/A')} | "
        f"{item.get('egld', 0):.6f} EGLD | "
        f"{item.get('pool', 'N/A')} | "
        f"{item.get('time', 'N/A')}"
    )


def update_readable_timestamps(state: dict) -> None:
    state["last_swap_scan_ts_readable"] = (
        datetime.utcfromtimestamp(state["last_swap_scan_ts"]).strftime("%Y-%m-%d %H:%M:%S UTC")
        if state.get("last_swap_scan_ts")
        else "N/A"
    )
    state["last_holders_scan_ts_readable"] = (
        datetime.utcfromtimestamp(state["last_holders_scan_ts"]).strftime("%Y-%m-%d %H:%M:%S UTC")
        if state.get("last_holders_scan_ts")
        else "N/A"
    )


def format_stats_text(state: dict) -> str:
    holders = get_holders_count()
    x_prev = "YES" if state.get("xexchange_prev") else "NO"
    o_prev = "YES" if state.get("onedex_prev") else "NO"

    return (
        "📊 *WOODY Monitor Stats*\n\n"
        f"• Bot running: *YES*\n"
        f"• Holders: *{holders if holders is not None else 'N/A'}*\n"
        f"• xExchange configured: *{'YES' if XEXCHANGE_POOL_ADDRESS else 'NO'}*\n"
        f"• xExchange cached state: *{x_prev}*\n"
        f"• OneDex configured: *{'YES' if ONEDEX_POOL_ADDRESS else 'NO'}*\n"
        f"• OneDex cached state: *{o_prev}*\n"
        f"• Last swap scan: *{state.get('last_swap_scan_ts_readable', 'N/A')}*\n"
        f"• Last holders scan: *{state.get('last_holders_scan_ts_readable', 'N/A')}*\n"
        f"• Greeting cooldown: *{GREETING_COOLDOWN_SECONDS}s*\n"
        f"• Alert cooldown: *{ALERT_COOLDOWN_SECONDS}s*\n\n"
        f"{format_last_alert_text(state.get('last_alert'), 'Last alert')}\n"
        f"{format_last_alert_text(state.get('last_buy'), 'Last buy')}\n"
        f"{format_last_alert_text(state.get('last_sell'), 'Last sell')}"
    )


def build_alert_caption(event: dict, pool_name: str) -> str:
    title = choose_title(event["type"], safe_float(event["egld"]))
    level = alert_level_label(safe_float(event["egld"]))
    return (
        f"{title}\n\n"
        f"📊 Type: {event['type']}\n"
        f"🏷 Level: {level}\n"
        f"💱 Pool: {pool_name}\n"
        f"🪙 Amount: {event['woody']:,.2f} WOODY\n"
        f"💰 Value: {event['egld']:.6f} EGLD\n"
        f"📈 Chart: {CHART_URL}"
    )


def should_send_alert(state: dict, event: dict, pool_name: str) -> bool:
    now_ts = int(time.time())
    signature = f"{pool_name}:{event['type']}:{round(safe_float(event['egld']), 6)}:{round(safe_float(event['woody']), 2)}"

    last_ts = int(state.get("last_alert_ts", 0))
    last_signature = state.get("last_alert_signature", "")

    if signature == last_signature and (now_ts - last_ts) < ALERT_COOLDOWN_SECONDS:
        logger.info("Duplicate alert skipped because of cooldown: %s", signature)
        return False

    state["last_alert_ts"] = now_ts
    state["last_alert_signature"] = signature
    return True


def update_daily_stats(state: dict, event: dict, caption: str) -> None:
    stats = state["daily_stats"]
    today = datetime.utcnow().strftime("%Y-%m-%d")

    if stats.get("last_reset_date") != today:
        stats["buy_count"] = 0
        stats["sell_count"] = 0
        stats["biggest_buy_egld"] = 0.0
        stats["biggest_sell_egld"] = 0.0
        stats["biggest_buy_caption"] = ""
        stats["biggest_sell_caption"] = ""
        stats["holders_start"] = stats.get("holders_current")
        stats["last_reset_date"] = today

    if event["type"] == "BUY":
        stats["buy_count"] += 1
        if safe_float(event["egld"]) > safe_float(stats.get("biggest_buy_egld", 0)):
            stats["biggest_buy_egld"] = safe_float(event["egld"])
            stats["biggest_buy_caption"] = caption

    elif event["type"] == "SELL":
        stats["sell_count"] += 1
        if safe_float(event["egld"]) > safe_float(stats.get("biggest_sell_egld", 0)):
            stats["biggest_sell_egld"] = safe_float(event["egld"])
            stats["biggest_sell_caption"] = caption


def recap_text(state: dict) -> str:
    stats = state["daily_stats"]
    holders_start = stats.get("holders_start")
    holders_current = stats.get("holders_current")

    holder_change = "N/A"
    if isinstance(holders_start, int) and isinstance(holders_current, int):
        holder_change = f"{holders_current - holders_start:+d}"

    return (
        "📘 *WOODY Daily Recap*\n\n"
        f"• Date: *{datetime.utcnow().strftime('%Y-%m-%d')}*\n"
        f"• Buy alerts: *{stats.get('buy_count', 0)}*\n"
        f"• Sell alerts: *{stats.get('sell_count', 0)}*\n"
        f"• Biggest buy: *{safe_float(stats.get('biggest_buy_egld', 0)):.6f} EGLD*\n"
        f"• Biggest sell: *{safe_float(stats.get('biggest_sell_egld', 0)):.6f} EGLD*\n"
        f"• Holders change: *{holder_change}*\n"
        f"• xExchange monitored: *{'YES' if XEXCHANGE_POOL_ADDRESS else 'NO'}*\n"
        f"• OneDex monitored: *{'YES' if ONEDEX_POOL_ADDRESS else 'NO'}*"
    )


# =========================
# TELEGRAM SENDERS
# =========================
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


# =========================
# TELEGRAM HANDLERS
# =========================
async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await send_start_menu(update.effective_chat.id, context)


async def menu_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await send_start_menu(update.effective_chat.id, context)


async def status_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    text = (
        "✅ *WOODY Monitor is running*\n\n"
        f"Private alerts: *{'YES' if PRIVATE_CHAT_ID else 'NO'}*\n"
        f"Group alerts: *{'YES' if GROUP_CHAT_ID else 'NO'}*\n\n"
        f"Normal alerts: *≥ {MIN_EGLD_ALERT} EGLD*\n"
        f"Big alerts: *≥ {BIG_ALERT_EGLD} EGLD*\n"
        f"Whale alerts: *≥ {WHALE_ALERT_EGLD} EGLD*\n"
        f"Super whale: *≥ {SUPER_WHALE_ALERT_EGLD} EGLD*"
    )
    await update.message.reply_text(text, parse_mode=ParseMode.MARKDOWN)


async def stats_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    state = context.application.bot_data["state"]
    update_readable_timestamps(state)
    save_state(state)
    await update.message.reply_text(
        format_stats_text(state),
        parse_mode=ParseMode.MARKDOWN,
        disable_web_page_preview=True,
    )


async def thresholds_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_text(
        format_thresholds_text(),
        parse_mode=ParseMode.MARKDOWN,
    )


async def lastbuy_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    state = context.application.bot_data["state"]
    item = state.get("last_buy")
    if not item:
        await update.message.reply_text("No buy alert recorded yet.")
        return
    await update.message.reply_text(
        format_last_alert_text(item, "Last buy"),
        disable_web_page_preview=True,
    )


async def lastsell_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    state = context.application.bot_data["state"]
    item = state.get("last_sell")
    if not item:
        await update.message.reply_text("No sell alert recorded yet.")
        return
    await update.message.reply_text(
        format_last_alert_text(item, "Last sell"),
        disable_web_page_preview=True,
    )


async def recap_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    state = context.application.bot_data["state"]
    await update.message.reply_text(
        recap_text(state),
        parse_mode=ParseMode.MARKDOWN,
    )


async def id_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_text(f"Chat ID: {update.effective_chat.id}")


async def menu_callbacks(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()
    state = context.application.bot_data["state"]

    if query.data == "price":
        text = (
            "💰 *WOODY Price*\n\n"
            "Open the official chart / price source below."
        )
        keyboard = InlineKeyboardMarkup(
            [[InlineKeyboardButton("📈 Open Price", url=PRICE_URL)]]
        )
        await query.message.reply_text(
            text,
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=keyboard,
        )

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
        await query.message.reply_text(
            text,
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=keyboard,
        )

    elif query.data == "stats":
        update_readable_timestamps(state)
        save_state(state)
        await query.message.reply_text(
            format_stats_text(state),
            parse_mode=ParseMode.MARKDOWN,
            disable_web_page_preview=True,
        )

    elif query.data == "thresholds":
        await query.message.reply_text(
            format_thresholds_text(),
            parse_mode=ParseMode.MARKDOWN,
        )

    elif query.data == "refresh":
        await send_start_menu(query.message.chat.id, context)


async def greeting_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not update.message or not update.message.text:
        return

    text = update.message.text.strip()
    if text.startswith("/"):
        return

    if not greeting_detected(text):
        return

    state = context.application.bot_data["state"]
    now_ts = int(time.time())
    last_ts = int(state.get("last_greet_ts", 0))

    if now_ts - last_ts < GREETING_COOLDOWN_SECONDS:
        return

    state["last_greet_ts"] = now_ts
    save_state(state)
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
async def process_pool(
    context: ContextTypes.DEFAULT_TYPE,
    state: dict,
    state_key: str,
    pool_address: str,
    pool_name: str,
) -> None:
    if not pool_address:
        return

    logger.info("Checking %s...", pool_name)
    previous = state.get(state_key)
    current = get_pool_state(pool_address)

    logger.info("%s previous: %s", pool_name, previous)
    logger.info("%s current: %s", pool_name, current)

    if previous and current:
        event = detect_swap(previous, current)
        logger.info("%s detected event: %s", pool_name, event)

        if event and safe_float(event["egld"]) >= MIN_EGLD_ALERT:
            if should_send_alert(state, event, pool_name):
                image = choose_image(event["type"], safe_float(event["egld"]))
                caption = build_alert_caption(event, pool_name)

                alert_data = {
                    "type": event["type"],
                    "woody": safe_float(event["woody"]),
                    "egld": safe_float(event["egld"]),
                    "pool": pool_name,
                    "time": now_text(),
                    "caption": caption,
                }

                state["last_alert"] = alert_data
                if event["type"] == "BUY":
                    state["last_buy"] = alert_data
                elif event["type"] == "SELL":
                    state["last_sell"] = alert_data

                update_daily_stats(state, event, caption)
                await send_alert_to_targets(context, image, caption)

    if current:
        state[state_key] = current


async def check_swaps(context: ContextTypes.DEFAULT_TYPE) -> None:
    state = context.application.bot_data["state"]
    state["last_swap_scan_ts"] = int(time.time())

    await process_pool(
        context=context,
        state=state,
        state_key="xexchange_prev",
        pool_address=XEXCHANGE_POOL_ADDRESS,
        pool_name="WOODY/EGLD xExchange",
    )

    await process_pool(
        context=context,
        state=state,
        state_key="onedex_prev",
        pool_address=ONEDEX_POOL_ADDRESS,
        pool_name="WOODY/EGLD OneDex",
    )

    save_state(state)


async def check_new_holders(context: ContextTypes.DEFAULT_TYPE) -> None:
    global last_known_holders
    global pending_holder_value

    state = context.application.bot_data["state"]
    state["last_holders_scan_ts"] = int(time.time())

    holders = get_holders_count()
    if holders is None:
        save_state(state)
        return

    state["daily_stats"]["holders_current"] = holders

    if state["daily_stats"].get("holders_start") is None:
        state["daily_stats"]["holders_start"] = holders

    if last_known_holders is None:
        last_known_holders = state.get("last_known_holders")
    if pending_holder_value is None:
        pending_holder_value = state.get("pending_holder_value")

    if last_known_holders is None:
        last_known_holders = holders
        state["last_known_holders"] = holders
        save_state(state)
        return

    if holders > last_known_holders:
        if pending_holder_value is None:
            pending_holder_value = holders
            state["pending_holder_value"] = holders
            save_state(state)
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
            state["last_known_holders"] = holders
            state["pending_holder_value"] = None
            save_state(state)
            return

    else:
        pending_holder_value = None
        state["pending_holder_value"] = None

    state["last_known_holders"] = last_known_holders
    save_state(state)


async def daily_recap_job(context: ContextTypes.DEFAULT_TYPE) -> None:
    state = context.application.bot_data["state"]
    text = recap_text(state)

    for target in chat_targets():
        try:
            await context.bot.send_message(
                chat_id=target,
                text=text,
                parse_mode=ParseMode.MARKDOWN,
            )
            logger.info("[OK] Daily recap sent to %s", target)
        except Exception as exc:
            logger.warning("[RECAP ERROR] %s -> %s", target, exc)


# =========================
# MAIN
# =========================
def main() -> None:
    global last_known_holders
    global pending_holder_value

    require_token()

    app = Application.builder().token(TOKEN).build()

    state = load_state()
    app.bot_data["state"] = state

    last_known_holders = state.get("last_known_holders")
    pending_holder_value = state.get("pending_holder_value")

    app.add_handler(CommandHandler("start", start_command))
    app.add_handler(CommandHandler("menu", menu_command))
    app.add_handler(CommandHandler("status", status_command))
    app.add_handler(CommandHandler("stats", stats_command))
    app.add_handler(CommandHandler("thresholds", thresholds_command))
    app.add_handler(CommandHandler("lastbuy", lastbuy_command))
    app.add_handler(CommandHandler("lastsell", lastsell_command))
    app.add_handler(CommandHandler("recap", recap_command))
    app.add_handler(CommandHandler("id", id_command))

    app.add_handler(CallbackQueryHandler(menu_callbacks))

    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, greeting_handler))
    app.add_handler(MessageHandler(filters.StatusUpdate.NEW_CHAT_MEMBERS, welcome_new_members))

    if app.job_queue is None:
        raise RuntimeError(
            "JobQueue is missing. Install python-telegram-bot[job-queue]."
        )

    app.job_queue.run_repeating(check_swaps, interval=CHECK_INTERVAL_SECONDS, first=10)
    app.job_queue.run_repeating(
        check_new_holders,
        interval=HOLDERS_CHECK_INTERVAL_SECONDS,
        first=20,
    )

    recap_time = dt_time(hour=DAILY_RECAP_HOUR, minute=DAILY_RECAP_MINUTE)
    app.job_queue.run_daily(daily_recap_job, time=recap_time)

    logger.info("WOODY Monitor Bot started...")
    app.run_polling(drop_pending_updates=True)


if __name__ == "__main__":
    main()
