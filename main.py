import os
import re
import requests
from dotenv import load_dotenv

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
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

TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
PRIVATE_CHAT_ID = os.getenv("TELEGRAM_PRIVATE_CHAT_ID")
GROUP_CHAT_ID = os.getenv("TELEGRAM_GROUP_CHAT_ID")

UA = {"User-Agent": "WOODY"}

MVX = "https://api.multiversx.com"
XOXNO = "https://swap.xoxno.com/api/v1/quote"
CG = "https://api.coingecko.com/api/v3/simple/price?ids=elrond-erd-2&vs_currencies=usd"

WOODY = "WOODY-5f9d9c"
WEGLD = "WEGLD-bd4d79"
BOBER = "BOBER-9eb764"
JEX = "JEX-9040ca"
MEX = "MEX-455c57"

XEX = "erd1qqqqqqqqqqqqqpgqvmgnk26tfvz6sj5yasw7p6yfvqpv628d2jpsnvmeaz"
ONEDX = "erd1qqqqqqqqqqqqqpgqqz6vp9y50ep867vnr296mqf3dduh6guvmvlsu3sujc"
WOODY_BOBER = "erd1qqqqqqqqqqqqqpgqvq8vtfn26fdezjm07a7yjqtgn3h02af86avs9vf6kw"
WOODY_JEX = "erd1qqqqqqqqqqqqqpgqdz5vj73j7h2velx83xwrad6zz82q2njr6avsrkua0n"
WOODY_MEX = "erd1qqqqqqqqqqqqqpgqzqtfej5s9hp7cg0ardy6mt3fvz4jrdsa2jpsdg959f"

TWITTER = "https://x.com/YOUR_ACCOUNT"

# Praguri swap alerts
MIN_WOODY_ALERT = 10000
MIN_EGLD_ALERT = 0.2

# BIG BUY / BIG SELL
BIG_BUY_EGLD = 1.0
BIG_SELL_EGLD = 1.0

# Praguri pentru liquidity added REAL
# Trimitem alertă doar dacă ambele rezerve cresc suficient
MIN_LIQUIDITY_ADD_WOODY = 1000
MIN_LIQUIDITY_ADD_EGLD = 0.05

LAST_SWAP_STATE = {
    "xexchange": None,
    "onedx": None,
}

LAST_HOLDERS_COUNT = None

# Ținem minte starea rezervelor pentru LP REAL
LAST_LIQUIDITY_STATE = {
    "xexchange": None,
    "onedx": None,
}


def j(url, params=None):
    r = requests.get(url, params=params, headers=UA, timeout=20)
    r.raise_for_status()
    return r.json()


def d(balance, decimals):
    return int(balance) / (10 ** int(decimals))


def reserves(pair_address):
    data = j(f"{MVX}/accounts/{pair_address}/tokens")
    return {t["identifier"]: d(t["balance"], t["decimals"]) for t in data}


def egld_usd():
    return float(j(CG)["elrond-erd-2"]["usd"])


def quote_to_wegld(token):
    if token == WEGLD:
        return 1
    q = j(XOXNO, {"from": token, "to": WEGLD, "amountIn": str(10**18)})
    out = q.get("amountOut") or q.get("toAmount")
    return int(out) / (10**18) if out else 0


def liq_wegld(pair_address):
    r = reserves(pair_address)
    return 2 * r.get(WEGLD, 0) if r.get(WEGLD, 0) > 0 else None


def liq_other(pair_address, token):
    r = reserves(pair_address)
    token_amount = r.get(token, 0)
    if token_amount <= 0:
        return None
    price_in_wegld = quote_to_wegld(token)
    if price_in_wegld <= 0:
        return None
    return 2 * token_amount * price_in_wegld


def all_liq():
    usd = egld_usd()
    total = 0
    lines = []

    for name, value in [
        ("WOODY/EGLD xExchange", liq_wegld(XEX)),
        ("WOODY/EGLD OneDex", liq_wegld(ONEDX)),
        ("WOODY/BOBER", liq_other(WOODY_BOBER, BOBER)),
        ("WOODY/JEX", liq_other(WOODY_JEX, JEX)),
        ("WOODY/MEX", liq_other(WOODY_MEX, MEX)),
    ]:
        if value:
            total += value
            lines.append(f"• {name}: {value:.3f} EGLD (${value * usd:,.2f})")
        else:
            lines.append(f"• {name}: N/A")

    return lines, total, usd


def price():
    r = reserves(XEX)
    woody = r.get(WOODY, 0)
    wegld = r.get(WEGLD, 0)
    return wegld / woody if woody > 0 else None


def holders():
    try:
        return int(j(f"{MVX}/tokens/{WOODY}")["accounts"])
    except Exception:
        return None


def kb():
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("💰 Price", callback_data="p"),
            InlineKeyboardButton("💧 Liquidity", callback_data="l"),
        ],
        [
            InlineKeyboardButton("👥 Holders", callback_data="h")
        ],
        [
            InlineKeyboardButton("🟢 BUY xExchange", url="https://xexchange.com"),
            InlineKeyboardButton("🟢 BUY XOXNO", url="https://xoxno.com"),
        ],
        [
            InlineKeyboardButton("𝕏 Twitter", url=TWITTER)
        ],
    ])


def get_pair_state(pair_address):
    r = reserves(pair_address)
    return {
        "woody": r.get(WOODY, 0),
        "wegld": r.get(WEGLD, 0),
    }


def detect_swap(old_state, new_state):
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

    return None


def detect_real_liquidity_add(old_state, new_state):
    """
    Detectăm LP add REAL doar dacă:
    - crește rezerva de WOODY
    - crește rezerva de WEGLD
    - ambele diferențe sunt peste prag minim

    Asta elimină multe false alerts.
    """
    if not old_state or not new_state:
        return None

    delta_woody = new_state["woody"] - old_state["woody"]
    delta_wegld = new_state["wegld"] - old_state["wegld"]

    if delta_woody > 0 and delta_wegld > 0:
        if delta_woody >= MIN_LIQUIDITY_ADD_WOODY and delta_wegld >= MIN_LIQUIDITY_ADD_EGLD:
            return {
                "woody_added": delta_woody,
                "egld_added": delta_wegld,
                "new_woody_total": new_state["woody"],
                "new_wegld_total": new_state["wegld"],
            }

    return None


async def send_photo_alert(context: ContextTypes.DEFAULT_TYPE, image_name: str, message: str):
    base_dir = os.path.dirname(os.path.abspath(__file__))
    image_path = os.path.join(base_dir, image_name)

    targets = []
    if PRIVATE_CHAT_ID:
        targets.append(PRIVATE_CHAT_ID)
    if GROUP_CHAT_ID:
        targets.append(GROUP_CHAT_ID)

    if not targets:
        print("[WARN] No target chat IDs configured.")
        return

    for chat_id in targets:
        try:
            with open(image_path, "rb") as photo:
                await context.bot.send_photo(
                    chat_id=chat_id,
                    photo=photo,
                    caption=message
                )
            print(f"[OK] Sent photo alert to {chat_id}")
        except Exception as e:
            print(f"[photo alert error] {image_name}: {e}")


async def send_text_alert(context: ContextTypes.DEFAULT_TYPE, message: str):
    targets = []
    if PRIVATE_CHAT_ID:
        targets.append(PRIVATE_CHAT_ID)
    if GROUP_CHAT_ID:
        targets.append(GROUP_CHAT_ID)

    if not targets:
        print("[WARN] No target chat IDs configured.")
        return

    for chat_id in targets:
        try:
            await context.bot.send_message(chat_id=chat_id, text=message)
            print(f"[OK] Sent text alert to {chat_id}")
        except Exception as e:
            print(f"[text alert error] {e}")


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.message:
        await update.message.reply_text("WOODY Monitor Bot", reply_markup=kb())


async def status(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = (
        "✅ WOODY Monitor is running\n\n"
        f"Private alerts: {'YES' if PRIVATE_CHAT_ID else 'NO'}\n"
        f"Group alerts: {'YES' if GROUP_CHAT_ID else 'NO'}\n"
        f"Thresholds:\n"
        f"• WOODY >= {MIN_WOODY_ALERT}\n"
        f"• EGLD >= {MIN_EGLD_ALERT}\n"
        f"• BIG BUY >= {BIG_BUY_EGLD} EGLD\n"
        f"• BIG SELL >= {BIG_SELL_EGLD} EGLD\n"
        f"• REAL LP add >= {MIN_LIQUIDITY_ADD_WOODY} WOODY and {MIN_LIQUIDITY_ADD_EGLD} EGLD"
    )
    if update.message:
        await update.message.reply_text(text)


async def get_id(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.message:
        await update.message.reply_text(f"Chat ID: {update.effective_chat.id}")


async def btn(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    if not q:
        return

    await q.answer()

    if q.data == "l":
        lines, total, usd = all_liq()
        txt = "💧 Liquidity\n\n" + "\n".join(lines) + f"\n\nTOTAL: {total:.3f} EGLD (${total * usd:,.2f})"
    elif q.data == "p":
        p = price()
        txt = f"💰 Price: {p:.12f} EGLD / WOODY" if p else "N/A"
    elif q.data == "h":
        h = holders()
        txt = f"👥 Holders: {h if h is not None else 'N/A'}"
    else:
        txt = "N/A"

    await q.edit_message_text(txt, reply_markup=kb())


GREET = re.compile(r"\b(hi|hello|gm)\b", re.I)
SPAM = re.compile(r"airdrop|claim|seed|100x|double", re.I)


async def monitor_group_messages(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message:
        return

    t = update.message.text or ""

    if GREET.search(t):
        await update.message.reply_text("Hey! Welcome to WOODY 👋")

    if SPAM.search(t):
        try:
            await update.message.delete()
        except Exception:
            pass


async def welcome(update: Update, context: ContextTypes.DEFAULT_TYPE):
    cm = update.chat_member
    if cm.old_chat_member.status in ("left", "kicked"):
        try:
            await context.bot.send_message(
                update.effective_chat.id,
                f"Welcome {cm.new_chat_member.user.first_name}!"
            )
        except Exception as e:
            print(f"[welcome error] {e}")


async def check_swaps(context: ContextTypes.DEFAULT_TYPE):
    try:
        print("Checking swaps...")

        pairs = [
            ("xexchange", "WOODY/EGLD xExchange", XEX),
            ("onedx", "WOODY/EGLD OneDex", ONEDX),
        ]

        for key, label, address in pairs:
            print(f"Checking {label}...")

            current_state = get_pair_state(address)
            previous_state = LAST_SWAP_STATE.get(key)

            print(f"{label} previous: {previous_state}")
            print(f"{label} current: {current_state}")

            event = detect_swap(previous_state, current_state)

            print(f"{label} detected event: {event}")

            if event:
                if event["type"] == "BUY":
                    if event["egld"] >= BIG_BUY_EGLD:
                        message = (
                            f"🚀 WOODY BIG BUY\n\n"
                            f"💱 Pool: {label}\n"
                            f"🪙 Amount: {event['woody']:,.2f} WOODY\n"
                            f"💰 Value: {event['egld']:.6f} EGLD"
                        )
                        await send_photo_alert(context, "big_buy.png", message)
                    else:
                        message = (
                            f"🟢 WOODY BUY ALERT\n\n"
                            f"💱 Pool: {label}\n"
                            f"🪙 Amount: {event['woody']:,.2f} WOODY\n"
                            f"💰 Value: {event['egld']:.6f} EGLD"
                        )
                        await send_photo_alert(context, "buy.png", message)

                elif event["type"] == "SELL":
                    if event["egld"] >= BIG_SELL_EGLD:
                        message = (
                            f"💥 WOODY BIG SELL\n\n"
                            f"💱 Pool: {label}\n"
                            f"🪙 Amount: {event['woody']:,.2f} WOODY\n"
                            f"💰 Value: {event['egld']:.6f} EGLD"
                        )
                        await send_photo_alert(context, "big_sell.png", message)
                    else:
                        message = (
                            f"🔴 WOODY SELL ALERT\n\n"
                            f"💱 Pool: {label}\n"
                            f"🪙 Amount: {event['woody']:,.2f} WOODY\n"
                            f"💰 Value: {event['egld']:.6f} EGLD"
                        )
                        await send_photo_alert(context, "sell.png", message)

            LAST_SWAP_STATE[key] = current_state

    except Exception as e:
        print(f"[swap monitor error] {e}")


async def check_holders(context: ContextTypes.DEFAULT_TYPE):
    global LAST_HOLDERS_COUNT

    try:
        current_holders = holders()
        if current_holders is None:
            return

        if LAST_HOLDERS_COUNT is None:
            LAST_HOLDERS_COUNT = current_holders
            return

        if current_holders > LAST_HOLDERS_COUNT:
            diff = current_holders - LAST_HOLDERS_COUNT
            message = (
                f"👤 WOODY NEW HOLDER\n\n"
                f"Added holders: +{diff}\n"
                f"Total holders: {current_holders}"
            )
            await send_photo_alert(context, "new_holder.png", message)

        LAST_HOLDERS_COUNT = current_holders

    except Exception as e:
        print(f"[holders monitor error] {e}")


async def check_real_liquidity_added(context: ContextTypes.DEFAULT_TYPE):
    """
    Alertă doar pentru LP add real-ish:
    - cresc ambele rezerve
    - diferența depășește pragurile minime
    """
    try:
        pairs = [
            ("xexchange", "WOODY/EGLD xExchange", XEX),
            ("onedx", "WOODY/EGLD OneDex", ONEDX),
        ]

        usd = egld_usd()

        for key, label, address in pairs:
            current_state = get_pair_state(address)
            previous_state = LAST_LIQUIDITY_STATE.get(key)

            print(f"[LIQ] {label} previous: {previous_state}")
            print(f"[LIQ] {label} current: {current_state}")

            event = detect_real_liquidity_add(previous_state, current_state)

            print(f"[LIQ] {label} detected event: {event}")

            if event:
                estimated_total_value_egld = event["egld_added"] * 2
                estimated_total_value_usd = estimated_total_value_egld * usd

                message = (
                    f"💧 WOODY REAL LIQUIDITY ADDED\n\n"
                    f"💱 Pool: {label}\n"
                    f"🪙 Added WOODY: {event['woody_added']:,.2f}\n"
                    f"💰 Added EGLD: {event['egld_added']:.6f}\n"
                    f"📊 Est. total value: {estimated_total_value_egld:.3f} EGLD\n"
                    f"💵 Est. USD value: ${estimated_total_value_usd:,.2f}\n"
                    f"🏦 New pool reserves:\n"
                    f"• WOODY: {event['new_woody_total']:,.2f}\n"
                    f"• WEGLD: {event['new_wegld_total']:.6f}"
                )
                await send_photo_alert(context, "liquidity.png", message)

            LAST_LIQUIDITY_STATE[key] = current_state

    except Exception as e:
        print(f"[real liquidity monitor error] {e}")


def main():
    if not TOKEN:
        raise ValueError("TELEGRAM_BOT_TOKEN is missing from environment variables")

    app = Application.builder().token(TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("status", status))
    app.add_handler(CommandHandler("id", get_id))
    app.add_handler(CallbackQueryHandler(btn))
    app.add_handler(ChatMemberHandler(welcome, ChatMemberHandler.CHAT_MEMBER))
    app.add_handler(MessageHandler(filters.TEXT & filters.ChatType.GROUPS, monitor_group_messages))

    if app.job_queue is None:
        raise RuntimeError("JobQueue is not available. Make sure python-telegram-bot[job-queue] is installed.")

    app.job_queue.run_repeating(check_swaps, interval=30, first=10)
    app.job_queue.run_repeating(check_holders, interval=120, first=20)
    app.job_queue.run_repeating(check_real_liquidity_added, interval=60, first=30)

    print("WOODY Monitor Bot started...")
    app.run_polling(drop_pending_updates=True)


if __name__ == "__main__":
    main()
