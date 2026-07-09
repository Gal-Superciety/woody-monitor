import os
from dataclasses import dataclass
from typing import Any, Dict, List

from dotenv import load_dotenv

load_dotenv()


def _required_env(name: str) -> str:
    value = os.getenv(name, "").strip()
    if not value:
        raise ValueError(f"{name} is missing")
    return value


TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "").strip()

PRIVATE_CHAT_ID = os.getenv("TELEGRAM_PRIVATE_CHAT_ID", "").strip()
GROUP_CHAT_ID = os.getenv("TELEGRAM_GROUP_CHAT_ID", "").strip()

ENABLE_PRIVATE_ALERTS = os.getenv("ENABLE_PRIVATE_ALERTS", "true").strip().lower() == "true"
ENABLE_GROUP_ALERTS = os.getenv("ENABLE_GROUP_ALERTS", "false").strip().lower() == "true"
ADMIN_TELEGRAM_ID = os.getenv("ADMIN_TELEGRAM_ID", "").strip()

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
XEXCHANGE_LP_TOKEN_ID = os.getenv("XEXCHANGE_LP_TOKEN_ID", "").strip()
LP_HOLDERS_PAGE_SIZE = max(1, int(os.getenv("LP_HOLDERS_PAGE_SIZE", "100")))
LP_HOLDERS_MAX_PAGES = max(1, int(os.getenv("LP_HOLDERS_MAX_PAGES", "20")))
LP_SNAPSHOT_CHECK_INTERVAL = int(os.getenv("LP_SNAPSHOT_CHECK_INTERVAL", "3600"))
LP_SNAPSHOT_FILE = os.getenv("LP_SNAPSHOT_FILE", "data/lp_snapshots.json").strip()
LP_REWARDS_FILE = os.getenv("LP_REWARDS_FILE", "data/lp_rewards.json").strip()
LP_EXPORT_REWARD_POOL_EGLD = float(os.getenv("LP_EXPORT_REWARD_POOL_EGLD", "0"))
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
# WOODY GLOBAL LP SNAPSHOT CONFIG
# =========================================================
WOODY_OLV_POOL_ADDRESS = os.getenv(
    "WOODY_OLV_POOL_ADDRESS",
    "erd1qqqqqqqqqqqqqpgqysf23hg6d5sazz46alfhtveate5na4fz6avs650hc9",
).strip()
GLOBAL_LP_DUST_EGLD = float(os.getenv("GLOBAL_LP_DUST_EGLD", "0.000001"))

LP_POOLS: List[Dict[str, Any]] = [
    {"dex": "xExchange", "name": "WOODY/EGLD", "pair_address": XEXCHANGE_POOL_ADDRESS, "lp_token": "WOODYWEGLD-5c3558", "status": "active"},
    {"dex": "xExchange", "name": "WOODY/MEX", "pair_address": WOODY_MEX_POOL_ADDRESS, "lp_token": "WOODYMEX-12e1aa", "status": "active"},
    {"dex": "xExchange", "name": "WOODY/USDC", "pair_address": WOODY_USDC_POOL_ADDRESS, "lp_token": "", "status": "active"},
    {"dex": "OneDex", "name": "WOODY/EGLD", "pair_address": ONEDEX_POOL_ADDRESS, "lp_token": "WOODYWEGLD-9832b2", "status": "active"},
    {"dex": "OneDex", "name": "WOODY/ONE", "pair_address": "", "lp_token": "WOODYONE-826f23", "status": "active"},
    {"dex": "JEX", "name": "WOODY/BOBER", "pair_address": WOODY_BOBER_POOL_ADDRESS, "lp_token": "", "status": "active"},
    {"dex": "JEX", "name": "WOODY/JEX", "pair_address": WOODY_JEX_POOL_ADDRESS, "lp_token": "", "status": "active"},
    {"dex": "JEX", "name": "WOODY/OLV", "pair_address": WOODY_OLV_POOL_ADDRESS, "lp_token": "", "status": "active"},
    {"dex": "OneDex", "name": "WOODY/BOBER", "pair_address": "", "lp_token": "WOODYBOBER-1a1703", "status": "excluded", "reason": "broken pool"},
]


# Runtime/data files
DATA_DIR = os.getenv("DATA_DIR", "data").strip()
LAST_ALERTS_FILE = os.getenv("LAST_ALERTS_FILE", "data/last_alerts.json").strip()
TOP_VOLUME_FILE = os.getenv("TOP_VOLUME_FILE", "data/top_volume.json").strip()
VOLUME_HISTORY_FILE = os.getenv("VOLUME_HISTORY_FILE", "data/volume_history.json").strip()
ROOT_CACHE_FILE = os.getenv("ROOT_CACHE_FILE", "data/root_cache.json").strip()
PUBLIC_STATUS_FILE = os.getenv("PUBLIC_STATUS_FILE", "public/woody-monitor-status.json").strip()
PUBLIC_STATUS_INTERVAL = int(os.getenv("PUBLIC_STATUS_INTERVAL", "30"))
PUBLIC_STATUS_HOST = os.getenv("PUBLIC_STATUS_HOST", "0.0.0.0").strip()
PUBLIC_STATUS_PORT = int(os.getenv("PUBLIC_STATUS_PORT") or os.getenv("PORT") or "8080")
TX_DETAILS_CACHE_TTL_SECONDS = int(os.getenv("TX_DETAILS_CACHE_TTL_SECONDS", "45"))
ROOT_PROCESSING_CONCURRENCY = max(1, int(os.getenv("ROOT_PROCESSING_CONCURRENCY", "4")))

USE_WEBHOOKS = os.getenv("USE_WEBHOOKS", "false").strip().lower() == "true"
WEBHOOK_URL = os.getenv("WEBHOOK_URL", "").strip()
WEBHOOK_PATH = os.getenv("WEBHOOK_PATH", "/webhook").strip()
WEBHOOK_PORT = int(os.getenv("WEBHOOK_PORT", "8443"))


@dataclass(frozen=True)
class Config:
    telegram_bot_token: str = TOKEN
    admin_telegram_id: str = ADMIN_TELEGRAM_ID
    mvx_api: str = MVX_API
    ws_url: str = WS_URL
    woody_token_id: str = WOODY
    wegld_token_id: str = WEGLD
    private_chat_id: str = PRIVATE_CHAT_ID
    group_chat_id: str = GROUP_CHAT_ID
    enable_private_alerts: bool = ENABLE_PRIVATE_ALERTS
    enable_group_alerts: bool = ENABLE_GROUP_ALERTS
    use_webhooks: bool = USE_WEBHOOKS
    webhook_url: str = WEBHOOK_URL
    webhook_path: str = WEBHOOK_PATH
    webhook_port: int = WEBHOOK_PORT

    def validate(self) -> None:
        if not self.telegram_bot_token:
            raise ValueError("TELEGRAM_BOT_TOKEN is missing")
        if not self.admin_telegram_id:
            raise ValueError("ADMIN_TELEGRAM_ID is missing")
        if self.use_webhooks:
            if not self.webhook_url:
                raise ValueError("WEBHOOK_URL is required when USE_WEBHOOKS=true")
            if not self.webhook_url.startswith(("https://", "http://")):
                raise ValueError("WEBHOOK_URL must start with http:// or https:// when USE_WEBHOOKS=true")
            if not self.webhook_path or not self.webhook_path.startswith("/"):
                raise ValueError("WEBHOOK_PATH must start with / when USE_WEBHOOKS=true")
            if not 1 <= self.webhook_port <= 65535:
                raise ValueError("WEBHOOK_PORT must be between 1 and 65535 when USE_WEBHOOKS=true")


CONFIG = Config()
SETTINGS: Dict[str, Any] = {
    "TELEGRAM_BOT_TOKEN": TOKEN,
    "ADMIN_TELEGRAM_ID": ADMIN_TELEGRAM_ID,
    "MVX_API": MVX_API,
    "WS_URL": WS_URL,
    "WOODY_TOKEN_ID": WOODY,
    "WEGLD_TOKEN_ID": WEGLD,
    "PRIVATE_CHAT_ID": PRIVATE_CHAT_ID,
    "GROUP_CHAT_ID": GROUP_CHAT_ID,
    "ENABLE_PRIVATE_ALERTS": ENABLE_PRIVATE_ALERTS,
    "ENABLE_GROUP_ALERTS": ENABLE_GROUP_ALERTS,
    "USE_WEBHOOKS": USE_WEBHOOKS,
    "WEBHOOK_URL": WEBHOOK_URL,
    "WEBHOOK_PATH": WEBHOOK_PATH,
    "WEBHOOK_PORT": WEBHOOK_PORT,
}


def validate_config() -> None:
    CONFIG.validate()
