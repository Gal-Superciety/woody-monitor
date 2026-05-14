import os
import time
import random
import logging
import asyncio
import json
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
ADMIN_TELEGRAM_ID = os.getenv("ADMIN_TELEGRAM_ID", "5279028327").strip()

MVX_API = os.getenv("MVX_API", "https://api.multiversx.com").strip()
WS_URL = os.getenv("WS_URL", "https://socket-api-ovh.multiversx.com").strip()
COINGECKO_EGLD_API = os.getenv(
    "COINGECKO_EGLD_API",
    "https://api.coingecko.com/api/v3/simple/price?ids=elrond-erd-2&vs_currencies=usd",
).strip()
BINANCE_EGLD_PRICE_API = os.getenv(
    "BINANCE_EGLD_PRICE_API",
    "https://api.binance.com/api/v3/ticker/price?symbol=EGLDUSDT",
).strip()
COINBASE_EGLD_SPOT_API = os.getenv(
    "COINBASE_EGLD_SPOT_API",
    "https://api.coinbase.com/v2/prices/EGLD-USD/spot",
).strip()

WOODY = os.getenv("WOODY_TOKEN_ID", "WOODY-5f9d9c").strip()
WEGLD = os.getenv("WEGLD_TOKEN_ID", "WEGLD-bd4d79").strip()
USDC_HINT = os.getenv("USDC_TOKEN_HINT", "USDC").strip()
JEX = os.getenv("JEX_TOKEN_ID", "JEX-9040ca").strip()
MEX = os.getenv("MEX_TOKEN_ID", "MEX-455c57").strip()
BOBER = os.getenv("BOBER_TOKEN_ID", "BOBER-9eb764").strip()
ONE = os.getenv("ONE_TOKEN_ID", "").strip()
ROUTER_ADDRESS = os.getenv("ROUTER_ADDRESS", "erd1qqqqqqqqqqqqqpgq5rf2sppxk2xu4m0pkmugw2es4gak3rgjah0sxvajva").strip()

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
BUY_XEXCHANGE_URL = os.getenv(
    "BUY_XEXCHANGE_URL",
    "https://xexchange.com/trade?firstToken=EGLD&secondToken=WOODY-5f9d9c",
).strip()
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
API_TIMEOUT_SECONDS = int(os.getenv("API_TIMEOUT_SECONDS", "10"))
PRICE_TTL_SECONDS = int(os.getenv("PRICE_TTL_SECONDS", "20"))
POOL_SNAPSHOT_TTL_SECONDS = int(os.getenv("POOL_SNAPSHOT_TTL_SECONDS", "20"))
EGLD_PRICE_SOFT_TTL_SECONDS = int(os.getenv("EGLD_PRICE_SOFT_TTL_SECONDS", "60"))
EGLD_PRICE_HARD_TTL_SECONDS = int(os.getenv("EGLD_PRICE_HARD_TTL_SECONDS", "21600"))

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
BEST_PRICE_CACHE: Optional[Tuple[Dict[str, Any], float]] = None
POOL_SNAPSHOT_CACHE: Dict[str, Tuple[Dict[str, Any], float]] = {}
ROOT_PENDING: Dict[str, Dict[str, Any]] = {}
ROOT_PROCESSED: Set[str] = set()
ROOT_IN_PROGRESS: Set[str] = set()
PROCESS_PENDING_LOCK: Optional[asyncio.Lock] = None
WS_CONNECTED = False
WS_STOP_EVENT: Optional[asyncio.Event] = None
WS_TASK: Optional[asyncio.Task] = None
API_OK_COUNT = 0
API_FAIL_COUNT = 0
LAST_API_ERROR = "N/A"
LAST_ALERT_SENT_AT = 0
LAST_TX_PROCESSED = ""
LAST_ROOT_PROCESSED_AT = 0
LAST_WOODY_TX_AT = 0
LAST_EGLD_USD_SOURCE = "N/A"
TX_DETAILS_CACHE: Dict[str, Tuple[Optional[dict], float]] = {}
TX_DETAILS_CACHE_TTL_SECONDS = int(os.getenv("TX_DETAILS_CACHE_TTL_SECONDS", "45"))
ROOT_PROCESSING_CONCURRENCY = max(1, int(os.getenv("ROOT_PROCESSING_CONCURRENCY", "4")))

LAST_HOLDERS_COUNT: Optional[int] = None
PENDING_HOLDER_VALUE: Optional[int] = None

DATA_DIR = os.getenv("DATA_DIR", "data").strip()
LAST_ALERTS_FILE = os.getenv("LAST_ALERTS_FILE", "data/last_alerts.json").strip()
TOP_VOLUME_FILE = os.getenv("TOP_VOLUME_FILE", "data/top_volume.json").strip()
VOLUME_HISTORY_FILE = os.getenv("VOLUME_HISTORY_FILE", "data/volume_history.json").strip()
ROOT_CACHE_FILE = os.getenv("ROOT_CACHE_FILE", "data/root_cache.json").strip()

TOP_VOLUME: Dict[str, Dict[str, float]] = {}
VOLUME_HISTORY: List[Dict[str, float]] = []
LAST_ALERTS: Dict[str, Dict[str, Any]] = {"BUY": {}, "SELL": {}}
LAST_KNOWN_WOODY_USD: float = 0.0

WATCHED_POOLS = {
    XEXCHANGE_POOL_ADDRESS: "xExchange",
    ONEDEX_POOL_ADDRESS: "OneDex",
    WOODY_USDC_POOL_ADDRESS: "WOODY/USDC",
    WOODY_BOBER_POOL_ADDRESS: "WOODY/BOBER",
    WOODY_JEX_POOL_ADDRESS: "WOODY/JEX",
    WOODY_MEX_POOL_ADDRESS: "WOODY/MEX",
}
WATCHED_POOLS = {k: v for k, v in WATCHED_POOLS.items() if k}
POOL_PAIR_HINTS = {
    XEXCHANGE_POOL_ADDRESS: WEGLD,
    ONEDEX_POOL_ADDRESS: WEGLD,
    WOODY_USDC_POOL_ADDRESS: USDC_HINT,
    WOODY_BOBER_POOL_ADDRESS: BOBER,
    WOODY_JEX_POOL_ADDRESS: JEX,
    WOODY_MEX_POOL_ADDRESS: MEX,
}

MARKET_CONTEXT_TOKENS: List[Tuple[str, str]] = [
    ("EGLD", WEGLD),
    ("BOBER", BOBER),
    ("MEX", MEX),
]
if JEX:
    MARKET_CONTEXT_TOKENS.append(("JEX", JEX))
if ONE:
    MARKET_CONTEXT_TOKENS.append(("ONE", ONE))

DEFAULT_TECH_ADDRESSES = {
    XEXCHANGE_POOL_ADDRESS,
    ONEDEX_POOL_ADDRESS,
    WOODY_USDC_POOL_ADDRESS,
    WOODY_BOBER_POOL_ADDRESS,
    WOODY_JEX_POOL_ADDRESS,
    WOODY_MEX_POOL_ADDRESS,
    ONEDEX_BURN_ADDRESS,
    ROUTER_ADDRESS,
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


def data_path(path: str) -> str:
    base_dir = os.path.dirname(os.path.abspath(__file__))
    return os.path.join(base_dir, path)


def ensure_data_dir() -> None:
    os.makedirs(data_path(DATA_DIR), exist_ok=True)


def read_json_file(path: str, default: Any) -> Any:
    try:
        with open(data_path(path), "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return default


def write_json_file(path: str, payload: Any) -> None:
    ensure_data_dir()
    try:
        target = data_path(path)
        tmp = f"{target}.tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(payload, f, indent=2, ensure_ascii=False)
        os.replace(tmp, target)
    except Exception as exc:
        logger.warning("Failed writing json file %s -> %s", path, exc)


def trim_old_volume_entries(hours: int = 24) -> None:
    global VOLUME_HISTORY
    cutoff = time.time() - (hours * 3600)
    VOLUME_HISTORY = [x for x in VOLUME_HISTORY if safe_float(x.get("ts")) >= cutoff]


def save_runtime_state() -> None:
    trim_old_volume_entries(48)
    write_json_file(LAST_ALERTS_FILE, LAST_ALERTS)
    write_json_file(TOP_VOLUME_FILE, TOP_VOLUME)
    write_json_file(VOLUME_HISTORY_FILE, VOLUME_HISTORY)
    # Keep a bounded processed-roots cache to avoid unbounded growth.
    roots = list(ROOT_PROCESSED)[-5000:]
    write_json_file(ROOT_CACHE_FILE, {"roots": roots})


def load_runtime_state() -> None:
    global LAST_ALERTS, TOP_VOLUME, VOLUME_HISTORY
    LAST_ALERTS = read_json_file(LAST_ALERTS_FILE, {"BUY": {}, "SELL": {}})
    TOP_VOLUME = read_json_file(TOP_VOLUME_FILE, {})
    VOLUME_HISTORY = read_json_file(VOLUME_HISTORY_FILE, [])

    cache = read_json_file(ROOT_CACHE_FILE, {"roots": []})
    for root in cache.get("roots", []):
        if isinstance(root, str) and root:
            ROOT_PROCESSED.add(root)




def validate_runtime_config() -> None:
    if not ROUTER_ADDRESS:
        logger.warning("CONFIG WARNING | ROUTER_ADDRESS is empty; routed swap SELL detection may misidentify real wallet and miss quote recovery")

def get_json(url: str, params: Optional[dict] = None) -> Optional[Any]:
    global API_OK_COUNT, API_FAIL_COUNT, LAST_API_ERROR
    try:
        r = requests.get(url, params=params, headers=UA, timeout=API_TIMEOUT_SECONDS)
        r.raise_for_status()
        API_OK_COUNT += 1
        return r.json()
    except Exception as exc:
        API_FAIL_COUNT += 1
        LAST_API_ERROR = f"{type(exc).__name__}: {exc}"
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


def get_tx_details_cached(tx_hash: str, force_refresh: bool = False) -> Optional[dict]:
    if not tx_hash:
        return None
    now = time.time()
    cached = TX_DETAILS_CACHE.get(tx_hash)
    if cached and not force_refresh:
        cached_tx, cached_at = cached
        if now - cached_at <= TX_DETAILS_CACHE_TTL_SECONDS:
            logger.debug("TX CACHE | hit root=%s age=%.1fs", tx_hash, now - cached_at)
            return cached_tx
    tx = get_tx_details(tx_hash)
    TX_DETAILS_CACHE[tx_hash] = (tx, now)
    return tx


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
    global LAST_EGLD_USD_SOURCE
    now = time.time()
    cached = PRICE_CACHE.get("egld_usd")
    if cached and cached[0] > 0 and now - cached[1] < EGLD_PRICE_SOFT_TTL_SECONDS:
        return cached[0]

    fallback_price = safe_float(cached[0]) if cached else 0.0
    fallback_age = now - cached[1] if cached else -1.0

    data = get_json(COINGECKO_EGLD_API)
    try:
        price = safe_float(data["elrond-erd-2"]["usd"])
    except Exception:
        price = 0.0

    if price > 0:
        PRICE_CACHE["egld_usd"] = (price, now)
        LAST_EGLD_USD_SOURCE = "coingecko"
        return price

    for source_name, source_url, parser in (
        ("binance", BINANCE_EGLD_PRICE_API, lambda payload: safe_float(payload.get("price")) if isinstance(payload, dict) else 0.0),
        ("coinbase", COINBASE_EGLD_SPOT_API, lambda payload: safe_float(payload.get("data", {}).get("amount")) if isinstance(payload, dict) else 0.0),
    ):
        payload = get_json(source_url)
        parsed = parser(payload)
        if parsed > 0:
            PRICE_CACHE["egld_usd"] = (parsed, now)
            LAST_EGLD_USD_SOURCE = source_name
            logger.warning(
                "PRICE_FALLBACK_USED | token=EGLD source=%s computed_usd=%.8f reason=coingecko_unavailable",
                source_name,
                parsed,
            )
            return parsed

    if fallback_price > 0 and (fallback_age < 0 or fallback_age <= EGLD_PRICE_HARD_TTL_SECONDS):
        logger.warning(
            "PRICE_FALLBACK_USED | token=EGLD source=last_known computed_usd=%.8f age_sec=%.1f reason=coingecko_unavailable",
            fallback_price,
            max(fallback_age, 0.0),
        )
        LAST_EGLD_USD_SOURCE = "last_known"
        return fallback_price

    return 0.0


def find_token_amount(res_map: Dict[str, float], token_hint: str) -> float:
    if token_hint in res_map:
        return safe_float(res_map[token_hint])

    hint = token_hint.upper()
    for token_id, amount in res_map.items():
        if hint in token_id.upper():
            return safe_float(amount)
    return 0.0


def get_best_price() -> Optional[Dict[str, Any]]:
    global BEST_PRICE_CACHE
    now = time.time()
    if BEST_PRICE_CACHE and now - BEST_PRICE_CACHE[1] < PRICE_TTL_SECONDS:
        return BEST_PRICE_CACHE[0]

    egld_usd = get_egld_usd()

    # xExchange WOODY/WEGLD
    r = reserves(XEXCHANGE_POOL_ADDRESS)
    woody = find_token_amount(r, WOODY)
    wegld = find_token_amount(r, WEGLD)
    if woody > 0 and wegld > 0:
        p_egld = wegld / woody
        best = {
            "price_egld": p_egld,
            "price_usd": p_egld * egld_usd,
            "source": "xExchange WOODY/WEGLD",
            "woody_reserve": woody,
            "quote_symbol": "WEGLD",
            "quote_reserve": wegld,
        }
        BEST_PRICE_CACHE = (best, now)
        return best

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
        best = {
            "price_egld": p_usd / egld_usd if egld_usd > 0 else 0.0,
            "price_usd": p_usd,
            "source": "WOODY/USDC",
            "woody_reserve": woody,
            "quote_symbol": "USDC",
            "quote_reserve": usdc,
        }
        BEST_PRICE_CACHE = (best, now)
        return best

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
    rows: List[Tuple[str, float, str]] = []
    total_usd = 0.0

    for addr, label in WATCHED_POOLS.items():
        snap = get_pool_snapshot(addr, label)
        if not snap.get("ok"):
            reason = str(snap.get("reason", "unavailable"))
            if label == "OneDex" and "WOODY balance" in reason:
                reason = "OneDex pool detected but WOODY balance unavailable from API"
            rows.append((label, 0.0, f"⚠️ {reason}"))
            continue
        pool_value = safe_float(snap.get("pool_value_usd"))
        total_usd += pool_value
        rows.append((label, pool_value, ""))

    dominant_pool = max(rows, key=lambda x: x[1])[0] if rows else "N/A"
    healthy_pools = sum(1 for _, value, reason in rows if value > 0 and not reason)
    health = "Stable" if healthy_pools >= max(1, len(rows) // 2) else "Fragile"
    lines: List[str] = []
    for idx, (label, value, reason) in enumerate(rows, start=1):
        if reason:
            lines.append(f"{idx}. *{label}* → {reason}")
            continue
        share = (value / total_usd * 100) if total_usd > 0 else 0.0
        bar_fill = int(round(share / 10))
        bar = "█" * bar_fill + "░" * (10 - bar_fill)
        lines.append(f"{idx}. *{label}* • `${value:,.2f}`\n   `{bar}` {share:.1f}%")

    return (
        "💧 *WOODY Liquidity Intelligence*\n\n"
        f"Dominant pool: *{dominant_pool}*\n"
        f"Liquidity health: *{health}*\n\n"
        + "\n".join(lines)
        + f"\n\nPool distribution summary • total: `${total_usd:,.2f}`"
    )


def get_price_text() -> str:
    best = get_best_price()
    if not best:
        return "💰 *WOODY Price*\n\nMarket feed temporarily unavailable."
    trades_1h = _recent_trades(1)
    buy_1h = sum(safe_float(x.get("usd")) for x in trades_1h if _entry_side(x) > 0)
    sell_1h = sum(safe_float(x.get("usd")) for x in trades_1h if _entry_side(x) < 0)
    mood = "Neutral"
    trend_icon = "⚪"
    if buy_1h > sell_1h * 1.1:
        mood = "Bullish"
        trend_icon = "🟢"
    elif sell_1h > buy_1h * 1.1:
        mood = "Defensive"
        trend_icon = "🔴"
    change_pct = ((buy_1h - sell_1h) / max(1.0, buy_1h + sell_1h)) * 100
    return (
        "💰 *WOODY Price*\n\n"
        f"Current: *${safe_float(best.get('price_usd')):.10f}*\n"
        f"≈ *{safe_float(best.get('price_egld')):.12f} EGLD*\n\n"
        f"DEX: *{best['source']}*\n"
        f"Trend: *{trend_icon} {mood}*\n"
        f"Flow change (1h): *{change_pct:+.1f}%*\n"
        f"Market mood: *{mood}*"
    )


def _estimate_token_context_price(token_id: str) -> Dict[str, Any]:
    for addr, label in WATCHED_POOLS.items():
        res_map = reserves(addr)
        token_amount = find_token_amount(res_map, token_id)
        if token_amount <= 0:
            continue
        wegld_amount = find_token_amount(res_map, WEGLD)
        if wegld_amount > 0:
            egld_usd = get_egld_usd()
            price_egld = wegld_amount / token_amount
            return {
                "ok": True,
                "price_usd": price_egld * egld_usd,
                "pool": label,
                "pool_status": "active",
            }
        usdc_amount = find_token_amount(res_map, USDC_HINT)
        if usdc_amount > 0:
            return {
                "ok": True,
                "price_usd": usdc_amount / token_amount,
                "pool": label,
                "pool_status": "active",
            }
    return {"ok": False, "pool_status": "no readable pool"}


def build_market_context() -> Dict[str, Any]:
    woody = get_best_price() or {}
    egld_usd = get_egld_usd()
    trades = _recent_trades(24)
    buy_count = sum(1 for x in trades if _entry_side(x) > 0)
    sell_count = sum(1 for x in trades if _entry_side(x) < 0)
    market_mood = "neutral"
    if sell_count > buy_count * 1.25:
        market_mood = "caution"
    elif buy_count > sell_count * 1.15 and egld_usd > 0:
        market_mood = "bullish"

    ecosystem_activity = any(
        symbol(str(x.get("token", ""))).upper() in {"BOBER", "MEX", "JEX", "ONE"}
        for x in trades
    )

    token_context: Dict[str, Dict[str, Any]] = {}
    for label, token_id in MARKET_CONTEXT_TOKENS:
        token_context[label] = _estimate_token_context_price(token_id)

    return {
        "woody_price_usd": safe_float(woody.get("price_usd")),
        "egld_price_usd": egld_usd,
        "tokens": token_context,
        "market_mood": market_mood,
        "ecosystem_activity": ecosystem_activity,
        "volume_24h_usd": sum(safe_float(x.get("usd")) for x in trades),
    }


def get_market_context_text() -> str:
    ctx = build_market_context()
    bober = ctx["tokens"].get("BOBER", {})
    mex = ctx["tokens"].get("MEX", {})
    def fmt_row(name: str, data: Dict[str, Any]) -> str:
        if safe_float(data.get("price_usd")) > 0:
            return f"• {name}: *${safe_float(data.get('price_usd')):.8f}* ({data.get('pool', 'pool n/a')})"
        return f"• {name}: _context unavailable_ ({data.get('pool_status', 'n/a')})"
    return (
        "🌍 *WOODY Ecosystem Context*\n"
        "_AI ecosystem readout · public-safe_\n\n"
        f"• WOODY price: *${ctx['woody_price_usd']:.10f}*\n" if ctx["woody_price_usd"] > 0 else "🌍 *WOODY Ecosystem Context*\n_AI ecosystem readout · public-safe_\n\n• WOODY price: *N/A*\n"
    ) + (
        f"• EGLD price: *${ctx['egld_price_usd']:.4f}*\n"
        f"{fmt_row('BOBER', bober)}\n"
        f"{fmt_row('MEX', mex)}\n"
        f"• EGLD mood: *{ctx['market_mood']}*\n"
        f"• Liquidity stability: *stable-to-moderate*\n"
        f"• Trading activity quality: *{'healthy' if ctx['volume_24h_usd'] > 0 else 'low'}*\n"
        f"• 24h detected volume: *${ctx['volume_24h_usd']:,.2f}*"
    )


def get_token_supply() -> Tuple[float, float]:
    """
    Returns (total_supply, circulating_supply) when available.
    """
    data = get_json(f"{MVX_API}/tokens/{WOODY}")
    if not isinstance(data, dict):
        return 0.0, 0.0
    decimals = safe_int(data.get("decimals", 18), 18)
    total = amount_from_raw(data.get("supply", "0"), decimals)
    circulating = amount_from_raw(data.get("circulatingSupply", "0"), decimals)
    return total, circulating


def get_top_holders_text(limit: int = 10) -> str:
    params = {"size": 200}
    accounts = get_json(f"{MVX_API}/tokens/{WOODY}/accounts", params=params)
    if not isinstance(accounts, list):
        return "🏆 *Top Holders*\n\nI couldn't load holders right now."

    total_supply, circulating_supply = get_token_supply()
    denom = circulating_supply if circulating_supply > 0 else total_supply
    rows: List[Tuple[str, float]] = []
    for item in accounts:
        address = str(item.get("address") or "")
        if not is_real_wallet(address):
            continue
        bal = amount_from_raw(item.get("balance", "0"), item.get("decimals", 18))
        if bal <= 0:
            continue
        rows.append((address, bal))

    rows = sorted(rows, key=lambda x: x[1], reverse=True)[:limit]
    if not rows:
        return "🏆 *Top Holders*\n\nNo eligible holders after applying filters."

    lines = []
    for idx, (address, amount) in enumerate(rows, start=1):
        pct = (amount / denom * 100) if denom > 0 else 0.0
        lines.append(f"{idx}. `{short_wallet(address)}` • {amount:,.0f} WOODY • {pct:.2f}%")

    basis = "circulant" if circulating_supply > 0 else "total"
    return (
        "🏆 *Top Holders (real wallets)*\n"
        "_Filtered: tech/aggregators/pools/burn_\n\n"
        + "\n".join(lines)
        + f"\n\nSupply basis: *{basis}*"
    )


def update_volume_state(parsed: Dict[str, Any]) -> None:
    def resolved_usd_value() -> float:
        global LAST_KNOWN_WOODY_USD
        usd_value = safe_float(parsed.get("swap_usd_value"))
        woody_amount_value = safe_float(parsed.get("woody_amount"))
        quote_token_value = str(parsed.get("quote_token") or "")
        quote_amount_value = safe_float(parsed.get("quote_amount"))
        if usd_value <= 0 and woody_amount_value > 0:
            best = get_best_price()
            if best:
                usd_value = woody_amount_value * safe_float(best.get("price_usd"))
        if usd_value <= 0 and quote_token_value and quote_amount_value > 0:
            usd_value = token_usd_estimate(quote_token_value, quote_amount_value)
        if usd_value <= 0 and woody_amount_value > 0 and LAST_KNOWN_WOODY_USD > 0:
            usd_value = woody_amount_value * LAST_KNOWN_WOODY_USD
        if usd_value > 0 and woody_amount_value > 0:
            LAST_KNOWN_WOODY_USD = usd_value / woody_amount_value
        return usd_value

    wallet = str(parsed.get("wallet") or "")
    usd = resolved_usd_value()
    tx_type = str(parsed.get("type") or "")
    if not wallet:
        return
    if not is_real_wallet(wallet):
        return
    if usd > 0:
        parsed["swap_usd_value"] = usd

    slot = TOP_VOLUME.get(wallet, {"buy_usd": 0.0, "sell_usd": 0.0, "total_usd": 0.0, "tx_count": 0})
    if tx_type == "BUY":
        slot["buy_usd"] = safe_float(slot.get("buy_usd")) + usd
    elif tx_type == "SELL":
        slot["sell_usd"] = safe_float(slot.get("sell_usd")) + usd
    slot["total_usd"] = safe_float(slot.get("total_usd")) + usd
    slot["tx_count"] = safe_float(slot.get("tx_count")) + 1
    TOP_VOLUME[wallet] = slot

    VOLUME_HISTORY.append(
        {
            "ts": time.time(),
            "wallet": wallet,
            "type": 1.0 if tx_type == "BUY" else -1.0,
            "usd": usd,
        }
    )
    trim_old_volume_entries(48)
    save_runtime_state()


def update_last_alert(parsed: Dict[str, Any], message: str) -> None:
    tx_type = str(parsed.get("type") or "")
    if tx_type not in {"BUY", "SELL"}:
        return
    LAST_ALERTS[tx_type] = {
        "wallet": parsed.get("wallet", ""),
        "woody_amount": safe_float(parsed.get("woody_amount")),
        "quote_token": parsed.get("quote_token", ""),
        "quote_amount": safe_float(parsed.get("quote_amount")),
        "swap_usd_value": safe_float(parsed.get("swap_usd_value")),
        "dex": parsed.get("dex", "Unknown"),
        "root_hash": parsed.get("root_hash", ""),
        "time": int(time.time()),
        "message": message,
    }
    save_runtime_state()


def get_last_trade_text(tx_type: str) -> str:
    item = LAST_ALERTS.get(tx_type, {})
    emoji = "🟢" if tx_type == "BUY" else "🔴"
    if not item:
        return f"{emoji} *Last {tx_type.title()}*\n\nNo saved alert yet."
    dt = time.strftime("%Y-%m-%d %H:%M:%S UTC", time.gmtime(safe_int(item.get("time"), 0)))
    return (
        f"{emoji} *Last {tx_type.title()}*\n\n"
        f"👤 {short_wallet(str(item.get('wallet', '')))}\n"
        f"🪶 {safe_float(item.get('woody_amount')):,.2f} WOODY\n"
        f"💲 ${safe_float(item.get('swap_usd_value')):,.2f}\n"
        f"🏦 {item.get('dex', 'Unknown')}\n"
        f"🕒 {dt}\n"
        f"🔗 https://explorer.multiversx.com/transactions/{item.get('root_hash', '')}"
    )


def get_volume_24h_text() -> str:
    trim_old_volume_entries(24)
    def entry_side(entry: Dict[str, Any]) -> int:
        raw_type = entry.get("type")
        if isinstance(raw_type, str):
            upper = raw_type.upper()
            if upper == "BUY":
                return 1
            if upper == "SELL":
                return -1
        numeric_type = safe_float(raw_type)
        if numeric_type > 0:
            return 1
        if numeric_type < 0:
            return -1
        return 0

    total = sum(safe_float(x.get("usd")) for x in VOLUME_HISTORY)
    buys = sum(safe_float(x.get("usd")) for x in VOLUME_HISTORY if entry_side(x) > 0)
    sells = sum(safe_float(x.get("usd")) for x in VOLUME_HISTORY if entry_side(x) < 0)
    buy_trades = sum(1 for x in VOLUME_HISTORY if entry_side(x) > 0)
    sell_trades = sum(1 for x in VOLUME_HISTORY if entry_side(x) < 0)
    return (
        "📊 *24h Volume (estimated)*\n\n"
        f"Total: *${total:,.2f}*\n"
        f"Buy: *${buys:,.2f}*\n"
        f"Sell: *${sells:,.2f}*\n"
        f"Trades: *{len(VOLUME_HISTORY)}* (B {buy_trades} / S {sell_trades})"
    )


def _recent_trades(hours: int = 24) -> List[Dict[str, Any]]:
    cutoff = time.time() - (hours * 3600)
    return [x for x in VOLUME_HISTORY if safe_float(x.get("ts")) >= cutoff]


def _entry_side(entry: Dict[str, Any]) -> int:
    raw_type = entry.get("type")
    if isinstance(raw_type, str):
        upper = raw_type.upper()
        if upper == "BUY":
            return 1
        if upper == "SELL":
            return -1
    numeric_type = safe_float(raw_type)
    return 1 if numeric_type > 0 else (-1 if numeric_type < 0 else 0)


def get_market_summary_text(hours: int = 24) -> str:
    trades = _recent_trades(hours)
    buys = [x for x in trades if _entry_side(x) > 0]
    sells = [x for x in trades if _entry_side(x) < 0]
    total_usd = sum(safe_float(x.get("usd")) for x in trades)
    biggest_buy = max((safe_float(x.get("usd")) for x in buys), default=0.0)
    biggest_sell = max((safe_float(x.get("usd")) for x in sells), default=0.0)
    dex_histogram: Dict[str, int] = {}
    for side in ("BUY", "SELL"):
        dex = str(LAST_ALERTS.get(side, {}).get("dex", "")).strip()
        if dex:
            dex_histogram[dex] = dex_histogram.get(dex, 0) + 1
    dominant_dex = max(dex_histogram.items(), key=lambda x: x[1])[0] if dex_histogram else "Unknown"
    sentiment = "bullish" if len(buys) > len(sells) else ("bearish" if len(sells) > len(buys) else "neutral")
    logger.info("MARKET SUMMARY GENERATED")
    ratio = len(buys) / max(1, len(sells))
    energy = "High" if total_usd > WHALE_ALERT_USD * 8 else ("Medium" if total_usd > BIG_ALERT_USD * 4 else "Low")
    pressure = "Buy pressure" if ratio > 1.15 else ("Sell pressure" if ratio < 0.9 else "Balanced")
    return (
        "📈 *Market Summary*\n\n"
        f"Dominant DEX: *{dominant_dex}*\n"
        f"Volume trend: *${total_usd:,.2f} / {hours}h*\n"
        f"Buy/Sell ratio: *{ratio:.2f}x*\n"
        f"Strongest wallet activity: *BUY ${biggest_buy:,.0f} · SELL ${biggest_sell:,.0f}*\n"
        f"Market direction: *{sentiment.title()}*\n"
        f"Market energy: *{energy}*\n"
        f"Volume pressure: *{pressure}*\n"
        f"Trend state: *{'Expansion' if energy != 'Low' else 'Consolidation'}*"
    )


def get_ai_analysis_text(hours: int = 24) -> str:
    trades = _recent_trades(hours)
    buys = [x for x in trades if _entry_side(x) > 0]
    sells = [x for x in trades if _entry_side(x) < 0]
    buy_volume = sum(safe_float(x.get("usd")) for x in buys)
    sell_volume = sum(safe_float(x.get("usd")) for x in sells)
    whale_buy = max((safe_float(x.get("usd")) for x in buys), default=0.0) >= WHALE_ALERT_USD
    whale_sell = max((safe_float(x.get("usd")) for x in sells), default=0.0) >= WHALE_ALERT_USD
    recent_6h_volume = sum(safe_float(x.get("usd")) for x in _recent_trades(6))
    old_6h_volume = max(0.0, sum(safe_float(x.get("usd")) for x in _recent_trades(12)) - recent_6h_volume)
    bullets: List[str] = []
    if len(buys) > len(sells):
        bullets.append("• bullish pressure")
    elif len(sells) > len(buys):
        bullets.append("• sell pressure")
    else:
        bullets.append("• balanced pressure")
    if whale_buy:
        bullets.append("• accumulation detected")
    if whale_sell:
        bullets.append("• caution")
    if recent_6h_volume > old_6h_volume and recent_6h_volume > 0:
        bullets.append("• increased activity")
    bullets.append(f"• buy volume ${buy_volume:,.2f} vs sell volume ${sell_volume:,.2f}")
    confidence = max(35, min(92, int(55 + (buy_volume - sell_volume) / max(1.0, buy_volume + sell_volume) * 40)))
    outlook = "NEUTRAL-BULLISH" if confidence >= 60 else ("NEUTRAL" if confidence >= 48 else "DEFENSIVE")
    bullets.append(f"• liquidity behavior: {'stable across major pools' if len(WATCHED_POOLS) > 1 else 'limited data'}")
    bullets.append(f"• holders trend: {'stable' if (PENDING_HOLDER_VALUE or 0) >= (LAST_HOLDERS_COUNT or 0) else 'soft decline'}")
    logger.info("AI ANALYSIS GENERATED")
    return "🧠 *WOODY AI Analysis*\n\n" + "\n".join(bullets) + f"\n\nAI Confidence: *{confidence}/100*\nShort-term outlook: *{outlook}*"


def get_risk_radar_text(hours: int = 24) -> str:
    trades = _recent_trades(hours)
    buys = [x for x in trades if _entry_side(x) > 0]
    sells = [x for x in trades if _entry_side(x) < 0]
    buy_volume = sum(safe_float(x.get("usd")) for x in buys)
    sell_volume = sum(safe_float(x.get("usd")) for x in sells)
    total_volume = buy_volume + sell_volume

    whale_sell = max((safe_float(x.get("usd")) for x in sells), default=0.0) >= WHALE_ALERT_USD
    pool_snapshots = [get_pool_snapshot(addr, label) for addr, label in WATCHED_POOLS.items()]
    readable_pools = sum(1 for snap in pool_snapshots if snap.get("ok"))
    missing_readable_pools = readable_pools == 0
    partial_liquidity = 0 < readable_pools < len(pool_snapshots)

    warnings = get_diagnostic_warnings()
    ws_or_api_instability = (not WS_CONNECTED) or any("API" in warning or "timeout" in warning for warning in warnings)

    recent_2h = _recent_trades(2)
    low_recent_activity = len(recent_2h) < 3 or sum(safe_float(x.get("usd")) for x in recent_2h) < BIG_ALERT_USD

    holder_decline = False
    if LAST_HOLDERS_COUNT is not None and PENDING_HOLDER_VALUE is not None:
        holder_decline = PENDING_HOLDER_VALUE < LAST_HOLDERS_COUNT

    detected: List[str] = []
    score = 0

    if sell_volume > buy_volume * 1.15 and total_volume > 0:
        detected.append("increased sell pressure")
        score += 18
    if whale_sell:
        detected.append("whale sell activity detected")
        score += 20
    if partial_liquidity:
        detected.append("partial liquidity visibility")
        score += 14
    if missing_readable_pools:
        detected.append("missing readable pools")
        score += 22
    if ws_or_api_instability:
        detected.append("websocket/API instability")
        score += 16
    if low_recent_activity:
        detected.append("low recent activity")
        score += 10
    if holder_decline:
        detected.append("holder decline signal")
        score += 12

    if score >= 55:
        risk_level = "HIGH"
        suggestion = "Reduce exposure to noise and wait for stronger confirmation."
    elif score >= 28:
        risk_level = "MEDIUM"
        suggestion = "Monitor next market moves carefully."
    else:
        risk_level = "LOW"
        suggestion = "Risk structure is controlled; continue disciplined monitoring."

    detected_lines = "\n".join(f"• {item}" for item in detected) if detected else "• no major risk anomalies detected"
    logger.info("RISK RADAR GENERATED | level=%s score=%s detected=%s", risk_level, score, len(detected))
    return (
        "⚠️ *WOODY AI Risk Radar*\n\n"
        f"Risk Level: *{risk_level}*\n"
        f"Risk Score: *{min(100, score)}/100*\n\n"
        "Detected:\n"
        f"{detected_lines}\n\n"
        "AI Suggestion:\n"
        f"{suggestion}"
    )




def get_accumulation_detection_text(hours: int = 24) -> str:
    trades = _recent_trades(hours)
    buys = [x for x in trades if _entry_side(x) > 0]
    sells = [x for x in trades if _entry_side(x) < 0]

    buy_volume = sum(safe_float(x.get("usd")) for x in buys)
    sell_volume = sum(safe_float(x.get("usd")) for x in sells)
    total_volume = buy_volume + sell_volume

    buy_ratio = buy_volume / max(1.0, total_volume)
    sell_pressure = sell_volume / max(1.0, total_volume)

    small_medium_buy_count = sum(
        1 for x in buys if MIN_ALERT_USD <= safe_float(x.get("usd")) <= WHALE_ALERT_USD
    )
    repeated_buy_activity = len(buys) >= 5 and small_medium_buy_count >= max(3, int(len(buys) * 0.45))

    whale_buy_volume = sum(
        safe_float(x.get("usd")) for x in buys if safe_float(x.get("usd")) >= WHALE_ALERT_USD
    )
    whale_sell_volume = sum(
        safe_float(x.get("usd")) for x in sells if safe_float(x.get("usd")) >= WHALE_ALERT_USD
    )
    whale_accumulation = whale_buy_volume > whale_sell_volume * 1.10 and whale_buy_volume > 0

    top_wallets = [
        (wallet, slot)
        for wallet, slot in TOP_VOLUME.items()
        if is_real_wallet(wallet)
    ]
    top_wallets = sorted(top_wallets, key=lambda x: safe_float(x[1].get("total_usd")), reverse=True)[:8]

    wallet_buyers = 0
    concentration_total = 0.0
    concentration_buy = 0.0
    for _, slot in top_wallets:
        b = safe_float(slot.get("buy_usd"))
        t = safe_float(slot.get("total_usd"))
        if b > safe_float(slot.get("sell_usd")):
            wallet_buyers += 1
        concentration_total += t
        concentration_buy += b

    buyer_concentration_ok = (wallet_buyers >= max(2, len(top_wallets) // 2)) if top_wallets else False
    wallet_concentration_bias = concentration_buy / max(1.0, concentration_total)

    recent_6h = _recent_trades(6)
    older_6h = [x for x in _recent_trades(12) if safe_float(x.get("ts")) < (time.time() - 6 * 3600)]
    recent_6h_buys = sum(1 for x in recent_6h if _entry_side(x) > 0)
    older_6h_buys = sum(1 for x in older_6h if _entry_side(x) > 0)
    activity_consistent = recent_6h_buys >= max(2, int(older_6h_buys * 0.7)) if older_6h else recent_6h_buys >= 2

    holder_growth = 0
    if LAST_HOLDERS_COUNT is not None and PENDING_HOLDER_VALUE is not None:
        holder_growth = PENDING_HOLDER_VALUE - LAST_HOLDERS_COUNT

    pool_snapshots = [get_pool_snapshot(addr, label) for addr, label in WATCHED_POOLS.items()]
    readable_pools = [snap for snap in pool_snapshots if snap.get("ok")]
    stable_liquidity = len(readable_pools) >= max(1, len(pool_snapshots) // 2)

    score = 40
    detected: List[str] = []

    if buy_ratio >= 0.58 and buy_volume > 0:
        score += 14
        detected.append("repeated buy activity" if repeated_buy_activity else "buy flow dominance")
    if repeated_buy_activity:
        score += 10
    if sell_pressure <= 0.40 and total_volume > 0:
        score += 12
        detected.append("low sell pressure")
    if holder_growth > 0:
        score += min(12, holder_growth * 2)
        detected.append("gradual holder growth")
    if whale_accumulation:
        score += 12
        detected.append("whale accumulation")
    if buyer_concentration_ok and wallet_concentration_bias >= 0.52:
        score += 8
        detected.append("wallet concentration favors buys")
    if activity_consistent:
        score += 8
        detected.append("consistent activity cadence")
    if stable_liquidity:
        score += 6
        detected.append("stable liquidity")

    if total_volume < BIG_ALERT_USD:
        score -= 8
    if sell_pressure >= 0.52 and total_volume > 0:
        score -= 16

    score = max(0, min(100, int(score)))

    if score >= 78:
        level = "STRONG"
        interpretation = "Market structure suggests possible smart money accumulation behavior."
    elif score >= 62:
        level = "MODERATE"
        interpretation = "Market structure suggests controlled accumulation behavior."
    elif score >= 46:
        level = "NEUTRAL"
        interpretation = "Signals are mixed; accumulation is present but not decisive."
    else:
        level = "WEAK"
        interpretation = "Accumulation signals are weak or absent right now."

    if not detected:
        detected = ["no clear accumulation edge yet"]

    logger.info("ACCUMULATION DETECTION GENERATED | level=%s confidence=%s detected=%s", level, score, len(detected))
    return (
        "🧠 *WOODY Accumulation Detection*\n\n"
        f"Accumulation Level: *{level}*\n"
        f"Confidence: *{score}/100*\n\n"
        "Detected:\n"
        + "\n".join(f"• {item}" for item in detected[:6])
        + "\n\nAI Interpretation:\n"
        + interpretation
    )
def get_market_pulse_text(hours: int = 24) -> str:
    trades = _recent_trades(hours)
    buys = [x for x in trades if _entry_side(x) > 0]
    sells = [x for x in trades if _entry_side(x) < 0]
    buy_volume = sum(safe_float(x.get("usd")) for x in buys)
    sell_volume = sum(safe_float(x.get("usd")) for x in sells)
    total_volume = buy_volume + sell_volume

    pool_snapshots = [get_pool_snapshot(addr, label) for addr, label in WATCHED_POOLS.items()]
    readable_pools = sum(1 for snap in pool_snapshots if snap.get("ok"))
    whales_buy = max((safe_float(x.get("usd")) for x in buys), default=0.0) >= WHALE_ALERT_USD

    recent_6h = sum(safe_float(x.get("usd")) for x in _recent_trades(6))
    previous_6h = max(0.0, sum(safe_float(x.get("usd")) for x in _recent_trades(12)) - recent_6h)

    score = 50
    reasons: List[str] = []

    if buy_volume > sell_volume * 1.12 and total_volume > 0:
        score += 16
        reasons.append("buy volume exceeds sell volume")
    elif sell_volume > buy_volume * 1.12 and total_volume > 0:
        score -= 16
        reasons.append("sell volume dominates recent flow")
    else:
        reasons.append("buy/sell flow is relatively balanced")

    if readable_pools == len(pool_snapshots) and pool_snapshots:
        score += 10
        reasons.append("liquidity stable across tracked pools")
    elif readable_pools > 0:
        score += 2
        reasons.append("liquidity partially visible")
    else:
        score -= 14
        reasons.append("liquidity visibility is weak")

    if whales_buy:
        score += 8
        reasons.append("whale accumulation detected")

    if recent_6h > previous_6h and recent_6h > 0:
        score += 8
        activity = "Rising"
        reasons.append("recent activity is accelerating")
    elif recent_6h > 0:
        activity = "Stable"
    else:
        score -= 10
        activity = "Low"
        reasons.append("activity is currently low")

    score = max(0, min(100, int(score)))
    mood = "Bullish" if score >= 68 else ("Balanced" if score >= 45 else "Defensive")
    trend_strength = "Strong" if score >= 78 else ("Moderate" if score >= 55 else "Weak")

    logger.info("MARKET PULSE GENERATED | score=%s mood=%s", score, mood)
    return (
        "🧠 *WOODY Market Pulse*\n\n"
        f"Pulse Score: *{score}/100*\n"
        f"Mood: *{mood}*\n"
        f"Trend Strength: *{trend_strength}*\n"
        f"Activity: *{activity}*\n\n"
        "Reasons:\n"
        + "\n".join(f"• {reason}" for reason in reasons[:4])
    )




def get_fake_pump_detection_text(hours: int = 24) -> str:
    trades = _recent_trades(hours)
    buys = [x for x in trades if _entry_side(x) > 0]
    sells = [x for x in trades if _entry_side(x) < 0]

    buy_volume = sum(safe_float(x.get("usd")) for x in buys)
    sell_volume = sum(safe_float(x.get("usd")) for x in sells)
    total_volume = buy_volume + sell_volume

    recent_3h_volume = sum(safe_float(x.get("usd")) for x in _recent_trades(3))
    previous_9h_trades = [x for x in _recent_trades(12) if safe_float(x.get("ts")) < (time.time() - 3 * 3600)]
    previous_9h_volume = sum(safe_float(x.get("usd")) for x in previous_9h_trades)
    volume_spike = recent_3h_volume > max(BIG_ALERT_USD * 1.5, previous_9h_volume * 0.8) and recent_3h_volume > 0

    buy_pressure_ratio = buy_volume / max(1.0, sell_volume)
    aggressive_buy_pressure = buy_pressure_ratio >= 1.8 and buy_volume >= BIG_ALERT_USD

    pool_snapshots = [get_pool_snapshot(addr, label) for addr, label in WATCHED_POOLS.items()]
    readable_pools = [snap for snap in pool_snapshots if snap.get("ok")]
    weak_or_partial_liquidity = len(readable_pools) < len(pool_snapshots) or sum(safe_float(s.get("pool_value_usd")) for s in readable_pools) < BIG_ALERT_USD * 4

    whale_buys = [safe_float(x.get("usd")) for x in buys if safe_float(x.get("usd")) >= WHALE_ALERT_USD]
    whale_sells = [safe_float(x.get("usd")) for x in sells if safe_float(x.get("usd")) >= WHALE_ALERT_USD]
    rapid_whale_rotation = bool(whale_buys and whale_sells and abs(sum(whale_buys) - sum(whale_sells)) <= max(1.0, (sum(whale_buys) + sum(whale_sells)) * 0.35))

    wallet_trade_counts: Dict[str, int] = {}
    for entry in trades:
        wallet = str(entry.get("wallet") or "").strip()
        if wallet and is_real_wallet(wallet):
            wallet_trade_counts[wallet] = wallet_trade_counts.get(wallet, 0) + 1
    repeated_wallet_activity = any(count >= 3 for count in wallet_trade_counts.values())

    abnormal_volatility = False
    if total_volume > 0 and len(trades) >= 6:
        avg_trade = total_volume / max(1, len(trades))
        max_trade = max((safe_float(x.get("usd")) for x in trades), default=0.0)
        abnormal_volatility = max_trade >= avg_trade * 4

    holder_growth: Optional[int] = None
    if LAST_HOLDERS_COUNT is not None and PENDING_HOLDER_VALUE is not None:
        holder_growth = PENDING_HOLDER_VALUE - LAST_HOLDERS_COUNT
    low_holder_growth_high_volume = (
        holder_growth is not None
        and holder_growth <= 1
        and total_volume >= BIG_ALERT_USD * 2
    )

    possible_dump_risk_after_hype = aggressive_buy_pressure and (rapid_whale_rotation or len(sells) >= max(2, len(buys) // 2))

    score = 18
    detected: List[str] = []

    if volume_spike:
        score += 14
        detected.append("sudden volume spike")
    if aggressive_buy_pressure:
        score += 12
        detected.append("aggressive short-term buy pressure")
    if weak_or_partial_liquidity:
        score += 15
        detected.append("weak liquidity depth")
    if rapid_whale_rotation:
        score += 12
        detected.append("rapid whale buy/sell rotation")
    if repeated_wallet_activity:
        score += 10
        detected.append("repeated wallet activity")
    if abnormal_volatility:
        score += 10
        detected.append("abnormal volatility")
    if low_holder_growth_high_volume:
        score += 11
        detected.append("low holder expansion")
    if possible_dump_risk_after_hype:
        score += 16
        detected.append("possible dump risk after hype")

    confidence = max(0, min(100, int(score)))

    if confidence >= 82:
        status = "HIGH DUMP RISK"
        interpretation = "Momentum looks unstable and vulnerable to sharp downside after hype-driven flows."
    elif confidence >= 64:
        status = "POSSIBLE FAKE PUMP"
        interpretation = "Current structure suggests unstable momentum with elevated dump risk."
    elif confidence >= 45:
        status = "SPECULATIVE MOMENTUM"
        interpretation = "Momentum is active but speculative. Confirmation from liquidity and holder growth is still weak."
    else:
        status = "HEALTHY MOMENTUM"
        interpretation = "Momentum appears healthier, with fewer fake-pump characteristics right now."

    if not detected:
        detected = ["no strong fake pump markers detected"]

    logger.info("FAKE PUMP DETECTION GENERATED")
    return (
        "⚠️ *WOODY Fake Pump Detection*\n\n"
        f"Status: *{status}*\n"
        f"Confidence: *{confidence}/100*\n\n"
        "Detected:\n"
        + "\n".join(f"• {item}" for item in detected[:6])
        + "\n\nAI Interpretation:\n"
        + interpretation
    )

def build_ai_recommendation() -> Dict[str, Any]:
    best = get_best_price()
    last_buy = LAST_ALERTS.get("BUY", {})
    last_sell = LAST_ALERTS.get("SELL", {})
    warnings = get_diagnostic_warnings()

    volume_24h = sum(safe_float(x.get("usd")) for x in _recent_trades(24))
    recent_trades = _recent_trades(24)
    buy_usd = sum(safe_float(x.get("usd")) for x in recent_trades if _entry_side(x) > 0)
    sell_usd = sum(safe_float(x.get("usd")) for x in recent_trades if _entry_side(x) < 0)

    top_wallets = [
        (wallet, safe_float(slot.get("total_usd")))
        for wallet, slot in TOP_VOLUME.items()
        if is_real_wallet(wallet)
    ]
    top_wallets.sort(key=lambda x: x[1], reverse=True)
    top_wallets = top_wallets[:3]

    liquidity_snapshots = [get_pool_snapshot(addr, label) for addr, label in WATCHED_POOLS.items()]
    liquidity_ok = sum(1 for s in liquidity_snapshots if s.get("ok"))
    total_liquidity_usd = sum(safe_float(s.get("pool_value_usd")) for s in liquidity_snapshots if s.get("ok"))

    holders_delta = 0
    if LAST_HOLDERS_COUNT is not None and PENDING_HOLDER_VALUE is not None:
        holders_delta = PENDING_HOLDER_VALUE - LAST_HOLDERS_COUNT

    market_ctx = build_market_context()
    score = 50
    if buy_usd > sell_usd * 1.15:
        score += 12
    elif sell_usd > buy_usd * 1.15:
        score -= 12

    if volume_24h >= WHALE_ALERT_USD * 20:
        score += 8
    elif volume_24h < BIG_ALERT_USD * 2:
        score -= 8

    if liquidity_ok == len(liquidity_snapshots) and total_liquidity_usd > 0:
        score += 12
    elif liquidity_ok == 0:
        score -= 20
    else:
        score -= 6

    score += max(-8, min(8, holders_delta * 2))
    score -= min(20, len(warnings) * 5)
    if market_ctx["egld_price_usd"] > 0:
        score += 4 if market_ctx["market_mood"] == "bullish" else 0
        score -= 6 if market_ctx["market_mood"] == "caution" else 0
    if market_ctx["ecosystem_activity"]:
        score += 3
    confidence = max(0, min(100, int(score)))

    if confidence >= 72:
        recommendation = "ACCUMULATE"
        risk = "LOW"
        action = "Volume is rising, consider social update"
        reason = "Buy-side activity and liquidity look constructive."
    elif confidence >= 56:
        recommendation = "HOLD"
        risk = "MEDIUM"
        action = "Liquidity looks stable"
        reason = "Signals are mostly balanced with acceptable market health."
    elif confidence >= 40:
        recommendation = "WATCH"
        risk = "MEDIUM"
        action = "Monitor next 30 minutes"
        reason = "Mixed momentum and incomplete confirmation from recent flows."
    else:
        recommendation = "CAUTION"
        risk = "HIGH"
        action = "Avoid hype announcement now"
        reason = "Risk signals are elevated from sell pressure, warnings, or weak liquidity."

    return {
        "recommendation": recommendation,
        "confidence": confidence,
        "reason": reason,
        "risk": risk,
        "action": action,
        "last_buy_ts": safe_int(last_buy.get("time"), 0),
        "last_sell_ts": safe_int(last_sell.get("time"), 0),
        "volume_24h": volume_24h,
        "top_wallets": top_wallets,
        "liquidity_ok": liquidity_ok,
        "liquidity_total": len(liquidity_snapshots),
        "total_liquidity_usd": total_liquidity_usd,
        "holders_delta": holders_delta,
        "holders_count": LAST_HOLDERS_COUNT,
        "price_usd": safe_float(best.get("price_usd")) if best else 0.0,
        "warnings": warnings,
        "market_mood": market_ctx["market_mood"],
        "ecosystem_activity": market_ctx["ecosystem_activity"],
        "egld_price_usd": market_ctx["egld_price_usd"],
    }


def get_ai_recommendation_text(is_public: bool) -> str:
    rec = build_ai_recommendation()
    top_wallet_line = ", ".join(
        f"{short_wallet(wallet)} (${usd:,.0f})" for wallet, usd in rec["top_wallets"]
    ) or "N/A"
    warning_count = len(rec["warnings"])

    lines = [
        "🧭 *WOODY AI Recommendation*",
        "_Public-safe observation. Not financial advice._",
        "",
        f"Signal: *{rec['recommendation']}*",
        f"Confidence: *{rec['confidence']} / 100*",
        f"Signal strength: *{rec['confidence']}/100*",
        f"Momentum: *{'Building slowly' if rec['confidence'] >= 55 else 'Uncertain'}*",
        f"Volatility: *{'Medium' if rec['risk'] == 'MEDIUM' else rec['risk'].title()}*",
        f"Risk: *{rec['risk'].title()}*",
        f"Reason: _{rec['reason']}_",
        f"Suggested next action: *{rec['action']}*",
        "",
        "📌 *Inputs analyzed*",
        f"• Last BUY: *{_format_ts(rec['last_buy_ts'])}*",
        f"• Last SELL: *{_format_ts(rec['last_sell_ts'])}*",
        f"• 24h volume (est.): *${rec['volume_24h']:,.2f}*",
        f"• Top volume wallets: `{top_wallet_line}`",
        f"• Liquidity status: *{rec['liquidity_ok']}/{rec['liquidity_total']} pools readable*",
        f"• Liquidity estimate: *${rec['total_liquidity_usd']:,.2f}*",
        f"• Holder changes (pending): *{rec['holders_delta']:+d}*",
        f"• Holders count: *{rec['holders_count'] if rec['holders_count'] is not None else 'N/A'}*",
        f"• Current price estimate: *${rec['price_usd']:.10f}*" if rec['price_usd'] > 0 else "• Current price estimate: *N/A*",
        f"• EGLD market context: *${rec['egld_price_usd']:.4f}* / mood *{rec['market_mood']}*" if rec["egld_price_usd"] > 0 else f"• EGLD market context: *{rec['market_mood']}*",
        f"• Ecosystem activity: *{'detected' if rec['ecosystem_activity'] else 'low'}*",
        f"• Diagnostics warnings: *{warning_count}*",
    ]

    if (not is_public) and rec["warnings"]:
        lines.append("\n⚠️ *Warnings detail:*")
        lines.extend([f"• {w}" for w in rec["warnings"]])

    if is_public:
        lines.append("\n🔒 Admin-only internals remain hidden.")

    return "\n".join(lines)
def get_top_volume_text(limit: int = 10) -> str:
    rows: List[Tuple[str, Dict[str, float]]] = []
    for wallet, slot in TOP_VOLUME.items():
        if not is_real_wallet(wallet):
            continue
        rows.append((wallet, slot))
    rows = sorted(rows, key=lambda x: safe_float(x[1].get("total_usd")), reverse=True)[:limit]
    if not rows:
        return "🔥 *Top Volume*\n\nNot enough data yet."
    lines = []
    for idx, (wallet, slot) in enumerate(rows, start=1):
        lines.append(
            f"{idx}. `{short_wallet(wallet)}` • ${safe_float(slot.get('total_usd')):,.2f} "
            f"(B ${safe_float(slot.get('buy_usd')):,.0f} / S ${safe_float(slot.get('sell_usd')):,.0f})"
        )
    return "🔥 *Top Volume (real wallets)*\n_Filtered: tech/aggregators/pools_\n\n" + "\n".join(lines)


def get_wallet_intelligence_text(limit: int = 10) -> str:
    wallets: List[Tuple[str, Dict[str, float]]] = []
    for wallet, slot in TOP_VOLUME.items():
        if not is_real_wallet(wallet):
            continue
        wallets.append((wallet, slot))

    wallets = sorted(wallets, key=lambda x: safe_float(x[1].get("total_usd")), reverse=True)[:limit]
    if not wallets:
        return "🧠 *WOODY Wallet Intelligence*\n\nNot enough wallet activity data yet."

    recent_24h = _recent_trades(24)
    recent_wallet_stats: Dict[str, Dict[str, float]] = {}
    for entry in recent_24h:
        wallet = str(entry.get("wallet") or "")
        if not wallet or not is_real_wallet(wallet):
            continue
        slot = recent_wallet_stats.setdefault(wallet, {"buy": 0.0, "sell": 0.0, "total": 0.0, "tx": 0.0})
        usd = safe_float(entry.get("usd"))
        side = _entry_side(entry)
        if side > 0:
            slot["buy"] += usd
        elif side < 0:
            slot["sell"] += usd
        slot["total"] += usd
        slot["tx"] += 1

    last_buy_wallet = str(LAST_ALERTS.get("BUY", {}).get("wallet") or "")
    last_sell_wallet = str(LAST_ALERTS.get("SELL", {}).get("wallet") or "")

    lines: List[str] = ["🧠 *WOODY Wallet Intelligence*", "_Admin-only wallet behavior readout_", ""]
    for idx, (wallet, totals) in enumerate(wallets, start=1):
        buy_usd = safe_float(totals.get("buy_usd"))
        sell_usd = safe_float(totals.get("sell_usd"))
        total_usd = safe_float(totals.get("total_usd"))
        tx_count = safe_float(totals.get("tx_count"))

        recent = recent_wallet_stats.get(wallet, {"buy": 0.0, "sell": 0.0, "total": 0.0, "tx": 0.0})
        recent_weight = min(15, int(safe_float(recent.get("tx")) * 2))

        if total_usd < MIN_ALERT_USD and tx_count < 2:
            behavior = "New/Low Data"
            score = 45 + recent_weight
            ai_read = "limited history; wait for more confirmations."
        elif buy_usd > sell_usd * 1.35:
            behavior = "Accumulator"
            score = 72 + recent_weight
            ai_read = "wallet shows accumulation behavior."
        elif sell_usd > buy_usd * 1.35:
            behavior = "Seller"
            score = 38 + min(20, int((sell_usd / max(1.0, total_usd)) * 30))
            ai_read = "wallet favors distribution and potential exit pressure."
        else:
            behavior = "Mixed Trader"
            score = 55 + recent_weight
            ai_read = "wallet is active but direction is unclear."

        if wallet == last_buy_wallet:
            score += 4
        if wallet == last_sell_wallet:
            score -= 4

        score = max(0, min(100, int(score)))
        lines.extend([
            f"{idx}. `{short_wallet(wallet)}`",
            f"Type: *{behavior}*",
            f"Score: *{score}/100*",
            f"Volume: *${total_usd:,.2f}*",
            f"Buy/Sell: *${buy_usd:,.2f} / ${sell_usd:,.2f}*",
            f"AI Read: _{ai_read}_",
            "",
        ])

    logger.info("WALLET INTELLIGENCE GENERATED | wallets=%s", len(wallets))
    return "\n".join(lines).strip()


def get_pool_snapshot(pool_address: str, label: str) -> Dict[str, Any]:
    now = time.time()
    cached = POOL_SNAPSHOT_CACHE.get(pool_address)
    if cached and now - cached[1] < POOL_SNAPSHOT_TTL_SECONDS:
        return cached[0]

    data = get_json(f"{MVX_API}/accounts/{pool_address}/tokens")
    if data is None:
        result = {"label": label, "ok": False, "reason": "API unavailable / timeout"}
        POOL_SNAPSHOT_CACHE[pool_address] = (result, now)
        return result
    if not isinstance(data, list):
        result = {"label": label, "ok": False, "reason": "unexpected API response"}
        POOL_SNAPSHOT_CACHE[pool_address] = (result, now)
        return result
    if not data:
        result = {"label": label, "ok": False, "reason": "pool has no readable balances"}
        POOL_SNAPSHOT_CACHE[pool_address] = (result, now)
        return result

    res_map: Dict[str, float] = {}
    for item in data:
        token = str(item.get("identifier") or "")
        if not token:
            continue
        res_map[token] = amount_from_raw(item.get("balance"), item.get("decimals"))

    woody_amount = find_token_amount(res_map, WOODY)
    if woody_amount <= 0:
        result = {"label": label, "ok": False, "reason": "WOODY balance not found in pool"}
        POOL_SNAPSHOT_CACHE[pool_address] = (result, now)
        return result

    pair_token = ""
    pair_amount = 0.0
    pair_hint = POOL_PAIR_HINTS.get(pool_address, "")
    if pair_hint:
        hint_upper = pair_hint.upper()
        for token_id, amount in res_map.items():
            if token_id == WOODY:
                continue
            if hint_upper in token_id.upper():
                pair_token = token_id
                pair_amount = safe_float(amount)
                break
    if not pair_token:
        for token_id, amount in sorted(res_map.items(), key=lambda x: x[1], reverse=True):
            if token_id == WOODY:
                continue
            pair_token, pair_amount = token_id, amount
            break

    if not pair_token:
        result = {"label": label, "ok": False, "reason": "pair token not found"}
        POOL_SNAPSHOT_CACHE[pool_address] = (result, now)
        return result

    best = get_best_price()
    woody_leg_usd = 0.0
    if best:
        woody_leg_usd = woody_amount * safe_float(best.get("price_usd", 0.0))
    pair_leg_usd = token_usd_estimate(pair_token, pair_amount)

    value_candidates = [x for x in [woody_leg_usd * 2, pair_leg_usd * 2] if x > 0]
    pool_value_usd = max(value_candidates) if value_candidates else 0.0

    result = {
        "label": label,
        "ok": True,
        "woody_amount": woody_amount,
        "pair_token": pair_token,
        "pair_symbol": symbol(pair_token),
        "pair_amount": pair_amount,
        "pool_value_usd": pool_value_usd,
        "value_reason": "" if pool_value_usd > 0 else "no trusted USD route for pair token",
    }
    POOL_SNAPSHOT_CACHE[pool_address] = (result, now)
    return result


def get_pools_text(title: str = "📦 *WOODY Pools*") -> str:
    blocks: List[str] = []
    total_usd = 0.0

    for idx, (addr, label) in enumerate(WATCHED_POOLS.items(), start=1):
        snap = get_pool_snapshot(addr, label)
        if not snap.get("ok"):
            blocks.append(f"{idx}. *{label}*\nWOODY pool read error: {snap.get('reason')}")
            continue

        pool_value = safe_float(snap.get("pool_value_usd"))
        total_usd += pool_value
        value_line = f"${pool_value:,.2f}" if pool_value > 0 else f"unavailable ({snap.get('value_reason')})"
        blocks.append(
            f"{idx}. *{label}*\n"
            f"WOODY: {safe_float(snap.get('woody_amount')):,.2f}\n"
            f"{snap.get('pair_symbol', '?')}: {safe_float(snap.get('pair_amount')):,.6f}\n"
            f"Value: {value_line}"
        )

    return (
        f"{title}\n\n"
        + "\n\n".join(blocks)
        + f"\n\n*Total liquidity across all WOODY pools:* `${total_usd:,.2f}`"
    )


def _format_ts(ts: int) -> str:
    if ts <= 0:
        return "N/A"
    return time.strftime("%Y-%m-%d %H:%M:%S UTC", time.gmtime(ts))


def _parse_chat_id(raw: str) -> Tuple[bool, bool]:
    text = str(raw or "").strip()
    if not text:
        return False, False
    if text in {"123456789", "-1001234567890"}:
        return False, True
    try:
        int(text)
        return True, False
    except Exception:
        return False, True


def get_diagnostic_warnings(no_woody_minutes: int = 30) -> List[str]:
    warnings: List[str] = []
    private_ok, private_placeholder = _parse_chat_id(PRIVATE_CHAT_ID)
    group_ok, group_placeholder = _parse_chat_id(GROUP_CHAT_ID)

    if not private_ok:
        warnings.append("TELEGRAM_PRIVATE_CHAT_ID missing or invalid")
    if not group_ok:
        warnings.append("TELEGRAM_GROUP_CHAT_ID missing or invalid")
    if private_placeholder:
        warnings.append("TELEGRAM_PRIVATE_CHAT_ID appears to be a placeholder")
    if group_placeholder:
        warnings.append("TELEGRAM_GROUP_CHAT_ID appears to be a placeholder")
    if ENABLE_PRIVATE_ALERTS and private_ok and (not ENABLE_GROUP_ALERTS or not group_ok):
        warnings.append("Alerts are currently routed only to private chat")
    if not WS_CONNECTED:
        warnings.append("WebSocket is not connected")

    now = int(time.time())
    if LAST_WOODY_TX_AT <= 0 or (now - LAST_WOODY_TX_AT) > (no_woody_minutes * 60):
        warnings.append("Low recent WOODY activity detected")

    for warning in warnings:
        logger.warning("DIAGNOSTIC_WARNING | %s", warning)
    return warnings


def get_ai_status_text(is_public: bool = False) -> str:
    best = get_best_price()
    last_buy = LAST_ALERTS.get("BUY", {})
    last_sell = LAST_ALERTS.get("SELL", {})
    warnings = get_diagnostic_warnings()

    lines = [
        "🧠 *AI Core Status*",
        "",
        f"Core engine: *{'🟢 ONLINE' if WS_TASK and not WS_TASK.done() else '🔴 OFFLINE'}*",
        f"WebSocket health: *{'Healthy' if WS_CONNECTED else 'Degraded'}*",
        f"Subscribed pools: *{len(WATCHED_POOLS)}*",
        f"Pending roots queue: *{len(ROOT_PENDING)}*",
        f"Last processed root: *{_format_ts(LAST_ROOT_PROCESSED_AT)}*",
        f"Last alert time: *{_format_ts(LAST_ALERT_SENT_AT)}*",
        f"Last market activity: *{_format_ts(LAST_WOODY_TX_AT)}*",
        f"Last BUY / SELL: *{_format_ts(safe_int(last_buy.get('time'), 0))}* / *{_format_ts(safe_int(last_sell.get('time'), 0))}*",
        f"Holders count: *{LAST_HOLDERS_COUNT if LAST_HOLDERS_COUNT is not None else 'N/A'}*",
        f"WOODY price estimate: *${safe_float(best.get('price_usd')):.10f}*" if best else "WOODY price estimate: *N/A*",
        f"AI health score: *{max(1, 100 - len(warnings) * 12)}/100*",
        f"Monitoring quality: *{'High' if len(warnings) <= 1 else 'Moderate' if len(warnings) <= 3 else 'Needs attention'}*",
        f"EGLD/USD source: *{LAST_EGLD_USD_SOURCE}*",
    ]

    if warnings:
        lines.append("")
        lines.append("⚠️ *Diagnostics warnings:*")
        lines.extend([f"• {w}" for w in warnings])
    else:
        lines.append("")
        lines.append("✅ No active diagnostic warnings.")

    if is_public:
        lines.append("")
        lines.append("🔒 Public-safe summary (no secrets exposed).")

    return "\n".join(lines)


def get_bot_status_text() -> str:
    return (
        "🤖 *Bot Status*\n\n"
        f"WebSocket: *{'RUNNING' if WS_CONNECTED else 'DISCONNECTED'}*\n"
        f"Roots in queue: *{len(ROOT_PENDING)}*\n"
        f"Roots processed: *{len(ROOT_PROCESSED)}*\n"
        f"Last holders count: *{LAST_HOLDERS_COUNT if LAST_HOLDERS_COUNT is not None else 'N/A'}*\n"
        f"Thresholds: *min ${MIN_ALERT_USD} / big ${BIG_ALERT_USD} / whale ${WHALE_ALERT_USD} / super ${SUPER_WHALE_ALERT_USD}*\n"
        f"Private alerts: *{'ON' if (ENABLE_PRIVATE_ALERTS and PRIVATE_CHAT_ID) else 'OFF'}*\n"
        f"Group alerts: *{'ON' if (ENABLE_GROUP_ALERTS and GROUP_CHAT_ID) else 'OFF'}*"
    )


def get_diagnostics_text() -> str:
    last_alert = (
        time.strftime("%Y-%m-%d %H:%M:%S UTC", time.gmtime(LAST_ALERT_SENT_AT))
        if LAST_ALERT_SENT_AT > 0
        else "N/A"
    )
    return (
        "🧪 *Diagnostics*\n\n"
        f"API OK: *{API_OK_COUNT}*\n"
        f"API FAIL: *{API_FAIL_COUNT}*\n"
        f"Last API error: `{LAST_API_ERROR}`\n"
        f"Last processed tx: `{LAST_TX_PROCESSED or 'N/A'}`\n"
        f"Last alert sent: *{last_alert}*\n"
        f"Pending roots: *{len(ROOT_PENDING)}*"
    )

# =========================================================
# TELEGRAM UI
# =========================================================
def is_admin_user(user_id: Optional[int]) -> bool:
    return bool(user_id is not None and ADMIN_TELEGRAM_ID and str(user_id) == ADMIN_TELEGRAM_ID)


def is_public_menu_context(chat_type: Optional[str], user_id: Optional[int]) -> bool:
    if chat_type in {"group", "supergroup"}:
        return True
    if chat_type == "private":
        return not is_admin_user(user_id)
    return True


def public_menu_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("💰 Price", callback_data="price"),
            InlineKeyboardButton("💧 Liquidity", callback_data="liquidity"),
        ],
        [
            InlineKeyboardButton("👥 Holders", callback_data="holders"),
            InlineKeyboardButton("📊 Chart", url=CHART_URL),
        ],
        [
            InlineKeyboardButton("🟢 Buy xExchange", url=BUY_XEXCHANGE_URL),
            InlineKeyboardButton("🟢 Buy XOXNO", url=BUY_XOXNO_URL),
        ],
        [
            InlineKeyboardButton("𝕏 Twitter", url=TWITTER_URL),
        ],
        [
            InlineKeyboardButton("🧠 AI Core", callback_data="ai_status"),
            InlineKeyboardButton("🧠 AI Analysis", callback_data="ai_analysis"),
            InlineKeyboardButton("🧭 AI Signal", callback_data="ai_recommendation"),
        ],
        [
            InlineKeyboardButton("📈 Summary", callback_data="market_summary"),
            InlineKeyboardButton("🌍 Context", callback_data="market_context"),
        ],
        [
            InlineKeyboardButton("⚠️ Risk Radar", callback_data="risk_radar"),
            InlineKeyboardButton("🧠 Market Pulse", callback_data="market_pulse"),
        ],
    ])


def main_menu_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("💰 Price", callback_data="price"),
            InlineKeyboardButton("💧 Liquidity", callback_data="liquidity"),
        ],
        [
            InlineKeyboardButton("👥 Holders", callback_data="holders"),
            InlineKeyboardButton("🏆 Top Holders", callback_data="top_holders"),
        ],
        [
            InlineKeyboardButton("🟢 Last Buy", callback_data="last_buy"),
            InlineKeyboardButton("🔴 Last Sell", callback_data="last_sell"),
        ],
        [
            InlineKeyboardButton("📊 Volume 24h", callback_data="volume_24h"),
            InlineKeyboardButton("🔥 Top Volume", callback_data="top_volume"),
        ],
        [
            InlineKeyboardButton("📈 Chart", url=CHART_URL),
            InlineKeyboardButton("📦 Pools", callback_data="pools"),
        ],
        [
            InlineKeyboardButton("🟢 Buy xExchange", url=BUY_XEXCHANGE_URL),
            InlineKeyboardButton("🟢 Buy XOXNO", url=BUY_XOXNO_URL),
        ],
        [
            InlineKeyboardButton("🧠 AI Core", callback_data="ai_status"),
            InlineKeyboardButton("🧪 Diagnostics", callback_data="diagnostics"),
            InlineKeyboardButton("🧭 AI Signal", callback_data="ai_recommendation"),
        ],
        [
            InlineKeyboardButton("🧠 Wallet Intel", callback_data="wallet_intelligence"),
            InlineKeyboardButton("🧠 Accumulation", callback_data="accumulation_detection"),
        ],
        [
            InlineKeyboardButton("📈 Summary", callback_data="market_summary"),
            InlineKeyboardButton("🧠 AI Analysis", callback_data="ai_analysis"),
            InlineKeyboardButton("🌍 Context", callback_data="market_context"),
        ],
        [
            InlineKeyboardButton("⚠️ Risk Radar", callback_data="risk_radar"),
            InlineKeyboardButton("🧠 Market Pulse", callback_data="market_pulse"),
        ],
        [
            InlineKeyboardButton("⚠️ Fake Pump", callback_data="fake_pump_detection"),
        ],
        [
            InlineKeyboardButton("𝕏 Twitter", url=TWITTER_URL),
        ],
    ])


def start_caption(is_public: bool) -> str:
    if is_public:
        return (
            "🪶 *WOODY Monitor V2*\n\n"
            "Live monitoring for WOODY:\n"
            "• Price\n"
            "• Liquidity\n"
            "• Holders\n"
            "• Chart & Buy\n\n"
            "Choose an option 👇"
        )
    return (
        "🪶 *WOODY Monitor V2 • Admin Menu*\n\n"
        "Live monitoring for WOODY:\n"
        "• BUY/SELL alerts\n"
        "• Price & Liquidity\n"
        "• Holders & Volume analytics\n"
        "• Pool insights & bot health\n\n"
        "Choose an option 👇"
    )


async def send_start_menu(
    chat_id: int,
    context: ContextTypes.DEFAULT_TYPE,
    chat_type: Optional[str],
    user_id: Optional[int],
) -> None:
    is_public = is_public_menu_context(chat_type, user_id)
    keyboard = public_menu_keyboard() if is_public else main_menu_keyboard()
    logger.info("MENU PUBLIC LOADED" if is_public else "MENU PRIVATE ADMIN LOADED")
    if file_exists(BANNER_IMAGE):
        with open(image_path(BANNER_IMAGE), "rb") as photo:
            await context.bot.send_photo(
                chat_id=chat_id,
                photo=InputFile(photo),
                caption=start_caption(is_public),
                parse_mode=ParseMode.MARKDOWN,
                reply_markup=keyboard,
            )
    else:
        await context.bot.send_message(
            chat_id=chat_id,
            text=start_caption(is_public),
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=keyboard,
        )


async def send_alert_to_targets(
    context: ContextTypes.DEFAULT_TYPE,
    image_name: str,
    caption: str,
) -> None:
    global LAST_ALERT_SENT_AT
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
                        parse_mode=ParseMode.MARKDOWN,
                    )
            else:
                await context.bot.send_message(
                    chat_id=target,
                    text=caption,
                    parse_mode=ParseMode.MARKDOWN,
                    disable_web_page_preview=True,
                )
            logger.info("Alert sent to %s", target)
            LAST_ALERT_SENT_AT = int(time.time())
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


def pick_real_wallet_candidates(tx: dict) -> List[str]:
    counts: Dict[str, int] = {}

    for addr in [tx.get("sender", ""), tx.get("receiver", "")]:
        if is_real_wallet(addr):
            counts[addr] = counts.get(addr, 0) + 3

    for op in tx.get("operations") or []:
        for field in ("sender", "receiver"):
            addr = op.get(field, "")
            if is_real_wallet(addr):
                counts[addr] = counts.get(addr, 0) + 1

    return [addr for addr, _ in sorted(counts.items(), key=lambda x: x[1], reverse=True)]


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


def choose_wallet_by_woody_delta(tx: dict) -> Optional[str]:
    candidates = pick_real_wallet_candidates(tx)
    if not candidates:
        return None

    best_wallet: Optional[str] = None
    best_abs_delta = 0.0
    best_rank = len(candidates) + 1

    for rank, candidate in enumerate(candidates):
        sent, received = get_wallet_flows_aggregated(tx, candidate)
        woody_delta = received.get(WOODY, 0.0) - sent.get(WOODY, 0.0)
        logger.info(
            "TX DEBUG | stage=WALLET_WOODY_DELTA_CANDIDATE wallet=%s woody_delta=%s rank=%s",
            candidate, woody_delta, rank
        )
        if abs(woody_delta) > best_abs_delta or (abs(woody_delta) == best_abs_delta and rank < best_rank):
            best_wallet = candidate
            best_abs_delta = abs(woody_delta)
            best_rank = rank

    if best_wallet and best_abs_delta > 0:
        logger.info(
            "TX DEBUG | stage=WALLET_WOODY_DELTA_SELECTED wallet=%s woody_abs_delta=%s",
            best_wallet, best_abs_delta
        )
        return best_wallet

    fallback = choose_real_wallet(tx)
    logger.info(
        "TX DEBUG | stage=WALLET_WOODY_DELTA_FALLBACK wallet=%s reason=NO_NONZERO_WOODY_DELTA_CANDIDATE",
        fallback
    )
    return fallback


def get_wallet_flows(tx: dict, wallet: str) -> Tuple[Dict[str, float], Dict[str, float]]:
    sent: Dict[str, float] = {}
    received: Dict[str, float] = {}

    def add(token: str, amount: float, from_addr: str, to_addr: str) -> None:
        if not token or amount <= 0:
            return
        if from_addr == wallet:
            sent[token] = sent.get(token, 0.0) + amount
        if to_addr == wallet:
            received[token] = received.get(token, 0.0) + amount

    def as_amount(entry: Dict[str, Any]) -> float:
        if "value" in entry:
            return operation_amount(entry)
        return safe_float(entry.get("amount"))

    def walk(node: Any) -> None:
        if isinstance(node, list):
            for item in node:
                walk(item)
            return
        if not isinstance(node, dict):
            return

        token = str(
            node.get("identifier")
            or node.get("tokenIdentifier")
            or node.get("token")
            or node.get("ticker")
            or ""
        )
        sender = str(node.get("sender") or node.get("from") or node.get("owner") or "")
        receiver = str(node.get("receiver") or node.get("to") or node.get("destination") or "")
        amount = as_amount(node)
        if token and amount > 0 and (sender == wallet or receiver == wallet):
            add(token, amount, sender, receiver)

        transfer_like_keys = {
            "operations", "transfers", "results", "events", "logs", "innerResults",
            "innerTransactions", "scResults", "smartContractResults", "tokens", "payment", "payments", "arguments",
        }
        for key, value in node.items():
            if isinstance(value, (dict, list)):
                if key in transfer_like_keys or isinstance(value, list):
                    walk(value)

    top_sender = str(tx.get("sender") or "")
    top_receiver = str(tx.get("receiver") or "")
    top_value = amount_from_raw(tx.get("value", "0"), 18)
    if top_value > 0 and (top_sender == wallet or top_receiver == wallet):
        add("EGLD", top_value, top_sender, top_receiver)

    walk(tx)

    return sent, received


def tx_contains_token(tx: dict, token_id: str) -> bool:
    needle = str(token_id or "").strip().lower()
    if not needle:
        return False

    def has_text(value: Any) -> bool:
        return needle in str(value or "").lower()
    logged_flags = {
        "scr": False,
        "op": False,
        "inner": False,
    }

    def log_context(path: str, key: str, value: Any) -> None:
        path_low = path.lower()
        if ("smartcontractresults" in path_low or "scresults" in path_low or "results" in path_low) and not logged_flags["scr"]:
            logged_flags["scr"] = True
            logger.info("TX DEBUG | stage=WOODY_FOUND_IN_SCR path=%s key=%s value=%s", path, key, value)
        if "operations" in path_low and not logged_flags["op"]:
            logged_flags["op"] = True
            logger.info("TX DEBUG | stage=WOODY_FOUND_IN_OPERATION path=%s key=%s value=%s", path, key, value)
        if ("innerresults" in path_low or "innertransactions" in path_low or "innertransfers" in path_low) and not logged_flags["inner"]:
            logged_flags["inner"] = True
            logger.info("TX DEBUG | stage=WOODY_FOUND_IN_INNER_TRANSFER path=%s key=%s value=%s", path, key, value)

    def walk(node: Any, path: str = "tx") -> bool:
        if isinstance(node, dict):
            for key, value in node.items():
                current_path = f"{path}.{key}"
                if isinstance(value, (dict, list)):
                    if walk(value, current_path):
                        return True
                    continue
                if has_text(value):
                    log_context(path, key, value)
                    return True
            return False
        if isinstance(node, list):
            for idx, item in enumerate(node):
                if walk(item, f"{path}[{idx}]"):
                    return True
            return False
        if has_text(node):
            log_context(path, "value", node)
            return True
        return False

    return walk(tx)




def _hex_to_text(value: str) -> str:
    raw = str(value or "").strip()
    if not raw:
        return ""
    if raw.startswith("0x"):
        raw = raw[2:]
    if len(raw) % 2 == 1:
        raw = "0" + raw
    try:
        return bytes.fromhex(raw).decode("utf-8", errors="ignore")
    except Exception:
        return ""


def _hex_to_int(value: str) -> int:
    raw = str(value or "").strip()
    if raw.startswith("0x"):
        raw = raw[2:]
    try:
        return int(raw, 16)
    except Exception:
        return 0


def extract_scr_transfers(tx: dict) -> List[Dict[str, Any]]:
    out: List[Dict[str, Any]] = []
    containers = []
    for key in ("results", "smartContractResults", "scResults"):
        val = tx.get(key)
        if isinstance(val, list):
            containers.extend(val)

    def add_transfer(token: str, amount_raw: int, sender: str, receiver: str) -> None:
        if not token or amount_raw <= 0:
            return
        decimals = 18
        t_up = symbol(token).upper()
        if "USDC" in token.upper() or t_up == "USDC":
            decimals = 6
        amount = amount_raw / (10 ** decimals)
        out.append({"token": token, "amount": amount, "sender": sender, "receiver": receiver})
        logger.info("TX DEBUG | stage=SCR_TRANSFER_DECODED token=%s amount=%s sender=%s receiver=%s", token, amount, sender, receiver)

    for scr in containers:
        if not isinstance(scr, dict):
            continue
        sender = str(scr.get("sender") or scr.get("from") or "")
        receiver = str(scr.get("receiver") or scr.get("to") or "")
        data = str(scr.get("data") or "")
        parts = data.split("@") if data else []
        if not parts:
            continue
        fn = parts[0]
        if fn in {"ESDTTransfer", "MultiESDTNFTTransfer"}:
            decoded = [_hex_to_text(x) for x in parts[1:]]
            # try direct token/amount pairs from args
            for i, text in enumerate(decoded):
                if "-" in text and len(text) >= 4:
                    token = text
                    amount_raw = _hex_to_int(parts[i + 2]) if i + 2 < len(parts) else 0
                    add_transfer(token, amount_raw, sender, receiver)

    return out


def get_scr_flows(tx: dict, wallet: str) -> Tuple[Dict[str, float], Dict[str, float]]:
    """Extract token flows for *wallet* from Smart Contract Results (SCR) operations.

    xExchange and OneDex routed swaps often return the quote token to the user
    via an SCR's nested ``operations`` list rather than in the main transaction
    operations.  This function iterates every SCR entry and processes its
    ``operations`` sub-array the same way ``get_wallet_flows`` processes the
    top-level operations, so those quote-token transfers are not missed.
    """
    sent: Dict[str, float] = {}
    received: Dict[str, float] = {}

    containers: List[dict] = []
    for key in ("results", "smartContractResults", "scResults"):
        val = tx.get(key)
        if isinstance(val, list):
            containers.extend(val)

    for scr in containers:
        if not isinstance(scr, dict):
            continue

        # Process the SCR's own operations sub-list
        for op in scr.get("operations") or []:
            if not isinstance(op, dict):
                continue
            token = str(
                op.get("identifier")
                or op.get("tokenIdentifier")
                or op.get("token")
                or op.get("ticker")
                or ""
            )
            if not token:
                continue
            op_sender = str(op.get("sender") or op.get("from") or "")
            op_receiver = str(op.get("receiver") or op.get("to") or "")
            amount = operation_amount(op) if "value" in op else safe_float(op.get("amount"))
            if amount <= 0:
                continue
            if op_sender == wallet:
                sent[token] = sent.get(token, 0.0) + amount
                logger.info(
                    "TX DEBUG | stage=SCR_OP_FLOW direction=SENT token=%s amount=%s wallet=%s op_sender=%s op_receiver=%s",
                    token, amount, wallet, op_sender, op_receiver,
                )
            if op_receiver == wallet:
                received[token] = received.get(token, 0.0) + amount
                logger.info(
                    "TX DEBUG | stage=SCR_OP_FLOW direction=RECEIVED token=%s amount=%s wallet=%s op_sender=%s op_receiver=%s",
                    token, amount, wallet, op_sender, op_receiver,
                )

    return sent, received


def get_wallet_flows_aggregated(tx: dict, wallet: str) -> Tuple[Dict[str, float], Dict[str, float]]:
    """Aggregate wallet flows across operations, SCR operations, and decoded SCR transfers."""
    sent, received = get_wallet_flows(tx, wallet)
    scr_sent, scr_received = get_scr_flows(tx, wallet)

    for token, amount in scr_sent.items():
        sent[token] = sent.get(token, 0.0) + amount
    for token, amount in scr_received.items():
        received[token] = received.get(token, 0.0) + amount

    for tr in extract_scr_transfers(tx):
        if tr["sender"] == wallet:
            sent[tr["token"]] = sent.get(tr["token"], 0.0) + tr["amount"]
        if tr["receiver"] == wallet:
            received[tr["token"]] = received.get(tr["token"], 0.0) + tr["amount"]

    logger.info("TX DEBUG | stage=FINAL_WALLET_AGGREGATION wallet=%s sent=%s received=%s", wallet, sent, received)
    return sent, received


def is_quote_token(token: str) -> bool:
    token_id = str(token or "")
    token_up = symbol(token_id).upper()
    configured_quotes = {
        WEGLD.upper(),
        JEX.upper(),
        MEX.upper(),
        BOBER.upper(),
        "ONE",
    }
    return (
        token_id.upper() in configured_quotes
        or token_up in {"WEGLD", "XEGLD", "EGLD", "USDC", "USDT", "MEX", "JEX", "ONE", "BOBER"}
        or USDC_HINT.upper() in token_id.upper()
    )


def recover_quote_received_from_full_tx(root_hash: str, wallet: str, tx_hint: Optional[dict] = None) -> Tuple[Dict[str, float], str]:
    tx_full = tx_hint if isinstance(tx_hint, dict) else get_tx_details_cached(root_hash)
    if not tx_full:
        logger.info("TX DEBUG | root=%s stage=QUOTE_RECOVERY_FAILED reason=FULL_TX_FETCH_FAILED wallet=%s", root_hash, wallet)
        return {}, wallet

    _, full_received = get_wallet_flows_aggregated(tx_full, wallet)
    quote_received = {k: v for k, v in full_received.items() if is_quote_token(k) and v > 0}
    if quote_received:
        logger.info(
            "TX DEBUG | root=%s stage=QUOTE_RECOVERY_SUCCESS wallet=%s recovered_quote_received=%s",
            root_hash, wallet, quote_received
        )
        return quote_received, wallet

    best_wallet = wallet
    best_quote: Dict[str, float] = {}
    for candidate in pick_real_wallet_candidates(tx_full):
        candidate_sent, candidate_received = get_wallet_flows_aggregated(tx_full, candidate)
        candidate_woody_sent = candidate_sent.get(WOODY, 0.0)
        candidate_quote_received = {k: v for k, v in candidate_received.items() if is_quote_token(k) and v > 0}
        if candidate_woody_sent > 0 and sum(candidate_quote_received.values()) > sum(best_quote.values()):
            best_wallet = candidate
            best_quote = candidate_quote_received

    if best_quote:
        logger.info(
            "TX DEBUG | root=%s stage=QUOTE_RECOVERY_SUCCESS wallet=%s recovered_quote_received=%s inferred_wallet=%s",
            root_hash, wallet, best_quote, best_wallet
        )
        return best_quote, best_wallet

    logger.info(
        "TX DEBUG | root=%s stage=QUOTE_RECOVERY_FAILED reason=NO_QUOTE_IN_FULL_TX wallet=%s",
        root_hash, wallet
    )
    return {}, wallet


def token_usd_estimate(token: str, amount: float) -> float:
    if amount <= 0:
        return 0.0

    if token == WEGLD or symbol(token).upper() in {"WEGLD", "XEGLD", "EGLD"}:
        egld_usd = get_egld_usd()
        usd_value = amount * egld_usd
        if amount > 0 and usd_value > 0:
            logger.info(
                "PRICE_FALLBACK_USED | token=EGLD quote_amount=%.6f egld_usd=%.8f computed_usd=%.2f",
                amount,
                egld_usd,
                usd_value,
            )
        return usd_value

    if USDC_HINT.upper() in token.upper():
        return amount

    # rough fallback via pool reserve ratios if possible
    best = get_best_price()
    if best and token == WOODY:
        return amount * best["price_usd"]

    return 0.0


def classify_tx(tx: dict) -> Optional[Dict[str, Any]]:
    root_hash = tx.get("txHash") or tx.get("originalTxHash") or ""
    woody_present = tx_contains_token(tx, WOODY)
    if not woody_present:
        logger.info(
            "TX DEBUG | root=%s WOODY_PRESENT=false CLASSIFIED_AS=NONE SKIP_REASON=SKIP_NON_WOODY_TX",
            root_hash,
        )
        return None

    wallet = choose_wallet_by_woody_delta(tx)
    if not wallet:
        logger.info(
            "TX DEBUG | root=%s WOODY_PRESENT=true CLASSIFIED_AS=NONE SKIP_REASON=NO_REAL_WALLET",
            root_hash,
        )
        return None

    sent, received = get_wallet_flows_aggregated(tx, wallet)

    woody_sent = sent.get(WOODY, 0.0)
    woody_received = received.get(WOODY, 0.0)

    non_woody_sent = {k: v for k, v in sent.items() if k != WOODY and v > 0}
    non_woody_received = {k: v for k, v in received.items() if k != WOODY and v > 0}
    routed_intermediary_tokens = sorted(
        {
            token
            for token in set(non_woody_sent) | set(non_woody_received)
            if non_woody_sent.get(token, 0.0) > 0 or non_woody_received.get(token, 0.0) > 0
        }
    )
    for token in routed_intermediary_tokens:
        logger.info(
            "TX DEBUG | root=%s stage=ROUTED_INTERMEDIARY_ASSET wallet=%s token=%s sent=%s received=%s",
            root_hash,
            wallet,
            token,
            non_woody_sent.get(token, 0.0),
            non_woody_received.get(token, 0.0),
        )
    quote_sent = {k: v for k, v in non_woody_sent.items() if is_quote_token(k)}
    quote_received = {k: v for k, v in non_woody_received.items() if is_quote_token(k)}
    quote_sent_total = sum(quote_sent.values())
    quote_received_total = sum(quote_received.values())
    if woody_received > 0 and quote_sent_total <= 0:
        logger.info(
            "TX DEBUG | root=%s stage=QUOTE_RECOVERY reason=WOODY_RECEIVED_WITHOUT_QUOTE_SENT wallet=%s non_woody_sent=%s non_woody_received=%s",
            root_hash, wallet, non_woody_sent, non_woody_received
        )
        quote_sent = non_woody_sent
    if woody_sent > 0 and quote_received_total <= 0:
        logger.info(
            "TX DEBUG | root=%s stage=SELL_ENTER wallet=%s WOODY_SENT=%s QUOTE_RECEIVED=0 "
            "non_woody_sent=%s non_woody_received=%s reason=WOODY_SENT_WITHOUT_QUOTE_RECEIVED",
            root_hash, wallet, woody_sent, non_woody_sent, non_woody_received,
        )
        if not ROUTER_ADDRESS:
            logger.warning("TX DEBUG | root=%s stage=QUOTE_RECOVERY reason=ROUTER_ADDRESS_MISSING note=real_wallet_selection_may_be_inaccurate", root_hash)
        logger.info(
            "TX DEBUG | root=%s stage=SCR_QUOTE_ATTEMPT wallet=%s source=FULL_TX_REFETCH "
            "reason=SCR_OPS_EMPTY",
            root_hash, wallet,
        )
        recovered_quote, recovered_wallet = recover_quote_received_from_full_tx(root_hash, wallet, tx)
        if recovered_quote:
            quote_received = recovered_quote
            wallet = recovered_wallet
            quote_received_total = sum(quote_received.values())
            best_qt, best_qa = sorted(quote_received.items(), key=lambda x: x[1], reverse=True)[0]
            logger.info(
                "TX DEBUG | root=%s stage=SELL_RECOVERED_FROM_FULL_TX wallet=%s "
                "quote_token=%s quote_amount=%s quote_received_total=%s decision=SELL",
                root_hash, wallet, best_qt, best_qa, quote_received_total,
            )
        else:
            logger.info(
                "TX DEBUG | root=%s stage=SELL_QUOTE_NOT_FOUND wallet=%s "
                "WOODY_SENT=%s QUOTE_RECEIVED=0 decision=UNMATCHED_FLOW",
                root_hash, wallet, woody_sent,
            )
            quote_received = non_woody_received

    dex = detect_pool_dex(tx)

    def tx_text_blob() -> str:
        parts: List[str] = [
            str(tx.get("function") or ""),
            str(tx.get("action", {}).get("name") or ""),
            str(tx.get("action", {}).get("category") or ""),
            str(tx.get("data") or ""),
        ]
        for op in tx.get("operations") or []:
            parts.extend(
                [
                    str(op.get("action") or ""),
                    str(op.get("type") or ""),
                    str(op.get("identifier") or ""),
                    str(op.get("tokenIdentifier") or ""),
                ]
            )
        return " ".join(parts).lower()

    def liquidity_kind() -> Optional[str]:
        blob = tx_text_blob()
        has_add = any(k in blob for k in ["addliquidity", "add_liquidity", "add liquidity"])
        has_remove = any(k in blob for k in ["removeliquidity", "remove_liquidity", "remove liquidity"])
        has_lp_mint = any(k in blob for k in ["lp mint", "mintlp", "mint-lp", "mint_lp", "esdtlocalmint"])
        has_lp_burn = any(k in blob for k in ["lp burn", "burnlp", "burn-lp", "burn_lp", "esdtlocalburn"])
        egld_sent = sum(v for t, v in quote_sent.items() if symbol(t).upper() in {"WEGLD", "EGLD", "XEGLD"})
        egld_received = sum(v for t, v in quote_received.items() if symbol(t).upper() in {"WEGLD", "EGLD", "XEGLD"})
        lp_sent = sum(v for t, v in sent.items() if "LP" in symbol(t).upper())
        lp_received = sum(v for t, v in received.items() if "LP" in symbol(t).upper())

        if has_add or has_lp_mint or (woody_sent > 0 and egld_sent > 0 and lp_received > 0):
            return "LIQUIDITY_ADDED"
        if has_remove or has_lp_burn or (lp_sent > 0 and woody_received > 0 and egld_received > 0):
            return "LIQUIDITY_REMOVED"
        return None

    liquidity_type = liquidity_kind()
    if liquidity_type:
        if liquidity_type == "LIQUIDITY_ADDED":
            egld_amount = sum(amount for token, amount in quote_sent.items() if symbol(token).upper() in {"WEGLD", "EGLD", "XEGLD"})
            woody_amount = woody_sent
        else:
            egld_amount = sum(amount for token, amount in quote_received.items() if symbol(token).upper() in {"WEGLD", "EGLD", "XEGLD"})
            woody_amount = woody_received

        if woody_amount <= 0 or egld_amount <= 0:
            logger.info(
                "TX DEBUG | root=%s WOODY_PRESENT=true REAL_WALLET=%s WOODY_SENT=%s WOODY_RECEIVED=%s QUOTE_SENT=%s QUOTE_RECEIVED=%s CLASSIFIED_AS=NONE SKIP_REASON=INVALID_LIQUIDITY_SIDES",
                root_hash, wallet, woody_sent, woody_received, sum(quote_sent.values()), sum(quote_received.values())
            )
            return None

        detected = {
            "type": liquidity_type,
            "wallet": wallet,
            "woody_amount": woody_amount,
            "egld_amount": egld_amount,
            "dex": dex,
            "root_hash": root_hash,
        }
        logger.info(
            "TX DEBUG | root=%s WOODY_PRESENT=true REAL_WALLET=%s WOODY_SENT=%s WOODY_RECEIVED=%s QUOTE_SENT=%s QUOTE_RECEIVED=%s CLASSIFIED_AS=%s SKIP_REASON=",
            root_hash, wallet, woody_sent, woody_received, sum(quote_sent.values()), sum(quote_received.values()), detected["type"]
        )
        return detected

    net_woody = woody_received - woody_sent
    logger.info(
        "TX DEBUG | root=%s stage=FINAL_WALLET_DELTA wallet=%s WOODY_SENT=%s WOODY_RECEIVED=%s NET_WOODY=%s",
        root_hash, wallet, woody_sent, woody_received, net_woody
    )
    quote_sent_total = sum(quote_sent.values())
    quote_received_total = sum(quote_received.values())
    net_quote = quote_received_total - quote_sent_total

    detected: Optional[Dict[str, Any]] = None

    if net_woody > 0:
        quote_token, quote_amount = ("", 0.0)
        if quote_sent:
            quote_token, quote_amount = sorted(quote_sent.items(), key=lambda x: x[1], reverse=True)[0]
        else:
            logger.info(
                "TX DEBUG | root=%s stage=ROUTED_QUOTE_OPTIONAL wallet=%s side=BUY quote_seen=false "
                "reason=QUOTE_NOT_VISIBLE_IN_FINAL_WALLET_FLOWS",
                root_hash, wallet
            )
        usd_value = max(
            token_usd_estimate(quote_token, quote_amount),
            token_usd_estimate(WOODY, net_woody),
        )
        detected = {
            "type": "BUY",
            "wallet": wallet,
            "woody_amount": net_woody,
            "quote_token": quote_token,
            "quote_amount": quote_amount,
            "swap_usd_value": usd_value,
            "dex": dex,
            "root_hash": root_hash,
        }
        logger.info(
            "TX DEBUG | root=%s stage=FINAL_BUY_CLASSIFIED wallet=%s net_woody=%s routed_assets=%s",
            root_hash, wallet, net_woody, routed_intermediary_tokens
        )
        if not quote_token:
            logger.info(
                "TX DEBUG | root=%s stage=CLASSIFIED_WITHOUT_QUOTE wallet=%s side=BUY net_woody=%s",
                root_hash, wallet, net_woody
            )
    elif net_woody < 0:
        quote_token, quote_amount = ("", 0.0)
        if quote_received:
            quote_token, quote_amount = sorted(quote_received.items(), key=lambda x: x[1], reverse=True)[0]
        else:
            logger.info(
                "TX DEBUG | root=%s stage=ROUTED_QUOTE_OPTIONAL wallet=%s side=SELL quote_seen=false "
                "reason=QUOTE_NOT_VISIBLE_IN_FINAL_WALLET_FLOWS",
                root_hash, wallet
            )
        usd_value = max(
            token_usd_estimate(quote_token, quote_amount),
            token_usd_estimate(WOODY, abs(net_woody)),
        )
        detected = {
            "type": "SELL",
            "wallet": wallet,
            "woody_amount": abs(net_woody),
            "quote_token": quote_token,
            "quote_amount": quote_amount,
            "swap_usd_value": usd_value,
            "dex": dex,
            "root_hash": root_hash,
        }
        logger.info(
            "TX DEBUG | root=%s stage=FINAL_SELL_CLASSIFIED wallet=%s net_woody=%s routed_assets=%s",
            root_hash, wallet, net_woody, routed_intermediary_tokens
        )
        if not quote_token:
            logger.info(
                "TX DEBUG | root=%s stage=CLASSIFIED_WITHOUT_QUOTE wallet=%s side=SELL net_woody=%s",
                root_hash, wallet, net_woody
            )

    logger.info(
        "TX DEBUG | root=%s WOODY_PRESENT=true REAL_WALLET=%s WOODY_SENT=%s WOODY_RECEIVED=%s QUOTE_SENT=%s QUOTE_RECEIVED=%s NET_WOODY=%s NET_QUOTE=%s DEX=%s CLASSIFIED_AS=%s SKIP_REASON=%s SENT=%s RECEIVED=%s",
        root_hash, wallet, woody_sent, woody_received, quote_sent_total, quote_received_total,
        net_woody, net_quote, dex,
        detected.get("type") if detected else "NONE",
        "" if detected else "UNMATCHED_FLOW",
        sent, received
    )
    return detected


def choose_title(parsed: Dict[str, Any]) -> str:
    tx_type = parsed.get("type", "")
    if tx_type == "LIQUIDITY_ADDED":
        return "💧 *LIQUIDITY ADDED*"
    if tx_type == "LIQUIDITY_REMOVED":
        return "💧 *LIQUIDITY REMOVED*"

    usd = safe_float(parsed.get("swap_usd_value", 0.0))

    if usd >= BIG_ALERT_USD:
        return f"{'🚀' if tx_type == 'BUY' else '💥'} *BIG {tx_type}*"
    return f"{'🟢' if tx_type == 'BUY' else '🔴'} *{tx_type}*"


def choose_image(parsed: Dict[str, Any]) -> str:
    usd = safe_float(parsed.get("swap_usd_value", 0.0))
    tx_type = parsed.get("type", "")

    if tx_type in {"LIQUIDITY_ADDED", "LIQUIDITY_REMOVED"}:
        return BANNER_IMAGE if file_exists(BANNER_IMAGE) else BUY_IMAGE
    if tx_type == "BUY":
        return BIG_BUY_IMAGE if usd >= BIG_ALERT_USD else BUY_IMAGE
    return BIG_SELL_IMAGE if usd >= BIG_ALERT_USD else SELL_IMAGE


def build_message(parsed: Dict[str, Any]) -> str:
    explorer = f"https://explorer.multiversx.com/transactions/{parsed['root_hash']}"
    best = get_best_price()
    now_utc = time.strftime("%Y-%m-%d %H:%M:%S UTC", time.gmtime())

    price_line = ""
    if best:
        price_line = f"📊 Market: {best['price_egld']:.12f} EGLD (${best['price_usd']:.8f})\n"
    tx_type = parsed.get("type", "")
    if tx_type in {"LIQUIDITY_ADDED", "LIQUIDITY_REMOVED"}:
        return (
            "🪶 *WOODY Monitor V2*\n"
            f"{choose_title(parsed)}\n\n"
            f"🪙 *EGLD:* `{safe_float(parsed.get('egld_amount', 0.0)):,.6f}`\n"
            f"🪶 *WOODY:* `{safe_float(parsed.get('woody_amount', 0.0)):,.4f}`\n"
            f"🏦 *Pool:* `{parsed.get('dex', 'Unknown')}`\n"
            f"👤 *Wallet:* `{short_wallet(parsed.get('wallet', ''))}`\n"
            f"🔗 [Open in Explorer]({explorer})"
        )
    confidence = str(parsed.get("usd_confidence", "high")).upper()

    return (
        "🪶 *WOODY Monitor V2*\n"
        f"{choose_title(parsed)}\n\n"
        f"💲 *Value:* `${parsed['swap_usd_value']:,.2f}`\n"
        f"🧭 *USD Confidence:* `{confidence}`\n"
        f"🪶 *Amount:* `{parsed['woody_amount']:,.4f} WOODY`\n"
        f"💱 *Quote:* `{parsed['quote_amount']:,.4f} {symbol(parsed['quote_token'])}`\n"
        f"👤 *Wallet:* `{short_wallet(parsed['wallet'])}`\n"
        f"🏦 *DEX:* `{parsed['dex']}`\n"
        f"🕒 *Time:* `{now_utc}`\n"
        f"{price_line}"
        f"🔗 [Open in Explorer]({explorer})"
    )

# =========================================================
# ROOT QUEUE + WEBSOCKET
# =========================================================
def add_root(root_hash: str) -> None:
    if not root_hash:
        return
    if root_hash in ROOT_PROCESSED:
        logger.debug("add_root | root=%s already processed, skipping", root_hash)
        return

    item = ROOT_PENDING.get(root_hash)
    if item:
        item["updated"] = time.time()
        logger.debug("add_root | root=%s updated timestamp (already pending)", root_hash)
    else:
        ROOT_PENDING[root_hash] = {
            "created": time.time(),
            "updated": time.time(),
        }
        logger.info("add_root | root=%s added to ROOT_PENDING (queue size=%s)", root_hash, len(ROOT_PENDING))


async def _send_subscriptions(sio: socketio.AsyncClient) -> None:
    """Emit all subscribeCustomTransfers subscriptions and log each attempt."""
    logger.info("WS SUBSCRIBE | Sending token subscription for %s", WOODY)
    try:
        await sio.emit("subscribeCustomTransfers", {"token": WOODY})
        logger.info("WS SUBSCRIBE | Token subscription sent for %s", WOODY)
    except Exception as exc:
        logger.warning("WS SUBSCRIBE | Token subscription failed for %s -> %s", WOODY, exc)

    for pool in WATCHED_POOLS:
        logger.info("WS SUBSCRIBE | Sending address subscription for pool %s", pool)
        try:
            await sio.emit("subscribeCustomTransfers", {"address": pool})
            logger.info("WS SUBSCRIBE | Address subscription sent for pool %s", pool)
        except Exception as exc:
            logger.warning("WS SUBSCRIBE | Address subscription failed for pool %s -> %s", pool, exc)


def _extract_root_hashes(data: Any) -> List[str]:
    """Extract root/tx hashes from any customTransfers payload shape.

    The MultiversX WebSocket API may deliver events as:
      - A list of transfer objects directly
      - A dict with a ``transfers`` key containing a list
      - A single transfer object (dict without a ``transfers`` key)
    """
    hashes: List[str] = []

    if isinstance(data, list):
        items = data
    elif isinstance(data, dict):
        if "transfers" in data:
            items = data.get("transfers") or []
            if not isinstance(items, list):
                items = [items] if items else []
        else:
            # Single transfer object delivered directly
            items = [data]
    else:
        logger.warning("WS EVENT | Unexpected payload type: %s", type(data).__name__)
        return hashes

    for transfer in items:
        if not isinstance(transfer, dict):
            continue
        root_hash = str(
            transfer.get("originalTxHash")
            or transfer.get("txHash")
            or transfer.get("hash")
            or ""
        )
        if root_hash:
            hashes.append(root_hash)

    return hashes


async def ws_connect_loop(stop_event: asyncio.Event) -> None:
    global WS_CONNECTED
    while not stop_event.is_set():
        sio = socketio.AsyncClient(
            reconnection=True,
            reconnection_attempts=0,
            logger=False,
            engineio_logger=False,
        )

        @sio.event
        async def connect():
            global WS_CONNECTED
            WS_CONNECTED = True
            logger.info("WS EVENT | connect fired — WebSocket connected to %s", WS_URL)
            # Small yield so the socket handshake fully settles before emitting
            await asyncio.sleep(0.1)
            await _send_subscriptions(sio)

        @sio.event
        async def disconnect():
            global WS_CONNECTED
            WS_CONNECTED = False
            logger.warning("WS EVENT | disconnect fired — WebSocket disconnected")

        # Primary event name used by the MultiversX socket-api
        @sio.on("customTransfers")
        async def on_custom_transfers(data):
            logger.info("WS EVENT | customTransfers received — payload type=%s", type(data).__name__)
            hashes = _extract_root_hashes(data)
            logger.info("WS EVENT | customTransfers extracted %s root hash(es): %s", len(hashes), hashes)
            for root_hash in hashes:
                add_root(root_hash)

        # Legacy / alternative event name — kept for compatibility
        @sio.on("customTransferUpdate")
        async def on_custom_transfer_update(data):
            logger.info("WS EVENT | customTransferUpdate received — payload type=%s", type(data).__name__)
            hashes = _extract_root_hashes(data)
            logger.info("WS EVENT | customTransferUpdate extracted %s root hash(es): %s", len(hashes), hashes)
            for root_hash in hashes:
                add_root(root_hash)

        # Catch-all to surface any unexpected event names from the API
        @sio.on("*")
        async def on_any_event(event, data):
            if event in {"connect", "disconnect", "customTransfers", "customTransferUpdate"}:
                return
            logger.info("WS EVENT | unhandled event=%s payload_type=%s", event, type(data).__name__)

        try:
            logger.info("WS CONNECT | Connecting to %s (path=/ws/subscription)", WS_URL)
            await sio.connect(WS_URL, socketio_path="/ws/subscription", transports=["websocket"])
            logger.info("WS CONNECT | sio.connect() returned — waiting for events")
            while not stop_event.is_set():
                await asyncio.sleep(0.3)
        except asyncio.CancelledError:
            WS_CONNECTED = False
            break
        except Exception as exc:
            WS_CONNECTED = False
            logger.warning("WS CONNECT | Loop error -> %s", exc)
            if not stop_event.is_set():
                logger.info("WS CONNECT | Reconnecting in %ss...", WS_RECONNECT_DELAY)
                await asyncio.sleep(WS_RECONNECT_DELAY)
        finally:
            try:
                if sio.connected:
                    await sio.disconnect()
            except Exception as exc:
                logger.debug("WS CONNECT | Disconnect cleanup error: %s", exc)
            WS_CONNECTED = False

# =========================================================
# JOBS
# =========================================================
async def process_pending_roots(context: ContextTypes.DEFAULT_TYPE) -> None:
    global PROCESS_PENDING_LOCK
    if PROCESS_PENDING_LOCK is None:
        PROCESS_PENDING_LOCK = asyncio.Lock()
    if PROCESS_PENDING_LOCK.locked():
        logger.info("PROCESS ROOT | previous run still in progress - skipping this tick")
        return

    async with PROCESS_PENDING_LOCK:
        await _process_pending_roots_inner(context)


async def _process_pending_roots_inner(context: ContextTypes.DEFAULT_TYPE) -> None:
    now = time.time()
    to_delete: List[str] = []
    ready_roots: List[Tuple[str, Dict[str, Any], float]] = []

    for root_hash, data in list(ROOT_PENDING.items()):
        age = now - safe_float(data.get("created", now))
        idle = now - safe_float(data.get("updated", now))

        if idle < ROOT_SETTLE_SECONDS and age < ROOT_MAX_AGE_SECONDS:
            continue
        if root_hash in ROOT_IN_PROGRESS:
            logger.debug("PROCESS ROOT | root=%s already in progress, skipping duplicate run", root_hash)
            continue
        ready_roots.append((root_hash, data, age))

    ready_roots.sort(key=lambda item: safe_float(item[1].get("created", now)))
    if not ready_roots:
        return

    unique_ready: List[Tuple[str, Dict[str, Any], float]] = []
    seen_roots: Set[str] = set()
    for root_hash, data, age in ready_roots:
        if root_hash in seen_roots:
            logger.debug("PROCESS ROOT | root=%s duplicate candidate skipped in same tick", root_hash)
            continue
        seen_roots.add(root_hash)
        unique_ready.append((root_hash, data, age))

    semaphore = asyncio.Semaphore(ROOT_PROCESSING_CONCURRENCY)

    async def process_one(root_hash: str, age: float) -> Optional[str]:
        global LAST_TX_PROCESSED, LAST_ROOT_PROCESSED_AT, LAST_WOODY_TX_AT
        async with semaphore:
            ROOT_IN_PROGRESS.add(root_hash)
            try:
                tx = await asyncio.to_thread(get_tx_details_cached, root_hash)
                if not tx:
                    if age >= ROOT_MAX_AGE_SECONDS:
                        logger.warning("No tx details fetched for root %s (expired, dropping)", root_hash)
                        ROOT_PROCESSED.add(root_hash)
                        return root_hash
                    logger.info("No tx details yet for root %s (will retry)", root_hash)
                    return None

                logger.info("PROCESS ROOT | root=%s age=%.1fs — classifying tx", root_hash, age)
                parsed = classify_tx(tx)
                if parsed:
                    logger.info(
                        "PROCESS ROOT | root=%s classified type=%s wallet=%s woody=%.4f usd=%.2f dex=%s",
                        root_hash,
                        parsed.get("type"),
                        parsed.get("wallet"),
                        safe_float(parsed.get("woody_amount")),
                        safe_float(parsed.get("swap_usd_value")),
                        parsed.get("dex"),
                    )
                    update_volume_state(parsed)
                    message = build_message(parsed)
                    update_last_alert(parsed, message)
                else:
                    logger.info("PROCESS ROOT | root=%s classified as None (no alert)", root_hash)

                if parsed and parsed.get("type") in {"LIQUIDITY_ADDED", "LIQUIDITY_REMOVED"}:
                    logger.info(
                        "ALERT DISPATCH | root=%s type=%s targets=%s",
                        parsed["root_hash"], parsed["type"], chat_targets(),
                    )
                    await send_alert_to_targets(context, choose_image(parsed), message)
                    logger.info("ALERT SENT | root=%s type=%s", parsed["root_hash"], parsed["type"])
                elif parsed and parsed.get("swap_usd_value", 0.0) >= MIN_ALERT_USD:
                    logger.info(
                        "ALERT DISPATCH | root=%s type=%s usd=%.2f targets=%s",
                        parsed["root_hash"], parsed["type"], parsed["swap_usd_value"], chat_targets(),
                    )
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
                elif parsed:
                    logger.info(
                        "ALERT SKIP | root=%s type=%s usd=%.2f below MIN_ALERT_USD=%.2f",
                        root_hash, parsed.get("type"), safe_float(parsed.get("swap_usd_value")), MIN_ALERT_USD,
                    )
                else:
                    logger.info("ALERT SKIP | root=%s no parseable swap detected", root_hash)

                ROOT_PROCESSED.add(root_hash)
                LAST_TX_PROCESSED = root_hash
                LAST_ROOT_PROCESSED_AT = int(time.time())
                if parsed and parsed.get("type") in {"BUY", "SELL"}:
                    LAST_WOODY_TX_AT = LAST_ROOT_PROCESSED_AT
                return root_hash
            finally:
                ROOT_IN_PROGRESS.discard(root_hash)

    results = await asyncio.gather(*(process_one(root_hash, age) for root_hash, _data, age in unique_ready))
    to_delete.extend([root_hash for root_hash in results if root_hash])

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
    chat = update.effective_chat
    user = update.effective_user
    await send_start_menu(chat.id, context, chat.type if chat else None, user.id if user else None)


async def menu_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    chat = update.effective_chat
    user = update.effective_user
    await send_start_menu(chat.id, context, chat.type if chat else None, user.id if user else None)


async def status_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    logger.info("STATUS_COMMAND_USED | user=%s chat=%s", update.effective_user.id if update.effective_user else "?", update.effective_chat.id if update.effective_chat else "?")
    is_public = is_public_menu_context(update.effective_chat.type if update.effective_chat else None, update.effective_user.id if update.effective_user else None)
    text = await asyncio.to_thread(get_ai_status_text, is_public)
    if update.message:
        await update.message.reply_text(text, parse_mode=ParseMode.MARKDOWN)


async def price_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if update.message:
        await update.message.reply_text(await asyncio.to_thread(get_price_text), parse_mode=ParseMode.MARKDOWN)


async def liquidity_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if update.message:
        await update.message.reply_text(await asyncio.to_thread(get_liquidity_text), parse_mode=ParseMode.MARKDOWN)


async def holders_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if update.message:
        holders = await asyncio.to_thread(get_holders_count)
        await update.message.reply_text(
            f"👥 *WOODY Holders*\n\nCurrent holders: *{holders or 'N/A'}*",
            parse_mode=ParseMode.MARKDOWN,
        )


async def chart_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if update.message:
        await update.message.reply_text(f"📊 Chart: {CHART_URL}")


async def buy_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if update.message:
        await update.message.reply_text(
            f"🟢 Buy xExchange:\n{BUY_XEXCHANGE_URL}\n\n🟢 Buy XOXNO:\n{BUY_XOXNO_URL}"
        )


async def summary_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if update.message:
        await update.message.reply_text(await asyncio.to_thread(get_market_summary_text), parse_mode=ParseMode.MARKDOWN)


async def analysis_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if update.message:
        await update.message.reply_text(await asyncio.to_thread(get_ai_analysis_text), parse_mode=ParseMode.MARKDOWN)


async def pulse_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if update.message:
        await update.message.reply_text(await asyncio.to_thread(get_market_pulse_text), parse_mode=ParseMode.MARKDOWN)


async def risk_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if update.message:
        await update.message.reply_text(await asyncio.to_thread(get_risk_radar_text), parse_mode=ParseMode.MARKDOWN)


async def wallets_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if is_public_menu_context(update.effective_chat.type if update.effective_chat else None, update.effective_user.id if update.effective_user else None):
        return
    if update.message:
        await update.message.reply_text(await asyncio.to_thread(get_wallet_intelligence_text), parse_mode=ParseMode.MARKDOWN)




async def accumulation_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if is_public_menu_context(update.effective_chat.type if update.effective_chat else None, update.effective_user.id if update.effective_user else None):
        return
    if update.message:
        await update.message.reply_text(await asyncio.to_thread(get_accumulation_detection_text), parse_mode=ParseMode.MARKDOWN)

async def fakepump_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if is_public_menu_context(update.effective_chat.type if update.effective_chat else None, update.effective_user.id if update.effective_user else None):
        return
    if update.message:
        await update.message.reply_text(await asyncio.to_thread(get_fake_pump_detection_text), parse_mode=ParseMode.MARKDOWN)


async def diagnostics_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if is_public_menu_context(update.effective_chat.type if update.effective_chat else None, update.effective_user.id if update.effective_user else None):
        return
    if update.message:
        text = await asyncio.to_thread(get_diagnostics_text)
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
    logger.info(
        "BUTTON PRESS | data=%s user=%s chat=%s",
        query.data, query.from_user.id if query.from_user else "?", query.message.chat_id if query.message else "?"
    )

    if query.data == "price":
        await query.message.reply_text(await asyncio.to_thread(get_price_text), parse_mode=ParseMode.MARKDOWN)
    elif query.data == "liquidity":
        await query.message.reply_text(await asyncio.to_thread(get_liquidity_text), parse_mode=ParseMode.MARKDOWN)
    elif query.data == "holders":
        await query.message.reply_text(
            f"👥 *WOODY Holders*\n\nCurrent holders: *{get_holders_count() or 'N/A'}*",
            parse_mode=ParseMode.MARKDOWN,
        )
    elif query.data == "top_holders":
        if is_public_menu_context(query.message.chat.type if query.message and query.message.chat else None, query.from_user.id if query.from_user else None):
            return
        await query.message.reply_text(await asyncio.to_thread(get_top_holders_text), parse_mode=ParseMode.MARKDOWN)
    elif query.data == "last_buy":
        await query.message.reply_text(get_last_trade_text("BUY"), parse_mode=ParseMode.MARKDOWN)
    elif query.data == "last_sell":
        await query.message.reply_text(get_last_trade_text("SELL"), parse_mode=ParseMode.MARKDOWN)
    elif query.data == "volume_24h":
        if is_public_menu_context(query.message.chat.type if query.message and query.message.chat else None, query.from_user.id if query.from_user else None):
            return
        await query.message.reply_text(await asyncio.to_thread(get_volume_24h_text), parse_mode=ParseMode.MARKDOWN)
    elif query.data == "top_volume":
        if is_public_menu_context(query.message.chat.type if query.message and query.message.chat else None, query.from_user.id if query.from_user else None):
            return
        await query.message.reply_text(await asyncio.to_thread(get_top_volume_text), parse_mode=ParseMode.MARKDOWN)
    elif query.data == "pools":
        if is_public_menu_context(query.message.chat.type if query.message and query.message.chat else None, query.from_user.id if query.from_user else None):
            return
        await query.message.reply_text(await asyncio.to_thread(get_pools_text), parse_mode=ParseMode.MARKDOWN)
    elif query.data in {"bot_status", "ai_status"}:
        is_public = is_public_menu_context(query.message.chat.type if query.message and query.message.chat else None, query.from_user.id if query.from_user else None)
        logger.info("AI_STATUS_BUTTON_USED | user=%s chat=%s public=%s", query.from_user.id if query.from_user else "?", query.message.chat_id if query.message else "?", is_public)
        await query.message.reply_text(await asyncio.to_thread(get_ai_status_text, is_public), parse_mode=ParseMode.MARKDOWN)
    elif query.data == "diagnostics":
        if is_public_menu_context(query.message.chat.type if query.message and query.message.chat else None, query.from_user.id if query.from_user else None):
            return
        await query.message.reply_text(await asyncio.to_thread(get_diagnostics_text), parse_mode=ParseMode.MARKDOWN)
    elif query.data == "wallet_intelligence":
        if is_public_menu_context(query.message.chat.type if query.message and query.message.chat else None, query.from_user.id if query.from_user else None):
            return
        await query.message.reply_text(await asyncio.to_thread(get_wallet_intelligence_text), parse_mode=ParseMode.MARKDOWN)
    elif query.data == "accumulation_detection":
        if is_public_menu_context(query.message.chat.type if query.message and query.message.chat else None, query.from_user.id if query.from_user else None):
            return
        await query.message.reply_text(await asyncio.to_thread(get_accumulation_detection_text), parse_mode=ParseMode.MARKDOWN)
    elif query.data == "market_summary":
        await query.message.reply_text(await asyncio.to_thread(get_market_summary_text), parse_mode=ParseMode.MARKDOWN)
    elif query.data == "ai_analysis":
        await query.message.reply_text(await asyncio.to_thread(get_ai_analysis_text), parse_mode=ParseMode.MARKDOWN)
    elif query.data == "market_context":
        await query.message.reply_text(await asyncio.to_thread(get_market_context_text), parse_mode=ParseMode.MARKDOWN)
    elif query.data == "ai_recommendation":
        is_public = is_public_menu_context(query.message.chat.type if query.message and query.message.chat else None, query.from_user.id if query.from_user else None)
        await query.message.reply_text(await asyncio.to_thread(get_ai_recommendation_text, is_public), parse_mode=ParseMode.MARKDOWN)
    elif query.data == "risk_radar":
        await query.message.reply_text(await asyncio.to_thread(get_risk_radar_text), parse_mode=ParseMode.MARKDOWN)
    elif query.data == "market_pulse":
        await query.message.reply_text(await asyncio.to_thread(get_market_pulse_text), parse_mode=ParseMode.MARKDOWN)
    elif query.data == "fake_pump_detection":
        if is_public_menu_context(query.message.chat.type if query.message and query.message.chat else None, query.from_user.id if query.from_user else None):
            return
        await query.message.reply_text(await asyncio.to_thread(get_fake_pump_detection_text), parse_mode=ParseMode.MARKDOWN)
    else:
        logger.warning("Unhandled callback_data=%s", query.data)


async def greeting_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not update.message or not update.message.text:
        return

    text = update.message.text.strip().lower()
    if update.effective_chat and update.effective_chat.type in {"group", "supergroup"}:
        return

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
    load_runtime_state()
    validate_runtime_config()

    async def post_init(application: Application) -> None:
        global WS_STOP_EVENT, WS_TASK
        WS_STOP_EVENT = asyncio.Event()
        WS_TASK = application.create_task(ws_connect_loop(WS_STOP_EVENT))
        logger.info("Startup complete, websocket task launched")

    async def post_shutdown(_: Application) -> None:
        if WS_STOP_EVENT:
            WS_STOP_EVENT.set()
        if WS_TASK and not WS_TASK.done():
            WS_TASK.cancel()
            try:
                await WS_TASK
            except asyncio.CancelledError:
                pass

    app = Application.builder().token(TOKEN).post_init(post_init).post_shutdown(post_shutdown).build()

    app.add_handler(CommandHandler("start", start_command))
    app.add_handler(CommandHandler("menu", menu_command))
    app.add_handler(CommandHandler("status", status_command))
    app.add_handler(CommandHandler("price", price_command))
    app.add_handler(CommandHandler("pret", price_command))
    app.add_handler(CommandHandler("liquidity", liquidity_command))
    app.add_handler(CommandHandler("holders", holders_command))
    app.add_handler(CommandHandler("chart", chart_command))
    app.add_handler(CommandHandler("buy", buy_command))
    app.add_handler(CommandHandler("summary", summary_command))
    app.add_handler(CommandHandler("analysis", analysis_command))
    app.add_handler(CommandHandler("pulse", pulse_command))
    app.add_handler(CommandHandler("risk", risk_command))
    app.add_handler(CommandHandler("wallets", wallets_command))
    app.add_handler(CommandHandler("accumulation", accumulation_command))
    app.add_handler(CommandHandler("fakepump", fakepump_command))
    app.add_handler(CommandHandler("diag", diagnostics_command))
    app.add_handler(CommandHandler("id", id_command))
    app.add_handler(CommandHandler("testalert", testalert_command))
    app.add_handler(CallbackQueryHandler(menu_callbacks))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, greeting_handler))

    if app.job_queue is None:
        raise RuntimeError("JobQueue missing. Install python-telegram-bot[job-queue].")

    app.job_queue.run_repeating(check_holders, interval=CHECK_HOLDERS_INTERVAL, first=20)
    app.job_queue.run_repeating(process_pending_roots, interval=3, first=5)

    logger.info("WOODY Monitor V2 started...")
    app.run_polling(drop_pending_updates=True)


if __name__ == "__main__":
    main()
