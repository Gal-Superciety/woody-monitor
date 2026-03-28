import json
import logging
import os
import re
import time
from typing import Any, Dict, List, Optional, Set, Tuple

import requests
from dotenv import load_dotenv
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, InputFile, Update
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

WOODY_TOKEN_ID = os.getenv("WOODY_TOKEN_ID", "WOODY-5f9d9c").strip()
WEGLD_TOKEN_ID = os.getenv("WEGLD_TOKEN_ID", "WEGLD-bd4d79").strip()
BOBER_TOKEN_ID = os.getenv("BOBER_TOKEN_ID", "BOBER-9eb764").strip()
JEX_TOKEN_ID = os.getenv("JEX_TOKEN_ID", "JEX-9040ca").strip()
MEX_TOKEN_ID = os.getenv("MEX_TOKEN_ID", "MEX-455c57").strip()
USDC_TOKEN_HINT = os.getenv("USDC_TOKEN_HINT", "USDC").strip()

PRICE_URL = os.getenv("PRICE_URL", "https://e-compass.io/token/WOODY-5f9d9c").strip()
CHART_URL = os.getenv("CHART_URL", PRICE_URL).strip()
TWITTER_URL = os.getenv("TWITTER_URL", "https://x.com/WOODY_EX").strip()
BUY_XEXCHANGE_URL = os.getenv("BUY_XEXCHANGE_URL", "https://xexchange.com").strip()
BUY_XOXNO_URL = os.getenv("BUY_XOXNO_URL", "https://xoxno.com").strip()

# Pools
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

# Images
BANNER_IMAGE = os.getenv("BANNER_IMAGE", "banner.png").strip()
BUY_IMAGE = os.getenv("BUY_IMAGE", "buy.png").strip()
SELL_IMAGE = os.getenv("SELL_IMAGE", "sell.png").strip()
BIG_BUY_IMAGE = os.getenv("BIG_BUY_IMAGE", "big_buy.png").strip()
BIG_SELL_IMAGE = os.getenv("BIG_SELL_IMAGE", "big_sell.png").strip()
LIQUIDITY_IMAGE = os.getenv("LIQUIDITY_IMAGE", "liquidity.png").strip()
NEW_HOLDER_IMAGE = os.getenv("NEW_HOLDER_IMAGE", "new_holder.png").strip()
WHALE_BUY_IMAGE = os.getenv("WHALE_BUY_IMAGE", BIG_BUY_IMAGE).strip()
WHALE_SELL_IMAGE = os.getenv("WHALE_SELL_IMAGE", BIG_SELL_IMAGE).strip()

# Thresholds
MIN_ALERT_USD = float(os.getenv("MIN_ALERT_USD", "2"))
BIG_ALERT_USD = float(os.getenv("BIG_ALERT_USD", "10"))
WHALE_ALERT_USD = float(os.getenv("WHALE_ALERT_USD", "100"))
SUPER_WHALE_ALERT_USD = float(os.getenv("SUPER_WHALE_ALERT_USD", "500"))

LIQUIDITY_ADDED_MIN_EGLD = float(os.getenv("LIQUIDITY_ADDED_MIN_EGLD", "0.05"))

# Timing
CHECK_SWAPS_INTERVAL = int(os.getenv("CHECK_SWAPS_INTERVAL", "8"))
CHECK_HOLDERS_INTERVAL = int(os.getenv("CHECK_HOLDERS_INTERVAL", "120"))
CHECK_LIQUIDITY_INTERVAL = int(os.getenv("CHECK_LIQUIDITY_INTERVAL", "120"))
GREETING_COOLDOWN_SECONDS = int(os.getenv("GREETING_COOLDOWN_SECONDS", "120"))

TOKEN_PRICE_CACHE_TTL = int(os.getenv("TOKEN_PRICE_CACHE_TTL", "60"))
POOL_CACHE_TTL = int(os.getenv("POOL_CACHE_TTL", "60"))
TX_CACHE_TTL = int(os.getenv("TX_CACHE_TTL", "15"))

SEEN_TX_FILE = os.getenv("SEEN_TX_FILE", "seen_swaps.json").strip()

# =========================================================
# LOGGING
# =========================================================
logging.basicConfig(
    format="%(asctime)s | %(levelname)s | %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger("WOODY_ULTRA_PRO")

# =========================================================
# GLOBALS
# =========================================================
UA = {"User-Agent": "WOODY Ultra Pro Bot"}

TOKEN_PRICE_CACHE: Dict[str, Dict[str, Any]] = {}
POOL_CACHE: Dict[str, Dict[str, Any]] = {}
MISC_CACHE: Dict[str, Dict[str, Any]] = {}

SEEN_TX_CACHE: Set[str] = set()

LAST_HOLDERS_COUNT: Optional[int] = None
LAST_TOTAL_LIQUIDITY_EGLD: Optional[float] = None
PENDING_HOLDER_VALUE: Optional[int] = None

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

GREET = re.compile(r"\b(hi|hello|gm|salut|buna|bună|hey)\b", re.I)
SPAM = re.compile(r"airdrop|claim|seed|100x|double", re.I)

GREETING_REPLIES = [
    "Hey! Welcome to WOODY 👋",
    "GM and welcome to WOODY 🪶",
    "Glad to see you here in WOODY 🚀",
]

WELCOME_NEW_MEMBER_MESSAGES = [
    "🪶 Welcome to the WOODY community!",
    "🚀 Welcome! WOODY Monitor is watching the ecosystem 24/7.",
    "👋 Glad to have you here in WOODY.",
]

# =========================================================
# BASIC HELPERS
# =========================================================
def require_token() -> None:
    if not TOKEN:
        raise ValueError("TELEGRAM_BOT_TOKEN is missing from .env")


def file_exists(path: str) -> bool:
    if not path:
        return False
    base_dir = os.path.dirname(os.path.abspath(__file__))
    return os.path.exists(os.path.join(base_dir, path))


def image_path(path: str) -> str:
    base_dir = os.path.dirname(os.path.abspath(__file__))
    return os.path.join(base_dir, path)


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


def normalize_amount(raw: Any, decimals: int) -> float:
    try:
        return int(str(raw)) / (10 ** int(decimals))
    except Exception:
        return safe_float(raw)


def short_wallet(addr: str) -> str:
    if not addr:
        return "unknown"
    if len(addr) < 18:
        return addr
    return f"{addr[:10]}...{addr[-8:]}"


def symbol_from_token(token_id: str) -> str:
    if not token_id:
        return "?"
    return token_id.split("-")[0]


def is_technical_address(addr: str) -> bool:
    if not addr:
        return False
    if addr in KNOWN_TECHNICAL_ADDRESSES:
        return True
    if addr.startswith("erd1qqqqqqqqqqqqqpgq"):
        return True
    return False


def get_json(url: str, params: Optional[dict] = None) -> Optional[Any]:
    try:
        r = requests.get(url, params=params, headers=UA, timeout=25)
        r.raise_for_status()
        return r.json()
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
    tmp_path = f"{path}.tmp"
    try:
        with open(tmp_path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        os.replace(tmp_path, path)
    except Exception as exc:
        logger.warning("Could not save %s -> %s", path, exc)


def init_seen_cache() -> None:
    global SEEN_TX_CACHE
    loaded = load_json_file(SEEN_TX_FILE, [])
    if isinstance(loaded, list):
        SEEN_TX_CACHE = set(str(x) for x in loaded if x)
    else:
        SEEN_TX_CACHE = set()


def add_seen_tx(tx_hash: str) -> None:
    global SEEN_TX_CACHE
    if tx_hash not in SEEN_TX_CACHE:
        SEEN_TX_CACHE.add(tx_hash)
        save_json_file(SEEN_TX_FILE, list(SEEN_TX_CACHE)[-5000:])


def has_seen_tx(tx_hash: str) -> bool:
    return tx_hash in SEEN_TX_CACHE


def chat_targets() -> List[str]:
    targets = []
    if PRIVATE_CHAT_ID:
        targets.append(PRIVATE_CHAT_ID)
    if GROUP_CHAT_ID:
        targets.append(GROUP_CHAT_ID)
    return targets


def format_token_map(items: Dict[str, float]) -> str:
    if not items:
        return "-"
    lines = []
    for token, amount in items.items():
        lines.append(f"{amount:,.6f} {token}")
    return "\n".join(lines)


# =========================================================
# CACHE HELPERS
# =========================================================
def get_cached(cache: Dict[str, Dict[str, Any]], key: str, ttl: int) -> Optional[Any]:
    item = cache.get(key)
    if not item:
        return None
    if time.time() - item.get("ts", 0) > ttl:
        return None
    return item.get("value")


def set_cached(cache: Dict[str, Dict[str, Any]], key: str, value: Any) -> None:
    cache[key] = {"value": value, "ts": time.time()}


# =========================================================
# TOKEN / PRICE / HOLDERS
# =========================================================
def get_egld_usd_price() -> float:
    cached = get_cached(MISC_CACHE, "egld_usd", TOKEN_PRICE_CACHE_TTL)
    if cached is not None:
        return safe_float(cached)

    data = get_json(COINGECKO_EGLD_API)
    price = 0.0
    try:
        price = safe_float(data["elrond-erd-2"]["usd"])
    except Exception:
        price = 0.0

    set_cached(MISC_CACHE, "egld_usd", price)
    return price


def get_token_usd_price(token_id: str) -> float:
    if not token_id:
        return 0.0

    cached = get_cached(TOKEN_PRICE_CACHE, token_id, TOKEN_PRICE_CACHE_TTL)
    if cached is not None:
        return safe_float(cached)

    # WEGLD = EGLD
    if WEGLD_TOKEN_ID in token_id or symbol_from_token(token_id).upper() == "WEGLD":
        price = get_egld_usd_price()
        set_cached(TOKEN_PRICE_CACHE, token_id, price)
        return price

    # USDC
    if USDC_TOKEN_HINT.upper() in token_id.upper():
        set_cached(TOKEN_PRICE_CACHE, token_id, 1.0)
        return 1.0

    # XOXNO quote -> WEGLD -> USD
    amount_in = str(10**18)
    quote = get_json(XOXNO_QUOTE_API, {"from": token_id, "to": WEGLD_TOKEN_ID, "amountIn": amount_in})
    amount_out = None
    if isinstance(quote, dict):
        amount_out = quote.get("amountOut") or quote.get("toAmount")

    price_egld = 0.0
    if amount_out:
        try:
            price_egld = int(str(amount_out)) / (10**18)
        except Exception:
            price_egld = 0.0

    price_usd = price_egld * get_egld_usd_price()
    set_cached(TOKEN_PRICE_CACHE, token_id, price_usd)
    return price_usd


def get_quote_usd_value(quote_token: str, quote_amount: float) -> float:
    if quote_amount <= 0 or not quote_token or quote_token == "?":
        return 0.0
    if USDC_TOKEN_HINT.upper() in quote_token.upper():
        return quote_amount
    return quote_amount * get_token_usd_price(quote_token)


def get_holders_count() -> Optional[int]:
    cached = get_cached(MISC_CACHE, "holders_count", TOKEN_PRICE_CACHE_TTL)
    if cached is not None:
        return safe_int(cached)

    data = get_json(f"{MVX_API}/tokens/{WOODY_TOKEN_ID}")
    if not isinstance(data, dict):
        return None

    try:
        count = int(data["accounts"])
    except Exception:
        count = None

    set_cached(MISC_CACHE, "holders_count", count)
    return count


# =========================================================
# RESERVES / LIQUIDITY
# =========================================================
def get_pool_reserves(pair_address: str) -> Dict[str, float]:
    cache_key = f"reserves::{pair_address}"
    cached = get_cached(POOL_CACHE, cache_key, POOL_CACHE_TTL)
    if cached is not None:
        return cached

    data = get_json(f"{MVX_API}/accounts/{pair_address}/tokens")
    reserves: Dict[str, float] = {}

    if isinstance(data, list):
        for token in data:
            identifier = str(token.get("identifier") or token.get("tokenIdentifier") or "")
            balance = token.get("balance")
            decimals = safe_int(token.get("decimals", 18))
            if identifier:
                reserves[identifier] = normalize_amount(balance, decimals)

    set_cached(POOL_CACHE, cache_key, reserves)
    return reserves


def get_pool_liquidity_egld_for_wegld_pair(pair_address: str) -> Optional[float]:
    reserves = get_pool_reserves(pair_address)
    wegld_amount = reserves.get(WEGLD_TOKEN_ID, 0.0)
    if wegld_amount > 0:
        return wegld_amount * 2
    return None


def get_pool_liquidity_egld_for_other_quote(pair_address: str, quote_token: str) -> Optional[float]:
    reserves = get_pool_reserves(pair_address)
    quote_amount = reserves.get(quote_token, 0.0)
    if quote_amount <= 0:
        return None

    quote_usd = quote_amount * get_token_usd_price(quote_token)
    egld_usd = get_egld_usd_price()
    if quote_usd <= 0 or egld_usd <= 0:
        return None

    quote_side_egld = quote_usd / egld_usd
    return quote_side_egld * 2


def get_total_liquidity_snapshot() -> Tuple[List[str], float, float]:
    egld_usd = get_egld_usd_price()
    total_egld = 0.0
    lines: List[str] = []

    sources = [
        ("WOODY/EGLD xExchange", get_pool_liquidity_egld_for_wegld_pair(XEXCHANGE_POOL_ADDRESS)),
        ("WOODY/EGLD OneDex", get_pool_liquidity_egld_for_wegld_pair(ONEDEX_POOL_ADDRESS)),
        ("WOODY/BOBER", get_pool_liquidity_egld_for_other_quote(WOODY_BOBER_POOL_ADDRESS, BOBER_TOKEN_ID)),
        ("WOODY/JEX", get_pool_liquidity_egld_for_other_quote(WOODY_JEX_POOL_ADDRESS, JEX_TOKEN_ID)),
        ("WOODY/MEX", get_pool_liquidity_egld_for_other_quote(WOODY_MEX_POOL_ADDRESS, MEX_TOKEN_ID)),
    ]

    if WOODY_USDC_POOL_ADDRESS:
        sources.append(("WOODY/USDC", get_pool_liquidity_egld_for_other_quote(WOODY_USDC_POOL_ADDRESS, USDC_TOKEN_HINT)))

    for name, value in sources:
        if value is not None and value > 0:
            total_egld += value
            lines.append(f"• {name}: {value:.3f} EGLD (${value * egld_usd:,.2f})")
        else:
            lines.append(f"• {name}: N/A")

    return lines, total_egld, egld_usd


def get_main_price_egld() -> Optional[float]:
    reserves = get_pool_reserves(XEXCHANGE_POOL_ADDRESS)
    woody = reserves.get(WOODY_TOKEN_ID, 0.0)
    wegld = reserves.get(WEGLD_TOKEN_ID, 0.0)
    if woody > 0:
        return wegld / woody
    return None


def get_main_price_usd() -> Optional[float]:
    price_egld = get_main_price_egld()
    if price_egld is None:
        return None
    return price_egld * get_egld_usd_price()


# =========================================================
# TRANSACTIONS (REAL BUY / SELL)
# =========================================================
def fetch_recent_woody_transactions(size: int = 60) -> List[dict]:
    cached = get_cached(MISC_CACHE, "recent_txs", TX_CACHE_TTL)
    if cached is not None:
        return cached

    params = {
        "status": "success",
        "withOperations": "true",
        "withScResults": "true",
        "token": WOODY_TOKEN_ID,
        "size": size,
    }
    data = get_json(f"{MVX_API}/transactions", params=params)
    txs = data if isinstance(data, list) else []
    set_cached(MISC_CACHE, "recent_txs", txs)
    return txs


def merge_token_items(items: List[Dict[str, Any]]) -> Dict[str, float]:
    merged: Dict[str, float] = {}
    for item in items:
        merged[item["token"]] = merged.get(item["token"], 0.0) + safe_float(item["amount"])
    return merged


def get_sent_received_for_wallet(tx: dict, wallet: str) -> Tuple[Dict[str, float], Dict[str, float]]:
    sent_items: List[Dict[str, Any]] = []
    received_items: List[Dict[str, Any]] = []

    for op in (tx.get("operations") or []):
        token_id = (op.get("identifier") or op.get("tokenIdentifier") or "").strip()
        if not token_id:
            continue

        amount = normalize_amount(op.get("value", "0"), safe_int(op.get("decimals", 18)))
        sender = op.get("sender", "")
        receiver = op.get("receiver", "")

        if sender == wallet:
            sent_items.append({"token": token_id, "amount": amount})
        if receiver == wallet:
            received_items.append({"token": token_id, "amount": amount})

    return merge_token_items(sent_items), merge_token_items(received_items)


def pick_real_wallet_candidates(tx: dict) -> List[str]:
    counts: Dict[str, int] = {}

    for addr in [tx.get("sender", ""), tx.get("receiver", "")]:
        if addr and not is_technical_address(addr):
            counts[addr] = counts.get(addr, 0) + 3

    for op in (tx.get("operations") or []):
        for field in ("sender", "receiver"):
            addr = op.get(field, "")
            if addr and not is_technical_address(addr):
                counts[addr] = counts.get(addr, 0) + 1

    ordered = sorted(counts.items(), key=lambda x: x[1], reverse=True)
    return [addr for addr, _ in ordered]


def get_primary_user_wallet(tx: dict) -> Optional[str]:
    sender = (tx.get("sender") or "").strip()
    receiver = (tx.get("receiver") or "").strip()

    if sender and not is_technical_address(sender):
        return sender
    if receiver and not is_technical_address(receiver):
        return receiver

    candidates = pick_real_wallet_candidates(tx)
    return candidates[0] if candidates else None


def looks_like_lp_token(token_id: str) -> bool:
    token_upper = token_id.upper()
    if "LP" in token_upper:
        return True
    if "WOODY" in token_upper and (
        "WEGLD" in token_upper or "USDC" in token_upper or "BOBER" in token_upper or "JEX" in token_upper or "MEX" in token_upper
    ):
        return True
    return False


def get_global_non_woody_flows(tx: dict) -> Tuple[Dict[str, float], Dict[str, float]]:
    global_sent: Dict[str, float] = {}
    global_received: Dict[str, float] = {}

    for op in (tx.get("operations") or []):
        token_id = (op.get("identifier") or op.get("tokenIdentifier") or "").strip()
        if not token_id or token_id == WOODY_TOKEN_ID or looks_like_lp_token(token_id):
            continue

        amount = normalize_amount(op.get("value", "0"), safe_int(op.get("decimals", 18)))
        sender = op.get("sender", "")
        receiver = op.get("receiver", "")

        if sender and not is_technical_address(sender):
            global_sent[token_id] = global_sent.get(token_id, 0.0) + amount

        if receiver and not is_technical_address(receiver):
            global_received[token_id] = global_received.get(token_id, 0.0) + amount

    return global_sent, global_received


def tx_function_name(tx: dict) -> str:
    fn = str(tx.get("function") or "").lower()
    action_name = str((tx.get("action") or {}).get("name") or "").lower()
    data_field = str(tx.get("data") or "").lower()
    return " | ".join(x for x in [fn, action_name, data_field] if x)


def detect_pair_and_dex(tx: dict, quote_token: str) -> Tuple[str, str]:
    addresses = set()

    for op in (tx.get("operations") or []):
        sender = op.get("sender", "")
        receiver = op.get("receiver", "")
        if sender:
            addresses.add(sender)
        if receiver:
            addresses.add(receiver)

    dex = "Aggregator"
    if XEXCHANGE_POOL_ADDRESS in addresses:
        dex = "xExchange"
    elif ONEDEX_POOL_ADDRESS in addresses:
        dex = "OneDex"
    elif WOODY_USDC_POOL_ADDRESS in addresses:
        dex = "WOODY/USDC"
    elif WOODY_BOBER_POOL_ADDRESS in addresses:
        dex = "WOODY/BOBER"
    elif WOODY_JEX_POOL_ADDRESS in addresses:
        dex = "WOODY/JEX"
    elif WOODY_MEX_POOL_ADDRESS in addresses:
        dex = "WOODY/MEX"

    pair = f"WOODY / {symbol_from_token(quote_token)}"
    return pair, dex


def classify_tx(tx: dict) -> Optional[Dict[str, Any]]:
    primary_wallet = get_primary_user_wallet(tx)
    candidates = pick_real_wallet_candidates(tx)

    if primary_wallet and primary_wallet not in candidates:
        candidates.insert(0, primary_wallet)

    if not candidates:
        return None

    global_sent_non_woody, global_received_non_woody = get_global_non_woody_flows(tx)
    fn_text = tx_function_name(tx)

    best_match = None
    best_score = -1.0

    for wallet in candidates:
        sent, received = get_sent_received_for_wallet(tx, wallet)

        woody_sent = safe_float(sent.get(WOODY_TOKEN_ID, 0.0))
        woody_received = safe_float(received.get(WOODY_TOKEN_ID, 0.0))

        sent_non_woody = {
            k: v for k, v in sent.items()
            if k != WOODY_TOKEN_ID and not looks_like_lp_token(k)
        }
        received_non_woody = {
            k: v for k, v in received.items()
            if k != WOODY_TOKEN_ID and not looks_like_lp_token(k)
        }

        lp_received = any(looks_like_lp_token(token) for token in received.keys())

        tx_type: Optional[str] = None
        woody_amount = 0.0
        quote_token = "?"
        quote_amount = 0.0

        if woody_sent > 0 and sent_non_woody and (
            lp_received or "addliquidity" in fn_text or "multiaddliquidity" in fn_text or "add liquidity" in fn_text
        ):
            tx_type = "LIQUIDITY"
            woody_amount = woody_sent
            quote_token, quote_amount = max(sent_non_woody.items(), key=lambda x: x[1])

        elif woody_received > 0:
            tx_type = "BUY"
            woody_amount = woody_received

            if sent_non_woody:
                quote_token, quote_amount = max(sent_non_woody.items(), key=lambda x: x[1])
            elif global_sent_non_woody:
                quote_token, quote_amount = max(global_sent_non_woody.items(), key=lambda x: x[1])
            else:
                tx_type = None

        elif woody_sent > 0:
            tx_type = "SELL"
            woody_amount = woody_sent

            if received_non_woody:
                quote_token, quote_amount = max(received_non_woody.items(), key=lambda x: x[1])
            elif global_received_non_woody:
                quote_token, quote_amount = max(global_received_non_woody.items(), key=lambda x: x[1])
            else:
                tx_type = None

        if not tx_type or quote_amount <= 0:
            continue

        pair, dex = detect_pair_and_dex(tx, quote_token)
        usd_value = get_quote_usd_value(quote_token, quote_amount)

        score = usd_value + woody_amount + quote_amount
        if tx_type == "LIQUIDITY":
            score += 1000
        elif tx_type == "BUY":
            score += 500
        elif tx_type == "SELL":
            score += 400

        match = {
            "wallet": wallet,
            "type": tx_type,
            "woody_amount": woody_amount,
            "quote_token": quote_token,
            "quote_amount": quote_amount,
            "pair": pair,
            "dex": dex,
            "sent": sent,
            "received": received,
            "swap_usd_value": usd_value,
        }

        if score > best_score:
            best_score = score
            best_match = match

    return best_match


def should_alert(parsed: Dict[str, Any]) -> bool:
    return safe_float(parsed.get("swap_usd_value", 0.0)) >= MIN_ALERT_USD


# =========================================================
# ALERT FORMATTING
# =========================================================
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

    if "LIQUIDITY" in label:
        return "💧 WOODY LIQUIDITY ADDED"
    if "SUPER WHALE BUY" in label:
        return "🟢🐋 WOODY SUPER WHALE BUY"
    if "SUPER WHALE SELL" in label:
        return "🔴🐋 WOODY SUPER WHALE SELL"
    if "WHALE BUY" in label:
        return "🟢🐳 WOODY WHALE BUY"
    if "WHALE SELL" in label:
        return "🔴🐳 WOODY WHALE SELL"
    if "BIG BUY" in label:
        return "🟢 WOODY BIG BUY"
    if "BIG SELL" in label:
        return "🔴 WOODY BIG SELL"
    if label == "BUY":
        return "🟢 WOODY BUY ALERT"
    return "🔴 WOODY SELL ALERT"


def choose_image(parsed: Dict[str, Any]) -> str:
    label = alert_label(parsed)
    tx_type = parsed.get("type", "")

    if tx_type == "LIQUIDITY":
        return LIQUIDITY_IMAGE
    if "SUPER WHALE BUY" in label or "WHALE BUY" in label:
        return WHALE_BUY_IMAGE
    if "SUPER WHALE SELL" in label or "WHALE SELL" in label:
        return WHALE_SELL_IMAGE
    if "BIG BUY" in label:
        return BIG_BUY_IMAGE
    if "BIG SELL" in label:
        return BIG_SELL_IMAGE
    if tx_type == "BUY":
        return BUY_IMAGE
    return SELL_IMAGE


def build_tx_message(tx_hash: str, parsed: Dict[str, Any]) -> str:
    explorer = f"https://explorer.multiversx.com/transactions/{tx_hash}"
    title = choose_title(parsed)
    price_egld = get_main_price_egld()
    price_usd = get_main_price_usd()

    price_line = ""
    if price_egld is not None and price_usd is not None:
        price_line = f"📊 Price: {price_egld:.10f} EGLD (${price_usd:.10f})\n"

    return (
        f"{title}\n\n"
        f"👤 Wallet: {short_wallet(parsed['wallet'])}\n"
        f"🪶 WOODY: {parsed['woody_amount']:,.2f}\n"
        f"💵 Quote: {parsed['quote_amount']:,.6f} {symbol_from_token(parsed['quote_token'])}\n"
        f"💲 Value: ${parsed['swap_usd_value']:,.2f}\n"
        f"💱 Pair: {parsed['pair']}\n"
        f"🏦 DEX: {parsed['dex']}\n"
        f"{price_line}\n"
        f"⬅️ Sent:\n{format_token_map(parsed['sent'])}\n\n"
        f"➡️ Received:\n{format_token_map(parsed['received'])}\n\n"
        f"🔗 Explorer: {explorer}"
    )


# =========================================================
# TELEGRAM UI
# =========================================================
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
            InlineKeyboardButton("🟢 BUY xExchange", url=BUY_XEXCHANGE_URL),
            InlineKeyboardButton("🟢 BUY XOXNO", url=BUY_XOXNO_URL),
        ],
        [
            InlineKeyboardButton("𝕏 Twitter", url=TWITTER_URL),
        ],
    ]
    return InlineKeyboardMarkup(keyboard)


def start_caption() -> str:
    return (
        "🪶 *WOODY Monitor Ultra Pro*\n\n"
        "Live tracker for the WOODY ecosystem.\n\n"
        "Tracks:\n"
        "• Real buy / sell transactions\n"
        "• Liquidity across pools\n"
        "• Holders\n"
        "• Live price\n"
        "• Professional alerts with images\n\n"
        "Choose an option below 👇"
    )


def format_price_text() -> str:
    price_egld = get_main_price_egld()
    price_usd = get_main_price_usd()
    holders = get_holders_count()

    if price_egld is None:
        return "💰 *WOODY Price*\n\nCould not fetch price right now."

    return (
        "💰 *WOODY Price*\n\n"
        f"Price: *{price_egld:.12f} EGLD*\n"
        f"USD: *${(price_usd or 0):.10f}*\n"
        f"Holders: *{holders if holders is not None else 'N/A'}*"
    )


def format_liquidity_text() -> str:
    lines, total, usd = get_total_liquidity_snapshot()
    return (
        "💧 *WOODY Liquidity*\n\n"
        + "\n".join(lines)
        + f"\n\n*TOTAL:* `{total:.3f} EGLD (${total * usd:,.2f})`\n\n"
        + "🔒 *OneDex burn wallet:*\n"
        + f"`{ONEDEX_BURN_ADDRESS}`"
    )


def format_holders_text(count: Optional[int]) -> str:
    if count is None:
        return "👥 *WOODY Holders*\n\nCould not fetch holders right now."
    return f"👥 *WOODY Holders*\n\nCurrent holders: *{count}*"


async def send_start_menu(chat_id: int, context: ContextTypes.DEFAULT_TYPE) -> None:
    keyboard = main_menu_keyboard()
    caption = start_caption()

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


async def send_alert_to_targets(
    context: ContextTypes.DEFAULT_TYPE,
    image_name: str,
    caption: str,
) -> None:
    for target in chat_targets():
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
# COMMANDS / HANDLERS
# =========================================================
async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await send_start_menu(update.effective_chat.id, context)


async def status_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    text = (
        "✅ *WOODY Monitor Ultra Pro is running*\n\n"
        f"Private alerts: *{'YES' if PRIVATE_CHAT_ID else 'NO'}*\n"
        f"Group alerts: *{'YES' if GROUP_CHAT_ID else 'NO'}*\n"
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


async def price_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    keyboard = InlineKeyboardMarkup([[InlineKeyboardButton("📈 Chart", url=CHART_URL)]])
    if update.message:
        await update.message.reply_text(
            format_price_text(),
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=keyboard,
        )


async def liquidity_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if update.message:
        await update.message.reply_text(
            format_liquidity_text(),
            parse_mode=ParseMode.MARKDOWN,
        )


async def holders_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if update.message:
        await update.message.reply_text(
            format_holders_text(get_holders_count()),
            parse_mode=ParseMode.MARKDOWN,
        )


async def testalert_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    caption = "🧪 WOODY TEST ALERT\n\nIf you received this, image alerts work correctly."
    await send_alert_to_targets(context, BUY_IMAGE, caption)
    if update.message:
        await update.message.reply_text("Test alert sent.")


async def menu_callbacks(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    q = update.callback_query
    if not q:
        return

    await q.answer()

    if q.data == "price":
        keyboard = InlineKeyboardMarkup([[InlineKeyboardButton("📈 Chart", url=CHART_URL)]])
        await q.message.reply_text(
            format_price_text(),
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=keyboard,
        )

    elif q.data == "liquidity":
        await q.message.reply_text(
            format_liquidity_text(),
            parse_mode=ParseMode.MARKDOWN,
        )

    elif q.data == "holders":
        await q.message.reply_text(
            format_holders_text(get_holders_count()),
            parse_mode=ParseMode.MARKDOWN,
        )

    elif q.data == "chart":
        keyboard = InlineKeyboardMarkup([[InlineKeyboardButton("📊 Open Chart", url=CHART_URL)]])
        await q.message.reply_text(
            "📈 *WOODY Chart*",
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=keyboard,
        )


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


async def welcome_member(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    cm = update.chat_member
    if cm.old_chat_member.status in ("left", "kicked"):
        await context.bot.send_message(
            update.effective_chat.id,
            WELCOME_NEW_MEMBER_MESSAGES[int(time.time()) % len(WELCOME_NEW_MEMBER_MESSAGES)],
        )


# =========================================================
# JOBS
# =========================================================
async def check_swaps(context: ContextTypes.DEFAULT_TYPE) -> None:
    txs = fetch_recent_woody_transactions(size=60)
    if not txs:
        logger.info("No WOODY tx fetched")
        return

    if not context.application.bot_data.get("swaps_initialized"):
        for tx in txs:
            tx_hash = tx.get("txHash") or tx.get("hash")
            if tx_hash:
                add_seen_tx(tx_hash)
        context.application.bot_data["swaps_initialized"] = True
        logger.info("Initial swap sync completed")
        return

    for tx in reversed(txs):
        tx_hash = tx.get("txHash") or tx.get("hash")
        if not tx_hash or has_seen_tx(tx_hash):
            continue

        add_seen_tx(tx_hash)
        parsed = classify_tx(tx)

        if not parsed:
            logger.info("Could not classify tx %s", tx_hash)
            continue

        logger.info(
            "TX %s -> type=%s woody=%.2f quote=%.6f %s usd=%.2f",
            tx_hash,
            parsed["type"],
            parsed["woody_amount"],
            parsed["quote_amount"],
            parsed["quote_token"],
            parsed["swap_usd_value"],
        )

        if not should_alert(parsed):
            continue

        caption = build_tx_message(tx_hash, parsed)
        await send_alert_to_targets(context, choose_image(parsed), caption)


async def check_holders(context: ContextTypes.DEFAULT_TYPE) -> None:
    global LAST_HOLDERS_COUNT, PENDING_HOLDER_VALUE

    try:
        current_holders = get_holders_count()
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
                await send_alert_to_targets(context, NEW_HOLDER_IMAGE, message)
                LAST_HOLDERS_COUNT = current_holders
                PENDING_HOLDER_VALUE = None
        else:
            PENDING_HOLDER_VALUE = None

    except Exception as exc:
        logger.warning("[holders monitor error] %s", exc)


async def check_liquidity(context: ContextTypes.DEFAULT_TYPE) -> None:
    global LAST_TOTAL_LIQUIDITY_EGLD

    try:
        _, total, usd = get_total_liquidity_snapshot()

        if LAST_TOTAL_LIQUIDITY_EGLD is None:
            LAST_TOTAL_LIQUIDITY_EGLD = total
            return

        diff = total - LAST_TOTAL_LIQUIDITY_EGLD

        if diff > LIQUIDITY_ADDED_MIN_EGLD:
            message = (
                f"💧 WOODY LIQUIDITY ADDED\n\n"
                f"Added: {diff:.3f} EGLD\n"
                f"New total: {total:.3f} EGLD\n"
                f"USD value: ${total * usd:,.2f}"
            )
            await send_alert_to_targets(context, LIQUIDITY_IMAGE, message)

        LAST_TOTAL_LIQUIDITY_EGLD = total

    except Exception as exc:
        logger.warning("[liquidity monitor error] %s", exc)


# =========================================================
# MAIN
# =========================================================
def main() -> None:
    require_token()
    init_seen_cache()

    app = Application.builder().token(TOKEN).build()

    app.add_handler(CommandHandler("start", start_command))
    app.add_handler(CommandHandler("status", status_command))
    app.add_handler(CommandHandler("id", id_command))
    app.add_handler(CommandHandler("price", price_command))
    app.add_handler(CommandHandler("liquidity", liquidity_command))
    app.add_handler(CommandHandler("holders", holders_command))
    app.add_handler(CommandHandler("testalert", testalert_command))

    app.add_handler(CallbackQueryHandler(menu_callbacks))
    app.add_handler(ChatMemberHandler(welcome_member, ChatMemberHandler.CHAT_MEMBER))
    app.add_handler(MessageHandler(filters.TEXT & filters.ChatType.GROUPS, monitor_messages))

    if app.job_queue is None:
        raise RuntimeError("JobQueue missing. Install python-telegram-bot[job-queue].")

    app.job_queue.run_repeating(check_swaps, interval=CHECK_SWAPS_INTERVAL, first=10)
    app.job_queue.run_repeating(check_holders, interval=CHECK_HOLDERS_INTERVAL, first=20)
    app.job_queue.run_repeating(check_liquidity, interval=CHECK_LIQUIDITY_INTERVAL, first=30)

    logger.info("WOODY Monitor Ultra Pro started...")
    app.run_polling(drop_pending_updates=True)


if __name__ == "__main__":
    main()
