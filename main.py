import os
import re
import time
import json
import base64
import logging
from typing import Dict, Optional, Tuple, List, Any, Set

import requests
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
MVX_GATEWAY = os.getenv("MVX_GATEWAY", "https://gateway.multiversx.com").strip()
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

MIN_ALERT_USD = float(os.getenv("MIN_ALERT_USD", "2"))
BIG_ALERT_USD = float(os.getenv("BIG_ALERT_USD", "10"))
WHALE_ALERT_USD = float(os.getenv("WHALE_ALERT_USD", "100"))
SUPER_WHALE_ALERT_USD = float(os.getenv("SUPER_WHALE_ALERT_USD", "500"))

CHECK_SWAPS_INTERVAL = int(os.getenv("CHECK_SWAPS_INTERVAL", "10"))
CHECK_HOLDERS_INTERVAL = int(os.getenv("CHECK_HOLDERS_INTERVAL", "120"))
GREETING_COOLDOWN_SECONDS = int(os.getenv("GREETING_COOLDOWN_SECONDS", "120"))

SEEN_TX_FILE = os.getenv("SEEN_TX_FILE", "seen_swaps.json").strip()
RECENT_PER_POOL = int(os.getenv("RECENT_PER_POOL", "20"))

# =========================================================
# LOGGING
# =========================================================
logging.basicConfig(
    format="%(asctime)s | %(levelname)s | %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger("WOODY_PROMAX_GATEWAY")

# =========================================================
# GLOBALS
# =========================================================
UA = {"User-Agent": "WOODY ProMax Gateway Bot"}

PRICE_CACHE: Dict[str, Tuple[float, float]] = {}
SEEN_TX_CACHE: Set[str] = set()
LAST_HOLDERS_COUNT: Optional[int] = None
PENDING_HOLDER_VALUE: Optional[int] = None

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

WATCHED_POOLS = [
    ("xExchange", XEXCHANGE_POOL_ADDRESS),
    ("OneDex", ONEDEX_POOL_ADDRESS),
    ("WOODY/USDC", WOODY_USDC_POOL_ADDRESS),
    ("WOODY/BOBER", WOODY_BOBER_POOL_ADDRESS),
    ("WOODY/JEX", WOODY_JEX_POOL_ADDRESS),
    ("WOODY/MEX", WOODY_MEX_POOL_ADDRESS),
]

# =========================================================
# BASIC HELPERS
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


def normalize_amount(raw: Any, decimals: Any) -> float:
    try:
        return int(str(raw)) / (10 ** int(decimals))
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
    targets: List[str] = []
    if PRIVATE_CHAT_ID:
        targets.append(PRIVATE_CHAT_ID)
    if GROUP_CHAT_ID:
        targets.append(GROUP_CHAT_ID)
    return targets


def is_technical_address(addr: str) -> bool:
    if not addr:
        return False
    if addr in KNOWN_TECHNICAL_ADDRESSES:
        return True
    if addr.startswith("erd1qqqqqqqqqqqqqpgq"):
        return True
    return False


# =========================================================
# BECH32 FOR MULTIVERSX ADDRESS DECODING
# =========================================================
CHARSET = "qpzry9x8gf2tvdw0s3jn54khce6mua7l"

def bech32_polymod(values):
    generator = [0x3b6a57b2, 0x26508e6d, 0x1ea119fa, 0x3d4233dd, 0x2a1462b3]
    chk = 1
    for value in values:
        b = chk >> 25
        chk = ((chk & 0x1FFFFFF) << 5) ^ value
        for i in range(5):
            chk ^= generator[i] if ((b >> i) & 1) else 0
    return chk

def bech32_hrp_expand(hrp):
    return [ord(x) >> 5 for x in hrp] + [0] + [ord(x) & 31 for x in hrp]

def bech32_create_checksum(hrp, data):
    values = bech32_hrp_expand(hrp) + data
    polymod = bech32_polymod(values + [0, 0, 0, 0, 0, 0]) ^ 1
    return [(polymod >> 5 * (5 - i)) & 31 for i in range(6)]

def bech32_encode(hrp, data):
    combined = data + bech32_create_checksum(hrp, data)
    return hrp + "1" + "".join([CHARSET[d] for d in combined])

def convertbits(data, frombits, tobits, pad=True):
    acc = 0
    bits = 0
    ret = []
    maxv = (1 << tobits) - 1
    for value in data:
        if value < 0 or (value >> frombits):
            return None
        acc = (acc << frombits) | value
        bits += frombits
        while bits >= tobits:
            bits -= tobits
            ret.append((acc >> bits) & maxv)
    if pad:
        if bits:
            ret.append((acc << (tobits - bits)) & maxv)
    elif bits >= frombits or ((acc << (tobits - bits)) & maxv):
        return None
    return ret

def bytes_to_erd_address(raw: bytes) -> Optional[str]:
    if not raw:
        return None
    data5 = convertbits(list(raw), 8, 5, True)
    if data5 is None:
        return None
    return bech32_encode("erd", data5)

# =========================================================
# PRICE / HOLDERS / RESERVES
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

    total_quote_wegld = quote_amount * quote_in_wegld
    p_egld = total_quote_wegld / woody
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
# SWAP DISCOVERY VIA GATEWAY
# =========================================================
def gateway_address_transactions(address: str) -> List[dict]:
    """
    Deprecated endpoint, but used here as a workaround to discover recent tx hashes for watched pools.
    """
    if not address:
        return []

    data = get_json(f"{MVX_GATEWAY}/address/{address}/transactions")
    if isinstance(data, dict):
        txs = ((data.get("data") or {}).get("transactions") or [])
        if isinstance(txs, list):
            return txs[:RECENT_PER_POOL]
    return []


def gateway_transaction_by_hash(tx_hash: str) -> Optional[dict]:
    data = get_json(f"{MVX_GATEWAY}/transaction/{tx_hash}", {"withResults": "true"})
    if not isinstance(data, dict):
        return None
    tx = (data.get("data") or {}).get("transaction")
    return tx if isinstance(tx, dict) else None


def collect_recent_hashes_from_pools() -> List[str]:
    hashes: List[str] = []
    seen_local: Set[str] = set()

    for _, pool_address in WATCHED_POOLS:
        for tx in gateway_address_transactions(pool_address):
            tx_hash = str(tx.get("hash") or "")
            if tx_hash and tx_hash not in seen_local:
                hashes.append(tx_hash)
                seen_local.add(tx_hash)

    return hashes


def get_all_event_sources(tx: dict) -> List[dict]:
    sources: List[dict] = []

    logs = tx.get("logs") or {}
    events = logs.get("events") or []
    if isinstance(events, list):
        sources.extend(events)

    for scr in (tx.get("smartContractResults") or []):
        scr_logs = (scr.get("logs") or {})
        scr_events = scr_logs.get("events") or []
        if isinstance(scr_events, list):
            sources.extend(scr_events)

    for scr in (tx.get("scResults") or []):
        scr_logs = (scr.get("logs") or {})
        scr_events = scr_logs.get("events") or []
        if isinstance(scr_events, list):
            sources.extend(scr_events)

    return sources


def decode_topic_b64_str(topic: Any) -> str:
    try:
        raw = base64.b64decode(topic)
        return raw.decode("utf-8", errors="ignore")
    except Exception:
        return ""


def decode_topic_b64_int(topic: Any) -> int:
    try:
        raw = base64.b64decode(topic)
        if not raw:
            return 0
        return int.from_bytes(raw, byteorder="big", signed=False)
    except Exception:
        return 0


def decode_topic_b64_address(topic: Any) -> Optional[str]:
    try:
        raw = base64.b64decode(topic)
        return bytes_to_erd_address(raw)
    except Exception:
        return None


def parse_data_field_for_outgoing_token(tx: dict) -> Tuple[Optional[str], float]:
    """
    Încearcă să extragă tokenul trimis de wallet din tx.data.
    Funcționează pentru cazurile simple de ESDTTransfer.
    """
    data_field = tx.get("data") or ""
    if not isinstance(data_field, str) or not data_field:
        return None, 0.0

    # format de tip ESDTTransfer@TOKENHEX@AMOUNTHEX@...
    if data_field.startswith("ESDTTransfer@"):
        parts = data_field.split("@")
        if len(parts) >= 3:
            try:
                token_id = bytes.fromhex(parts[1]).decode("utf-8", errors="ignore")
                amount_int = int(parts[2], 16)
                # decimals unknown here -> fallback by token-specific guess later
                return token_id, float(amount_int)
            except Exception:
                return None, 0.0

    return None, 0.0


def token_decimals_from_api(token_id: str) -> int:
    if not token_id:
        return 18
    data = get_json(f"{MVX_API}/tokens/{token_id}")
    if isinstance(data, dict):
        return safe_int(data.get("decimals", 18))
    return 18


def normalize_token_raw(token_id: str, raw_amount: float) -> float:
    decimals = token_decimals_from_api(token_id)
    try:
        return raw_amount / (10 ** decimals)
    except Exception:
        return 0.0


def parse_transfers_for_wallet(tx: dict, wallet: str) -> Tuple[Dict[str, float], Dict[str, float]]:
    """
    Aggregate transfers relevant to wallet:
    - received[token] from logs recipient == wallet
    - sent[token] from tx.data simple ESDTTransfer or EGLD tx.value
    """
    received: Dict[str, float] = {}
    sent: Dict[str, float] = {}

    # native EGLD send
    tx_value = safe_float(tx.get("value", "0"))
    if tx_value > 0:
        sent["EGLD"] = tx_value / (10 ** 18)

    # data-field token send (simple ESDTTransfer)
    sent_token, raw_sent_amount = parse_data_field_for_outgoing_token(tx)
    if sent_token and raw_sent_amount > 0:
        sent[sent_token] = sent.get(sent_token, 0.0) + normalize_token_raw(sent_token, raw_sent_amount)

    # logs / scResults events -> received by wallet
    for event in get_all_event_sources(tx):
        identifier = event.get("identifier") or ""
        topics = event.get("topics") or []

        if identifier not in {"ESDTTransfer", "ESDTNFTTransfer"}:
            continue
        if len(topics) < 4:
            continue

        token_id = decode_topic_b64_str(topics[0])
        amount_int = decode_topic_b64_int(topics[2])
        recipient = decode_topic_b64_address(topics[3])

        if not token_id or amount_int <= 0:
            continue

        amount = normalize_token_raw(token_id, float(amount_int))
        if recipient == wallet:
            received[token_id] = received.get(token_id, 0.0) + amount

    return sent, received


def detect_pair_and_dex_from_tx(tx: dict, quote_token: str) -> Tuple[str, str]:
    addresses = set()

    for field in ("sender", "receiver"):
        v = tx.get(field) or ""
        if v:
            addresses.add(v)

    for scr in (tx.get("smartContractResults") or []):
        for field in ("sender", "receiver"):
            v = scr.get(field) or ""
            if v:
                addresses.add(v)

    for scr in (tx.get("scResults") or []):
        for field in ("sender", "receiver"):
            v = scr.get(field) or ""
            if v:
                addresses.add(v)

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

    return f"WOODY / {symbol(quote_token)}", dex


def classify_tx(tx: dict) -> Optional[Dict[str, Any]]:
    wallet = str(tx.get("sender") or "").strip()
    if not wallet or is_technical_address(wallet):
        return None

    sent, received = parse_transfers_for_wallet(tx, wallet)

    woody_received = safe_float(received.get(WOODY, 0.0))
    woody_sent = safe_float(sent.get(WOODY, 0.0))

    # BUY: wallet primește WOODY, plătește alt token
    if woody_received > 0:
        quote_candidates = {k: v for k, v in sent.items() if k != WOODY and v > 0}
        if not quote_candidates:
            return None
        quote_token, quote_amount = max(quote_candidates.items(), key=lambda x: x[1])

        if quote_token == "EGLD":
            usd_value = quote_amount * egld_usd()
        elif USDC_HINT.upper() in quote_token.upper():
            usd_value = quote_amount
        elif quote_token == WEGLD or symbol(quote_token).upper() == "WEGLD":
            usd_value = quote_amount * egld_usd()
        else:
            usd_value = quote_amount * quote_to_wegld(quote_token) * egld_usd()

        if usd_value < MIN_ALERT_USD:
            return None

        pair, dex = detect_pair_and_dex_from_tx(tx, quote_token)
        return {
            "wallet": wallet,
            "type": "BUY",
            "woody_amount": woody_received,
            "quote_token": quote_token,
            "quote_amount": quote_amount,
            "pair": pair,
            "dex": dex,
            "swap_usd_value": usd_value,
        }

    # SELL: wallet trimite WOODY, primește alt token
    if woody_sent > 0:
        quote_candidates = {k: v for k, v in received.items() if k != WOODY and v > 0}
        if not quote_candidates:
            return None
        quote_token, quote_amount = max(quote_candidates.items(), key=lambda x: x[1])

        if quote_token == "EGLD":
            usd_value = quote_amount * egld_usd()
        elif USDC_HINT.upper() in quote_token.upper():
            usd_value = quote_amount
        elif quote_token == WEGLD or symbol(quote_token).upper() == "WEGLD":
            usd_value = quote_amount * egld_usd()
        else:
            usd_value = quote_amount * quote_to_wegld(quote_token) * egld_usd()

        if usd_value < MIN_ALERT_USD:
            return None

        pair, dex = detect_pair_and_dex_from_tx(tx, quote_token)
        return {
            "wallet": wallet,
            "type": "SELL",
            "woody_amount": woody_sent,
            "quote_token": quote_token,
            "quote_amount": quote_amount,
            "pair": pair,
            "dex": dex,
            "swap_usd_value": usd_value,
        }

    return None


# =========================================================
# ALERTS
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


def build_swap_message(tx_hash: str, parsed: Dict[str, Any]) -> str:
    explorer = f"https://explorer.multiversx.com/transactions/{tx_hash}"
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
        "🪶 *WOODY Monitor ProMax (gateway mode)*\n\n"
        "Tracks:\n"
        "• Price\n"
        "• Liquidity view\n"
        "• Holders\n"
        "• Real BUY / SELL alerts\n"
        "• Wallet short address\n"
        "• Quote token used\n"
        "• DEX detection\n\n"
        "*Automatic liquidity alerts are disabled* to avoid false alerts.\n\n"
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
# COMMANDS
# =========================================================
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await send_start_menu(update.effective_chat.id, context)


async def status(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    text = (
        "✅ *WOODY Monitor ProMax (gateway mode) is running*\n\n"
        f"Private alerts: *{'YES' if PRIVATE_CHAT_ID else 'NO'}*\n"
        f"Group alerts: *{'YES' if GROUP_CHAT_ID else 'NO'}*\n"
        f"Min alert: *${MIN_ALERT_USD}*\n"
        f"BIG alert: *${BIG_ALERT_USD}*\n"
        f"WHALE alert: *${WHALE_ALERT_USD}*\n"
        f"SUPER WHALE alert: *${SUPER_WHALE_ALERT_USD}*\n\n"
        "*Automatic liquidity alerts are OFF* to avoid false alerts."
    )
    if update.message:
        await update.message.reply_text(text, parse_mode=ParseMode.MARKDOWN)


async def get_id(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if update.message:
        await update.message.reply_text(f"Chat ID: {update.effective_chat.id}")


async def price_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if update.message:
        await update.message.reply_text(
            format_price_text(),
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=kb(),
        )


async def liquidity_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if update.message:
        await update.message.reply_text(
            format_liquidity_text(),
            parse_mode=ParseMode.MARKDOWN,
        )


async def holders_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if update.message:
        await update.message.reply_text(
            format_holders_text(holders()),
            parse_mode=ParseMode.MARKDOWN,
        )


async def testalert_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await send_photo_alert(
        context,
        BUY_IMAGE,
        "🧪 WOODY TEST ALERT\n\nIf you received this, alerts work correctly."
    )
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

    await q.message.reply_text(txt, parse_mode=ParseMode.MARKDOWN, reply_markup=kb())


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


# =========================================================
# JOBS
# =========================================================
async def check_swaps(context: ContextTypes.DEFAULT_TYPE) -> None:
    try:
        hashes = collect_recent_hashes_from_pools()
        if not hashes:
            logger.info("No recent tx hashes from pools")
            return

        if not context.application.bot_data.get("swaps_initialized"):
            for h in hashes:
                add_seen_tx(h)
            context.application.bot_data["swaps_initialized"] = True
            logger.info("Initial tx sync completed")
            return

        for tx_hash in reversed(hashes):
            if has_seen_tx(tx_hash):
                continue

            add_seen_tx(tx_hash)
            tx = gateway_transaction_by_hash(tx_hash)
            if not tx:
                continue

            parsed = classify_tx(tx)
            if not parsed:
                continue

            message = build_swap_message(tx_hash, parsed)
            await send_photo_alert(context, choose_image(parsed), message)

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


async def error_handler(update: object, context: ContextTypes.DEFAULT_TYPE) -> None:
    logger.exception("Unhandled exception: %s", context.error)


# =========================================================
# MAIN
# =========================================================
def main() -> None:
    require_token()
    init_seen_cache()

    app = Application.builder().token(TOKEN).build()

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

    app.job_queue.run_repeating(check_swaps, interval=CHECK_SWAPS_INTERVAL, first=10)
    app.job_queue.run_repeating(check_holders, interval=CHECK_HOLDERS_INTERVAL, first=20)

    logger.info("WOODY Monitor ProMax (gateway mode) started...")
    app.run_polling(drop_pending_updates=True)


if __name__ == "__main__":
    main()
