import os
import json
import logging
import asyncio
from datetime import datetime
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
    int(x.strip()) for x in os.environ.get("ADMIN_IDS", "8455891912,6097181868").split(",") if x.strip()
]

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

USERS_FILE = "users.json"
WAITING_BROADCAST = 1  # ConversationHandler state


# ──────────────────────────────────────────────
#  USER STORAGE
# ──────────────────────────────────────────────
def load_users() -> dict:
    """Load stored users from JSON file. Returns dict of user_id -> details."""
    try:
        with open(USERS_FILE, "r") as f:
            data = json.load(f)
        # Migrate from old list format [id, id, ...] to new dict format
        if isinstance(data, list):
            migrated = {}
            for uid in data:
                migrated[str(uid)] = {"name": "Unknown", "username": None, "joined": None}
            with open(USERS_FILE, "w") as f:
                json.dump(migrated, f, indent=2)
            return migrated
        return data
    except (FileNotFoundError, json.JSONDecodeError):
        return {}


def load_user_ids() -> set:
    """Load just the user IDs as a set of ints."""
    users = load_users()
    return {int(uid) for uid in users.keys()}


def save_user(user):
    """Save user with details. Accepts a Telegram User object or just an int ID."""
    users = load_users()
    if hasattr(user, "id"):
        uid = str(user.id)
        name = user.full_name or "Unknown"
        username = user.username
    else:
        uid = str(user)
        name = "Unknown"
        username = None

    if uid not in users:
        users[uid] = {
            "name": name,
            "username": username,
            "joined": datetime.now().strftime("%Y-%m-%d %H:%M"),
        }
        with open(USERS_FILE, "w") as f:
            json.dump(users, f, indent=2)
        logger.info(f"New user saved: {uid} - {name} (total: {len(users)})")
    elif users[uid]["name"] == "Unknown" and hasattr(user, "full_name"):
        # Update name if it was previously unknown
        users[uid]["name"] = user.full_name or "Unknown"
        users[uid]["username"] = user.username
        with open(USERS_FILE, "w") as f:
            json.dump(users, f, indent=2)


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
    # Track user with details
    save_user(update.effective_user)

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

    try:
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
    except Exception:
        pass  # Message already shows the same content


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
#  ADMIN PANEL
# ──────────────────────────────────────────────
def get_admin_keyboard():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("📊 Stats", callback_data="admin_stats"),
         InlineKeyboardButton("👥 Users", callback_data="admin_users")],
        [InlineKeyboardButton("📢 Broadcast", callback_data="admin_broadcast"),
         InlineKeyboardButton("🔍 Check Channels", callback_data="admin_checkbot")],
    ])


def get_back_keyboard():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("◀️ Back to Admin Panel", callback_data="admin_panel")],
    ])


ADMIN_PANEL_TEXT = (
    "⚙️ <b>Admin Panel</b>\n"
    "\n"
    "━━━━━━━━━━━━━━━━━━━━━━\n"
    "\n"
    "Choose an option below 👇\n"
)


async def admin_command(update: Update, context):
    """Show admin panel (admin only)."""
    if update.effective_user.id not in ADMIN_IDS:
        return
    await update.message.reply_text(
        ADMIN_PANEL_TEXT,
        parse_mode=ParseMode.HTML,
        reply_markup=get_admin_keyboard(),
    )


async def admin_panel_callback(update: Update, context):
    """Handle admin panel button clicks."""
    query = update.callback_query
    if query.from_user.id not in ADMIN_IDS:
        await query.answer("⛔ Admin only!", show_alert=True)
        return

    action = query.data
    await query.answer()

    if action == "admin_panel":
        await query.edit_message_text(
            ADMIN_PANEL_TEXT,
            parse_mode=ParseMode.HTML,
            reply_markup=get_admin_keyboard(),
        )
        return

    if action == "admin_stats":
        users = load_users()
        await query.edit_message_text(
            f"📊 <b>Bot Stats</b>\n\n"
            f"👥 Total users: <b>{len(users)}</b>",
            parse_mode=ParseMode.HTML,
            reply_markup=get_back_keyboard(),
        )

    elif action == "admin_users":
        users = load_users()
        if not users:
            await query.edit_message_text(
                "❌ No users yet.",
                reply_markup=get_back_keyboard(),
            )
            return
        lines = [f"👥 <b>All Users ({len(users)})</b>\n"]
        for i, (uid, info) in enumerate(users.items(), 1):
            name = info.get("name", "Unknown")
            username = info.get("username")
            joined = info.get("joined", "N/A")
            uname_str = f" @{username}" if username else ""
            lines.append(f"{i}. <b>{name}</b>{uname_str}\n   ID: <code>{uid}</code> | Joined: {joined}")
        text = "\n".join(lines)
        # Telegram message limit is 4096 chars
        if len(text) > 4000:
            text = text[:4000] + "\n\n... (truncated)"
        await query.edit_message_text(
            text,
            parse_mode=ParseMode.HTML,
            reply_markup=get_back_keyboard(),
        )

    elif action == "admin_broadcast":
        await query.edit_message_text(
            "📢 <b>Broadcast Mode</b>\n\n"
            "Send me the message you want to broadcast to all users.\n"
            "Send /cancel to abort.",
            parse_mode=ParseMode.HTML,
        )
        # Set conversation state for broadcast
        context.user_data["awaiting_broadcast"] = True

    elif action == "admin_checkbot":
        lines = ["🔍 <b>Channel Access Check</b>\n"]
        for i, chat_id in enumerate(CHANNEL_IDS, 1):
            try:
                chat = await context.bot.get_chat(chat_id)
                lines.append(f"✅ Channel {i}: <b>{chat.title}</b> (ID: <code>{chat_id}</code>)")
            except Exception as e:
                lines.append(f"❌ Channel {i}: ID <code>{chat_id}</code> — <b>{e}</b>")
        lines.append(f"\n📋 Configured IDs: <code>{CHANNEL_IDS}</code>")
        await query.edit_message_text(
            "\n".join(lines),
            parse_mode=ParseMode.HTML,
            reply_markup=get_back_keyboard(),
        )


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


async def users_command(update: Update, context):
    """Show all users with details (admin only)."""
    if update.effective_user.id not in ADMIN_IDS:
        return
    users = load_users()
    if not users:
        await update.message.reply_text("❌ No users yet.")
        return

    lines = [f"👥 <b>All Users ({len(users)})</b>\n"]
    for i, (uid, info) in enumerate(users.items(), 1):
        name = info.get("name", "Unknown")
        username = info.get("username")
        joined = info.get("joined", "N/A")
        uname_str = f" @{username}" if username else ""
        lines.append(f"{i}. <b>{name}</b>{uname_str}\n   ID: <code>{uid}</code> | Joined: {joined}")

    # Telegram message limit is 4096 chars, split if needed
    text = "\n".join(lines)
    if len(text) <= 4096:
        await update.message.reply_text(text, parse_mode=ParseMode.HTML)
    else:
        # Send in chunks
        chunk = []
        chunk_len = 0
        for line in lines:
            if chunk_len + len(line) + 1 > 4000:
                await update.message.reply_text("\n".join(chunk), parse_mode=ParseMode.HTML)
                chunk = []
                chunk_len = 0
            chunk.append(line)
            chunk_len += len(line) + 1
        if chunk:
            await update.message.reply_text("\n".join(chunk), parse_mode=ParseMode.HTML)


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
    users = load_user_ids()
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
            await context.bot.copy_message(
                chat_id=user_id,
                from_chat_id=update.message.chat_id,
                message_id=update.message.message_id,
            )
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
    app.add_handler(CommandHandler("admin", admin_command))
    app.add_handler(CommandHandler("stats", stats_command))
    app.add_handler(CommandHandler("users", users_command))
    app.add_handler(CommandHandler("checkbot", checkbot_command))
    app.add_handler(CallbackQueryHandler(admin_panel_callback, pattern="^admin_"))
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
