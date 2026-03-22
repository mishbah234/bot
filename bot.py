import os
import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, MessageHandler, filters
from telegram.constants import ParseMode

# ──────────────────────────────────────────────
#  CONFIG
# ──────────────────────────────────────────────
TOKEN = os.environ.get("BOT_TOKEN")
RENDER_URL = os.environ.get("RENDER_EXTERNAL_URL")
PORT = int(os.environ.get("PORT", 10000))

# Channel chat IDs (bot must be admin in these channels)
CHANNEL_IDS = [
    int(os.environ.get("CHANNEL_ID_1", "-1002169640991")),
    int(os.environ.get("CHANNEL_ID_2", "-1002111582843")),
]

# Channel invite links
CHANNEL_URLS = [
    os.environ.get("CHANNEL_URL_1", "https://t.me/+Yr_j3b9zwnRiMjNl"),
    os.environ.get("CHANNEL_URL_2", "https://t.me/+uGeLDa05s7M4NjFl"),
]

# Registration link
REG_LINK = os.environ.get(
    "REG_LINK",
    "https://www.tgdream16.com/#/register?invitationCode=632738378641",
)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


# ──────────────────────────────────────────────
#  MESSAGES
# ──────────────────────────────────────────────
def welcome_text():
    return (
        "💰 <b>Claim Your Free UPI Cash!</b> 💰\n"
        "\n"
        "━━━━━━━━━━━━━━━━━━━━━━\n"
        "\n"
        "🎉 <b>Welcome!</b> You're just 2 steps away\n"
        "from claiming your reward!\n"
        "\n"
        "📌 <b>Step 1:</b> Join <b>BOTH</b> channels below 👇\n"
        "\n"
        "━━━━━━━━━━━━━━━━━━━━━━\n"
        "\n"
        f"👉 <a href='{CHANNEL_URLS[0]}'>🌟 Join Channel 1</a>\n"
        "\n"
        f"👉 <a href='{CHANNEL_URLS[1]}'>🌟 Join Channel 2</a>\n"
        "\n"
        "━━━━━━━━━━━━━━━━━━━━━━\n"
        "\n"
        "📌 <b>Step 2:</b> After joining <b>both</b> channels,\n"
        "tap the ✅ button below to verify!\n"
    )


def verified_text():
    return (
        "✅ <b>Verification Successful!</b>\n"
        "\n"
        "━━━━━━━━━━━━━━━━━━━━━━\n"
        "\n"
        "⚠️ <b>MUST REGISTER WITH OFFICIAL</b>\n"
        "<b>LINK FOR GIFTCODES ACCESS</b> ⚠️\n"
        "\n"
        "━━━━━━━━━━━━━━━━━━━━━━\n"
        "\n"
        "✅ <b>82 BET OFFICIAL LINK</b> 🔗\n"
        "\n"
        f"👉 <a href='{REG_LINK}'>🎰 Register Now — 82 BET</a>\n"
        "\n"
        "━━━━━━━━━━━━━━━━━━━━━━\n"
        "\n"
        "👆 Register first, then click below 👇\n"
    )


def not_joined_text():
    return (
        "❌ <b>Verification Failed!</b>\n"
        "\n"
        "You haven't joined <b>both</b> channels yet!\n"
        "\n"
        f"👉 <a href='{CHANNEL_URLS[0]}'>🌟 Join Channel 1</a>\n"
        f"👉 <a href='{CHANNEL_URLS[1]}'>🌟 Join Channel 2</a>\n"
        "\n"
        "After joining, tap ✅ Verify again 👇\n"
    )


WITHDRAW_TEXT = (
    "💰 <b>Withdraw Money</b>\n"
    "\n"
    "━━━━━━━━━━━━━━━━━━━━━━\n"
    "\n"
    "✅ To withdraw your money:\n"
    "\n"
    "1️⃣ Register on 82 BET using the link\n"
    "2️⃣ Complete your profile\n"
    "3️⃣ Claim your giftcode reward\n"
    "4️⃣ Withdraw to your UPI 💸\n"
    "\n"
    "━━━━━━━━━━━━━━━━━━━━━━\n"
    "\n"
    "🌟 <b>Good luck & enjoy!</b> 🌟\n"
)


# ──────────────────────────────────────────────
#  KEYBOARDS
# ──────────────────────────────────────────────
def get_welcome_keyboard():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("🌟 Join Channel 1", url=CHANNEL_URLS[0])],
        [InlineKeyboardButton("🌟 Join Channel 2", url=CHANNEL_URLS[1])],
        [InlineKeyboardButton("✅ I've Joined Both — Verify", callback_data="verify_join")],
    ])


def get_retry_keyboard():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("🌟 Join Channel 1", url=CHANNEL_URLS[0])],
        [InlineKeyboardButton("🌟 Join Channel 2", url=CHANNEL_URLS[1])],
        [InlineKeyboardButton("✅ I've Joined Both — Verify", callback_data="verify_join")],
    ])


def get_verified_keyboard():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("🎰 Register — 82 BET", url=REG_LINK)],
        [InlineKeyboardButton("💸 Withdraw Money", callback_data="withdraw_money")],
    ])


# ──────────────────────────────────────────────
#  MEMBERSHIP CHECK
# ──────────────────────────────────────────────
async def check_membership(bot, user_id):
    """Check if user is a member of ALL required channels."""
    for chat_id in CHANNEL_IDS:
        try:
            member = await bot.get_chat_member(chat_id=chat_id, user_id=user_id)
            if member.status in ("left", "kicked"):
                return False
        except Exception as e:
            logger.error(f"Error checking channel {chat_id}: {e}")
            return False
    return True


# ──────────────────────────────────────────────
#  HANDLERS
# ──────────────────────────────────────────────
async def start(update: Update, context):
    await update.message.reply_text(
        welcome_text(),
        parse_mode=ParseMode.HTML,
        reply_markup=get_welcome_keyboard(),
        disable_web_page_preview=True,
    )


async def verify_callback(update: Update, context):
    query = update.callback_query
    await query.answer()

    is_member = await check_membership(context.bot, query.from_user.id)

    if is_member:
        await query.edit_message_text(
            verified_text(),
            parse_mode=ParseMode.HTML,
            reply_markup=get_verified_keyboard(),
            disable_web_page_preview=True,
        )
    else:
        await query.edit_message_text(
            not_joined_text(),
            parse_mode=ParseMode.HTML,
            reply_markup=get_retry_keyboard(),
            disable_web_page_preview=True,
        )


async def withdraw_callback(update: Update, context):
    query = update.callback_query
    await query.answer()
    await query.edit_message_text(
        WITHDRAW_TEXT,
        parse_mode=ParseMode.HTML,
    )


async def forwarded_msg(update: Update, context):
    """Forward a channel message to the bot to get its chat ID."""
    fwd = update.message.forward_origin
    if fwd and hasattr(fwd, "chat"):
        chat = fwd.chat
        await update.message.reply_text(
            f"📋 <b>Channel Info</b>\n\n"
            f"Name: <b>{chat.title}</b>\n"
            f"Chat ID: <code>{chat.id}</code>\n",
            parse_mode=ParseMode.HTML,
        )


# ──────────────────────────────────────────────
#  MAIN
# ──────────────────────────────────────────────
def main():
    if not TOKEN:
        raise ValueError("Set the BOT_TOKEN environment variable!")

    app = Application.builder().token(TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CallbackQueryHandler(verify_callback, pattern="^verify_join$"))
    app.add_handler(CallbackQueryHandler(withdraw_callback, pattern="^withdraw_money$"))
    app.add_handler(MessageHandler(filters.FORWARDED, forwarded_msg))

    if RENDER_URL:
        webhook_url = f"{RENDER_URL}/webhook"
        logger.info(f"Starting webhook → {webhook_url}")
        app.run_webhook(
            listen="0.0.0.0",
            port=PORT,
            url_path="/webhook",
            webhook_url=webhook_url,
        )
    else:
        logger.info("Polling mode (local dev)")
        app.run_polling(drop_pending_updates=True)


if __name__ == "__main__":
    main()
