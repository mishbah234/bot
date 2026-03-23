import os
import json
import logging
import asyncio
from datetime import datetime
from telegram import Update, KeyboardButton, ReplyKeyboardMarkup, InlineKeyboardButton, InlineKeyboardMarkup
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
BALANCE_FILE = "balance.json"
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
#  BALANCE & REFERRAL SYSTEM
# ──────────────────────────────────────────────
def load_balance_data() -> dict:
    """Load balance and referral data."""
    try:
        with open(BALANCE_FILE, "r") as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return {
            "config": {"joining_bonus": 2, "referral_bonus": 3, "min_withdrawal": 30, "max_daily_withdrawals": 1},
            "users": {}
        }


def save_balance_data(data: dict) -> None:
    """Save balance and referral data."""
    with open(BALANCE_FILE, "w") as f:
        json.dump(data, f, indent=2)


def get_user_balance(user_id: str) -> dict:
    """Get user's balance data."""
    data = load_balance_data()
    uid = str(user_id)
    if uid not in data["users"]:
        data["users"][uid] = {
            "balance": 0,
            "referrals": [],
            "withdrawals": [],
            "last_withdrawal": None
        }
        save_balance_data(data)
    return data["users"][uid]


def add_balance(user_id: str, amount: float, reason: str = "bonus") -> None:
    """Add balance to user."""
    data = load_balance_data()
    uid = str(user_id)
    if uid not in data["users"]:
        data["users"][uid] = {"balance": 0, "referrals": [], "withdrawals": [], "last_withdrawal": None}
    data["users"][uid]["balance"] = data["users"][uid].get("balance", 0) + amount
    logger.info(f"Added ₹{amount} to user {uid} ({reason})")
    save_balance_data(data)


def subtract_balance(user_id: str, amount: float) -> bool:
    """Subtract balance (for withdrawals). Returns True if successful."""
    data = load_balance_data()
    uid = str(user_id)
    if uid not in data["users"]:
        return False
    if data["users"][uid].get("balance", 0) >= amount:
        data["users"][uid]["balance"] -= amount
        save_balance_data(data)
        return True
    return False


def add_referral(referrer_id: str, referred_id: str) -> None:
    """Add referral relationship."""
    data = load_balance_data()
    referrer_uid = str(referrer_id)
    referred_uid = str(referred_id)
    
    if referrer_uid not in data["users"]:
        data["users"][referrer_uid] = {"balance": 0, "referrals": [], "withdrawals": [], "last_withdrawal": None}
    
    if referred_uid not in data["users"][referrer_uid]["referrals"]:
        data["users"][referrer_uid]["referrals"].append(referred_uid)
        # Add referral bonus
        bonus = data["config"]["referral_bonus"]
        data["users"][referrer_uid]["balance"] = data["users"][referrer_uid].get("balance", 0) + bonus
        logger.info(f"Referral registered: {referrer_uid} → {referred_uid}, bonus ₹{bonus}")
        save_balance_data(data)


def can_withdraw(user_id: str) -> bool:
    """Check if user can withdraw today."""
    data = load_balance_data()
    uid = str(user_id)
    user_data = data["users"].get(uid)
    if not user_data:
        return False
    
    last_withdraw = user_data.get("last_withdrawal")
    if not last_withdraw:
        return True
    
    try:
        last_date = datetime.strptime(last_withdraw, "%Y-%m-%d").date()
        today = datetime.now().date()
        return last_date < today
    except:
        return True


def record_withdrawal(user_id: str, amount: float) -> None:
    """Record withdrawal transaction."""
    data = load_balance_data()
    uid = str(user_id)
    if uid in data["users"]:
        data["users"][uid]["withdrawals"].append({
            "amount": amount,
            "date": datetime.now().strftime("%Y-%m-%d %H:%M")
        })
        data["users"][uid]["last_withdrawal"] = datetime.now().strftime("%Y-%m-%d")
        save_balance_data(data)


# ──────────────────────────────────────────────
#  MESSAGES
# ──────────────────────────────────────────────
def welcome_text():
    return (
        "🎉 <b>Welcome to TG Dream!</b> 🎉\n"
        "\n"
        "━━━━━━━━━━━━━━━━━━━━━━\n"
        "\n"
        "💰 Earn money by joining & referring!\n"
        "\n"
        "📌 <b>Quick Start:</b>\n"
        "1️⃣  Join both channels (links below)\n"
        "2️⃣  Get ₹2 joining bonus instantly\n"
        "3️⃣  Invite friends & earn ₹3 per person\n"
        "4️⃣  Withdraw when you reach ₹30\n"
        "\n"
        "━━━━━━━━━━━━━━━━━━━━━━\n"
        "\n"
        "🔗 <a href='{channel1}'>Join Channel 1</a>  •  <a href='{channel2}'>Join Channel 2</a>\n"
        "\n"
        "Once joined, tap \"✅ Verify\" below 👇\n"
    ).format(channel1=CHANNEL_URLS[0], channel2=CHANNEL_URLS[1])


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
    return ReplyKeyboardMarkup([
        [KeyboardButton("✅ Verify Both Channels")],
    ], resize_keyboard=True)


def get_retry_keyboard():
    return ReplyKeyboardMarkup([
        [KeyboardButton("✅ Try Verifying Again")],
    ], resize_keyboard=True)


def get_verified_keyboard(user_id=None):
    buttons = [
        [KeyboardButton("💰 Balance"), KeyboardButton("🔗 Referral Link")],
        [KeyboardButton("💸 Withdraw"), KeyboardButton("👥 My Referrals")],
        [KeyboardButton("⚙️ Settings"), KeyboardButton("📞 Help")],
    ]
    if user_id and user_id in ADMIN_IDS:
        buttons.append([KeyboardButton("⚙️ Admin Panel")])
    return ReplyKeyboardMarkup(buttons, resize_keyboard=True)


def get_back_keyboard():
    return ReplyKeyboardMarkup([
        [KeyboardButton("◀️ Back")],
    ], resize_keyboard=True)


ADMIN_PANEL_TEXT = (
    "⚙️ <b>Admin Panel</b>\n"
    "\n"
    "━━━━━━━━━━━━━━━━━━━━━━\n"
    "\n"
    "Choose an option below 👇\n"
)



async def start(update: Update, context):
    """Start command - handles referrals and welcome."""
    user_id = update.effective_user.id
    save_user(update.effective_user)
    
    # Check if this user was referred
    if context.args:
        ref_code = context.args[0]
        if ref_code.startswith("ref_"):
            try:
                referrer_id = ref_code.split("_")[1]
                # Add referral bonus only if not already referred
                user_balance = get_user_balance(user_id)
                if referrer_id not in user_balance.get("referrals", []):
                    add_referral(referrer_id, user_id)
                    # Get joining bonus
                    data = load_balance_data()
                    joining_bonus = data["config"]["joining_bonus"]
                    add_balance(str(user_id), joining_bonus, "joining_bonus")
                    
                    await update.message.reply_text(
                        f"🎉 <b>Welcome!</b>\n\n"
                        f"You were referred by a friend!\n"
                        f"💵 <b>₹{joining_bonus} bonus added!</b>\n"
                        f"(Your friend also earned ₹3)\n\n"
                        "Now verify to continue →",
                        parse_mode=ParseMode.HTML,
                        reply_markup=get_welcome_keyboard(),
                        disable_web_page_preview=True,
                    )
                    return
            except:
                pass
    
    await update.message.reply_text(
        welcome_text(),
        parse_mode=ParseMode.HTML,
        reply_markup=get_welcome_keyboard(),
        disable_web_page_preview=True,
    )

def get_purge_keyboard():
    """Confirmation keyboard for purge operation."""
    return ReplyKeyboardMarkup([
        [KeyboardButton("✅ Yes, Purge"), KeyboardButton("❌ Cancel")],
    ], resize_keyboard=True)


def get_delete_all_keyboard():
    """Confirmation keyboard for delete all operation."""
    return ReplyKeyboardMarkup([
        [KeyboardButton("⚠️ Yes Delete ALL"), KeyboardButton("❌ Cancel")],
    ], resize_keyboard=True)


def get_analytics_summary() -> str:
    """Generate analytics summary."""
    from datetime import datetime as dt, timedelta
    
    users = load_users()
    if not users:
        return "📈 <b>Analytics</b>\n\nNo user data yet."
    
    # Parse join dates
    join_dates = []
    today = dt.now().date()
    last_7_days = 0
    last_30_days = 0
    
    for uid, info in users.items():
        joined_str = info.get("joined")
        if joined_str:
            try:
                joined_date = dt.strptime(joined_str, "%Y-%m-%d %H:%M").date()
                join_dates.append(joined_date)
                
                days_diff = (today - joined_date).days
                if days_diff <= 7:
                    last_7_days += 1
                if days_diff <= 30:
                    last_30_days += 1
            except:
                pass
    
    # Count unknown users (haven't updated profile)
    unknown_count = sum(1 for info in users.values() if info.get("name") == "Unknown")
    
    # Build summary
    lines = [
        "📈 <b>Analytics</b>\n",
        "━━━━━━━━━━━━━━━━━━━━━━\n",
        f"👥 Total Users: <b>{len(users)}</b>",
        f"🆕 Last 7 Days: <b>{last_7_days}</b>",
        f"📅 Last 30 Days: <b>{last_30_days}</b>",
        f"❓ Unknown Users: <b>{unknown_count}</b>",
        f"✅ Registered: <b>{len(users) - unknown_count}</b>",
    ]
    
    return "\n".join(lines)


def purge_inactive_users(days: int = 30) -> tuple:
    """Remove users who joined more than 'days' ago and are still unknown.
    Returns (purged_count, remaining_count)"""
    from datetime import datetime as dt
    
    users = load_users()
    today = dt.now().date()
    purged = 0
    
    to_remove = []
    for uid, info in users.items():
        joined_str = info.get("joined")
        if joined_str:
            try:
                joined_date = dt.strptime(joined_str, "%Y-%m-%d %H:%M").date()
                days_old = (today - joined_date).days
                
                # Remove if: older than threshold AND still unknown (not verified)
                if days_old >= days and info.get("name") == "Unknown":
                    to_remove.append(uid)
            except:
                pass
    
    for uid in to_remove:
        del users[uid]
        purged += 1
    
    if purged > 0:
        with open(USERS_FILE, "w") as f:
            json.dump(users, f, indent=2)
    
    return purged, len(users)


def delete_all_users() -> None:
    """Delete all users from the database."""
    with open(USERS_FILE, "w") as f:
        json.dump({}, f, indent=2)
    logger.info("All users deleted!")


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

    elif action == "admin_analytics":
        await query.edit_message_text(
            get_analytics_summary(),
            parse_mode=ParseMode.HTML,
            reply_markup=get_back_keyboard(),
        )

    elif action == "admin_export":
        users = load_users()
        export_lines = ["user_id,name,username,joined"]
        for uid, info in users.items():
            name = info.get("name", "Unknown").replace(",", ";")
            username = info.get("username") or ""
            joined = info.get("joined", "N/A")
            export_lines.append(f"{uid},{name},{username},{joined}")
        
        csv_content = "\n".join(export_lines)
        
        # Save to file
        export_file = "users_export.csv"
        with open(export_file, "w", encoding="utf-8") as f:
            f.write(csv_content)
        
        # Send file
        try:
            with open(export_file, "rb") as f:
                await context.bot.send_document(
                    chat_id=query.from_user.id,
                    document=f,
                    caption=f"📄 User Export\n\n✅ {len(users)} users exported to CSV",
                    parse_mode=ParseMode.HTML,
                )
            await query.answer("📤 File sent to your DM!", show_alert=False)
        except Exception as e:
            await query.answer(f"❌ Error: {e}", show_alert=True)

    elif action == "admin_purge":
        await query.edit_message_text(
            "🗑️ <b>Purge Inactive Users</b>\n\n"
            "This will delete users who:\n"
            "• Joined more than 30 days ago\n"
            "• Haven't completed registration (still 'Unknown')\n\n"
            "Are you sure?",
            parse_mode=ParseMode.HTML,
            reply_markup=get_purge_keyboard(),
        )

    elif action == "admin_purge_confirm":
        purged, remaining = purge_inactive_users(days=30)
        await query.edit_message_text(
            f"✅ <b>Purge Complete!</b>\n\n"
            f"🗑️ Deleted: <b>{purged}</b> inactive users\n"
            f"👥 Remaining: <b>{remaining}</b> users",
            parse_mode=ParseMode.HTML,
            reply_markup=get_back_keyboard(),
        )
        logger.info(f"Purged {purged} inactive users. {remaining} remaining.")

    elif action == "admin_delete_confirm":
        await query.edit_message_text(
            "⚠️ <b>DELETE ALL USERS</b>\n\n"
            "This will <b>permanently delete</b> ALL user data!\n"
            "This action <b>cannot be undone</b>.\n\n"
            "Are you absolutely sure?",
            parse_mode=ParseMode.HTML,
            reply_markup=get_delete_all_keyboard(),
        )

    elif action == "admin_delete_all_confirm":
        delete_all_users()
        await query.edit_message_text(
            "⚠️ <b>All users deleted!</b>\n\n"
            "The database is now empty.",
            parse_mode=ParseMode.HTML,
            reply_markup=get_back_keyboard(),
        )

    elif action == "admin_balance_config":
        data = load_balance_data()
        config = data["config"]
        await query.edit_message_text(
            f"⚙️ <b>Balance Configuration</b>\n\n"
            f"━━━━━━━━━━━━━━━━━━━━━━\n"
            f"💵 Joining Bonus: ₹<b>{config['joining_bonus']}</b>\n"
            f"👥 Referral Bonus: ₹<b>{config['referral_bonus']}</b>\n"
            f"🏦 Min Withdrawal: ₹<b>{config['min_withdrawal']}</b>\n"
            f"📅 Max Daily Withdrawals: <b>{config['max_daily_withdrawals']}</b>\n"
            f"\n"
            f"(To edit these values, modify balance.json)",
            parse_mode=ParseMode.HTML,
            reply_markup=get_back_keyboard(),
        )

    elif action == "admin_top_balances":
        data = load_balance_data()
        users_data = data["users"]
        
        if not users_data:
            await query.answer("No balance data yet.", show_alert=True)
            return
        
        # Sort by balance
        sorted_users = sorted(users_data.items(), key=lambda x: x[1].get("balance", 0), reverse=True)[:10]
        
        lines = ["💰 <b>Top 10 Balances</b>\n"]
        total_distributed = 0
        for i, (uid, user_data) in enumerate(sorted_users, 1):
            balance = user_data.get("balance", 0)
            referrals = len(user_data.get("referrals", []))
            lines.append(f"{i}. ID: <code>{uid}</code> | Balance: ₹<b>{balance}</b> | Refs: {referrals}")
            total_distributed += balance
        
        lines.append(f"\n💵 Total Distributed: <b>₹{total_distributed}</b>")
        
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
#  BALANCE COMMANDS
# ──────────────────────────────────────────────
async def balance_command(update: Update, context):
    """Show user's balance and referral info."""
    user_id = update.effective_user.id
    user_balance = get_user_balance(user_id)
    
    balance = user_balance.get("balance", 0)
    referrals = user_balance.get("referrals", [])
    
    text = (
        "💰 <b>Your Wallet</b>\n"
        "\n"
        "━━━━━━━━━━━━━━━━━━━━━━\n"
        f"💵 Balance: <b>₹{balance}</b>\n"
        f"👥 Referrals: <b>{len(referrals)}</b>\n"
        f"📊 Earnings: <b>₹{len(referrals) * 3}</b> (from referrals)\n"
        "\n"
        "━━━━━━━━━━━━━━━━━━━━━━\n"
        f"💳 Min Withdraw: ₹30\n"
        f"📅 Max/Day: 1 withdrawal\n"
    )
    
    await update.message.reply_text(text, parse_mode=ParseMode.HTML)


async def referral_command(update: Update, context):
    """Show referral link and info."""
    user_id = update.effective_user.id
    user_balance = get_user_balance(user_id)
    referrals = user_balance.get("referrals", [])
    
    data = load_balance_data()
    referral_bonus = data["config"]["referral_bonus"]
    joining_bonus = data["config"]["joining_bonus"]
    
    # Get bot username
    bot_username = context.bot.username or "bot"
    referral_link = f"https://t.me/{bot_username}?start=ref_{user_id}"
    
    text = (
        "🔗 <b>Your Referral Link</b>\n"
        "\n"
        "━━━━━━━━━━━━━━━━━━━━━━\n"
        f"📊 Earning Details:\n"
        f"• Joining Bonus: ₹{joining_bonus}\n"
        f"• Per Referral: ₹{referral_bonus}\n"
        "\n"
        "Your Link:\n"
        f"<code>https://t.me/{bot_username}?start=ref_{user_id}</code>\n"
        "\n"
        "━━━━━━━━━━━━━━━━━━━━━━\n"
        f"👥 Total Referrals: <b>{len(referrals)}</b>\n"
        f"💵 Total Earned: <b>₹{len(referrals) * referral_bonus}</b>\n"
        "\n"
        "🎯 Share with friends & earn!\n"
    )
    
    keyboard = ReplyKeyboardMarkup([
        [KeyboardButton("👥 My Referrals")],
        [KeyboardButton("💰 Check Balance")],
        [KeyboardButton("◀️ Back")],
    ], resize_keyboard=True)
    
    await update.message.reply_text(text, parse_mode=ParseMode.HTML, reply_markup=keyboard)


async def withdraw_command(update: Update, context):
    """Start withdrawal process."""
    user_id = update.effective_user.id
    user_balance = get_user_balance(user_id)
    balance = user_balance.get("balance", 0)
    
    data = load_balance_data()
    min_withdraw = data["config"]["min_withdrawal"]
    
    if not can_withdraw(user_id):
        await update.message.reply_text(
            "❌ <b>Withdrawal Limit Reached</b>\n\n"
            "You can only withdraw once per day.\n"
            "Try again tomorrow.",
            parse_mode=ParseMode.HTML,
        )
        return
    
    if balance < min_withdraw:
        await update.message.reply_text(
            f"❌ <b>Insufficient Balance</b>\n\n"
            f"Your Balance: ₹{balance}\n"
            f"Minimum Required: ₹{min_withdraw}",
            parse_mode=ParseMode.HTML,
        )
        return
    
    text = (
        "💳 <b>Withdraw Money</b>\n"
        "\n"
        "━━━━━━━━━━━━━━━━━━━━━━\n"
        f"🎯 Available: <b>₹{balance}</b>\n"
        f"💰 Min Amount: ₹{min_withdraw}\n"
        "\n"
        "Send the amount you want to withdraw (e.g., 30)\n"
        "Send /cancel to abort.\n"
    )
    
    context.user_data["withdrawing"] = True
    await update.message.reply_text(text, parse_mode=ParseMode.HTML)


async def withdrawal_amount(update: Update, context):
    """Process withdrawal amount."""
    if not context.user_data.get("withdrawing"):
        return
    
    try:
        user_id = update.effective_user.id
        amount = float(update.message.text)
        
        data = load_balance_data()
        min_withdraw = data["config"]["min_withdrawal"]
        
        if amount < min_withdraw:
            await update.message.reply_text(f"❌ Minimum amount is ₹{min_withdraw}")
            return
        
        user_balance = get_user_balance(user_id)
        if user_balance.get("balance", 0) < amount:
            await update.message.reply_text("❌ Insufficient balance!")
            return
        
        # Process withdrawal
        if subtract_balance(str(user_id), amount):
            record_withdrawal(str(user_id), amount)
            context.user_data["withdrawing"] = False
            
            await update.message.reply_text(
                f"✅ <b>Withdrawal Successful!</b>\n\n"
                f"Amount: <b>₹{amount}</b>\n"
                f"Status: Pending\n\n"
                f"You'll receive it in 24 hours.\n"
                f"Admin will review and process.",
                parse_mode=ParseMode.HTML,
            )
        else:
            await update.message.reply_text("❌ Withdrawal failed. Try again.")
    except ValueError:
        await update.message.reply_text("❌ Invalid amount. Send a number (e.g., 30)")


async def my_referrals_command(update: Update, context):
    """Show list of user's referrals."""
    user_id = update.effective_user.id
    user_balance = get_user_balance(user_id)
    referrals = user_balance.get("referrals", [])
    
    if not referrals:
        await update.message.reply_text(
            "👥 <b>My Referrals</b>\n\n"
            "You don't have any referrals yet.\n"
            "Start sharing your link to earn! 🔗",
            parse_mode=ParseMode.HTML,
            reply_markup=ReplyKeyboardMarkup([
                [KeyboardButton("🔗 Share Referral Link")],
                [KeyboardButton("◀️ Back")],
            ], resize_keyboard=True),
        )
        return
    
    data = load_balance_data()
    referral_bonus = data["config"]["referral_bonus"]
    
    lines = [f"👥 <b>My Referrals ({len(referrals)})</b>\n"]
    for i, ref_id in enumerate(referrals, 1):
        lines.append(f"{i}. ID: <code>{ref_id}</code>")
    
    lines.append(f"\n💵 Total Earned: <b>₹{len(referrals) * referral_bonus}</b>")
    
    text = "\n".join(lines)
    await update.message.reply_text(
        text,
        parse_mode=ParseMode.HTML,
        reply_markup=ReplyKeyboardMarkup([
            [KeyboardButton("🔗 Referral Link")],
            [KeyboardButton("◀️ Back")],
        ], resize_keyboard=True),
    )


async def settings_command(update: Update, context):
    """Show user settings."""
    user_id = update.effective_user.id
    user_data = load_users().get(str(user_id), {})
    
    text = (
        "⚙️ <b>Settings</b>\n"
        "\n"
        "━━━━━━━━━━━━━━━━━━━━━━\n"
        f"👤 <b>User ID:</b> <code>{user_id}</code>\n"
        f"📝 <b>Name:</b> {user_data.get('name', 'Unknown')}\n"
        f"📅 <b>Joined:</b> {user_data.get('joined', 'N/A')}\n"
        "\n"
        "━━━━━━━━━━━━━━━━━━━━━━\n"
        "\n"
        "✅ Language: English\n"
        "🔔 Notifications: On\n"
        "🔒 Account: Verified ✓\n"
    )
    
    await update.message.reply_text(
        text,
        parse_mode=ParseMode.HTML,
        reply_markup=ReplyKeyboardMarkup([
            [KeyboardButton("📞 Need Help?")],
            [KeyboardButton("◀️ Back")],
        ], resize_keyboard=True),
    )


async def help_command(update: Update, context):
    """Show help/FAQ."""
    text = (
        "📞 <b>Help & FAQ</b>\n"
        "\n"
        "━━━━━━━━━━━━━━━━━━━━━━\n"
        "\n"
        "<b>❓ How to earn?</b>\n"
        "✅ Join both channels\n"
        "✅ Get ₹2 bonus instantly\n"
        "✅ Share your referral link\n"
        "✅ Earn ₹3 per referral\n"
        "\n"
        "<b>💸 How to withdraw?</b>\n"
        "• Minimum: ₹30\n"
        "• Max per day: 1 withdrawal\n"
        "• Time: 24 hours\n"
        "\n"
        "<b>❓ Need more help?</b>\n"
        "Contact: @support\n"
        "\n"
        "━━━━━━━━━━━━━━━━━━━━━━\n"
    )
    
    await update.message.reply_text(
        text,
        parse_mode=ParseMode.HTML,
        reply_markup=ReplyKeyboardMarkup([
            [KeyboardButton("💰 Check Balance")],
            [KeyboardButton("🔗 Referral Link")],
            [KeyboardButton("◀️ Back")],
        ], resize_keyboard=True),
    )


async def handle_button_press(update: Update, context):
    """Handle keyboard button presses."""
    if not update.message or not update.message.text:
        return
    
    text = update.message.text
    user_id = update.effective_user.id
    
    # Verification buttons
    if text in ["✅ Verify Both Channels", "✅ Try Verifying Again"]:
        await verify_callback(update, context)
        return
    
    # User balance/wallet buttons
    if text == "💰 Balance" or text == "💰 Check Balance":
        await balance_command(update, context)
        return
    
    if text in ["🔗 Referral Link", "🔗 Share Link", "🔗 Share Referral Link"]:
        await referral_command(update, context)
        return
    
    if text == "👥 My Referrals":
        await my_referrals_command(update, context)
        return
    
    if text in ["💸 Withdraw", "💸 Withdraw Money"]:
        await withdraw_command(update, context)
        return
    
    if text in ["⚙️ Settings", "Settings"]:
        await settings_command(update, context)
        return
    
    if text in ["📞 Help", "📞 Need Help?"]:
        await help_command(update, context)
        return
    
    if text == "⚙️ Admin Panel":
        # Only admins can access admin panel
        if update.effective_user.id not in ADMIN_IDS:
            await update.message.reply_text("⛔ Admin only!", reply_markup=get_verified_keyboard(update.effective_user.id))
            return
        await admin_command(update, context)
        return
    
    # Admin buttons
    if text == "📊 Stats":
        users = load_users()
        await update.message.reply_text(
            f"📊 <b>Bot Stats</b>\n\n👥 Total users: <b>{len(users)}</b>",
            parse_mode=ParseMode.HTML,
            reply_markup=get_back_keyboard(),
        )
        return
    
    if text == "📈 Analytics":
        await update.message.reply_text(
            get_analytics_summary(),
            parse_mode=ParseMode.HTML,
            reply_markup=get_back_keyboard(),
        )
        return
    
    if text in ["👥 All Users", "👥 Users"]:
        users = load_users()
        if not users:
            await update.message.reply_text("❌ No users yet.", reply_markup=get_back_keyboard())
            return
        lines = [f"👥 <b>All Users ({len(users)})</b>\n"]
        for i, (uid, info) in enumerate(list(users.items())[:50], 1):
            name = info.get("name", "Unknown")
            username = info.get("username")
            joined = info.get("joined", "N/A")
            uname_str = f" @{username}" if username else ""
            lines.append(f"{i}. <b>{name}</b>{uname_str} | ID: <code>{uid}</code> | {joined}")
        text_output = "\n".join(lines[:2000])
        await update.message.reply_text(text_output, parse_mode=ParseMode.HTML, reply_markup=get_back_keyboard())
        return
    
    if text == "🔍 Check Channels":
        lines = ["🔍 <b>Channel Access Check</b>\n"]
        for i, chat_id in enumerate(CHANNEL_IDS, 1):
            try:
                chat = await context.bot.get_chat(chat_id)
                lines.append(f"✅ Channel {i}: <b>{chat.title}</b> (ID: <code>{chat_id}</code>)")
            except Exception as e:
                lines.append(f"❌ Channel {i}: ID <code>{chat_id}</code>")
        await update.message.reply_text("\n".join(lines), parse_mode=ParseMode.HTML, reply_markup=get_back_keyboard())
        return
    
    if text == "💰 Balance Config":
        data = load_balance_data()
        config = data["config"]
        await update.message.reply_text(
            f"⚙️ <b>Balance Configuration</b>\n\n"
            f"💵 Joining Bonus: ₹<b>{config['joining_bonus']}</b>\n"
            f"👥 Referral Bonus: ₹<b>{config['referral_bonus']}</b>\n"
            f"🏦 Min Withdrawal: ₹<b>{config['min_withdrawal']}</b>\n"
            f"📅 Max Daily: <b>{config['max_daily_withdrawals']}</b>",
            parse_mode=ParseMode.HTML,
            reply_markup=get_back_keyboard(),
        )
        return
    
    if text == "💵 Top Balances":
        data = load_balance_data()
        users_data = data["users"]
        if not users_data:
            await update.message.reply_text("No balance data yet.", reply_markup=get_back_keyboard())
            return
        sorted_users = sorted(users_data.items(), key=lambda x: x[1].get("balance", 0), reverse=True)[:10]
        lines = ["💰 <b>Top 10 Balances</b>\n"]
        total = 0
        for i, (uid, user_data) in enumerate(sorted_users, 1):
            balance = user_data.get("balance", 0)
            refs = len(user_data.get("referrals", []))
            lines.append(f"{i}. ID:<code>{uid}</code> | ₹<b>{balance}</b> | Refs:{refs}")
            total += balance
        lines.append(f"\n💵 Total: ₹<b>{total}</b>")
        await update.message.reply_text("\n".join(lines), parse_mode=ParseMode.HTML, reply_markup=get_back_keyboard())
        return
    
    if text == "📢 Broadcast":
        await update.message.reply_text(
            "📢 <b>Broadcast Mode</b>\n\nSend the message to broadcast.\nSend /cancel to abort.",
            parse_mode=ParseMode.HTML,
        )
        context.user_data["awaiting_broadcast"] = True
        return
    
    if text == "💾 Export Users":
        users = load_users()
        export_lines = ["user_id,name,username,joined"]
        for uid, info in users.items():
            name = info.get("name", "Unknown").replace(",", ";")
            username = info.get("username") or ""
            joined = info.get("joined", "N/A")
            export_lines.append(f"{uid},{name},{username},{joined}")
        csv_content = "\n".join(export_lines)
        export_file = "users_export.csv"
        with open(export_file, "w", encoding="utf-8") as f:
            f.write(csv_content)
        try:
            with open(export_file, "rb") as f:
                await context.bot.send_document(chat_id=user_id, document=f, caption=f"📄 User Export ({len(users)} users)")
            await update.message.reply_text("📤 File sent to your DM!", reply_markup=get_back_keyboard())
        except Exception as e:
            await update.message.reply_text(f"❌ Error: {e}", reply_markup=get_back_keyboard())
        return
    
    if text == "� Export Balance":
        data = load_balance_data()
        export_file = "balance_export.json"
        with open(export_file, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
        try:
            with open(export_file, "rb") as f:
                total_balance = sum(user.get("balance", 0) for user in data["users"].values())
                await context.bot.send_document(chat_id=user_id, document=f, caption=f"💰 Balance Export\n\nUsers: {len(data['users'])}\nTotal Balance: ₹{total_balance}")
            await update.message.reply_text("📤 File sent to your DM!", reply_markup=get_back_keyboard())
        except Exception as e:
            await update.message.reply_text(f"❌ Error: {e}", reply_markup=get_back_keyboard())
        return
    
    if text == "�🗑️ Purge Inactive":
        await update.message.reply_text(
            "🗑️ <b>Purge Inactive Users</b>\n\nDelete users who joined 30+ days ago and haven't registered?",
            parse_mode=ParseMode.HTML,
            reply_markup=get_purge_keyboard(),
        )
        return
    
    if text == "✅ Yes, Purge":
        purged, remaining = purge_inactive_users(days=30)
        await update.message.reply_text(
            f"✅ <b>Purge Complete!</b>\n🗑️ Deleted: <b>{purged}</b>\n👥 Remaining: <b>{remaining}</b>",
            parse_mode=ParseMode.HTML,
            reply_markup=get_back_keyboard(),
        )
        return
    
    if text == "⚠️ Delete All":
        await update.message.reply_text(
            "⚠️ <b>DELETE ALL USERS</b>\n\nThis will permanently delete ALL data! Confirm?",
            parse_mode=ParseMode.HTML,
            reply_markup=get_delete_all_keyboard(),
        )
        return
    
    if text == "⚠️ Yes Delete ALL":
        delete_all_users()
        await update.message.reply_text("⚠️ <b>All users deleted!</b>", parse_mode=ParseMode.HTML, reply_markup=get_back_keyboard())
        return
    
    if text == "◀️ Main Menu":
        await start(update, context)
        return
    
    if text == "◀️ Back":
        # Go to admin panel for admins, or main menu for users
        if update.effective_user.id in ADMIN_IDS:
            await admin_command(update, context)
        else:
            await start(update, context)
        return
    
    if text == "❌ Cancel":
        await update.message.reply_text("Cancelled.", reply_markup=get_back_keyboard())
        return


# ──────────────────────────────────────────────
#  MAIN
# ──────────────────────────────────────────────
def main():
    # Initialize bot application with handlers
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
    app.add_handler(CommandHandler("balance", balance_command))
    app.add_handler(CommandHandler("referral", referral_command))
    
    # Withdrawal conversation handler
    withdrawal_handler = ConversationHandler(
        entry_points=[CommandHandler("withdraw", withdraw_command)],
        states={
            1: [MessageHandler(filters.TEXT & ~filters.COMMAND, withdrawal_amount)]
        },
        fallbacks=[CommandHandler("cancel", lambda u, c: None)],
    )
    app.add_handler(withdrawal_handler)
    
    # Text message handler for button presses (must come before other handlers)
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_button_press))
    
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
