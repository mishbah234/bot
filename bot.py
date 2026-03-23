import os
import json
import logging
import asyncio
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application, CommandHandler, CallbackQueryHandler,
    MessageHandler, filters, ConversationHandler,
)
from telegram.constants import ParseMode

# ──────────────────────────────────────────────
#  CONFIG
# ──────────────────────────────────────────────
TOKEN = os.environ.get("BOT_TOKEN")
RENDER_URL = os.environ.get("RENDER_EXTERNAL_URL")
PORT = int(os.environ.get("PORT", 10000))
# Comma-separated admin Telegram IDs, e.g. "123456,789012"
ADMIN_IDS = [
    int(x.strip()) for x in os.environ.get("ADMIN_IDS", "0").split(",") if x.strip()
]

# Channel chat IDs (bot must be admin in these channels)
CHANNEL_IDS = [
    int(os.environ.get("CHANNEL_ID_1", "-6097181868")),
    int(os.environ.get("CHANNEL_ID_2", "-8455891912")),
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

USERS_FILE = "users.json"
WAITING_BROADCAST = 1  # ConversationHandler state


# ──────────────────────────────────────────────
#  USER STORAGE
# ──────────────────────────────────────────────
def load_users() -> set:
    """Load stored user IDs from JSON file."""
    try:
        with open(USERS_FILE, "r") as f:
            return set(json.load(f))
    except (FileNotFoundError, json.JSONDecodeError):
        return set()


def save_user(user_id: int):
    """Add a user ID and persist to file."""
    users = load_users()
    if user_id not in users:
        users.add(user_id)
        with open(USERS_FILE, "w") as f:
            json.dump(list(users), f)
        logger.info(f"New user saved: {user_id} (total: {len(users)})")


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
        "✅ <b>Tiranga OFFICIAL LINK</b> 🔗\n"
        "\n"
        f"👉 <a href='{REG_LINK}'>🎰 Register Now — Tiranga</a>\n"
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
    "1️⃣ Register on Tiranga using the link\n"
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
            logger.info(f"User {user_id} status in {chat_id}: {member.status}")
            if member.status in ("left", "kicked"):
                return False
        except Exception as e:
            logger.error(f"Error checking channel {chat_id} for user {user_id}: {e}")
            return False
    return True


# ──────────────────────────────────────────────
#  HANDLERS
# ──────────────────────────────────────────────
async def start(update: Update, context):
    # Track user
    save_user(update.effective_user.id)

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
#  ADMIN COMMANDS
# ──────────────────────────────────────────────
async def stats_command(update: Update, context):
    """Show bot statistics (admin only)."""
    if update.effective_user.id not in ADMIN_IDS:
        return
    users = load_users()
    await update.message.reply_text(
        f"📊 <b>Bot Stats</b>\n\n"
        f"👥 Total users: <b>{len(users)}</b>",
        parse_mode=ParseMode.HTML,
    )


async def checkbot_command(update: Update, context):
    """Debug command to check if bot can access all channels (admin only)."""
    if update.effective_user.id not in ADMIN_IDS:
        return
    lines = ["🔍 <b>Channel Access Check</b>\n"]
    for i, chat_id in enumerate(CHANNEL_IDS, 1):
        try:
            chat = await context.bot.get_chat(chat_id)
            lines.append(f"✅ Channel {i}: <b>{chat.title}</b> (ID: <code>{chat_id}</code>)")
        except Exception as e:
            lines.append(f"❌ Channel {i}: ID <code>{chat_id}</code> — <b>{e}</b>")
    lines.append(f"\n📋 Configured IDs: <code>{CHANNEL_IDS}</code>")
    await update.message.reply_text("\n".join(lines), parse_mode=ParseMode.HTML)


async def broadcast_command(update: Update, context):
    """Start broadcast flow (admin only)."""
    if update.effective_user.id not in ADMIN_IDS:
        return ConversationHandler.END
    await update.message.reply_text(
        "📢 <b>Broadcast Mode</b>\n\n"
        "Send me the message you want to broadcast to all users.\n"
        "Send /cancel to abort.",
        parse_mode=ParseMode.HTML,
    )
    return WAITING_BROADCAST


async def broadcast_message(update: Update, context):
    """Receive the message and send it to all users."""
    users = load_users()
    if not users:
        await update.message.reply_text("❌ No users in the database yet.")
        return ConversationHandler.END

    sent, failed = 0, 0
    status_msg = await update.message.reply_text(
        f"📤 Broadcasting to <b>{len(users)}</b> users...",
        parse_mode=ParseMode.HTML,
    )

    for user_id in users:
        try:
            await update.message.copy_message(chat_id=user_id)
            sent += 1
        except Exception as e:
            logger.warning(f"Failed to send to {user_id}: {e}")
            failed += 1
        # Small delay to avoid hitting Telegram rate limits
        await asyncio.sleep(0.05)

    await status_msg.edit_text(
        f"✅ <b>Broadcast Complete!</b>\n\n"
        f"📨 Sent: <b>{sent}</b>\n"
        f"❌ Failed: <b>{failed}</b>",
        parse_mode=ParseMode.HTML,
    )
    return ConversationHandler.END


async def cancel_broadcast(update: Update, context):
    """Cancel the broadcast."""
    await update.message.reply_text("❌ Broadcast cancelled.")
    return ConversationHandler.END


# ──────────────────────────────────────────────
#  MAIN
# ──────────────────────────────────────────────
def main():
    if not TOKEN:
        raise ValueError("Set the BOT_TOKEN environment variable!")

    app = Application.builder().token(TOKEN).build()

    # Admin broadcast conversation handler
    broadcast_handler = ConversationHandler(
        entry_points=[CommandHandler("broadcast", broadcast_command)],
        states={
            WAITING_BROADCAST: [
                MessageHandler(
                    filters.ALL & ~filters.COMMAND,
                    broadcast_message,
                )
            ],
        },
        fallbacks=[CommandHandler("cancel", cancel_broadcast)],
    )
    app.add_handler(broadcast_handler)

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("stats", stats_command))
    app.add_handler(CommandHandler("checkbot", checkbot_command))
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
