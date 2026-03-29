import os
import re
import time
import logging
import asyncio
from typing import Dict, Optional, Tuple, List, Any, Set

import requests
import socketio
from dotenv import load_dotenv

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, InputFile
from telegram.constants import ParseMode
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

MVX_API = os.getenv("MVX_API", "https://api.multiversx.com").strip()
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

XEXCHANGE_POOL_ADDRESS = os.getenv(
    "XEXCHANGE_POOL_ADDRESS",
    "erd1qqqqqqqqqqqqqpgqvmgnk26tfvz6sj5yasw7p6yfvqpv628d2jpsnvmeaz",
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

WOODY_MEX_POOL_ADDRESS = os.getenv(
    "WOODY_MEX_POOL_ADDRESS",
    "erd1qqqqqqqqqqqqqpgqzqtfej5s9hp7cg0ardy6mt3fvz4jrdsa2jpsdg959f",
).strip()

ONEDEX_BURN_ADDRESS = os.getenv(
    "ONEDEX_BURN_ADDRESS",
    "erd1deaddeaddeaddeaddeaddeaddeaddeaddeaddeaddeaddeaddeaqtv0gag",
).strip()

ROUTER_ADDRESSES = {
    x.strip()
    for x in os.getenv("ROUTER_ADDRESSES", "").split(",")
    if x.strip()
}

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

# praguri
MIN_ALERT_USD = float(os.getenv("MIN_ALERT_USD", "2"))
BIG_ALERT_USD = float(os.getenv("BIG_ALERT_USD", "10"))
WHALE_ALERT_USD = float(os.getenv("WHALE_ALERT_USD", "100"))
SUPER_WHALE_ALERT_USD = float(os.getenv("SUPER_WHALE_ALERT_USD", "500"))

MIN_WOODY_AMOUNT = float(os.getenv("MIN_WOODY_AMOUNT", "1"))
MIN_QUOTE_AMOUNT = float(os.getenv("MIN_QUOTE_AMOUNT", "0.0001"))

CHECK_HOLDERS_INTERVAL = int(os.getenv("CHECK_HOLDERS_INTERVAL", "120"))
GREETING_COOLDOWN_SECONDS = int(os.getenv("GREETING_COOLDOWN_SECONDS", "120"))
ROOT_STATE_TTL_SECONDS = int(os.getenv("ROOT_STATE_TTL_SECONDS", "180"))
WS_RECONNECT_DELAY = int(os.getenv("WS_RECONNECT_DELAY", "8"))
WS_DEBUG_LOG_TRANSFERS = os.getenv("WS_DEBUG_LOG_TRANSFERS", "0").strip() == "1"

# =========================================================
# LOGGING
# =========================================================
logging.basicConfig(
    format="%(asctime)s | %(levelname)s | %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger("WOODY_WS_PROMAX")

# =========================================================
# GLOBALS
# =========================================================
UA = {"User-Agent": "WOODY WS ProMax Bot"}

PRICE_CACHE: Dict[str, Tuple[float, float]] = {}
LAST_HOLDERS_COUNT: Optional[int] = None
PENDING_HOLDER_VALUE: Optional[int] = None

ROOT_STATE: Dict[str, Dict[str, Any]] = {}
SEEN_TRANSFER_KEYS: Set[str] = set()
ALERTED_ROOT_HASHES: Set[str] = set()

WS_CLIENT: Optional[socketio.AsyncClient] = None
WS_TASK: Optional[asyncio.Task] = None
APP_REF: Optional[Application] = None

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

POOL_LABELS = {
    XEXCHANGE_POOL_ADDRESS: "xExchange",
    ONEDEX_POOL_ADDRESS: "OneDex",
    WOODY_USDC_POOL_ADDRESS: "WOODY/USDC",
    WOODY_BOBER_POOL_ADDRESS: "WOODY/BOBER",
    WOODY_JEX_POOL_ADDRESS: "WOODY/JEX",
    WOODY_MEX_POOL_ADDRESS: "WOODY/MEX",
}

KNOWN_TECHNICAL_ADDRESSES = {
    XEXCHANGE_POOL_ADDRESS,
    ONEDEX_POOL_ADDRESS,
    WOODY_USDC_POOL_ADDRESS,
    WOODY_BOBER_POOL_ADDRESS,
    WOODY_JEX_POOL_ADDRESS,
    WOODY_MEX_POOL_ADDRESS,
    ONEDEX_BURN_ADDRESS,
    *ROUTER_ADDRESSES,
}
KNOWN_TECHNICAL_ADDRESSES = {x for x in KNOWN_TECHNICAL_ADDRESSES if x}
WATCHED_POOLS = [x for x in POOL_LABELS.keys() if x]

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


def short_wallet(addr: str) -> str:
    if not addr:
        return "unknown"
    if len(addr) < 18:
        return addr
    return f"{addr[:10]}...{addr[-8:]}"


def symbol(token_id: str) -> str:
    if not token_id:
        return "?"
    return token_id.split("-")[0]


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


def is_technical_address(addr: str) -> bool:
    if not addr:
        return False
    if addr in KNOWN_TECHNICAL_ADDRESSES:
        return True
    if addr.startswith("erd1qqqqqqqqqqqqqpgq"):
        return True
    return False


def is_pool_address(addr: str) -> bool:
    return addr in POOL_LABELS


def chat_targets() -> List[str]:
    targets: List[str] = []
    if PRIVATE_CHAT_ID:
        targets.append(PRIVATE_CHAT_ID)
    if GROUP_CHAT_ID:
        targets.append(GROUP_CHAT_ID)
    return targets


def looks_like_lp_token(token_id: str) -> bool:
    token_upper = token_id.upper()
    if "LP" in token_upper:
        return True
    if "WOODY" in token_upper and (
        "WEGLD" in token_upper
        or "USDC" in token_upper
        or "BOBER" in token_upper
        or "JEX" in token_upper
        or "MEX" in token_upper
    ):
        return True
    return False


def transfer_has_liquidity_signature(transfer: dict) -> bool:
    function_name = str(transfer.get("function") or "").lower()
    action = transfer.get("action") or {}
    action_name = str(action.get("name") or "").lower()
    data_field = str(transfer.get("data") or "").lower()

    hay = " | ".join([function_name, action_name, data_field])
    keywords = [
        "addliquidity",
        "multiaddliquidity",
        "removeliquidity",
        "add_liquidity",
        "remove_liquidity",
    ]
    return any(k in hay for k in keywords)


# =========================================================
# PRICE / HOLDERS / LIQUIDITY
# =========================================================
def reserves(pair_address: str) -> Dict[str, float]:
    if not pair_address:
        return {}

    data = get_json(f"{MVX_API}/accounts/{pair_address}/tokens")
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


def find_token_amount(pool_reserves: Dict[str, float], token_hint: str) -> float:
    if not pool_reserves or not token_hint:
        return 0.0

    if token_hint in pool_reserves:
        return safe_float(pool_reserves[token_hint])

    hint_upper = token_hint.upper()
    for token_id, amount in pool_reserves.items():
        if hint_upper in token_id.upper():
            return safe_float(amount)

    return 0.0


def quote_to_wegld(token: str) -> float:
    if token == WEGLD or symbol(token).upper() == "WEGLD":
        return 1.0

    if USDC_HINT.upper() in token.upper():
        egld = egld_usd()
        return 1.0 / egld if egld > 0 else 0.0

    q = get_json(XOXNO_QUOTE_API, {"from": token, "to": WEGLD, "amountIn": str(10**18)})
    out = None
    if isinstance(q, dict):
        out = q.get("amountOut") or q.get("toAmount")
    try:
        return int(str(out)) / (10**18) if out else 0.0
    except Exception:
        return 0.0


def quote_to_usd(token: str, amount: float) -> float:
    if amount <= 0:
        return 0.0

    if token == "EGLD":
        return amount * egld_usd()
    if token == WEGLD or symbol(token).upper() == "WEGLD":
        return amount * egld_usd()
    if USDC_HINT.upper() in token.upper():
        return amount

    wegld_equiv = quote_to_wegld(token)
    if wegld_equiv <= 0:
        return 0.0
    return amount * wegld_equiv * egld_usd()


def get_price_from_wegld_pool(pair_address: str, source_name: str) -> Optional[Dict[str, Any]]:
    r = reserves(pair_address)
    woody = find_token_amount(r, WOODY)
    wegld = find_token_amount(r, WEGLD)

    if woody > 0 and wegld > 0:
        p_egld = wegld / woody
        p_usd = p_egld * egld_usd()
        return {
            "price_egld": p_egld,
            "price_usd": p_usd,
            "source": source_name,
            "woody_reserve": woody,
            "quote_reserve": wegld,
            "quote_symbol": "WEGLD",
        }
    return None


def get_price_from_usdc_pool(pair_address: str, source_name: str) -> Optional[Dict[str, Any]]:
    r = reserves(pair_address)
    woody = find_token_amount(r, WOODY)

    usdc_amount = 0.0
    for token_id, amount in r.items():
        if USDC_HINT.upper() in token_id.upper():
            usdc_amount = safe_float(amount)
            break

    if woody > 0 and usdc_amount > 0:
        p_usd = usdc_amount / woody
        egld_price = egld_usd()
        p_egld = p_usd / egld_price if egld_price > 0 else 0.0
        return {
            "price_egld": p_egld,
            "price_usd": p_usd,
            "source": source_name,
            "woody_reserve": woody,
            "quote_reserve": usdc_amount,
            "quote_symbol": "USDC",
        }
    return None


def get_price_from_other_pool(pair_address: str, quote_token: str, source_name: str) -> Optional[Dict[str, Any]]:
    r = reserves(pair_address)
    woody = find_token_amount(r, WOODY)
    quote_amount = find_token_amount(r, quote_token)

    if woody <= 0 or quote_amount <= 0:
        return None

    quote_in_wegld = quote_to_wegld(quote_token)
    if quote_in_wegld <= 0:
        return None

    p_egld = (quote_amount * quote_in_wegld) / woody
    p_usd = p_egld * egld_usd()

    return {
        "price_egld": p_egld,
        "price_usd": p_usd,
        "source": source_name,
        "woody_reserve": woody,
        "quote_reserve": quote_amount,
        "quote_symbol": symbol(quote_token),
    }


def get_best_price() -> Optional[Dict[str, Any]]:
    candidates = [
        get_price_from_wegld_pool(XEXCHANGE_POOL_ADDRESS, "xExchange WOODY/WEGLD"),
        get_price_from_usdc_pool(WOODY_USDC_POOL_ADDRESS, "xExchange WOODY/USDC"),
        get_price_from_other_pool(WOODY_MEX_POOL_ADDRESS, MEX, "xExchange WOODY/MEX"),
        get_price_from_other_pool(WOODY_JEX_POOL_ADDRESS, JEX, "WOODY/JEX"),
        get_price_from_other_pool(WOODY_BOBER_POOL_ADDRESS, BOBER, "WOODY/BOBER"),
    ]
    if ONEDEX_POOL_ADDRESS:
        candidates.append(get_price_from_wegld_pool(ONEDEX_POOL_ADDRESS, "OneDex WOODY/WEGLD"))

    for item in candidates:
        if item and item.get("price_egld", 0) > 0:
            return item
    return None


def holders() -> Optional[int]:
    data = get_json(f"{MVX_API}/tokens/{WOODY}")
    if not isinstance(data, dict):
        return None
    try:
        return int(data["accounts"])
    except Exception:
        return None


def liq_wegld(pair_address: str) -> Optional[float]:
    r = reserves(pair_address)
    wegld = find_token_amount(r, WEGLD)
    return 2 * wegld if wegld > 0 else None


def liq_other(pair_address: str, token: str) -> Optional[float]:
    r = reserves(pair_address)
    amount = find_token_amount(r, token)
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
        ("WOODY/EGLD xExchange", liq_wegld(XEXCHANGE_POOL_ADDRESS)),
        ("WOODY/USDC", liq_other(WOODY_USDC_POOL_ADDRESS, USDC_HINT)),
        ("WOODY/BOBER", liq_other(WOODY_BOBER_POOL_ADDRESS, BOBER)),
        ("WOODY/JEX", liq_other(WOODY_JEX_POOL_ADDRESS, JEX)),
        ("WOODY/MEX", liq_other(WOODY_MEX_POOL_ADDRESS, MEX)),
    ]
    if ONEDEX_POOL_ADDRESS:
        sources.append(("WOODY/EGLD OneDex", liq_wegld(ONEDEX_POOL_ADDRESS)))

    for name, value in sources:
        if value is not None and value > 0:
            total += value
            lines.append(f"• {name}: {value:.3f} EGLD (${value * usd:,.2f})")
        else:
            lines.append(f"• {name}: N/A")
    return lines, total, usd


def format_price_text() -> str:
    best = get_best_price()
    if not best:
        return "💰 *WOODY Price*\n\nN/A"

    return (
        "💰 *WOODY Price*\n\n"
        f"Price: *{best['price_egld']:.12f} EGLD*\n"
        f"USD: *${best['price_usd']:.10f}*\n"
        f"Source: *{best['source']}*\n"
        f"WOODY Reserve: *{best['woody_reserve']:,.2f}*\n"
        f"{best['quote_symbol']} Reserve: *{best['quote_reserve']:,.6f}*"
    )


def format_liquidity_text() -> str:
    lines, total, usd = all_liq()
    best = get_best_price()
    price_line = ""
    if best:
        price_line = (
            f"\n*Live price source:* `{best['source']}`"
            f"\n*Live price:* `{best['price_egld']:.12f} EGLD (${best['price_usd']:.10f})`"
        )

    return (
        "💧 *WOODY Liquidity*\n\n"
        + "\n".join(lines)
        + f"\n\n*TOTAL:* `{total:.3f} EGLD (${total * usd:,.2f})`"
        + price_line
        + f"\n\n🔒 *OneDex burn wallet:*\n`{ONEDEX_BURN_ADDRESS}`"
    )


def format_holders_text(value: Optional[int]) -> str:
    return f"👥 *WOODY Holders*\n\nCurrent holders: *{value if value is not None else 'N/A'}*"


# =========================================================
# TELEGRAM ALERT HELPERS
# =========================================================
async def send_start_menu(chat_id: int, context: ContextTypes.DEFAULT_TYPE) -> None:
    caption = (
        "🪶 *WOODY Monitor WS ProMax*\n\n"
        "Tracks:\n"
        "• WebSocket real-time swap alerts\n"
        "• Price\n"
        "• Liquidity view\n"
        "• Holders\n"
        "• Wallet short address\n"
        "• Quote token used\n"
        "• DEX detection\n\n"
        "Choose an option below 👇"
    )
    keyboard = InlineKeyboardMarkup([
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

    if file_exists(BANNER_IMAGE):
        with open(image_path(BANNER_IMAGE), "rb") as photo:
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


async def send_photo_alert(context: ContextTypes.DEFAULT_TYPE, image_name: str, message: str) -> None:
    for target in chat_targets():
        try:
            if file_exists(image_name):
                with open(image_path(image_name), "rb") as photo:
                    await context.bot.send_photo(chat_id=target, photo=photo, caption=message)
            else:
                await context.bot.send_message(chat_id=target, text=message, disable_web_page_preview=True)
            logger.info("Alert sent to %s", target)
        except Exception as exc:
            logger.warning("[ALERT ERROR] %s -> %s", target, exc)


async def send_photo_alert_app(app: Application, image_name: str, message: str) -> None:
    for target in chat_targets():
        try:
            if file_exists(image_name):
                with open(image_path(image_name), "rb") as photo:
                    await app.bot.send_photo(chat_id=target, photo=photo, caption=message)
            else:
                await app.bot.send_message(chat_id=target, text=message, disable_web_page_preview=True)
            logger.info("WS alert sent to %s", target)
        except Exception as exc:
            logger.warning("[WS ALERT ERROR] %s -> %s", target, exc)


# =========================================================
# ROOT HASH / WALLET-CENTRIC AGGREGATION
# =========================================================
def cleanup_root_state() -> None:
    now = time.time()
    expired = [
        root_hash
        for root_hash, data in ROOT_STATE.items()
        if now - safe_float(data.get("updated", now)) > ROOT_STATE_TTL_SECONDS
    ]
    for root_hash in expired:
        ROOT_STATE.pop(root_hash, None)


def make_transfer_key(root_hash: str, sender: str, receiver: str, token: str, value: str) -> str:
    return f"{root_hash}|{sender}|{receiver}|{token}|{value}"


def get_root_hash(transfer: dict) -> str:
    return str(transfer.get("originalTxHash") or transfer.get("txHash") or "")


def get_transfers_from_action(transfer: dict) -> List[dict]:
    action = transfer.get("action") or {}
    args = action.get("arguments") or {}
    transfers = args.get("transfers") or []
    return transfers if isinstance(transfers, list) else []


def detect_dex_from_addresses(sender: str, receiver: str) -> str:
    if sender in POOL_LABELS:
        return POOL_LABELS[sender]
    if receiver in POOL_LABELS:
        return POOL_LABELS[receiver]
    return "Aggregator"


def add_leg_to_root(root_hash: str, sender: str, receiver: str, token: str, amount: float, dex: str) -> None:
    state = ROOT_STATE.setdefault(
        root_hash,
        {
            "legs": [],
            "wallet_net": {},   # wallet -> token -> net
            "updated": time.time(),
        },
    )
    state["updated"] = time.time()
    state["legs"].append(
        {
            "sender": sender,
            "receiver": receiver,
            "token": token,
            "amount": amount,
            "dex": dex,
        }
    )

    # wallet-centric net in/out only for non-technical addresses
    if not is_technical_address(sender):
        state["wallet_net"].setdefault(sender, {})
        state["wallet_net"][sender][token] = state["wallet_net"][sender].get(token, 0.0) - amount

    if not is_technical_address(receiver):
        state["wallet_net"].setdefault(receiver, {})
        state["wallet_net"][receiver][token] = state["wallet_net"][receiver].get(token, 0.0) + amount


def dominant_wallet_for_buy(root_hash: str) -> Optional[str]:
    state = ROOT_STATE.get(root_hash)
    if not state:
        return None

    best_wallet = None
    best_score = 0.0
    for wallet, nets in state["wallet_net"].items():
        woody_net = safe_float(nets.get(WOODY, 0.0))
        quote_out_usd = 0.0
        for token, net in nets.items():
            if token == WOODY:
                continue
            if net < 0:
                quote_out_usd += quote_to_usd(token, abs(net))
        score = woody_net + (quote_out_usd * 1000)
        if woody_net > MIN_WOODY_AMOUNT and quote_out_usd >= MIN_ALERT_USD and score > best_score:
            best_score = score
            best_wallet = wallet
    return best_wallet


def dominant_wallet_for_sell(root_hash: str) -> Optional[str]:
    state = ROOT_STATE.get(root_hash)
    if not state:
        return None

    best_wallet = None
    best_score = 0.0
    for wallet, nets in state["wallet_net"].items():
        woody_out = abs(min(safe_float(nets.get(WOODY, 0.0)), 0.0))
        quote_in_usd = 0.0
        for token, net in nets.items():
            if token == WOODY:
                continue
            if net > 0:
                quote_in_usd += quote_to_usd(token, net)
        score = woody_out + (quote_in_usd * 1000)
        if woody_out > MIN_WOODY_AMOUNT and quote_in_usd >= MIN_ALERT_USD and score > best_score:
            best_score = score
            best_wallet = wallet
    return best_wallet


def dominant_quote_from_wallet_nets(nets: Dict[str, float], want_positive: bool) -> Optional[Tuple[str, float]]:
    candidates: Dict[str, float] = {}
    for token, net in nets.items():
        if token == WOODY:
            continue
        if looks_like_lp_token(token):
            continue

        amount = 0.0
        if want_positive and net > 0:
            amount = net
        elif (not want_positive) and net < 0:
            amount = abs(net)

        if amount <= MIN_QUOTE_AMOUNT:
            continue
        candidates[token] = candidates.get(token, 0.0) + amount

    if not candidates:
        return None
    return max(candidates.items(), key=lambda x: quote_to_usd(x[0], x[1]))


def dominant_dex_for_buy(root_hash: str) -> str:
    state = ROOT_STATE.get(root_hash)
    if not state:
        return "Aggregator"

    dex_scores: Dict[str, float] = {}
    for leg in state["legs"]:
        if leg["token"] == WOODY and is_pool_address(leg["sender"]):
            dex_scores[leg["dex"]] = dex_scores.get(leg["dex"], 0.0) + safe_float(leg["amount"])

    if not dex_scores:
        return "Aggregator"
    return max(dex_scores.items(), key=lambda x: x[1])[0]


def dominant_dex_for_sell(root_hash: str) -> str:
    state = ROOT_STATE.get(root_hash)
    if not state:
        return "Aggregator"

    dex_scores: Dict[str, float] = {}
    for leg in state["legs"]:
        if leg["token"] == WOODY and is_pool_address(leg["receiver"]):
            dex_scores[leg["dex"]] = dex_scores.get(leg["dex"], 0.0) + safe_float(leg["amount"])

    if not dex_scores:
        return "Aggregator"
    return max(dex_scores.items(), key=lambda x: x[1])[0]


def find_buy_from_root(root_hash: str) -> Optional[Dict[str, Any]]:
    state = ROOT_STATE.get(root_hash)
    if not state:
        return None

    wallet = dominant_wallet_for_buy(root_hash)
    if not wallet:
        return None

    nets = state["wallet_net"].get(wallet, {})
    woody_amount = safe_float(nets.get(WOODY, 0.0))
    if woody_amount <= MIN_WOODY_AMOUNT:
        return None

    quote = dominant_quote_from_wallet_nets(nets, want_positive=False)
    if not quote:
        return None
    quote_token, quote_amount = quote

    usd_value = quote_to_usd(quote_token, quote_amount)
    if usd_value < MIN_ALERT_USD:
        return None

    return {
        "wallet": wallet,
        "type": "BUY",
        "woody_amount": woody_amount,
        "quote_token": quote_token,
        "quote_amount": quote_amount,
        "pair": f"WOODY / {symbol(quote_token)}",
        "dex": dominant_dex_for_buy(root_hash),
        "swap_usd_value": usd_value,
        "root_hash": root_hash,
    }


def find_sell_from_root(root_hash: str) -> Optional[Dict[str, Any]]:
    state = ROOT_STATE.get(root_hash)
    if not state:
        return None

    wallet = dominant_wallet_for_sell(root_hash)
    if not wallet:
        return None

    nets = state["wallet_net"].get(wallet, {})
    woody_amount = abs(min(safe_float(nets.get(WOODY, 0.0)), 0.0))
    if woody_amount <= MIN_WOODY_AMOUNT:
        return None

    quote = dominant_quote_from_wallet_nets(nets, want_positive=True)
    if not quote:
        return None
    quote_token, quote_amount = quote

    usd_value = quote_to_usd(quote_token, quote_amount)
    if usd_value < MIN_ALERT_USD:
        return None

    return {
        "wallet": wallet,
        "type": "SELL",
        "woody_amount": woody_amount,
        "quote_token": quote_token,
        "quote_amount": quote_amount,
        "pair": f"WOODY / {symbol(quote_token)}",
        "dex": dominant_dex_for_sell(root_hash),
        "swap_usd_value": usd_value,
        "root_hash": root_hash,
    }


def classify_root_hash(root_hash: str) -> Optional[Dict[str, Any]]:
    if root_hash in ALERTED_ROOT_HASHES:
        return None

    buy = find_buy_from_root(root_hash)
    sell = find_sell_from_root(root_hash)

    if buy and sell:
        if safe_float(buy["swap_usd_value"]) >= safe_float(sell["swap_usd_value"]):
            ALERTED_ROOT_HASHES.add(root_hash)
            return buy
        ALERTED_ROOT_HASHES.add(root_hash)
        return sell

    if buy:
        ALERTED_ROOT_HASHES.add(root_hash)
        return buy

    if sell:
        ALERTED_ROOT_HASHES.add(root_hash)
        return sell

    return None


def process_transfer_item(transfer: dict, item: dict) -> Optional[Dict[str, Any]]:
    root_hash = get_root_hash(transfer)
    if not root_hash:
        return None

    # anti-liquidity
    if transfer_has_liquidity_signature(transfer):
        if WS_DEBUG_LOG_TRANSFERS:
            logger.info("Ignoring liquidity event root=%s", root_hash)
        return None

    sender = str(transfer.get("sender") or "")
    receiver = str(transfer.get("receiver") or "")
    if not sender or not receiver:
        return None

    token = str(item.get("token") or "")
    value = str(item.get("value") or "0")
    decimals = safe_int(item.get("decimals", 18))
    amount = d(value, decimals)

    if WS_DEBUG_LOG_TRANSFERS:
        logger.info(
            "WS transfer | root=%s sender=%s receiver=%s token=%s value=%s decimals=%s amount=%s",
            root_hash, sender, receiver, token, value, decimals, amount
        )

    # anti-LP
    if looks_like_lp_token(token):
        if WS_DEBUG_LOG_TRANSFERS:
            logger.info("Ignoring LP-like token root=%s token=%s", root_hash, token)
        return None

    # anti-dust
    if token == WOODY and amount <= MIN_WOODY_AMOUNT:
        return None
    if token != WOODY and amount <= MIN_QUOTE_AMOUNT:
        return None

    transfer_key = make_transfer_key(root_hash, sender, receiver, token, value)
    if transfer_key in SEEN_TRANSFER_KEYS:
        return None
    SEEN_TRANSFER_KEYS.add(transfer_key)

    dex = detect_dex_from_addresses(sender, receiver)
    add_leg_to_root(root_hash, sender, receiver, token, amount, dex)

    parsed = classify_root_hash(root_hash)
    if WS_DEBUG_LOG_TRANSFERS and parsed:
        logger.info("WS swap parsed successfully: %s", parsed)

    return parsed


def alert_label(parsed: Dict[str, Any]) -> str:
    usd = safe_float(parsed.get("swap_usd_value", 0.0))
    tx_type = parsed.get("type", "")

    if usd >= SUPER_WHALE_ALERT_USD:
        return f"SUPER WHALE {tx_type}"
    if usd >= WHALE_ALERT_USD:
        return f"WHALE {tx_type}"
    if usd >= BIG_ALERT_USD:
        return f"BIG {tx_type}"
    return tx_type


def choose_title(parsed: Dict[str, Any]) -> str:
    label = alert_label(parsed)

    if label == "SUPER WHALE BUY":
        return "🟢🐋 WOODY SUPER WHALE BUY"
    if label == "SUPER WHALE SELL":
        return "🔴🐋 WOODY SUPER WHALE SELL"
    if label == "WHALE BUY":
        return "🟢🐳 WOODY WHALE BUY"
    if label == "WHALE SELL":
        return "🔴🐳 WOODY WHALE SELL"
    if label == "BIG BUY":
        return "🚀 WOODY BIG BUY"
    if label == "BIG SELL":
        return "💥 WOODY BIG SELL"
    if label == "BUY":
        return "🟢 WOODY BUY ALERT"
    return "🔴 WOODY SELL ALERT"


def choose_image(parsed: Dict[str, Any]) -> str:
    label = alert_label(parsed)
    if label in {"BIG BUY", "WHALE BUY", "SUPER WHALE BUY"}:
        return BIG_BUY_IMAGE
    if label in {"BIG SELL", "WHALE SELL", "SUPER WHALE SELL"}:
        return BIG_SELL_IMAGE
    if parsed.get("type") == "BUY":
        return BUY_IMAGE
    return SELL_IMAGE


def build_swap_message(parsed: Dict[str, Any]) -> str:
    explorer = f"https://explorer.multiversx.com/transactions/{parsed['root_hash']}"
    title = choose_title(parsed)
    best = get_best_price()

    price_line = ""
    if best:
        price_line = f"📊 Price: {best['price_egld']:.12f} EGLD (${best['price_usd']:.10f})\n"

    return (
        f"{title}\n\n"
        f"👤 Wallet: {short_wallet(parsed['wallet'])}\n"
        f"🪶 WOODY: {parsed['woody_amount']:,.2f}\n"
        f"💵 Token: {parsed['quote_amount']:,.6f} {symbol(parsed['quote_token'])}\n"
        f"💲 Value: ${parsed['swap_usd_value']:,.2f}\n"
        f"💱 Pair: {parsed['pair']}\n"
        f"🏦 DEX: {parsed['dex']}\n"
        f"{price_line}"
        f"🔗 Explorer: {explorer}"
    )


# =========================================================
# WEBSOCKET
# =========================================================
async def ws_get_endpoint() -> Optional[str]:
    try:
        data = await asyncio.to_thread(get_json, f"{MVX_API}/websocket/config")
        if isinstance(data, dict) and data.get("url"):
            return f"https://{data['url']}"
    except Exception as exc:
        logger.warning("Failed websocket config fetch -> %s", exc)
    return None


def extract_transfers_from_payload(data: Any) -> List[dict]:
    if isinstance(data, dict):
        transfers = data.get("transfers")
        if isinstance(transfers, list):
            return transfers

        if isinstance(data.get("transfer"), dict):
            return [data["transfer"]]

        if isinstance(data.get("data"), dict):
            inner = data["data"].get("transfers")
            if isinstance(inner, list):
                return inner

        if "sender" in data and "receiver" in data:
            return [data]

    elif isinstance(data, list):
        return [x for x in data if isinstance(x, dict)]

    return []


async def ws_connect_loop() -> None:
    global WS_CLIENT
    while True:
        try:
            endpoint = await ws_get_endpoint()
            if not endpoint:
                logger.warning("No websocket endpoint discovered, retrying...")
                await asyncio.sleep(WS_RECONNECT_DELAY)
                continue

            logger.info("Connecting websocket to %s", endpoint)

            sio = socketio.AsyncClient(
                reconnection=True,
                reconnection_attempts=0,
                logger=False,
                engineio_logger=False,
            )
            WS_CLIENT = sio

            @sio.event
            async def connect():
                logger.info("WebSocket connected")

                await sio.emit("subscribeCustomTransfers", {"token": WOODY})
                logger.info("Subscribed custom transfers for token: %s", WOODY)

                for pool in WATCHED_POOLS:
                    await sio.emit("subscribeCustomTransfers", {"address": pool})
                    logger.info("Subscribed custom transfers for address: %s", pool)

            @sio.event
            async def disconnect():
                logger.warning("WebSocket disconnected")

            @sio.on("error")
            async def on_error(data):
                logger.warning("WebSocket server error payload: %s", data)

            @sio.on("customTransferUpdate")
            async def on_custom_transfer_update(data):
                try:
                    logger.info("customTransferUpdate raw payload received")
                    cleanup_root_state()

                    transfers = extract_transfers_from_payload(data)
                    if not transfers:
                        logger.info("customTransferUpdate payload has no usable transfers")
                        if WS_DEBUG_LOG_TRANSFERS:
                            logger.info("RAW PAYLOAD: %s", data)
                        return

                    logger.info("customTransferUpdate transfers count=%s", len(transfers))

                    for transfer in transfers:
                        items = get_transfers_from_action(transfer)
                        if not items:
                            if WS_DEBUG_LOG_TRANSFERS:
                                logger.info("Transfer without action.arguments.transfers: %s", transfer)
                            continue

                        for item in items:
                            try:
                                parsed = process_transfer_item(transfer, item)
                                if parsed and APP_REF is not None:
                                    message = build_swap_message(parsed)
                                    await send_photo_alert_app(APP_REF, choose_image(parsed), message)
                            except Exception as item_exc:
                                logger.exception("Transfer item processing error: %s", item_exc)
                except Exception as exc:
                    logger.exception("customTransferUpdate handler error: %s", exc)

            await sio.connect(
                endpoint,
                socketio_path="/ws/subscription",
                transports=["websocket"],
                wait_timeout=20,
            )
            await sio.wait()

        except asyncio.CancelledError:
            raise
        except Exception as exc:
            logger.warning("WebSocket loop error -> %s", exc)
            try:
                if WS_CLIENT:
                    await WS_CLIENT.disconnect()
            except Exception:
                pass
            await asyncio.sleep(WS_RECONNECT_DELAY)


# =========================================================
# COMMANDS / HANDLERS
# =========================================================
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await send_start_menu(update.effective_chat.id, context)


async def status(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    text = (
        "✅ *WOODY Monitor WS ProMax is running*\n\n"
        f"Private alerts: *{'YES' if PRIVATE_CHAT_ID else 'NO'}*\n"
        f"Group alerts: *{'YES' if GROUP_CHAT_ID else 'NO'}*\n"
        f"Min alert: *${MIN_ALERT_USD}*\n"
        f"BIG alert: *${BIG_ALERT_USD}*\n"
        f"WHALE alert: *${WHALE_ALERT_USD}*\n"
        f"SUPER WHALE alert: *${SUPER_WHALE_ALERT_USD}*"
    )
    if update.message:
        await update.message.reply_text(text, parse_mode=ParseMode.MARKDOWN)


async def get_id(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if update.message:
        await update.message.reply_text(f"Chat ID: {update.effective_chat.id}")


async def price_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if update.message:
        await update.message.reply_text(format_price_text(), parse_mode=ParseMode.MARKDOWN)


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


async def menu_btn(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
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

    await q.message.reply_text(txt, parse_mode=ParseMode.MARKDOWN)


async def monitor_messages(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
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


async def error_handler(update: object, context: ContextTypes.DEFAULT_TYPE) -> None:
    logger.exception("Unhandled exception: %s", context.error)


# =========================================================
# APP LIFECYCLE
# =========================================================
async def on_startup(app: Application) -> None:
    global APP_REF, WS_TASK
    APP_REF = app
    WS_TASK = asyncio.create_task(ws_connect_loop())
    logger.info("Startup complete, websocket task launched")


async def on_shutdown(app: Application) -> None:
    global WS_TASK, WS_CLIENT
    if WS_TASK:
        WS_TASK.cancel()
        try:
            await WS_TASK
        except asyncio.CancelledError:
            pass
    if WS_CLIENT:
        try:
            await WS_CLIENT.disconnect()
        except Exception:
            pass
    logger.info("Shutdown complete")


# =========================================================
# MAIN
# =========================================================
def main() -> None:
    require_token()

    app = (
        Application.builder()
        .token(TOKEN)
        .post_init(on_startup)
        .post_shutdown(on_shutdown)
        .build()
    )

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("status", status))
    app.add_handler(CommandHandler("id", get_id))
    app.add_handler(CommandHandler("price", price_cmd))
    app.add_handler(CommandHandler("liquidity", liquidity_cmd))
    app.add_handler(CommandHandler("holders", holders_cmd))
    app.add_handler(CommandHandler("testalert", testalert_cmd))

    app.add_handler(CallbackQueryHandler(menu_btn))
    app.add_handler(ChatMemberHandler(welcome, ChatMemberHandler.CHAT_MEMBER))
    app.add_handler(MessageHandler(filters.TEXT & filters.ChatType.GROUPS, monitor_messages))

    app.add_error_handler(error_handler)

    if app.job_queue is None:
        raise RuntimeError("JobQueue missing. Install python-telegram-bot[job-queue].")

    app.job_queue.run_repeating(check_holders, interval=CHECK_HOLDERS_INTERVAL, first=20)

    logger.info("WOODY Monitor WS ProMax started...")
    app.run_polling(drop_pending_updates=True)


if __name__ == "__main__":
    main()
