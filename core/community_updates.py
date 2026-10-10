"""Opt-in Telegram community welcome and 09:00 Berlin market briefing."""
import asyncio
import html
import logging
import os
from datetime import datetime, time
from zoneinfo import ZoneInfo

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import CommandHandler, ContextTypes, MessageHandler, filters

log = logging.getLogger(__name__)
BERLIN = ZoneInfo("Europe/Berlin")
SITE = "https://www.woodyvmx.com"
X_URL = "https://x.com/WOODY_EX"
BUY_URL = "https://www.woodyvmx.com"
TOKEN = "WOODY-5f9d9c"


def enabled(name):
    return os.getenv(name, "false").strip().lower() in ("1", "true", "yes", "on")


def target_chat():
    return os.getenv("TELEGRAM_GROUP_CHAT_ID", "").strip()


def is_target(chat):
    return bool(chat and target_chat() and str(chat.id) == target_chat() and chat.type in ("group", "supergroup"))


def welcome_text(name):
    safe_name = html.escape(name[:80])
    return (
        f"🌲 <b>Welcome to the WOODY community, {safe_name}!</b> 💙\n\n"
        "WOODY is a community meme token on MultiversX.\n"
        f"🪙 Token: <code>{TOKEN}</code>\n"
        f"🌐 Website: {SITE}\n"
        f"🐦 X: {X_URL}\n"
        "🛒 Buy WOODY: use the Buy WOODY section on our website.\n\n"
        "Enjoy your stay! 🌲💙"
    )


def welcome_keyboard():
    return InlineKeyboardMarkup([[
        InlineKeyboardButton("🌐 Website", url=SITE),
        InlineKeyboardButton("🛒 Buy WOODY", url=BUY_URL),
    ]])


async def welcome_members(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not enabled("ENABLE_COMMUNITY_WELCOME") or not is_target(update.effective_chat):
        return
    message = update.effective_message
    if not message or not message.new_chat_members:
        return
    for member in message.new_chat_members:
        if member.is_bot:
            continue
        await message.reply_text(
            welcome_text(member.full_name),
            parse_mode="HTML",
            reply_markup=welcome_keyboard(),
            disable_web_page_preview=True,
        )


async def welcome_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_target(update.effective_chat):
        return
    user = update.effective_user
    if not user or not (await context.bot.get_chat_member(update.effective_chat.id, user.id)).status in ("administrator", "creator"):
        return
    await update.effective_message.reply_text(
        welcome_text("everyone"), parse_mode="HTML",
        reply_markup=welcome_keyboard(), disable_web_page_preview=True,
    )


def build_brief(egld, woody, holders, liquidity):
    date = datetime.now(BERLIN).strftime("%d %b %Y")
    egld_line = f"${egld:.4f}" if egld and egld > 0 else "Unavailable"
    woody_line = f"${woody:.10f}" if woody and woody > 0 else "Unavailable"
    holders_line = str(holders) if holders and holders > 0 else "Unavailable"
    liq_line = f"${liquidity:,.2f} (estimated)" if liquidity is not None else "Unavailable"
    return (
        f"☀️ WOODY Morning Market Brief | {date}\n\n"
        f"🔷 EGLD price: {egld_line}\n"
        f"🌲 WOODY price: {woody_line}\n"
        f"👥 WOODY holders: {holders_line}\n"
        f"💧 WOODY pool liquidity: {liq_line}\n\n"
        "📊 Market pulse: A snapshot of current available indicators, not a price prediction. "
        "Watch price, activity and liquidity together; short-term movements can be volatile.\n\n"
        f"🪙 {TOKEN} | {SITE}"
    )


async def make_brief():
    # Existing project price/holders/liquidity functions are synchronous HTTP calls.
    from core import multiversx as m
    def collect():
        egld = m.get_egld_usd()
        best = m.get_best_price() or {}
        woody = m.safe_float(best.get("price_usd"))
        holders = m.get_holders_count()
        liquidity = m.build_public_liquidity(woody, m.get_public_pool_reserves())
        return build_brief(egld, woody, holders, liquidity.get("totalUsd"))
    return await asyncio.to_thread(collect)


async def morning_job(context: ContextTypes.DEFAULT_TYPE):
    if not enabled("ENABLE_MORNING_BRIEF") or not target_chat():
        return
    from core import multiversx as m
    date = datetime.now(BERLIN).date().isoformat()
    state_file = "data/community_morning_brief.json"
    state = m.read_json_file(state_file, {})
    if state.get("last_sent_date") == date:
        return
    try:
        message = await make_brief()
        await context.bot.send_message(chat_id=target_chat(), text=message, disable_web_page_preview=True)
        m.write_json_file(state_file, {"last_sent_date": date})
    except Exception:
        log.exception("Morning brief failed; retry only on next scheduled run")


async def morning_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_target(update.effective_chat):
        return
    user = update.effective_user
    if not user or (await context.bot.get_chat_member(update.effective_chat.id, user.id)).status not in ("administrator", "creator"):
        return
    try:
        await update.effective_message.reply_text(await make_brief(), disable_web_page_preview=True)
    except Exception:
        log.exception("Manual morning brief failed")
        await update.effective_message.reply_text("Market data is temporarily unavailable.")


def register(app):
    app.add_handler(MessageHandler(filters.StatusUpdate.NEW_CHAT_MEMBERS, welcome_members))
    app.add_handler(CommandHandler("welcome", welcome_command))
    app.add_handler(CommandHandler("morning", morning_command))
    if app.job_queue is None:
        raise RuntimeError("JobQueue is required for morning briefing")
    app.job_queue.run_daily(morning_job, time=time(hour=9, minute=0, tzinfo=BERLIN), name="woody_morning_berlin")
