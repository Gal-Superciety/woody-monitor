import json
import logging
import os
import time
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Set, Tuple

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

# =========================================================
# CONFIG
# =========================================================
TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "").strip()
PRIVATE_CHAT_ID = os.getenv("TELEGRAM_PRIVATE_CHAT_ID", "").strip()
GROUP_CHAT_ID = os.getenv("TELEGRAM_GROUP_CHAT_ID", "").strip()

MVX_API = os.getenv("MVX_API", "https://api.multiversx.com").strip()

WOODY_TOKEN_ID = os.getenv("WOODY_TOKEN_ID", "WOODY-5f9d9c").strip()
WEGLD_TOKEN_ID = os.getenv("WEGLD_TOKEN_ID", "WEGLD-bd4d79").strip()
USDC_TOKEN_HINT = os.getenv("USDC_TOKEN_HINT", "USDC").strip()

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

ROUTER_ADDRESSES = {
    x.strip()
    for x in os.getenv("ROUTER_ADDRESSES", "").split(",")
    if x.strip()
}

# Images
BANNER_IMAGE = os.getenv("BANNER_IMAGE", "banner.png").strip()
BUY_IMAGE = os.getenv("BUY_IMAGE", "buy.png").strip()
SELL_IMAGE = os.getenv("SELL_IMAGE", "sell.png").strip()
LIQUIDITY_IMAGE = os.getenv("LIQUIDITY_IMAGE", "liquidity.png").strip()
NEW_HOLDER_IMAGE = os.getenv("NEW_HOLDER_IMAGE", "new_holder.png").strip()
BIG_BUY_IMAGE = os.getenv("BIG_BUY_IMAGE", "big_buy.png").strip()
BIG_SELL_IMAGE = os.getenv("BIG_SELL_IMAGE", "big_sell.png").strip()

# Thresholds
SWAP_MIN_USD = float(os.getenv("SWAP_MIN_USD", "2"))
BIG_ALERT_USD = float(os.getenv("BIG_ALERT_USD", "10"))
WHALE_ALERT_USD = float(os.getenv("WHALE_ALERT_USD", "100"))
SUPER_WHALE_ALERT_USD = float(os.getenv("SUPER_WHALE_ALERT_USD", "500"))

# Timing
CHECK_INTERVAL_SECONDS = int(os.getenv("CHECK_INTERVAL_SECONDS", "8"))
HOLDERS_CHECK_INTERVAL_SECONDS = int(os.getenv("HOLDERS_CHECK_INTERVAL_SECONDS", "180"))
GREETING_COOLDOWN_SECONDS = int(os.getenv("GREETING_COOLDOWN_SECONDS", "120"))
TOKEN_PRICE_CACHE_TTL = int(os.getenv("TOKEN_PRICE_CACHE_TTL", "60"))
POOL_CACHE_TTL = int(os.getenv("POOL_CACHE_TTL", "90"))
HOLDERS_CACHE_TTL = int(os.getenv("HOLDERS_CACHE_TTL", "90"))

# Files
SEEN_TX_FILE = os.getenv("SEEN_TX_FILE", "seen_swaps.json").strip()

# =========================================================
# LOGGING
# =========================================================
logging.basicConfig(
    format="%(asctime)s | %(levelname)s | %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger("WOODY_MONITOR")

# =========================================================
# GLOBALS
# =========================================================
last_known_holders: Optional[int] = None
pending_holder_value: Optional[int] = None
SEEN_TX_CACHE: Set[str] = set()

KNOWN_TECHNICAL_ADDRESSES = {
    XEXCHANGE_POOL_ADDRESS,
    ONEDEX_POOL_ADDRESS,
    WOODY_USDC_POOL_ADDRESS,
    WOODY_BOBER_POOL_ADDRESS,
    WOODY_JEX_POOL_ADDRESS,
    ONEDEX_BURN_ADDRESS,
    *ROUTER_ADDRESSES,
}
KNOWN_TECHNICAL_ADDRESSES = {x for x in KNOWN_TECHNICAL_ADDRESSES if x}

TOKEN_PRICE_CACHE: Dict[str, Dict[str, float]] = {}
POOL_CACHE: Dict[str, Dict[str, Any]] = {}
HOLDERS_CACHE: Dict[str, Any] = {}

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


# =========================================================
# DATA MODELS
# =========================================================
@dataclass
class ParsedTx:
    wallet: str
    tx_type: str
    woody_amount: float
    quote_token: str
    quote_amount: float
    pair: str
    dex: str
    sent: Dict[str, float]
    received: Dict[str, float]
    swap_usd_value: float


# =========================================================
# BASIC HELPERS
# =========================================================
def require_token() -> None:
    if not TOKEN:
        raise ValueError("TELEGRAM_BOT_TOKEN is missing")


def file_exists(path: str) -> bool:
    return bool(path) and os.path.exists(path)


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
        return int(str(raw)) / (10 ** decimals)
    except Exception:
        return safe_float(raw)


def short_wallet(addr: str) -> str:
    if not addr:
        return "unknown"
    if len(addr) < 18:
        return addr
    return f"{addr[:10]}...{addr[-8:]}"


def is_technical_address(addr: str) -> bool:
    if not addr:
        return False
    if addr in KNOWN_TECHNICAL_ADDRESSES:
        return True
    if addr.startswith("erd1qqqqqqqqqqqqqpgq"):
        return True
    return False


def format_compact_number(value: float) -> str:
    if value >= 1_000_000_000:
        return f"{value / 1_000_000_000:.2f}B"
    if value >= 1_000_000:
        return f"{value / 1_000_000:.2f}M"
    if value >= 1_000:
        return f"{value / 1_000:.2f}K"
    return f"{value:.2f}"


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
    temp_path = f"{path}.tmp"
    try:
        with open(temp_path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        os.replace(temp_path, path)
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
        recent = list(SEEN_TX_CACHE)[-5000:]
        save_json_file(SEEN_TX_FILE, recent)


def has_seen_tx(tx_hash: str) -> bool:
    return tx_hash in SEEN_TX_CACHE


def chat_targets() -> List[str]:
    targets = []
    if PRIVATE_CHAT_ID:
        targets.append(PRIVATE_CHAT_ID)
    if GROUP_CHAT_ID:
        targets.append(GROUP_CHAT_ID)
    return targets


# =========================================================
# TOKEN / HOLDERS / POOLS
# =========================================================
def get_woody_token_data() -> Optional[dict]:
    url = f"{MVX_API}/tokens/{WOODY_TOKEN_ID}"
    data = get_json(url)
    if isinstance(data, dict):
        return data
    return None


def get_holders_count() -> Optional[int]:
    now_ts = time.time()
    cached = HOLDERS_CACHE.get("holders")
    if cached and now_ts - cached.get("ts", 0) < HOLDERS_CACHE_TTL:
        return cached.get("value")

    data = get_woody_token_data()
    if not isinstance(data, dict):
        return None

    accounts = data.get("accounts")
    value: Optional[int] = None

    if isinstance(accounts, int):
        value = accounts
    else:
        try:
            value = int(accounts)
        except Exception:
            value = None

    HOLDERS_CACHE["holders"] = {"value": value, "ts": now_ts}
    return value


def get_token_usd_price(token_id: str) -> float:
    if not token_id:
        return 0.0

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


def get_quote_usd_value(quote_token: str, quote_amount: float) -> float:
    if quote_amount <= 0 or not quote_token or quote_token == "?":
        return 0.0

    if USDC_TOKEN_HINT.upper() in quote_token.upper():
        return quote_amount

    price = get_token_usd_price(quote_token)
    if price > 0:
        return quote_amount * price

    return 0.0


def looks_like_lp_token(token_id: str) -> bool:
    token_upper = token_id.upper()
    if "LP" in token_upper:
        return True
    if WOODY_TOKEN_ID.split("-")[0].upper() in token_upper and (
        "WEGLD" in token_upper or "USDC" in token_upper or "JEX" in token_upper or "BOBER" in token_upper
    ):
        return True
    return False


def get_account_tokens(address: str) -> List[dict]:
    if not address:
        return []

    now_ts = time.time()
    cached = POOL_CACHE.get(address)
    if cached and now_ts - cached.get("ts", 0) < POOL_CACHE_TTL:
        return cached.get("tokens", [])

    url = f"{MVX_API}/accounts/{address}/tokens"
    data = get_json(url)
    tokens = data if isinstance(data, list) else []

    POOL_CACHE[address] = {
        "tokens": tokens,
        "ts": now_ts,
    }
    return tokens


def extract_amount_from_token_entry(entry: dict) -> float:
    balance = entry.get("balance")
    decimals = safe_int(entry.get("decimals"))
    if balance is not None and decimals >= 0:
        try:
            return int(str(balance)) / (10 ** decimals)
        except Exception:
            pass

    for key in ("balanceNum", "amount", "supply", "value"):
        if entry.get(key) is not None:
            return safe_float(entry.get(key))

    return 0.0


def find_token_amount(tokens: List[dict], token_hint: str) -> float:
    token_hint_upper = token_hint.upper()
    for entry in tokens:
        identifier = str(entry.get("identifier") or entry.get("tokenIdentifier") or "").upper()
        if token_hint_upper in identifier:
            return extract_amount_from_token_entry(entry)
    return 0.0


def get_pool_snapshot(
    name: str,
    address: str,
    base_token_hint: str,
    quote_token_hint: str,
) -> Dict[str, Any]:
    tokens = get_account_tokens(address)
    base_amount = find_token_amount(tokens, base_token_hint)
    quote_amount = find_token_amount(tokens, quote_token_hint)

    quote_price = 1.0 if quote_token_hint.upper() == USDC_TOKEN_HINT.upper() else get_token_usd_price(quote_token_hint)
    quote_usd_value = quote_amount * quote_price if quote_amount > 0 else 0.0

    # Pentru pool AMM clasic, totalul aproximativ în USD poate fi estimat ca 2 x partea quote
    total_liquidity_usd = quote_usd_value * 2 if quote_usd_value > 0 else 0.0

    return {
        "name": name,
        "address": address,
        "base_amount": base_amount,
        "quote_amount": quote_amount,
        "quote_token": quote_token_hint,
        "quote_usd_value": quote_usd_value,
        "total_liquidity_usd": total_liquidity_usd,
    }


def get_all_pool_snapshots() -> List[Dict[str, Any]]:
    pools = [
        get_pool_snapshot("xExchange WOODY/WEGLD", XEXCHANGE_POOL_ADDRESS, WOODY_TOKEN_ID, WEGLD_TOKEN_ID),
        get_pool_snapshot("OneDex WOODY/WEGLD", ONEDEX_POOL_ADDRESS, WOODY_TOKEN_ID, WEGLD_TOKEN_ID),
        get_pool_snapshot("WOODY/USDC", WOODY_USDC_POOL_ADDRESS, WOODY_TOKEN_ID, USDC_TOKEN_HINT),
    ]

    if WOODY_BOBER_POOL_ADDRESS:
        pools.append(get_pool_snapshot("WOODY/BOBER", WOODY_BOBER_POOL_ADDRESS, WOODY_TOKEN_ID, "BOBER"))
    if WOODY_JEX_POOL_ADDRESS:
        pools.append(get_pool_snapshot("WOODY/JEX", WOODY_JEX_POOL_ADDRESS, WOODY_TOKEN_ID, "JEX"))

    return pools


# =========================================================
# FORMATTING
# =========================================================
def format_price_text() -> str:
    data = get_woody_token_data()
    if not data:
        return "💰 *WOODY Price*\n\nCould not fetch price right now."

    price = 0.0
    for key in ("price", "usdPrice", "priceUsd", "priceUSD"):
        if data.get(key) is not None:
            price = safe_float(data.get(key))
            break

    change_24h = safe_float(
        data.get("priceChange24hPercent")
        or data.get("change24h")
        or data.get("priceChange24h")
    )

    market_cap = safe_float(
        data.get("marketCap")
        or data.get("marketCapUsd")
        or data.get("marketCapUSD")
    )

    supply = safe_float(
        data.get("circulatingSupply")
        or data.get("circulatingSupplyNum")
        or data.get("supply")
    )

    holders = get_holders_count()
    holders_text = str(holders) if holders is not None else "?"

    return (
        "💰 *WOODY Price*\n\n"
        f"Price: *${price:,.10f}*\n"
        f"24h Change: *{change_24h:+.2f}%*\n"
        f"Market Cap: *${market_cap:,.2f}*\n"
        f"Circulating Supply: *{format_compact_number(supply)}*\n"
        f"Holders: *{holders_text}*"
    )


def format_liquidity_text() -> str:
    pools = get_all_pool_snapshots()

    lines = ["💧 *WOODY Liquidity*\n"]
    total_usd = 0.0

    for pool in pools:
        total_usd += safe_float(pool["total_liquidity_usd"])
        lines.append(
            f"*{pool['name']}*\n"
            f"WOODY: `{pool['base_amount']:,.2f}`\n"
            f"{pool['quote_token']}: `{pool['quote_amount']:,.6f}`\n"
            f"Est. Liquidity: `~${pool['total_liquidity_usd']:,.2f}`\n"
        )

    lines.append(f"*Estimated total liquidity:* `~${total_usd:,.2f}`\n")
    lines.append("🔒 *OneDex burn wallet:*")
    lines.append(f"`{ONEDEX_BURN_ADDRESS}`")

    return "\n".join(lines)


def format_holders_text(count: Optional[int]) -> str:
    if count is None:
        return "👥 *WOODY Holders*\n\nCould not fetch holders right now."
    return f"👥 *WOODY Holders*\n\nCurrent holders: *{count}*"


def format_token_map(items: Dict[str, float]) -> str:
    if not items:
        return "-"
    lines = []
    for token, amount in items.items():
        lines.append(f"{amount:,.6f} {token}")
    return "\n".join(lines)


# =========================================================
# FETCH TRANSACTIONS
# =========================================================
def fetch_recent_woody_transactions(size: int = 60) -> List[dict]:
    url = f"{MVX_API}/transactions"
    params = {
        "status": "success",
        "withOperations": "true",
        "withScResults": "true",
        "token": WOODY_TOKEN_ID,
        "size": size,
    }
    data = get_json(url, params=params)
    if isinstance(data, list):
        return data
    return []


# =========================================================
# PARSING HELPERS
# =========================================================
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
    if WOODY_USDC_POOL_ADDRESS in addresses:
        dex = "xExchange / USDC"
    elif XEXCHANGE_POOL_ADDRESS in addresses:
        dex = "xExchange"
    elif ONEDEX_POOL_ADDRESS in addresses:
        dex = "OneDex"
    elif WOODY_BOBER_POOL_ADDRESS in addresses:
        dex = "Other / BOBER"
    elif WOODY_JEX_POOL_ADDRESS in addresses:
        dex = "Other / JEX"

    pair = f"WOODY / {quote_token}"
    return pair, dex


def classify_tx(tx: dict) -> Optional[ParsedTx]:
    primary_wallet = get_primary_user_wallet(tx)
    candidates = pick_real_wallet_candidates(tx)

    if primary_wallet and primary_wallet not in candidates:
        candidates.insert(0, primary_wallet)

    if not candidates:
        return None

    global_sent_non_woody, global_received_non_woody = get_global_non_woody_flows(tx)
    fn_text = tx_function_name(tx)

    best_match: Optional[ParsedTx] = None
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

        # LIQUIDITY
        if woody_sent > 0 and sent_non_woody and (
            lp_received
            or "addliquidity" in fn_text
            or "multiaddliquidity" in fn_text
            or "add liquidity" in fn_text
        ):
            tx_type = "LIQUIDITY"
            woody_amount = woody_sent
            quote_token, quote_amount = max(sent_non_woody.items(), key=lambda x: x[1])

        # BUY
        elif woody_received > 0:
            tx_type = "BUY"
            woody_amount = woody_received

            if sent_non_woody:
                quote_token, quote_amount = max(sent_non_woody.items(), key=lambda x: x[1])
            elif global_sent_non_woody:
                quote_token, quote_amount = max(global_sent_non_woody.items(), key=lambda x: x[1])
            else:
                tx_type = None

        # SELL
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

        match = ParsedTx(
            wallet=wallet,
            tx_type=tx_type,
            woody_amount=woody_amount,
            quote_token=quote_token,
            quote_amount=quote_amount,
            pair=pair,
            dex=dex,
            sent=sent,
            received=received,
            swap_usd_value=usd_value,
        )

        if score > best_score:
            best_score = score
            best_match = match

    return best_match


def should_alert(parsed: ParsedTx) -> bool:
    return safe_float(parsed.swap_usd_value) >= SWAP_MIN_USD


def alert_label(parsed: ParsedTx) -> str:
    usd = safe_float(parsed.swap_usd_value)
    tx_type = parsed.tx_type

    if usd >= SUPER_WHALE_ALERT_USD:
        return f"SUPER WHALE {tx_type}"
    if usd >= WHALE_ALERT_USD:
        return f"WHALE {tx_type}"
    if usd >= BIG_ALERT_USD:
        return f"BIG {tx_type}"
    return tx_type


def choose_title(parsed: ParsedTx) -> str:
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


def choose_image(parsed: ParsedTx) -> str:
    label = alert_label(parsed)

    if parsed.tx_type == "LIQUIDITY":
        return LIQUIDITY_IMAGE
    if "BIG BUY" in label or "WHALE BUY" in label or "SUPER WHALE BUY" in label:
        return BIG_BUY_IMAGE if file_exists(BIG_BUY_IMAGE) else BUY_IMAGE
    if "BIG SELL" in label or "WHALE SELL" in label or "SUPER WHALE SELL" in label:
        return BIG_SELL_IMAGE if file_exists(BIG_SELL_IMAGE) else SELL_IMAGE
    if parsed.tx_type == "BUY":
        return BUY_IMAGE
    return SELL_IMAGE


def build_message(tx_hash: str, parsed: ParsedTx) -> str:
    explorer = f"https://explorer.multiversx.com/transactions/{tx_hash}"
    title = choose_title(parsed)

    return (
        f"{title}\n\n"
        f"👤 Wallet: {short_wallet(parsed.wallet)}\n"
        f"🪶 WOODY: {parsed.woody_amount:,.2f}\n"
        f"💵 Quote: {parsed.quote_amount:,.6f} {parsed.quote_token}\n"
        f"💲 Value: ${parsed.swap_usd_value:,.2f}\n"
        f"💱 Pair: {parsed.pair}\n"
        f"🏦 DEX: {parsed.dex}\n\n"
        f"⬅️ Sent:\n{format_token_map(parsed.sent)}\n\n"
        f"➡️ Received:\n{format_token_map(parsed.received)}\n\n"
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
        "Classic live tracker for the WOODY ecosystem.\n\n"
        "This bot monitors:\n"
        "• Price\n"
        "• Liquidity\n"
        "• Holders\n"
        "• WOODY transactions\n"
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
                await context.bot.send_message(
                    chat_id=target,
                    text=caption,
                    disable_web_page_preview=True,
                )
            logger.info("Alert sent to %s", target)
        except Exception as exc:
            logger.warning("[ALERT ERROR] %s -> %s", target, exc)


# =========================================================
# COMMAND HANDLERS
# =========================================================
async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await send_start_menu(update.effective_chat.id, context)


async def status_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    text = (
        "✅ *WOODY Monitor is running*\n\n"
        "Mode: *Classic token monitor*\n"
        "Tracking: *all WOODY transactions*\n"
        "Filter: *ignore pool / router / technical addresses*\n"
        f"Min swap value: *${SWAP_MIN_USD}*"
    )
    await update.message.reply_text(text, parse_mode=ParseMode.MARKDOWN)


async def testalert_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    caption = (
        "🧪 WOODY TEST ALERT\n\n"
        "If you received this, Telegram sending works correctly."
    )
    await send_alert_to_targets(context, BUY_IMAGE, caption)
    await update.message.reply_text("Test alert sent.")


async def id_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_text(f"Chat ID: {update.effective_chat.id}")


async def price_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("📈 Chart", url=CHART_URL)],
        [InlineKeyboardButton("🟢 Buy xExchange", url=BUY_XEXCHANGE_URL)],
    ])
    await update.message.reply_text(
        format_price_text(),
        parse_mode=ParseMode.MARKDOWN,
        reply_markup=keyboard,
    )


async def liquidity_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_text(
        format_liquidity_text(),
        parse_mode=ParseMode.MARKDOWN,
    )


async def holders_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    holders = get_holders_count()
    await update.message.reply_text(
        format_holders_text(holders),
        parse_mode=ParseMode.MARKDOWN,
    )


async def chart_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    keyboard = InlineKeyboardMarkup([[InlineKeyboardButton("📊 Open Chart", url=CHART_URL)]])
    await update.message.reply_text(
        "📈 *WOODY Chart*",
        parse_mode=ParseMode.MARKDOWN,
        reply_markup=keyboard,
    )


async def menu_callbacks(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()

    if query.data == "price":
        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton("📈 Chart", url=CHART_URL)],
            [InlineKeyboardButton("🟢 Buy xExchange", url=BUY_XEXCHANGE_URL)],
        ])
        await query.message.reply_text(
            format_price_text(),
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
        keyboard = InlineKeyboardMarkup([[InlineKeyboardButton("📊 Open Chart", url=CHART_URL)]])
        await query.message.reply_text(
            "📈 *WOODY Chart*",
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=keyboard,
        )


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


# =========================================================
# JOBS
# =========================================================
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
    txs = fetch_recent_woody_transactions(size=60)
    if not txs:
        logger.info("No WOODY tx fetched")
        return

    logger.info("Fetched %s WOODY transactions", len(txs))

    # Prima pornire: doar marchează că sistemul e inițializat, fără să consume tot istoric-ul.
    if not context.application.bot_data.get("swaps_initialized"):
        context.application.bot_data["swaps_initialized"] = True
        logger.info("Initial sync complete")
        return

    for tx in reversed(txs):
        tx_hash = tx.get("txHash") or tx.get("hash")
        if not tx_hash:
            continue

        if has_seen_tx(tx_hash):
            continue

        add_seen_tx(tx_hash)
        logger.info("NEW TX FOUND: %s", tx_hash)

        parsed = classify_tx(tx)

        if not parsed:
            logger.warning("Could not classify tx %s", tx_hash)
            logger.warning(
                "TX sender=%s receiver=%s function=%s",
                tx.get("sender"),
                tx.get("receiver"),
                tx.get("function"),
            )
            try:
                ops_preview = json.dumps(tx.get("operations", []), ensure_ascii=False)[:3000]
                logger.warning("Operations=%s", ops_preview)
            except Exception:
                pass
            continue

        logger.info(
            "TX %s -> type=%s wallet=%s woody=%.2f quote=%.6f %s usd=%.2f",
            tx_hash,
            parsed.tx_type,
            parsed.wallet,
            parsed.woody_amount,
            parsed.quote_amount,
            parsed.quote_token,
            parsed.swap_usd_value,
        )

        if not should_alert(parsed):
            logger.info(
                "TX %s skipped because value %.4f < %.2f",
                tx_hash,
                parsed.swap_usd_value,
                SWAP_MIN_USD,
            )
            continue

        caption = build_message(tx_hash, parsed)
        image = choose_image(parsed)

        logger.info("Sending alert for tx %s", tx_hash)
        await send_alert_to_targets(context, image, caption)


# =========================================================
# MAIN
# =========================================================
def main() -> None:
    require_token()
    init_seen_cache()

    app = Application.builder().token(TOKEN).build()

    app.add_handler(CommandHandler("start", start_command))
    app.add_handler(CommandHandler("status", status_command))
    app.add_handler(CommandHandler("testalert", testalert_command))
    app.add_handler(CommandHandler("id", id_command))
    app.add_handler(CommandHandler("price", price_command))
    app.add_handler(CommandHandler("liquidity", liquidity_command))
    app.add_handler(CommandHandler("holders", holders_command))
    app.add_handler(CommandHandler("chart", chart_command))

    app.add_handler(CallbackQueryHandler(menu_callbacks))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, greeting_handler))
    app.add_handler(MessageHandler(filters.StatusUpdate.NEW_CHAT_MEMBERS, welcome_new_members))

    if app.job_queue is None:
        raise RuntimeError("JobQueue missing. Install python-telegram-bot[job-queue].")

    app.job_queue.run_repeating(check_swaps, interval=CHECK_INTERVAL_SECONDS, first=10)
    app.job_queue.run_repeating(check_new_holders, interval=HOLDERS_CHECK_INTERVAL_SECONDS, first=20)

    logger.info("WOODY Monitor Bot started...")
    app.run_polling(drop_pending_updates=True)


if __name__ == "__main__":
    main()
