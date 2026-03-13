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

            logger.info("[OK] Sent photo alert to %s", target)
        except Exception as exc:
            logger.warning("[ALERT ERROR] %s -> %s", target, exc)


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
        f"Normal alerts: *≥ {MIN_EGLD_ALERT} EGLD*\n"
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
        text = (
            "💰 *WOODY Price*\n\n"
            "Open the official chart / price source below."
        )
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
async def check_swaps(context: ContextTypes.DEFAULT_TYPE) -> None:
    logger.info("Checking swaps...")

    # xExchange
    if XEXCHANGE_POOL_ADDRESS:
        logger.info("Checking WOODY/EGLD xExchange...")
        previous = context.application.bot_data.get("xexchange_prev")
        current = get_pool_state(XEXCHANGE_POOL_ADDRESS)

        logger.info("WOODY/EGLD xExchange previous: %s", previous)
        logger.info("WOODY/EGLD xExchange current: %s", current)

        if previous and current:
            event = detect_swap(previous, current)
            logger.info("WOODY/EGLD xExchange detected event: %s", event)

            if event and safe_float(event["egld"]) >= MIN_EGLD_ALERT:
                title = choose_title(event["type"], safe_float(event["egld"]))
                image = choose_image(event["type"], safe_float(event["egld"]))

                caption = (
                    f"{title}\n\n"
                    f"💱 Pool: WOODY/EGLD xExchange\n"
                    f"🪙 Amount: {event['woody']:,.2f} WOODY\n"
                    f"💰 Value: {event['egld']:.6f} EGLD"
                )

                await send_alert_to_targets(context, image, caption)

        if current:
            context.application.bot_data["xexchange_prev"] = current

    # OneDex
    if ONEDEX_POOL_ADDRESS:
        logger.info("Checking WOODY/EGLD OneDex...")
        previous = context.application.bot_data.get("onedex_prev")
        current = get_pool_state(ONEDEX_POOL_ADDRESS)

        logger.info("WOODY/EGLD OneDex previous: %s", previous)
        logger.info("WOODY/EGLD OneDex current: %s", current)

        if previous and current:
            event = detect_swap(previous, current)
            logger.info("WOODY/EGLD OneDex detected event: %s", event)

            if event and safe_float(event["egld"]) >= MIN_EGLD_ALERT:
                title = choose_title(event["type"], safe_float(event["egld"]))
                image = choose_image(event["type"], safe_float(event["egld"]))

                caption = (
                    f"{title}\n\n"
                    f"💱 Pool: WOODY/EGLD OneDex\n"
                    f"🪙 Amount: {event['woody']:,.2f} WOODY\n"
                    f"💰 Value: {event['egld']:.6f} EGLD"
                )

                await send_alert_to_targets(context, image, caption)

        if current:
            context.application.bot_data["onedex_prev"] = current


async def check_new_holders(context: ContextTypes.DEFAULT_TYPE) -> None:
    current = get_holders_count()
    previous = context.application.bot_data.get("holders_prev")

    logger.info("Checking holders... prev=%s current=%s", previous, current)

    if current is None:
        return

    if previous is None:
        context.application.bot_data["holders_prev"] = current
        return

    if current > previous:
        diff = current - previous
        caption = (
            "👤 WOODY NEW HOLDER\n\n"
            f"Added holders: +{diff}\n"
            f"Total holders: {current}"
        )
        await send_alert_to_targets(context, NEW_HOLDER_IMAGE, caption)

    context.application.bot_data["holders_prev"] = current


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
        raise RuntimeError(
            "JobQueue is missing. Install python-telegram-bot[job-queue]."
        )

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