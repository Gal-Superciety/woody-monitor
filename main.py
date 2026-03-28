import os
import re
import time
import logging
from typing import Dict, Optional, Tuple, List, Any

import requests
from dotenv import load_dotenv

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, InputFile
from telegram.ext import (
    Application,
    CallbackQueryHandler,
    ChatMemberHandler,
    CommandHandler,
    ContextTypes,
    MessageHandler,
    filters,
)

load_dotenv()

# =========================================================
# CONFIG
# =========================================================
TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "").strip()
PRIVATE_CHAT_ID = os.getenv("TELEGRAM_PRIVATE_CHAT_ID", "").strip()
GROUP_CHAT_ID = os.getenv("TELEGRAM_GROUP_CHAT_ID", "").strip()

MVX = os.getenv("MVX_API", "https://api.multiversx.com").strip()
XOXNO_QUOTE_API = os.getenv("XOXNO_QUOTE_API", "https://swap.xoxno.com/api/v1/quote").strip()
COINGECKO_EGLD_API = os.getenv(
    "COINGECKO_EGLD_API",
    "https://api.coingecko.com/api/v3/simple/price?ids=elrond-erd-2&vs_currencies=usd",
).strip()

WOODY = os.getenv("WOODY_TOKEN_ID", "WOODY-5f9d9c").strip()
WEGLD = os.getenv("WEGLD_TOKEN_ID", "WEGLD-bd4d79").strip()
BOBER = os.getenv("BOBER_TOKEN_ID", "BOBER-9eb764").strip()
JEX = os.getenv("JEX_TOKEN_ID", "JEX-9040ca").strip()
MEX = os.getenv("MEX_TOKEN_ID", "MEX-455c57").strip()
USDC_HINT = os.getenv("USDC_TOKEN_HINT", "USDC").strip()

XEX = os.getenv(
    "XEXCHANGE_POOL_ADDRESS",
    "erd1qqqqqqqqqqqqqpgqvmgnk26tfvz6sj5yasw7p6yfvqpv628d2jpsnvmeaz",
).strip()

ONEDX = os.getenv(
    "ONEDEX_POOL_ADDRESS",
    "erd1qqqqqqqqqqqqqpgqqz6vp9y50ep867vnr296mqf3dduh6guvmvlsu3sujc",
).strip()

WOODY_BOBER = os.getenv(
    "WOODY_BOBER_POOL_ADDRESS",
    "erd1qqqqqqqqqqqqqpgqvq8vtfn26fdezjm07a7yjqtgn3h02af86avs9vf6kw",
).strip()

WOODY_JEX = os.getenv(
    "WOODY_JEX_POOL_ADDRESS",
    "erd1qqqqqqqqqqqqqpgqdz5vj73j7h2velx83xwrad6zz82q2njr6avsrkua0n",
).strip()

WOODY_MEX = os.getenv(
    "WOODY_MEX_POOL_ADDRESS",
    "erd1qqqqqqqqqqqqqpgqzqtfej5s9hp7cg0ardy6mt3fvz4jrdsa2jpsdg959f",
).strip()

WOODY_USDC = os.getenv(
    "WOODY_USDC_POOL_ADDRESS",
    "erd1qqqqqqqqqqqqqpgqjhy8hut0d9rzwqlz37e5nsmlj2rch6vd2jpss7a69j",
).strip()

ONEDEX_BURN_ADDRESS = os.getenv(
    "ONEDEX_BURN_ADDRESS",
    "erd1deaddeaddeaddeaddeaddeaddeaddeaddeaddeaddeaddeaddeaqtv0gag",
).strip()

PRICE_URL = os.getenv("PRICE_URL", "https://e-compass.io/token/WOODY-5f9d9c").strip()
CHART_URL = os.getenv("CHART_URL", PRICE_URL).strip()
TWITTER_URL = os.getenv("TWITTER_URL", "https://x.com/WOODY_EX").strip()
BUY_XEXCHANGE_URL = os.getenv("BUY_XEXCHANGE_URL", "https://xexchange.com").strip()
BUY_XOXNO_URL = os.getenv("BUY_XOXNO_URL", "https://xoxno.com").strip()

BANNER_IMAGE = os.getenv("BANNER_IMAGE", "banner.png").strip()
BUY_IMAGE = os.getenv("BUY_IMAGE", "buy.png").strip()
SELL_IMAGE = os.getenv("SELL_IMAGE", "sell.png").strip()
BIG_BUY_IMAGE = os.getenv("BIG_BUY_IMAGE", "big_buy.png").strip()
BIG_SELL_IMAGE = os.getenv("BIG_SELL_IMAGE", "big_sell.png").strip()
NEW_HOLDER_IMAGE = os.getenv("NEW_HOLDER_IMAGE", "new_holder.png").strip()

# Praguri
MIN_WOODY_ALERT = float(os.getenv("MIN_WOODY_ALERT", "10000"))
MIN_EGLD_ALERT = float(os.getenv("MIN_EGLD_ALERT", "0.2"))

BIG_BUY_EGLD = float(os.getenv("BIG_BUY_EGLD", "1.0"))
BIG_SELL_EGLD = float(os.getenv("BIG_SELL_EGLD", "1.0"))
WHALE_BUY_EGLD = float(os.getenv("WHALE_BUY_EGLD", "5.0"))
WHALE_SELL_EGLD = float(os.getenv("WHALE_SELL_EGLD", "5.0"))

CHECK_SWAPS_INTERVAL = int(os.getenv("CHECK_SWAPS_INTERVAL", "10"))
CHECK_HOLDERS_INTERVAL = int(os.getenv("CHECK_HOLDERS_INTERVAL", "120"))
GREETING_COOLDOWN_SECONDS = int(os.getenv("GREETING_COOLDOWN_SECONDS", "120"))

# Anti-noise
MIN_PRICE_CHANGE_BPS = float(os.getenv("MIN_PRICE_CHANGE_BPS", "3"))  # 3 basis points
MIN_SECONDS_BETWEEN_SAME_POOL_ALERTS = int(os.getenv("MIN_SECONDS_BETWEEN_SAME_POOL_ALERTS", "6"))

# =========================================================
# LOGGING
# =========================================================
logging.basicConfig(
    format="%(asctime)s | %(levelname)s | %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger("WOODY_MONITOR_STABLE")

# =========================================================
# GLOBAL STATE
# =========================================================
UA = {"User-Agent": "WOODY Stable Bot"}

LAST_SWAP_STATE: Dict[str, Optional[Dict[str, float]]] = {
    "xexchange": None,
    "onedx": None,
}

LAST_ALERT_TS: Dict[str, float] = {
    "xexchange": 0.0,
    "onedx": 0.0,
}

LAST_HOLDERS_COUNT: Optional[int] = None
PENDING_HOLDER_VALUE: Optional[int] = None

PRICE_CACHE: Dict[str, Tuple[float, float]] = {}
GREETING_REPLIES = [
    "Hey! Welcome to WOODY 👋",
    "GM! Welcome to WOODY 🪶",
    "Glad to see you here in WOODY 🚀",
]

WELCOME_MESSAGES = [
    "🪶 Welcome to the WOODY community!",
    "🚀 Welcome! Glad to have you here.",
    "👋 Welcome to WOODY!",
]

GREET = re.compile(r"\b(hi|hello|gm|salut|buna|bună|hey)\b", re.I)
SPAM = re.compile(r"airdrop|claim|seed|100x|double", re.I)

# =========================================================
# HELPERS
# =========================================================
def require_token() -> None:
    if not TOKEN:
        raise ValueError("TELEGRAM_BOT_TOKEN is missing from .env")


def safe_float(value: Any) -> float:
    try:
        return float(value)
    except Exception:
        return 0.0


def safe_int(value: Any) -> int:
    try:
        return int(value)
    except Exception:
        return 0


def d(balance: Any, decimals: Any) -> float:
    try:
        return int(str(balance)) / (10 ** int(decimals))
    except Exception:
        return 0.0


def file_exists(path: str) -> bool:
    if not path:
        return False
    base_dir = os.path.dirname(os.path.abspath(__file__))
    return os.path.exists(os.path.join(base_dir, path))


def image_path(path: str) -> str:
    base_dir = os.path.dirname(os.path.abspath(__file__))
    return os.path.join(base_dir, path)


def get_json(url: str, params: Optional[dict] = None) -> Optional[Any]:
    try:
        r = requests.get(url, params=params, headers=UA, timeout=20)
        r.raise_for_status()
        return r.json()
    except Exception as exc:
        logger.warning("GET JSON failed for %s -> %s", url, exc)
        return None


def symbol(token_id: str) -> str:
    if not token_id:
        return "?"
    return token_id.split("-")[0]


def chat_targets() -> List[str]:
    targets: List[str] = []
    if PRIVATE_CHAT_ID:
        targets.append(PRIVATE_CHAT_ID)
    if GROUP_CHAT_ID:
        targets.append(GROUP_CHAT_ID)
    return targets


# =========================================================
# PRICE / HOLDERS / RESERVES
# =========================================================
def reserves(pair_address: str) -> Dict[str, float]:
    data = get_json(f"{MVX}/accounts/{pair_address}/tokens")
    if not isinstance(data, list):
        return {}
    out: Dict[str, float] = {}
    for t in data:
        identifier = str(t.get("identifier") or "")
        if not identifier:
            continue
        out[identifier] = d(t.get("balance"), t.get("decimals"))
    return out


def egld_usd() -> float:
    now = time.time()
    cached = PRICE_CACHE.get("egld_usd")
    if cached and now - cached[1] < 60:
        return cached[0]

    data = get_json(COINGECKO_EGLD_API)
    price = 0.0
    try:
        price = safe_float(data["elrond-erd-2"]["usd"])
    except Exception:
        price = 0.0

    PRICE_CACHE["egld_usd"] = (price, now)
    return price


def quote_to_wegld(token: str) -> float:
    if token == WEGLD or symbol(token).upper() == "WEGLD":
        return 1.0

    if USDC_HINT.upper() in token.upper():
        usd = 1.0
        egld = egld_usd()
        return usd / egld if egld > 0 else 0.0

    q = get_json(XOXNO_QUOTE_API, {"from": token, "to": WEGLD, "amountIn": str(10**18)})
    out = None
    if isinstance(q, dict):
        out = q.get("amountOut") or q.get("toAmount")

    try:
        return int(str(out)) / (10**18) if out else 0.0
    except Exception:
        return 0.0


def liq_wegld(pair_address: str) -> Optional[float]:
    r = reserves(pair_address)
    wegld = r.get(WEGLD, 0.0)
    return 2 * wegld if wegld > 0 else None


def liq_other(pair_address: str, token: str) -> Optional[float]:
    r = reserves(pair_address)
    amount = r.get(token, 0.0)
    if amount <= 0:
        return None
    quote = quote_to_wegld(token)
    if quote <= 0:
        return None
    return 2 * amount * quote


def all_liq() -> Tuple[List[str], float, float]:
    usd = egld_usd()
    total = 0.0
    lines = []

    sources = [
        ("WOODY/EGLD xExchange", liq_wegld(XEX)),
        ("WOODY/EGLD OneDex", liq_wegld(ONEDX)),
        ("WOODY/BOBER", liq_other(WOODY_BOBER, BOBER)),
        ("WOODY/JEX", liq_other(WOODY_JEX, JEX)),
        ("WOODY/MEX", liq_other(WOODY_MEX, MEX)),
    ]

    if WOODY_USDC:
        sources.append(("WOODY/USDC", liq_other(WOODY_USDC, USDC_HINT)))

    for name, value in sources:
        if value is not None and value > 0:
            total += value
            lines.append(f"• {name}: {value:.3f} EGLD (${value * usd:,.2f})")
        else:
            lines.append(f"• {name}: N/A")

    return lines, total, usd


def price_egld() -> Optional[float]:
    r = reserves(XEX)
    woody = r.get(WOODY, 0.0)
    wegld = r.get(WEGLD, 0.0)
    if woody > 0:
        return wegld / woody
    return None


def holders() -> Optional[int]:
    data = get_json(f"{MVX}/tokens/{WOODY}")
    if not isinstance(data, dict):
        return None
    try:
        return int(data["accounts"])
    except Exception:
        return None


# =========================================================
# TELEGRAM UI
# =========================================================
def kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("💰 Price", callback_data="price"),
            InlineKeyboardButton("💧 Liquidity", callback_data="liquidity"),
        ],
        [
            InlineKeyboardButton("👥 Holders", callback_data="holders"),
            InlineKeyboardButton("📈 Chart", url=CHART_URL),
        ],
        [
            InlineKeyboardButton("🟢 BUY xExchange", url=BUY_XEXCHANGE_URL),
            InlineKeyboardButton("🟢 BUY XOXNO", url=BUY_XOXNO_URL),
        ],
        [
            InlineKeyboardButton("𝕏 Twitter", url=TWITTER_URL),
        ],
    ])


def start_caption() -> str:
    return (
        "🪶 *WOODY Monitor Stable*\n\n"
        "Tracks:\n"
        "• Price\n"
        "• Liquidity view\n"
        "• Holders\n"
        "• BUY / SELL alerts from pool reserve changes\n\n"
        "*Note:* automatic liquidity alerts are disabled to avoid false alerts.\n\n"
        "Choose an option below 👇"
    )


def format_price_text() -> str:
    p = price_egld()
    if p is None:
        return "💰 *WOODY Price*\n\nN/A"
    usd = egld_usd()
    return (
        "💰 *WOODY Price*\n\n"
        f"Price: *{p:.12f} EGLD*\n"
        f"USD: *${(p * usd):.10f}*"
    )


def format_liquidity_text() -> str:
    lines, total, usd = all_liq()
    return (
        "💧 *WOODY Liquidity*\n\n"
        + "\n".join(lines)
        + f"\n\n*TOTAL:* `{total:.3f} EGLD (${total * usd:,.2f})`\n\n"
        + "🔒 *OneDex burn wallet:*\n"
        + f"`{ONEDEX_BURN_ADDRESS}`"
    )


def format_holders_text(value: Optional[int]) -> str:
    return f"👥 *WOODY Holders*\n\nCurrent holders: *{value if value is not None else 'N/A'}*"


async def send_start_menu(chat_id: int, context: ContextTypes.DEFAULT_TYPE) -> None:
    if file_exists(BANNER_IMAGE):
        with open(image_path(BANNER_IMAGE), "rb") as photo:
            await context.bot.send_photo(
                chat_id=chat_id,
                photo=InputFile(photo),
                caption=start_caption(),
                parse_mode=ParseMode.MARKDOWN,
                reply_markup=kb(),
            )
    else:
        await context.bot.send_message(
            chat_id=chat_id,
            text=start_caption(),
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=kb(),
        )


async def send_photo_alert(context: ContextTypes.DEFAULT_TYPE, image_name: str, message: str) -> None:
    for target in chat_targets():
        try:
            if file_exists(image_name):
                with open(image_path(image_name), "rb") as photo:
                    await context.bot.send_photo(
                        chat_id=target,
                        photo=photo,
                        caption=message,
                    )
            else:
                await context.bot.send_message(
                    chat_id=target,
                    text=message,
                    disable_web_page_preview=True,
                )
            logger.info("Alert sent to %s", target)
        except Exception as exc:
            logger.warning("[ALERT ERROR] %s -> %s", target, exc)


# =========================================================
# BUY / SELL DETECTION FROM RESERVE DELTAS
# =========================================================
def get_pair_state(pair_address: str) -> Dict[str, float]:
    r = reserves(pair_address)
    return {
        "woody": r.get(WOODY, 0.0),
        "wegld": r.get(WEGLD, 0.0),
    }


def calc_price_from_state(state: Dict[str, float]) -> Optional[float]:
    woody = state.get("woody", 0.0)
    wegld = state.get("wegld", 0.0)
    if woody > 0:
        return wegld / woody
    return None


def detect_swap(old_state: Dict[str, float], new_state: Dict[str, float]) -> Optional[Dict[str, float]]:
    if not old_state or not new_state:
        return None

    old_woody = old_state["woody"]
    old_wegld = old_state["wegld"]
    new_woody = new_state["woody"]
    new_wegld = new_state["wegld"]

    delta_woody = new_woody - old_woody
    delta_wegld = new_wegld - old_wegld

    abs_woody = abs(delta_woody)
    abs_wegld = abs(delta_wegld)

    old_price = calc_price_from_state(old_state)
    new_price = calc_price_from_state(new_state)

    # Filter noise: dacă prețul aproape nu se schimbă, ignoră
    if old_price and new_price and old_price > 0:
        bps = abs((new_price - old_price) / old_price) * 10000
        if bps < MIN_PRICE_CHANGE_BPS:
            return None

    # BUY: WOODY scade din pool, EGLD crește în pool
    if delta_woody < 0 and delta_wegld > 0:
        if abs_woody >= MIN_WOODY_ALERT or abs_wegld >= MIN_EGLD_ALERT:
            return {
                "type": "BUY",
                "woody": abs_woody,
                "egld": abs_wegld,
            }

    # SELL: WOODY crește în pool, EGLD scade în pool
    if delta_woody > 0 and delta_wegld < 0:
        if abs_woody >= MIN_WOODY_ALERT or abs_wegld >= MIN_EGLD_ALERT:
            return {
                "type": "SELL",
                "woody": abs_woody,
                "egld": abs_wegld,
            }

    # Dacă ambele cresc sau ambele scad = cel mai probabil add/remove liquidity sau altă mișcare => ignoră
    return None


def alert_tier(egld_value: float, tx_type: str) -> str:
    if tx_type == "BUY":
        if egld_value >= WHALE_BUY_EGLD:
            return "WHALE BUY"
        if egld_value >= BIG_BUY_EGLD:
            return "BIG BUY"
        return "BUY"

    if tx_type == "SELL":
        if egld_value >= WHALE_SELL_EGLD:
            return "WHALE SELL"
        if egld_value >= BIG_SELL_EGLD:
            return "BIG SELL"
        return "SELL"

    return tx_type


def choose_image(tx_type: str, egld_value: float) -> str:
    tier = alert_tier(egld_value, tx_type)

    if tier in {"WHALE BUY", "BIG BUY"}:
        return BIG_BUY_IMAGE
    if tier in {"WHALE SELL", "BIG SELL"}:
        return BIG_SELL_IMAGE
    if tx_type == "BUY":
        return BUY_IMAGE
    return SELL_IMAGE


def build_swap_message(pool_label: str, tx_type: str, woody_amount: float, egld_value: float) -> str:
    tier = alert_tier(egld_value, tx_type)

    if tier == "WHALE BUY":
        title = "🟢🐳 WOODY WHALE BUY"
    elif tier == "WHALE SELL":
        title = "🔴🐳 WOODY WHALE SELL"
    elif tier == "BIG BUY":
        title = "🚀 WOODY BIG BUY"
    elif tier == "BIG SELL":
        title = "💥 WOODY BIG SELL"
    elif tx_type == "BUY":
        title = "🟢 WOODY BUY ALERT"
    else:
        title = "🔴 WOODY SELL ALERT"

    current_price = price_egld()
    price_line = f"\n📊 Price: {current_price:.12f} EGLD" if current_price is not None else ""

    return (
        f"{title}\n\n"
        f"💱 Pool: {pool_label}\n"
        f"🪙 Amount: {woody_amount:,.2f} WOODY\n"
        f"💰 Value: {egld_value:.6f} EGLD"
        f"{price_line}"
    )


# =========================================================
# COMMANDS / CALLBACKS
# =========================================================
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await send_start_menu(update.effective_chat.id, context)


async def status(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    text = (
        "✅ *WOODY Monitor Stable is running*\n\n"
        f"Private alerts: *{'YES' if PRIVATE_CHAT_ID else 'NO'}*\n"
        f"Group alerts: *{'YES' if GROUP_CHAT_ID else 'NO'}*\n"
        f"WOODY threshold: *{MIN_WOODY_ALERT:,.0f}*\n"
        f"EGLD threshold: *{MIN_EGLD_ALERT}*\n"
        f"BIG BUY >= *{BIG_BUY_EGLD} EGLD*\n"
        f"BIG SELL >= *{BIG_SELL_EGLD} EGLD*\n"
        f"WHALE BUY >= *{WHALE_BUY_EGLD} EGLD*\n"
        f"WHALE SELL >= *{WHALE_SELL_EGLD} EGLD*\n\n"
        "*Automatic liquidity alerts are OFF* to avoid false alerts."
    )
    if update.message:
        await update.message.reply_text(text, parse_mode=ParseMode.MARKDOWN)


async def get_id(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if update.message:
        await update.message.reply_text(f"Chat ID: {update.effective_chat.id}")


async def price_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if update.message:
        await update.message.reply_text(format_price_text(), parse_mode=ParseMode.MARKDOWN, reply_markup=kb())


async def liquidity_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if update.message:
        await update.message.reply_text(format_liquidity_text(), parse_mode=ParseMode.MARKDOWN)


async def holders_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if update.message:
        await update.message.reply_text(format_holders_text(holders()), parse_mode=ParseMode.MARKDOWN)


async def testalert_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await send_photo_alert(context, BUY_IMAGE, "🧪 WOODY TEST ALERT\n\nIf you received this, alerts work correctly.")
    if update.message:
        await update.message.reply_text("Test alert sent.")


async def btn(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    q = update.callback_query
    if not q:
        return

    await q.answer()

    if q.data == "price":
        txt = format_price_text()
    elif q.data == "liquidity":
        txt = format_liquidity_text()
    elif q.data == "holders":
        txt = format_holders_text(holders())
    else:
        txt = "N/A"

    await q.message.reply_text(txt, parse_mode=ParseMode.MARKDOWN, reply_markup=kb())


async def monitor(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not update.message:
        return

    text = update.message.text or ""

    if GREET.search(text):
        now = int(time.time())
        last_ts = context.application.bot_data.get("last_greet_ts", 0)
        if now - last_ts >= GREETING_COOLDOWN_SECONDS:
            context.application.bot_data["last_greet_ts"] = now
            await update.message.reply_text(GREETING_REPLIES[now % len(GREETING_REPLIES)])

    if SPAM.search(text):
        try:
            await update.message.delete()
        except Exception:
            pass


async def welcome(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    cm = update.chat_member
    if cm.old_chat_member.status in ("left", "kicked"):
        await context.bot.send_message(
            update.effective_chat.id,
            WELCOME_MESSAGES[int(time.time()) % len(WELCOME_MESSAGES)],
        )


# =========================================================
# JOBS
# =========================================================
async def check_swaps(context: ContextTypes.DEFAULT_TYPE) -> None:
    try:
        pairs = [
            ("xexchange", "WOODY/EGLD xExchange", XEX),
            ("onedx", "WOODY/EGLD OneDex", ONEDX),
        ]

        for key, label, address in pairs:
            current_state = get_pair_state(address)
            previous_state = LAST_SWAP_STATE.get(key)

            if previous_state is None:
                LAST_SWAP_STATE[key] = current_state
                continue

            event = detect_swap(previous_state, current_state)

            if event:
                now = time.time()
                if now - LAST_ALERT_TS.get(key, 0.0) < MIN_SECONDS_BETWEEN_SAME_POOL_ALERTS:
                    LAST_SWAP_STATE[key] = current_state
                    continue

                LAST_ALERT_TS[key] = now

                message = build_swap_message(
                    pool_label=label,
                    tx_type=event["type"],
                    woody_amount=event["woody"],
                    egld_value=event["egld"],
                )
                await send_photo_alert(context, choose_image(event["type"], event["egld"]), message)

            LAST_SWAP_STATE[key] = current_state

    except Exception as exc:
        logger.warning("[swap monitor error] %s", exc)


async def check_holders(context: ContextTypes.DEFAULT_TYPE) -> None:
    global LAST_HOLDERS_COUNT, PENDING_HOLDER_VALUE

    try:
        current_holders = holders()
        if current_holders is None:
            return

        if LAST_HOLDERS_COUNT is None:
            LAST_HOLDERS_COUNT = current_holders
            return

        if current_holders > LAST_HOLDERS_COUNT:
            if PENDING_HOLDER_VALUE is None:
                PENDING_HOLDER_VALUE = current_holders
                return

            if current_holders == PENDING_HOLDER_VALUE:
                diff = current_holders - LAST_HOLDERS_COUNT
                message = (
                    f"👤 WOODY NEW HOLDER\n\n"
                    f"Added holders: +{diff}\n"
                    f"Total holders: {current_holders}"
                )
                await send_photo_alert(context, NEW_HOLDER_IMAGE, message)
                LAST_HOLDERS_COUNT = current_holders
                PENDING_HOLDER_VALUE = None
        else:
            PENDING_HOLDER_VALUE = None

    except Exception as exc:
        logger.warning("[holders monitor error] %s", exc)


# =========================================================
# MAIN
# =========================================================
def main() -> None:
    require_token()

    app = Application.builder().token(TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("status", status))
    app.add_handler(CommandHandler("id", get_id))
    app.add_handler(CommandHandler("price", price_cmd))
    app.add_handler(CommandHandler("liquidity", liquidity_cmd))
    app.add_handler(CommandHandler("holders", holders_cmd))
    app.add_handler(CommandHandler("testalert", testalert_cmd))

    app.add_handler(CallbackQueryHandler(btn))
    app.add_handler(ChatMemberHandler(welcome, ChatMemberHandler.CHAT_MEMBER))
    app.add_handler(MessageHandler(filters.TEXT & filters.ChatType.GROUPS, monitor))

    if app.job_queue is None:
        raise RuntimeError("JobQueue missing. Install python-telegram-bot[job-queue].")

    app.job_queue.run_repeating(check_swaps, interval=CHECK_SWAPS_INTERVAL, first=10)
    app.job_queue.run_repeating(check_holders, interval=CHECK_HOLDERS_INTERVAL, first=20)

    logger.info("WOODY Monitor Stable started...")
    app.run_polling(drop_pending_updates=True)


if __name__ == "__main__":
    main()
