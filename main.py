import os
import time
import random
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

ENABLE_PRIVATE_ALERTS = os.getenv("ENABLE_PRIVATE_ALERTS", "true").strip().lower() == "true"
ENABLE_GROUP_ALERTS = os.getenv("ENABLE_GROUP_ALERTS", "false").strip().lower() == "true"

MVX_API = os.getenv("MVX_API", "https://api.multiversx.com").strip()
WS_URL = os.getenv("WS_URL", "https://socket-api-ovh.multiversx.com").strip()
COINGECKO_EGLD_API = os.getenv(
    "COINGECKO_EGLD_API",
    "https://api.coingecko.com/api/v3/simple/price?ids=elrond-erd-2&vs_currencies=usd",
).strip()

WOODY = os.getenv("WOODY_TOKEN_ID", "WOODY-5f9d9c").strip()
WEGLD = os.getenv("WEGLD_TOKEN_ID", "WEGLD-bd4d79").strip()
USDC_HINT = os.getenv("USDC_TOKEN_HINT", "USDC").strip()
JEX = os.getenv("JEX_TOKEN_ID", "JEX-9040ca").strip()
MEX = os.getenv("MEX_TOKEN_ID", "MEX-455c57").strip()
BOBER = os.getenv("BOBER_TOKEN_ID", "BOBER-9eb764").strip()

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

MIN_ALERT_USD = float(os.getenv("MIN_ALERT_USD", "2"))
BIG_ALERT_USD = float(os.getenv("BIG_ALERT_USD", "10"))
WHALE_ALERT_USD = float(os.getenv("WHALE_ALERT_USD", "100"))
SUPER_WHALE_ALERT_USD = float(os.getenv("SUPER_WHALE_ALERT_USD", "500"))

ROOT_SETTLE_SECONDS = int(os.getenv("ROOT_SETTLE_SECONDS", "6"))
ROOT_MAX_AGE_SECONDS = int(os.getenv("ROOT_MAX_AGE_SECONDS", "90"))
CHECK_HOLDERS_INTERVAL = int(os.getenv("CHECK_HOLDERS_INTERVAL", "120"))
WS_RECONNECT_DELAY = int(os.getenv("WS_RECONNECT_DELAY", "8"))

EXTRA_TECHNICAL_ADDRESSES = {
    x.strip()
    for x in os.getenv("EXTRA_TECHNICAL_ADDRESSES", "").split(",")
    if x.strip()
}

# =========================================================
# LOGGING
# =========================================================
logging.basicConfig(
    format="%(asctime)s | %(levelname)s | %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger("WOODY_MONITOR_V2")

# =========================================================
# GLOBALS
# =========================================================
UA = {"User-Agent": "WOODY Monitor V2"}

PRICE_CACHE: Dict[str, Tuple[float, float]] = {}
ROOT_PENDING: Dict[str, Dict[str, Any]] = {}
ROOT_PROCESSED: Set[str] = set()

LAST_HOLDERS_COUNT: Optional[int] = None
PENDING_HOLDER_VALUE: Optional[int] = None

WATCHED_POOLS = {
    XEXCHANGE_POOL_ADDRESS: "xExchange",
    ONEDEX_POOL_ADDRESS: "OneDex",
    WOODY_USDC_POOL_ADDRESS: "WOODY/USDC",
    WOODY_BOBER_POOL_ADDRESS: "WOODY/BOBER",
    WOODY_JEX_POOL_ADDRESS: "WOODY/JEX",
    WOODY_MEX_POOL_ADDRESS: "WOODY/MEX",
}
WATCHED_POOLS = {k: v for k, v in WATCHED_POOLS.items() if k}

DEFAULT_TECH_ADDRESSES = {
    XEXCHANGE_POOL_ADDRESS,
    ONEDEX_POOL_ADDRESS,
    WOODY_USDC_POOL_ADDRESS,
    WOODY_BOBER_POOL_ADDRESS,
    WOODY_JEX_POOL_ADDRESS,
    WOODY_MEX_POOL_ADDRESS,
    ONEDEX_BURN_ADDRESS,
    "erd1qqqqqqqqqqqqqpgq5rf2sppxk2xu4m0pkmugw2es4gak3rgjah0sxvajva",
    "erd1xp9gdkln4s3t8qd2pw6sr7de6dfyy33yath48m6sc9ndt9jv08yqp84mtg",
    "erd17dr22kal8p9halkyp0xxe9kf7euyvn9j0jyr67223k8ccdtgdnuq2wfu5s",
    "erd1qqqqqqqqqqqqqpgqcc69ts8409p3h77q5chsaqz57y6hugvc4fvs64k74v",
    "erd1qqqqqqqqqqqqqpgqjsnxqprks7qxfwkcg2m2v9hxkrchgm9akp2segrswt",
}
KNOWN_TECH_ADDRESSES = {x for x in DEFAULT_TECH_ADDRESSES | EXTRA_TECHNICAL_ADDRESSES if x}

# =========================================================
# HELPERS
# =========================================================
def safe_float(value: Any) -> float:
    try:
        return float(value)
    except Exception:
        return 0.0


def safe_int(value: Any, default: int = 0) -> int:
    try:
        return int(str(value))
    except Exception:
        return default


def amount_from_raw(raw: Any, decimals: Any) -> float:
    try:
        return int(str(raw)) / (10 ** int(decimals))
    except Exception:
        return 0.0


def symbol(token_id: str) -> str:
    if not token_id:
        return "?"
    return token_id.split("-")[0]


def short_wallet(addr: str) -> str:
    if not addr:
        return "unknown"
    if len(addr) < 18:
        return addr
    return f"{addr[:10]}...{addr[-8:]}"


def is_technical_address(addr: str) -> bool:
    if not addr:
        return False
    if addr in KNOWN_TECH_ADDRESSES:
        return True
    if addr.startswith("erd1qqqqqqqqqqqqqpgq"):
        return True
    return False


def is_real_wallet(addr: str) -> bool:
    return bool(addr) and not is_technical_address(addr)


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
        r = requests.get(url, params=params, headers=UA, timeout=25)
        r.raise_for_status()
        return r.json()
    except Exception as exc:
        logger.warning("GET JSON failed for %s -> %s", url, exc)
        return None


def get_tx_details(tx_hash: str) -> Optional[dict]:
    if not tx_hash:
        return None
    params = {
        "withOperations": "true",
        "withScResults": "true",
        "withLogs": "true",
    }
    data = get_json(f"{MVX_API}/transactions/{tx_hash}", params=params)
    return data if isinstance(data, dict) else None


def chat_targets() -> List[str]:
    targets: List[str] = []
    if ENABLE_PRIVATE_ALERTS and PRIVATE_CHAT_ID:
        targets.append(PRIVATE_CHAT_ID)
    if ENABLE_GROUP_ALERTS and GROUP_CHAT_ID:
        targets.append(GROUP_CHAT_ID)
    return targets

# =========================================================
# PRICE / LIQUIDITY / HOLDERS
# =========================================================
def reserves(pair_address: str) -> Dict[str, float]:
    data = get_json(f"{MVX_API}/accounts/{pair_address}/tokens")
    if not isinstance(data, list):
        return {}
    out: Dict[str, float] = {}
    for item in data:
        token = str(item.get("identifier") or "")
        if not token:
            continue
        out[token] = amount_from_raw(item.get("balance"), item.get("decimals"))
    return out


def get_egld_usd() -> float:
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


def find_token_amount(res_map: Dict[str, float], token_hint: str) -> float:
    if token_hint in res_map:
        return safe_float(res_map[token_hint])

    hint = token_hint.upper()
    for token_id, amount in res_map.items():
        if hint in token_id.upper():
            return safe_float(amount)
    return 0.0


def get_best_price() -> Optional[Dict[str, Any]]:
    egld_usd = get_egld_usd()

    # xExchange WOODY/WEGLD
    r = reserves(XEXCHANGE_POOL_ADDRESS)
    woody = find_token_amount(r, WOODY)
    wegld = find_token_amount(r, WEGLD)
    if woody > 0 and wegld > 0:
        p_egld = wegld / woody
        return {
            "price_egld": p_egld,
            "price_usd": p_egld * egld_usd,
            "source": "xExchange WOODY/WEGLD",
            "woody_reserve": woody,
            "quote_symbol": "WEGLD",
            "quote_reserve": wegld,
        }

    # WOODY/USDC fallback
    r = reserves(WOODY_USDC_POOL_ADDRESS)
    woody = find_token_amount(r, WOODY)
    usdc = 0.0
    for token_id, amount in r.items():
        if USDC_HINT.upper() in token_id.upper():
            usdc = amount
            break

    if woody > 0 and usdc > 0:
        p_usd = usdc / woody
        return {
            "price_egld": p_usd / egld_usd if egld_usd > 0 else 0.0,
            "price_usd": p_usd,
            "source": "WOODY/USDC",
            "woody_reserve": woody,
            "quote_symbol": "USDC",
            "quote_reserve": usdc,
        }

    return None


def get_holders_count() -> Optional[int]:
    data = get_json(f"{MVX_API}/tokens/{WOODY}")
    if not isinstance(data, dict):
        return None
    try:
        return int(data["accounts"])
    except Exception:
        return None


def get_liquidity_text() -> str:
    lines: List[str] = []
    total_egld = 0.0
    egld_usd = get_egld_usd()

    for addr, label in WATCHED_POOLS.items():
        r = reserves(addr)
        woody = find_token_amount(r, WOODY)

        wegld = find_token_amount(r, WEGLD)
        if woody > 0 and wegld > 0:
            liq = 2 * wegld
            total_egld += liq
            lines.append(f"• {label}: {liq:.3f} EGLD (${liq * egld_usd:,.2f})")
            continue

        # try USDC
        usdc = 0.0
        for token_id, amount in r.items():
            if USDC_HINT.upper() in token_id.upper():
                usdc = amount
                break
        if woody > 0 and usdc > 0:
            liq_usd = usdc * 2
            liq_egld = liq_usd / egld_usd if egld_usd > 0 else 0.0
            total_egld += liq_egld
            lines.append(f"• {label}: {liq_egld:.3f} EGLD (${liq_usd:,.2f})")
            continue

        lines.append(f"• {label}: N/A")

    best = get_best_price()
    price_line = ""
    if best:
        price_line = (
            f"\nLive price source: {best['source']}\n"
            f"Live price: {best['price_egld']:.12f} EGLD (${best['price_usd']:.10f})"
        )

    return (
        "💧 *WOODY Liquidity*\n\n"
        + "\n".join(lines)
        + f"\n\n*TOTAL:* `{total_egld:.3f} EGLD (${total_egld * egld_usd:,.2f})`"
        + price_line
        + f"\n\n🔒 *OneDex burn wallet:*\n`{ONEDEX_BURN_ADDRESS}`"
    )


def get_price_text() -> str:
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

# =========================================================
# TELEGRAM UI
# =========================================================
def main_menu_keyboard() -> InlineKeyboardMarkup:
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
        "🪶 *WOODY Monitor V2*\n\n"
        "Tracks:\n"
        "• WebSocket root trigger\n"
        "• REST transaction parser\n"
        "• Price\n"
        "• Liquidity\n"
        "• Holders\n"
        "• Wallet short address\n"
        "• Quote token used\n"
        "• DEX detection\n\n"
        "Choose an option below 👇"
    )


async def send_start_menu(chat_id: int, context: ContextTypes.DEFAULT_TYPE) -> None:
    if file_exists(BANNER_IMAGE):
        with open(image_path(BANNER_IMAGE), "rb") as photo:
            await context.bot.send_photo(
                chat_id=chat_id,
                photo=InputFile(photo),
                caption=start_caption(),
                parse_mode=ParseMode.MARKDOWN,
                reply_markup=main_menu_keyboard(),
            )
    else:
        await context.bot.send_message(
            chat_id=chat_id,
            text=start_caption(),
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=main_menu_keyboard(),
        )


async def send_alert_to_targets(
    context: ContextTypes.DEFAULT_TYPE,
    image_name: str,
    caption: str,
) -> None:
    targets = chat_targets()
    if not targets:
        logger.warning("No alert targets configured")
        return

    for target in targets:
        try:
            if file_exists(image_name):
                with open(image_path(image_name), "rb") as photo:
                    await context.bot.send_photo(
                        chat_id=target,
                        photo=InputFile(photo),
                        caption=caption,
                    )
            else:
                await context.bot.send_message(
                    chat_id=target,
                    text=caption,
                    disable_web_page_preview=True,
                )
            logger.info("Alert sent to %s", target)
        except Exception as exc:
            logger.warning("[ALERT ERROR] %s -> %s", target, exc)

# =========================================================
# TRANSACTION CLASSIFIER
# =========================================================
def operation_token(op: dict) -> str:
    return str(op.get("identifier") or op.get("tokenIdentifier") or "")


def operation_amount(op: dict) -> float:
    return amount_from_raw(op.get("value", "0"), op.get("decimals", 18))


def detect_pool_dex(tx: dict) -> str:
    addresses = set()

    for op in tx.get("operations") or []:
        s = op.get("sender")
        r = op.get("receiver")
        if s:
            addresses.add(s)
        if r:
            addresses.add(r)

    for pool_addr, label in WATCHED_POOLS.items():
        if pool_addr in addresses:
            return label

    return "Unknown"


def choose_real_wallet(tx: dict) -> Optional[str]:
    counts: Dict[str, int] = {}

    for addr in [tx.get("sender", ""), tx.get("receiver", "")]:
        if is_real_wallet(addr):
            counts[addr] = counts.get(addr, 0) + 3

    for op in tx.get("operations") or []:
        for field in ("sender", "receiver"):
            addr = op.get(field, "")
            if is_real_wallet(addr):
                counts[addr] = counts.get(addr, 0) + 1

    if not counts:
        return None

    return sorted(counts.items(), key=lambda x: x[1], reverse=True)[0][0]


def get_wallet_flows(tx: dict, wallet: str) -> Tuple[Dict[str, float], Dict[str, float]]:
    sent: Dict[str, float] = {}
    received: Dict[str, float] = {}

    for op in tx.get("operations") or []:
        token = operation_token(op)
        if not token:
            continue
        amount = operation_amount(op)
        if amount <= 0:
            continue

        sender = str(op.get("sender") or "")
        receiver = str(op.get("receiver") or "")

        if sender == wallet:
            sent[token] = sent.get(token, 0.0) + amount
        if receiver == wallet:
            received[token] = received.get(token, 0.0) + amount

    return sent, received


def token_usd_estimate(token: str, amount: float) -> float:
    if amount <= 0:
        return 0.0

    if token == WEGLD or symbol(token).upper() in {"WEGLD", "XEGLD", "EGLD"}:
        return amount * get_egld_usd()

    if USDC_HINT.upper() in token.upper():
        return amount

    # rough fallback via pool reserve ratios if possible
    best = get_best_price()
    if best and token == WOODY:
        return amount * best["price_usd"]

    return 0.0


def classify_tx(tx: dict) -> Optional[Dict[str, Any]]:
    wallet = choose_real_wallet(tx)
    if not wallet:
        return None

    sent, received = get_wallet_flows(tx, wallet)

    woody_sent = sent.get(WOODY, 0.0)
    woody_received = received.get(WOODY, 0.0)

    non_woody_sent = {k: v for k, v in sent.items() if k != WOODY and v > 0}
    non_woody_received = {k: v for k, v in received.items() if k != WOODY and v > 0}

    dex = detect_pool_dex(tx)

    # BUY
    if woody_received > 0:
        quote_token = ""
        quote_amount = 0.0

        if non_woody_sent:
            quote_token, quote_amount = sorted(non_woody_sent.items(), key=lambda x: x[1], reverse=True)[0]
        else:
            # fallback: choose strongest non-WOODY token sent by any real/technical participant to watched pools
            pool_inflows: Dict[str, float] = {}
            for op in tx.get("operations") or []:
                token = operation_token(op)
                if not token or token == WOODY:
                    continue
                amount = operation_amount(op)
                if amount <= 0:
                    continue
                receiver = str(op.get("receiver") or "")
                if receiver in WATCHED_POOLS:
                    pool_inflows[token] = pool_inflows.get(token, 0.0) + amount

            if pool_inflows:
                quote_token, quote_amount = sorted(pool_inflows.items(), key=lambda x: x[1], reverse=True)[0]

        if quote_amount > 0:
            usd_value = max(
                token_usd_estimate(quote_token, quote_amount),
                token_usd_estimate(WOODY, woody_received),
            )
            return {
                "type": "BUY",
                "wallet": wallet,
                "woody_amount": woody_received,
                "quote_token": quote_token,
                "quote_amount": quote_amount,
                "swap_usd_value": usd_value,
                "dex": dex,
                "root_hash": tx.get("txHash") or tx.get("originalTxHash") or "",
            }

    # SELL
    if woody_sent > 0:
        quote_token = ""
        quote_amount = 0.0

        if non_woody_received:
            quote_token, quote_amount = sorted(non_woody_received.items(), key=lambda x: x[1], reverse=True)[0]
        else:
            pool_outflows: Dict[str, float] = {}
            for op in tx.get("operations") or []:
                token = operation_token(op)
                if not token or token == WOODY:
                    continue
                amount = operation_amount(op)
                if amount <= 0:
                    continue
                sender = str(op.get("sender") or "")
                if sender in WATCHED_POOLS:
                    pool_outflows[token] = pool_outflows.get(token, 0.0) + amount

            if pool_outflows:
                quote_token, quote_amount = sorted(pool_outflows.items(), key=lambda x: x[1], reverse=True)[0]

        if quote_amount > 0:
            usd_value = max(
                token_usd_estimate(quote_token, quote_amount),
                token_usd_estimate(WOODY, woody_sent),
            )
            return {
                "type": "SELL",
                "wallet": wallet,
                "woody_amount": woody_sent,
                "quote_token": quote_token,
                "quote_amount": quote_amount,
                "swap_usd_value": usd_value,
                "dex": dex,
                "root_hash": tx.get("txHash") or tx.get("originalTxHash") or "",
            }

    return None


def choose_title(parsed: Dict[str, Any]) -> str:
    usd = safe_float(parsed.get("swap_usd_value", 0.0))
    tx_type = parsed.get("type", "")

    if usd >= SUPER_WHALE_ALERT_USD:
        return f"{'🟢🐋' if tx_type == 'BUY' else '🔴🐋'} WOODY SUPER WHALE {tx_type}"
    if usd >= WHALE_ALERT_USD:
        return f"{'🟢🐳' if tx_type == 'BUY' else '🔴🐳'} WOODY WHALE {tx_type}"
    if usd >= BIG_ALERT_USD:
        return f"{'🚀' if tx_type == 'BUY' else '💥'} WOODY BIG {tx_type}"
    return f"{'🟢' if tx_type == 'BUY' else '🔴'} WOODY {tx_type} ALERT"


def choose_image(parsed: Dict[str, Any]) -> str:
    usd = safe_float(parsed.get("swap_usd_value", 0.0))
    tx_type = parsed.get("type", "")

    if tx_type == "BUY":
        return BIG_BUY_IMAGE if usd >= BIG_ALERT_USD else BUY_IMAGE
    return BIG_SELL_IMAGE if usd >= BIG_ALERT_USD else SELL_IMAGE


def build_message(parsed: Dict[str, Any]) -> str:
    explorer = f"https://explorer.multiversx.com/transactions/{parsed['root_hash']}"
    best = get_best_price()

    price_line = ""
    if best:
        price_line = f"📊 Price: {best['price_egld']:.12f} EGLD (${best['price_usd']:.10f})\n"

    return (
        f"{choose_title(parsed)}\n\n"
        f"👤 Wallet: {short_wallet(parsed['wallet'])}\n"
        f"🪶 WOODY: {parsed['woody_amount']:,.6f}\n"
        f"💵 Quote: {parsed['quote_amount']:,.6f} {symbol(parsed['quote_token'])}\n"
        f"💲 Value: ${parsed['swap_usd_value']:,.2f}\n"
        f"🏦 DEX: {parsed['dex']}\n"
        f"{price_line}"
        f"🔗 Explorer: {explorer}"
    )

# =========================================================
# ROOT QUEUE + WEBSOCKET
# =========================================================
def add_root(root_hash: str) -> None:
    if not root_hash:
        return
    if root_hash in ROOT_PROCESSED:
        return

    item = ROOT_PENDING.get(root_hash)
    if item:
        item["updated"] = time.time()
    else:
        ROOT_PENDING[root_hash] = {
            "created": time.time(),
            "updated": time.time(),
        }


async def ws_connect_loop() -> None:
    while True:
        sio = socketio.AsyncClient(
            reconnection=True,
            reconnection_attempts=0,
            logger=False,
            engineio_logger=False,
        )

        @sio.event
        async def connect():
            logger.info("WebSocket connected")
            try:
                await sio.emit("subscribeCustomTransfers", {"token": WOODY})
                logger.info("Subscribed custom transfers for token: %s", WOODY)
            except Exception as exc:
                logger.warning("Token subscription failed -> %s", exc)

            for pool in WATCHED_POOLS:
                try:
                    await sio.emit("subscribeCustomTransfers", {"address": pool})
                    logger.info("Subscribed custom transfers for address: %s", pool)
                except Exception as exc:
                    logger.warning("Address subscription failed for %s -> %s", pool, exc)

        @sio.event
        async def disconnect():
            logger.warning("WebSocket disconnected")

        @sio.on("customTransferUpdate")
        async def on_custom_transfer_update(data):
            logger.info("customTransferUpdate raw payload received")

            transfers = (data or {}).get("transfers") or []
            logger.info("customTransferUpdate transfers count=%s", len(transfers))

            if not isinstance(transfers, list):
                return

            for transfer in transfers:
                root_hash = str(transfer.get("originalTxHash") or transfer.get("txHash") or "")
                if not root_hash:
                    continue
                add_root(root_hash)

        try:
            logger.info("Connecting websocket to %s", WS_URL)
            await sio.connect(WS_URL, socketio_path="/ws/subscription", transports=["websocket"])
            await sio.wait()
        except asyncio.CancelledError:
            raise
        except Exception as exc:
            logger.warning("WebSocket loop error -> %s", exc)
            await asyncio.sleep(WS_RECONNECT_DELAY)

# =========================================================
# JOBS
# =========================================================
async def process_pending_roots(context: ContextTypes.DEFAULT_TYPE) -> None:
    now = time.time()
    to_delete: List[str] = []

    for root_hash, data in list(ROOT_PENDING.items()):
        age = now - safe_float(data.get("created", now))
        idle = now - safe_float(data.get("updated", now))

        if idle < ROOT_SETTLE_SECONDS and age < ROOT_MAX_AGE_SECONDS:
            continue

        tx = await asyncio.to_thread(get_tx_details, root_hash)
        if not tx:
            logger.warning("No tx details fetched for root %s", root_hash)
            to_delete.append(root_hash)
            ROOT_PROCESSED.add(root_hash)
            continue

        parsed = classify_tx(tx)
        if parsed and parsed.get("swap_usd_value", 0.0) >= MIN_ALERT_USD:
            message = build_message(parsed)
            await send_alert_to_targets(context, choose_image(parsed), message)
            logger.info(
                "ALERT SENT | root=%s type=%s wallet=%s woody=%s quote=%s %s dex=%s usd=%s",
                parsed["root_hash"],
                parsed["type"],
                parsed["wallet"],
                parsed["woody_amount"],
                parsed["quote_amount"],
                parsed["quote_token"],
                parsed["dex"],
                parsed["swap_usd_value"],
            )
        else:
            logger.info("Root %s classified as no alert", root_hash)

        to_delete.append(root_hash)
        ROOT_PROCESSED.add(root_hash)

    for root_hash in to_delete:
        ROOT_PENDING.pop(root_hash, None)

    if len(ROOT_PROCESSED) > 20000:
        ROOT_PROCESSED.clear()


async def check_holders(context: ContextTypes.DEFAULT_TYPE) -> None:
    global LAST_HOLDERS_COUNT, PENDING_HOLDER_VALUE

    current = get_holders_count()
    if current is None:
        return

    if LAST_HOLDERS_COUNT is None:
        LAST_HOLDERS_COUNT = current
        return

    if current > LAST_HOLDERS_COUNT:
        if PENDING_HOLDER_VALUE is None:
            PENDING_HOLDER_VALUE = current
            return

        if current == PENDING_HOLDER_VALUE:
            diff = current - LAST_HOLDERS_COUNT
            caption = (
                f"👤 WOODY NEW HOLDER\n\n"
                f"Added holders: +{diff}\n"
                f"Total holders: {current}"
            )
            await send_alert_to_targets(context, NEW_HOLDER_IMAGE, caption)
            LAST_HOLDERS_COUNT = current
            PENDING_HOLDER_VALUE = None
    else:
        PENDING_HOLDER_VALUE = None

# =========================================================
# COMMANDS
# =========================================================
async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await send_start_menu(update.effective_chat.id, context)


async def status_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    text = (
        "✅ *WOODY Monitor V2 is running*\n\n"
        f"Private alerts: *{'YES' if (ENABLE_PRIVATE_ALERTS and PRIVATE_CHAT_ID) else 'NO'}*\n"
        f"Group alerts: *{'YES' if (ENABLE_GROUP_ALERTS and GROUP_CHAT_ID) else 'NO'}*\n"
        f"Min alert: *${MIN_ALERT_USD}*\n"
        f"BIG alert: *${BIG_ALERT_USD}*\n"
        f"WHALE alert: *${WHALE_ALERT_USD}*\n"
        f"SUPER WHALE alert: *${SUPER_WHALE_ALERT_USD}*"
    )
    if update.message:
        await update.message.reply_text(text, parse_mode=ParseMode.MARKDOWN)


async def id_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if update.message:
        await update.message.reply_text(f"Chat ID: {update.effective_chat.id}")


async def testalert_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    caption = "🧪 WOODY TEST ALERT\n\nIf you received this, alerts work correctly."
    await send_alert_to_targets(context, BUY_IMAGE, caption)
    if update.message:
        await update.message.reply_text("Test alert sent.")


async def menu_callbacks(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    if not query:
        return

    await query.answer()

    if query.data == "price":
        await query.message.reply_text(get_price_text(), parse_mode=ParseMode.MARKDOWN)
    elif query.data == "liquidity":
        await query.message.reply_text(get_liquidity_text(), parse_mode=ParseMode.MARKDOWN)
    elif query.data == "holders":
        await query.message.reply_text(
            f"👥 *WOODY Holders*\n\nCurrent holders: *{get_holders_count() or 'N/A'}*",
            parse_mode=ParseMode.MARKDOWN,
        )


async def greeting_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not update.message or not update.message.text:
        return

    text = update.message.text.strip().lower()
    if text in {"hello", "hi", "gm", "hey", "salut", "buna", "bună"}:
        replies = [
            "👋 Welcome to WOODY!",
            "🪶 Glad to see you here!",
            "🚀 WOODY community growing!",
        ]
        await update.message.reply_text(random.choice(replies))

# =========================================================
# MAIN
# =========================================================
def main() -> None:
    if not TOKEN:
        raise ValueError("TELEGRAM_BOT_TOKEN is missing")

    app = Application.builder().token(TOKEN).build()

    app.add_handler(CommandHandler("start", start_command))
    app.add_handler(CommandHandler("status", status_command))
    app.add_handler(CommandHandler("id", id_command))
    app.add_handler(CommandHandler("testalert", testalert_command))
    app.add_handler(CallbackQueryHandler(menu_callbacks))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, greeting_handler))

    if app.job_queue is None:
        raise RuntimeError("JobQueue missing. Install python-telegram-bot[job-queue].")

    app.job_queue.run_repeating(check_holders, interval=CHECK_HOLDERS_INTERVAL, first=20)
    app.job_queue.run_repeating(process_pending_roots, interval=3, first=5)

    async def startup_task():
        await ws_connect_loop()

    async def post_init(application: Application) -> None:
        application.create_task(startup_task())
        logger.info("Startup complete, websocket task launched")

    app.post_init = post_init

    logger.info("WOODY Monitor V2 started...")
    app.run_polling(drop_pending_updates=True)


if __name__ == "__main__":
    main()
