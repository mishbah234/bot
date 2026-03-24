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
# Comma-separated admin Telegram IDs
ADMIN_IDS = [
    int(x.strip()) for x in os.environ.get("ADMIN_IDS", "8455891912,6097181868").split(",") if x.strip()
]

# Channel chat IDs (bot must be admin in these channels)
CHANNEL_IDS = [
    int(os.environ.get("CHANNEL_ID_1", "-1002169640991")),
    int(os.environ.get("CHANNEL_ID_2", "-1002111582843")),
]

# Channel invite links (used in inline buttons)
CHANNEL_URLS = [
    os.environ.get("CHANNEL_URL_1", "https://t.me/+Yr_j3b9zwnRiMjNl"),
    os.environ.get("CHANNEL_URL_2", "https://t.me/+uGeLDa05s7M4NjFl"),
]

# Registration link
REG_LINK = os.environ.get(
    "REG_LINK",
    "https://www.tgdream16.com/#/register?invitationCode=632738378641",
)

# Withdrawal notification channel ID (bot must be member)
WITHDRAWAL_CHANNEL_ID = int(os.environ.get("WITHDRAWAL_CHANNEL_ID", "0"))

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

USERS_FILE = "users.json"
BALANCE_FILE = "balance.json"
WAITING_BROADCAST = 1  # ConversationHandler state


# ──────────────────────────────────────────────
#  USER STORAGE (with verified flag)
# ──────────────────────────────────────────────
def load_users() -> dict:
    try:
        with open(USERS_FILE, "r") as f:
            data = json.load(f)
        # Migrate from old list format
        if isinstance(data, list):
            migrated = {}
            for uid in data:
                migrated[str(uid)] = {"name": "Unknown", "username": None, "joined": None, "verified": False}
            with open(USERS_FILE, "w") as f:
                json.dump(migrated, f, indent=2)
            return migrated
        # Ensure all users have "verified" field
        for uid, info in data.items():
            if "verified" not in info:
                info["verified"] = False
        return data
    except (FileNotFoundError, json.JSONDecodeError):
        return {}


def load_user_ids() -> set:
    users = load_users()
    return {int(uid) for uid in users.keys()}


async def notify_admins_new_user(user):
    if not ADMIN_IDS:
        return
    user_id = user.id
    name = user.full_name or "Unknown"
    username = user.username
    joined_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    mention = f"@{username}" if username else f"[{name}](tg://user?id={user_id})"
    text = (
        f"🆕 <b>New User Joined!</b>\n\n"
        f"👤 <b>Name:</b> {name}\n"
        f"📛 <b>Username:</b> {mention}\n"
        f"🆔 <b>ID:</b> <code>{user_id}</code>\n"
        f"📅 <b>Joined at:</b> {joined_at}\n\n🎉 Welcome aboard!"
    )
    for admin_id in ADMIN_IDS:
        try:
            await context.bot.send_message(chat_id=admin_id, text=text, parse_mode=ParseMode.HTML)
        except Exception as e:
            logger.warning(f"Failed to send new-user notification to admin {admin_id}: {e}")


def save_user(user):
    users = load_users()
    if hasattr(user, "id"):
        uid = str(user.id)
        name = user.full_name or "Unknown"
        username = user.username
    else:
        uid = str(user)
        name = "Unknown"
        username = None

    is_new = uid not in users
    if is_new:
        users[uid] = {
            "name": name,
            "username": username,
            "joined": datetime.now().strftime("%Y-%m-%d %H:%M"),
            "verified": False
        }
        with open(USERS_FILE, "w") as f:
            json.dump(users, f, indent=2)
        logger.info(f"New user saved: {uid} - {name} (total: {len(users)})")
        # Trigger admin notification (async)
        asyncio.create_task(notify_admins_new_user(user))
    elif users[uid]["name"] == "Unknown" and hasattr(user, "full_name"):
        users[uid]["name"] = user.full_name or "Unknown"
        users[uid]["username"] = user.username
        with open(USERS_FILE, "w") as f:
            json.dump(users, f, indent=2)


def set_verified(user_id: int) -> bool:
    users = load_users()
    uid = str(user_id)
    if uid in users and not users[uid].get("verified", False):
        users[uid]["verified"] = True
        with open(USERS_FILE, "w") as f:
            json.dump(users, f, indent=2)
        return True
    return False


def is_verified(user_id: int) -> bool:
    users = load_users()
    return users.get(str(user_id), {}).get("verified", False)


# ──────────────────────────────────────────────
#  BALANCE & REFERRAL SYSTEM
# ──────────────────────────────────────────────
def load_balance_data() -> dict:
    try:
        with open(BALANCE_FILE, "r") as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return {
            "config": {"joining_bonus": 2, "referral_bonus": 3, "min_withdrawal": 30, "max_daily_withdrawals": 1},
            "users": {}
        }


def save_balance_data(data: dict) -> None:
    with open(BALANCE_FILE, "w") as f:
        json.dump(data, f, indent=2)


def get_user_balance(user_id: str) -> dict:
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
    data = load_balance_data()
    uid = str(user_id)
    if uid not in data["users"]:
        data["users"][uid] = {"balance": 0, "referrals": [], "withdrawals": [], "last_withdrawal": None}
    data["users"][uid]["balance"] = data["users"][uid].get("balance", 0) + amount
    logger.info(f"Added ₹{amount} to user {uid} ({reason})")
    save_balance_data(data)


def subtract_balance(user_id: str, amount: float) -> bool:
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
    data = load_balance_data()
    referrer_uid = str(referrer_id)
    referred_uid = str(referred_id)
    if referrer_uid not in data["users"]:
        data["users"][referrer_uid] = {"balance": 0, "referrals": [], "withdrawals": [], "last_withdrawal": None}
    if referred_uid not in data["users"][referrer_uid]["referrals"]:
        data["users"][referrer_uid]["referrals"].append(referred_uid)
        bonus = data["config"]["referral_bonus"]
        data["users"][referrer_uid]["balance"] = data["users"][referrer_uid].get("balance", 0) + bonus
        logger.info(f"Referral registered: {referrer_uid} → {referred_uid}, bonus ₹{bonus}")
        save_balance_data(data)


def can_withdraw(user_id: str) -> bool:
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
        "1️⃣  Join both channels (buttons below)\n"
        "2️⃣  Get ₹2 joining bonus instantly\n"
        "3️⃣  Invite friends & earn ₹3 per person\n"
        "4️⃣  Withdraw when you reach ₹30\n"
        "\n"
        "━━━━━━━━━━━━━━━━━━━━━━\n"
        "\n"
        "🔗 Tap the buttons below to join the channels 👇\n"
    )


def verified_text():
    return (
        "✅ <b>Verification Successful!</b>\n"
        "\n"
        "━━━━━━━━━━━━━━━━━━━━━━\n"
        f"🎉 You've earned <b>₹{load_balance_data()['config']['joining_bonus']}</b> joining bonus!\n"
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


def get_back_inline_keyboard():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("◀️ Back", callback_data="admin_panel")]
    ])


def get_admin_keyboard():
    buttons = [
        [InlineKeyboardButton("📊 Stats", callback_data="admin_stats")],
        [InlineKeyboardButton("👥 Users", callback_data="admin_users")],
        [InlineKeyboardButton("📢 Broadcast", callback_data="admin_broadcast")],
        [InlineKeyboardButton("📈 Analytics", callback_data="admin_analytics")],
        [InlineKeyboardButton("💾 Export Users", callback_data="admin_export")],
        [InlineKeyboardButton("💰 Export Balance", callback_data="admin_export_balance")],
        [InlineKeyboardButton("🗑️ Purge Inactive", callback_data="admin_purge")],
        [InlineKeyboardButton("⚠️ Delete All", callback_data="admin_delete_confirm")],
        [InlineKeyboardButton("⚙️ Balance Config", callback_data="admin_balance_config")],
        [InlineKeyboardButton("💵 Top Balances", callback_data="admin_top_balances")],
        [InlineKeyboardButton("🔍 Check Channels", callback_data="admin_checkbot")],
    ]
    return InlineKeyboardMarkup(buttons)


def get_purge_keyboard():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("✅ Yes, Purge", callback_data="admin_purge_confirm")],
        [InlineKeyboardButton("❌ Cancel", callback_data="admin_panel")]
    ])


def get_delete_all_keyboard():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("⚠️ Yes Delete ALL", callback_data="admin_delete_all_confirm")],
        [InlineKeyboardButton("❌ Cancel", callback_data="admin_panel")]
    ])


def get_channel_inline_keyboard():
    """Inline keyboard with two channel join buttons."""
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("📢 Join Channel 1", url=CHANNEL_URLS[0]),
         InlineKeyboardButton("📢 Join Channel 2", url=CHANNEL_URLS[1])]
    ])


def get_analytics_summary() -> str:
    from datetime import datetime as dt
    users = load_users()
    if not users:
        return "📈 <b>Analytics</b>\n\nNo user data yet."
    today = dt.now().date()
    last_7_days = 0
    last_30_days = 0
    for uid, info in users.items():
        joined_str = info.get("joined")
        if joined_str:
            try:
                joined_date = dt.strptime(joined_str, "%Y-%m-%d %H:%M").date()
                days_diff = (today - joined_date).days
                if days_diff <= 7:
                    last_7_days += 1
                if days_diff <= 30:
                    last_30_days += 1
            except:
                pass
    unknown_count = sum(1 for info in users.values() if info.get("name") == "Unknown")
    verified_count = sum(1 for info in users.values() if info.get("verified", False))
    lines = [
        "📈 <b>Analytics</b>\n",
        "━━━━━━━━━━━━━━━━━━━━━━\n",
        f"👥 Total Users: <b>{len(users)}</b>",
        f"✅ Verified: <b>{verified_count}</b>",
        f"🆕 Last 7 Days: <b>{last_7_days}</b>",
        f"📅 Last 30 Days: <b>{last_30_days}</b>",
        f"❓ Unknown Users: <b>{unknown_count}</b>",
    ]
    return "\n".join(lines)


def purge_inactive_users(days: int = 30) -> tuple:
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
                if days_old >= days and not info.get("verified", False):
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
    with open(USERS_FILE, "w") as f:
        json.dump({}, f, indent=2)
    logger.info("All users deleted!")


# ──────────────────────────────────────────────
#  VERIFICATION
# ──────────────────────────────────────────────
async def verify_callback(update: Update, context):
    user_id = update.effective_user.id
    joined_all = True

    for channel_id in CHANNEL_IDS:
        try:
            member = await context.bot.get_chat_member(chat_id=channel_id, user_id=user_id)
            if member.status in ["left", "kicked"]:
                joined_all = False
                break
        except Exception as e:
            logger.error(f"Error checking channel {channel_id}: {e}")
            joined_all = False
            break

    if joined_all:
        if not is_verified(user_id):
            data = load_balance_data()
            joining_bonus = data["config"]["joining_bonus"]
            add_balance(str(user_id), joining_bonus, "joining_bonus")
            set_verified(user_id)
            await update.message.reply_text(
                verified_text(),
                parse_mode=ParseMode.HTML,
                reply_markup=get_verified_keyboard(user_id),
                disable_web_page_preview=True,
            )
        else:
            await update.message.reply_text(
                "✅ You are already verified!\n\nUse the buttons below.",
                parse_mode=ParseMode.HTML,
                reply_markup=get_verified_keyboard(user_id),
            )
    else:
        await update.message.reply_text(
            not_joined_text(),
            parse_mode=ParseMode.HTML,
            reply_markup=get_retry_keyboard(),
            disable_web_page_preview=True,
        )


# ──────────────────────────────────────────────
#  START COMMAND
# ──────────────────────────────────────────────
async def start(update: Update, context):
    user_id = update.effective_user.id
    save_user(update.effective_user)

    # Referral handling
    if context.args:
        ref_code = context.args[0]
        if ref_code.startswith("ref_"):
            try:
                referrer_id = ref_code.split("_")[1]
                user_balance = get_user_balance(user_id)
                if referrer_id not in user_balance.get("referrals", []):
                    add_referral(referrer_id, user_id)
                    await update.message.reply_text(
                        f"🎉 <b>Welcome!</b>\n\nYou were referred by a friend!\n"
                        f"Your friend earned ₹{load_balance_data()['config']['referral_bonus']}\n\n"
                        "Now verify to get your joining bonus →",
                        parse_mode=ParseMode.HTML,
                        reply_markup=get_welcome_keyboard(),
                        disable_web_page_preview=True,
                    )
                    # Send the channel join buttons
                    await update.message.reply_text(
                        "📢 Click the buttons below to join our channels:",
                        reply_markup=get_channel_inline_keyboard(),
                    )
                    return
            except:
                pass

    # Main start message
    await update.message.reply_text(
        welcome_text(),
        parse_mode=ParseMode.HTML,
        reply_markup=get_welcome_keyboard(),
        disable_web_page_preview=True,
    )
    # Send inline channel join buttons
    await update.message.reply_text(
        "📢 Click the buttons below to join our channels:",
        reply_markup=get_channel_inline_keyboard(),
    )


# ──────────────────────────────────────────────
#  ADMIN PANEL
# ──────────────────────────────────────────────
async def admin_command(update: Update, context):
    if update.effective_user.id not in ADMIN_IDS:
        return
    await update.message.reply_text(
        "⚙️ <b>Admin Panel</b>\n\nChoose an option below 👇",
        parse_mode=ParseMode.HTML,
        reply_markup=get_admin_keyboard(),
    )


async def admin_panel_callback(update: Update, context):
    query = update.callback_query
    if query.from_user.id not in ADMIN_IDS:
        await query.answer("⛔ Admin only!", show_alert=True)
        return

    action = query.data
    await query.answer()

    if action == "admin_panel":
        await query.edit_message_text(
            "⚙️ <b>Admin Panel</b>\n\nChoose an option below 👇",
            parse_mode=ParseMode.HTML,
            reply_markup=get_admin_keyboard(),
        )
        return

    if action == "admin_stats":
        users = load_users()
        await query.edit_message_text(
            f"📊 <b>Bot Stats</b>\n\n👥 Total users: <b>{len(users)}</b>",
            parse_mode=ParseMode.HTML,
            reply_markup=get_back_inline_keyboard(),
        )

    elif action == "admin_users":
        users = load_users()
        if not users:
            await query.edit_message_text("❌ No users yet.", reply_markup=get_back_inline_keyboard())
            return
        lines = [f"👥 <b>All Users ({len(users)})</b>\n"]
        for i, (uid, info) in enumerate(users.items(), 1):
            name = info.get("name", "Unknown")
            username = info.get("username")
            joined = info.get("joined", "N/A")
            verified = "✅" if info.get("verified") else "❌"
            uname_str = f" @{username}" if username else ""
            lines.append(f"{i}. {verified} <b>{name}</b>{uname_str}\n   ID: <code>{uid}</code> | Joined: {joined}")
        text = "\n".join(lines)
        if len(text) > 4000:
            text = text[:4000] + "\n\n... (truncated)"
        await query.edit_message_text(text, parse_mode=ParseMode.HTML, reply_markup=get_back_inline_keyboard())

    elif action == "admin_broadcast":
        await query.edit_message_text(
            "📢 <b>Broadcast Mode</b>\n\nSend me the message you want to broadcast to all users.\nSend /cancel to abort.",
            parse_mode=ParseMode.HTML,
        )
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
        if WITHDRAWAL_CHANNEL_ID:
            try:
                chat = await context.bot.get_chat(WITHDRAWAL_CHANNEL_ID)
                lines.append(f"\n💰 Withdrawal channel: <b>{chat.title}</b> (ID: <code>{WITHDRAWAL_CHANNEL_ID}</code>)")
            except:
                lines.append(f"\n⚠️ Withdrawal channel ID set but bot cannot access: <code>{WITHDRAWAL_CHANNEL_ID}</code>")
        else:
            lines.append(f"\n⚠️ Withdrawal channel ID not set.")
        await query.edit_message_text("\n".join(lines), parse_mode=ParseMode.HTML, reply_markup=get_back_inline_keyboard())

    elif action == "admin_analytics":
        await query.edit_message_text(get_analytics_summary(), parse_mode=ParseMode.HTML, reply_markup=get_back_inline_keyboard())

    elif action == "admin_export":
        users = load_users()
        export_lines = ["user_id,name,username,joined,verified"]
        for uid, info in users.items():
            name = info.get("name", "Unknown").replace(",", ";")
            username = info.get("username") or ""
            joined = info.get("joined", "N/A")
            verified = "yes" if info.get("verified") else "no"
            export_lines.append(f"{uid},{name},{username},{joined},{verified}")
        csv_content = "\n".join(export_lines)
        export_file = "users_export.csv"
        with open(export_file, "w", encoding="utf-8") as f:
            f.write(csv_content)
        try:
            with open(export_file, "rb") as f:
                await context.bot.send_document(chat_id=query.from_user.id, document=f, caption=f"📄 User Export\n\n✅ {len(users)} users exported")
            await query.answer("📤 File sent to your DM!", show_alert=False)
        except Exception as e:
            await query.answer(f"❌ Error: {e}", show_alert=True)

    elif action == "admin_export_balance":
        data = load_balance_data()
        export_file = "balance_export.json"
        with open(export_file, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
        try:
            with open(export_file, "rb") as f:
                total_balance = sum(user.get("balance", 0) for user in data["users"].values())
                await context.bot.send_document(chat_id=query.from_user.id, document=f, caption=f"💰 Balance Export\n\nUsers: {len(data['users'])}\nTotal Balance: ₹{total_balance}")
            await query.answer("📤 File sent to your DM!", show_alert=False)
        except Exception as e:
            await query.answer(f"❌ Error: {e}", show_alert=True)

    elif action == "admin_purge":
        await query.edit_message_text(
            "🗑️ <b>Purge Inactive Users</b>\n\nThis will delete users who:\n• Joined more than 30 days ago\n• Haven't verified their account\n\nAre you sure?",
            parse_mode=ParseMode.HTML,
            reply_markup=get_purge_keyboard(),
        )

    elif action == "admin_purge_confirm":
        purged, remaining = purge_inactive_users(days=30)
        await query.edit_message_text(
            f"✅ <b>Purge Complete!</b>\n\n🗑️ Deleted: <b>{purged}</b> inactive users\n👥 Remaining: <b>{remaining}</b> users",
            parse_mode=ParseMode.HTML,
            reply_markup=get_back_inline_keyboard(),
        )

    elif action == "admin_delete_confirm":
        await query.edit_message_text(
            "⚠️ <b>DELETE ALL USERS</b>\n\nThis will <b>permanently delete</b> ALL user data!\nThis action <b>cannot be undone</b>.\n\nAre you absolutely sure?",
            parse_mode=ParseMode.HTML,
            reply_markup=get_delete_all_keyboard(),
        )

    elif action == "admin_delete_all_confirm":
        delete_all_users()
        await query.edit_message_text("⚠️ <b>All users deleted!</b>\n\nThe database is now empty.", parse_mode=ParseMode.HTML, reply_markup=get_back_inline_keyboard())

    elif action == "admin_balance_config":
        data = load_balance_data()
        config = data["config"]
        await query.edit_message_text(
            f"⚙️ <b>Balance Configuration</b>\n\n━━━━━━━━━━━━━━━━━━━━━━\n💵 Joining Bonus: ₹<b>{config['joining_bonus']}</b>\n👥 Referral Bonus: ₹<b>{config['referral_bonus']}</b>\n🏦 Min Withdrawal: ₹<b>{config['min_withdrawal']}</b>\n📅 Max Daily Withdrawals: <b>{config['max_daily_withdrawals']}</b>\n\n(To edit these values, modify balance.json)",
            parse_mode=ParseMode.HTML,
            reply_markup=get_back_inline_keyboard(),
        )

    elif action == "admin_top_balances":
        data = load_balance_data()
        users_data = data["users"]
        if not users_data:
            await query.answer("No balance data yet.", show_alert=True)
            return
        sorted_users = sorted(users_data.items(), key=lambda x: x[1].get("balance", 0), reverse=True)[:10]
        lines = ["💰 <b>Top 10 Balances</b>\n"]
        total_distributed = 0
        for i, (uid, user_data) in enumerate(sorted_users, 1):
            balance = user_data.get("balance", 0)
            referrals = len(user_data.get("referrals", []))
            lines.append(f"{i}. ID: <code>{uid}</code> | Balance: ₹<b>{balance}</b> | Refs: {referrals}")
            total_distributed += balance
        lines.append(f"\n💵 Total Distributed: <b>₹{total_distributed}</b>")
        await query.edit_message_text("\n".join(lines), parse_mode=ParseMode.HTML, reply_markup=get_back_inline_keyboard())


# ──────────────────────────────────────────────
#  BALANCE COMMANDS
# ──────────────────────────────────────────────
async def balance_command(update: Update, context):
    user_id = update.effective_user.id
    user_balance = get_user_balance(user_id)
    balance = user_balance.get("balance", 0)
    referrals = user_balance.get("referrals", [])
    text = (
        "💰 <b>Your Wallet</b>\n\n━━━━━━━━━━━━━━━━━━━━━━\n"
        f"💵 Balance: <b>₹{balance}</b>\n👥 Referrals: <b>{len(referrals)}</b>\n"
        f"📊 Earnings: <b>₹{len(referrals) * 3}</b> (from referrals)\n\n"
        f"💳 Min Withdraw: ₹30\n📅 Max/Day: 1 withdrawal\n"
    )
    await update.message.reply_text(text, parse_mode=ParseMode.HTML)


async def referral_command(update: Update, context):
    user_id = update.effective_user.id
    user_balance = get_user_balance(user_id)
    referrals = user_balance.get("referrals", [])
    data = load_balance_data()
    referral_bonus = data["config"]["referral_bonus"]
    joining_bonus = data["config"]["joining_bonus"]
    bot_username = context.bot.username or "bot"
    text = (
        "🔗 <b>Your Referral Link</b>\n\n━━━━━━━━━━━━━━━━━━━━━━\n"
        f"📊 Earning Details:\n• Joining Bonus: ₹{joining_bonus}\n• Per Referral: ₹{referral_bonus}\n\n"
        f"Your Link:\n<code>https://t.me/{bot_username}?start=ref_{user_id}</code>\n\n"
        f"👥 Total Referrals: <b>{len(referrals)}</b>\n💵 Total Earned: <b>₹{len(referrals) * referral_bonus}</b>\n\n"
        "🎯 Share with friends & earn!\n"
    )
    keyboard = ReplyKeyboardMarkup([
        [KeyboardButton("👥 My Referrals")],
        [KeyboardButton("💰 Check Balance")],
        [KeyboardButton("◀️ Back")],
    ], resize_keyboard=True)
    await update.message.reply_text(text, parse_mode=ParseMode.HTML, reply_markup=keyboard)


async def withdraw_command(update: Update, context):
    user_id = update.effective_user.id
    user_balance = get_user_balance(user_id)
    balance = user_balance.get("balance", 0)
    data = load_balance_data()
    min_withdraw = data["config"]["min_withdrawal"]
    if not can_withdraw(user_id):
        await update.message.reply_text("❌ <b>Withdrawal Limit Reached</b>\n\nYou can only withdraw once per day.\nTry again tomorrow.", parse_mode=ParseMode.HTML)
        return ConversationHandler.END
    if balance < min_withdraw:
        await update.message.reply_text(f"❌ <b>Insufficient Balance</b>\n\nYour Balance: ₹{balance}\nMinimum Required: ₹{min_withdraw}", parse_mode=ParseMode.HTML)
        return ConversationHandler.END
    text = (
        "💳 <b>Withdraw Money</b>\n\n━━━━━━━━━━━━━━━━━━━━━━\n"
        f"🎯 Available: <b>₹{balance}</b>\n💰 Min Amount: ₹{min_withdraw}\n\n"
        "Send the amount you want to withdraw (e.g., 30)\nSend /cancel to abort.\n"
    )
    await update.message.reply_text(text, parse_mode=ParseMode.HTML)
    return 1


async def withdrawal_amount(update: Update, context):
    user_id = update.effective_user.id
    try:
        amount = float(update.message.text)
        data = load_balance_data()
        min_withdraw = data["config"]["min_withdrawal"]
        if amount < min_withdraw:
            await update.message.reply_text(f"❌ Minimum amount is ₹{min_withdraw}")
            return 1
        user_balance = get_user_balance(user_id)
        if user_balance.get("balance", 0) < amount:
            await update.message.reply_text("❌ Insufficient balance!")
            return 1
        if subtract_balance(str(user_id), amount):
            record_withdrawal(str(user_id), amount)
            await update.message.reply_text(
                f"✅ <b>Withdrawal Successful!</b>\n\nAmount: <b>₹{amount}</b>\nStatus: Pending\n\nYou'll receive it in 24 hours.\nAdmin will review and process.",
                parse_mode=ParseMode.HTML,
            )
            # Send withdrawal notification to admin channel
            if WITHDRAWAL_CHANNEL_ID:
                user = update.effective_user
                mention = f"@{user.username}" if user.username else f"[{user.full_name}](tg://user?id={user.id})"
                text = (
                    f"💸 <b>Withdrawal Request</b>\n\n"
                    f"👤 User: {mention}\n"
                    f"🆔 ID: <code>{user.id}</code>\n"
                    f"💰 Amount: ₹{amount}\n"
                    f"📅 Date: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n"
                    f"✅ Please process."
                )
                try:
                    await context.bot.send_message(chat_id=WITHDRAWAL_CHANNEL_ID, text=text, parse_mode=ParseMode.HTML)
                except Exception as e:
                    logger.error(f"Failed to send withdrawal notification to channel {WITHDRAWAL_CHANNEL_ID}: {e}")
            return ConversationHandler.END
        else:
            await update.message.reply_text("❌ Withdrawal failed. Try again.")
            return 1
    except ValueError:
        await update.message.reply_text("❌ Invalid amount. Send a number (e.g., 30)")
        return 1


async def cancel_withdrawal(update: Update, context):
    await update.message.reply_text("❌ Withdrawal cancelled.")
    return ConversationHandler.END


async def my_referrals_command(update: Update, context):
    user_id = update.effective_user.id
    user_balance = get_user_balance(user_id)
    referrals = user_balance.get("referrals", [])
    if not referrals:
        await update.message.reply_text(
            "👥 <b>My Referrals</b>\n\nYou don't have any referrals yet.\nStart sharing your link to earn! 🔗",
            parse_mode=ParseMode.HTML,
            reply_markup=ReplyKeyboardMarkup([[KeyboardButton("🔗 Referral Link")], [KeyboardButton("◀️ Back")]], resize_keyboard=True),
        )
        return
    data = load_balance_data()
    referral_bonus = data["config"]["referral_bonus"]
    lines = [f"👥 <b>My Referrals ({len(referrals)})</b>\n"]
    for i, ref_id in enumerate(referrals, 1):
        lines.append(f"{i}. ID: <code>{ref_id}</code>")
    lines.append(f"\n💵 Total Earned: <b>₹{len(referrals) * referral_bonus}</b>")
    text = "\n".join(lines)
    await update.message.reply_text(text, parse_mode=ParseMode.HTML, reply_markup=ReplyKeyboardMarkup([[KeyboardButton("🔗 Referral Link")], [KeyboardButton("◀️ Back")]], resize_keyboard=True))


async def settings_command(update: Update, context):
    user_id = update.effective_user.id
    user_data = load_users().get(str(user_id), {})
    text = (
        "⚙️ <b>Settings</b>\n\n━━━━━━━━━━━━━━━━━━━━━━\n"
        f"👤 <b>User ID:</b> <code>{user_id}</code>\n📝 <b>Name:</b> {user_data.get('name', 'Unknown')}\n"
        f"📅 <b>Joined:</b> {user_data.get('joined', 'N/A')}\n✅ <b>Verified:</b> {'Yes' if user_data.get('verified') else 'No'}\n\n"
        "✅ Language: English\n🔔 Notifications: On\n"
    )
    await update.message.reply_text(text, parse_mode=ParseMode.HTML, reply_markup=ReplyKeyboardMarkup([[KeyboardButton("📞 Need Help?")], [KeyboardButton("◀️ Back")]], resize_keyboard=True))


async def help_command(update: Update, context):
    text = (
        "📞 <b>Help & FAQ</b>\n\n━━━━━━━━━━━━━━━━━━━━━━\n\n"
        "<b>❓ How to earn?</b>\n✅ Join both channels\n✅ Get ₹2 bonus instantly\n✅ Share your referral link\n✅ Earn ₹3 per referral\n\n"
        "<b>💸 How to withdraw?</b>\n• Minimum: ₹30\n• Max per day: 1 withdrawal\n• Time: 24 hours\n\n"
        "<b>❓ Need more help?</b>\nContact: @support\n\n━━━━━━━━━━━━━━━━━━━━━━\n"
    )
    await update.message.reply_text(text, parse_mode=ParseMode.HTML, reply_markup=ReplyKeyboardMarkup([[KeyboardButton("💰 Check Balance")], [KeyboardButton("🔗 Referral Link")], [KeyboardButton("◀️ Back")]], resize_keyboard=True))


# ──────────────────────────────────────────────
#  MAIN MENU BUTTON HANDLER
# ──────────────────────────────────────────────
async def handle_button_press(update: Update, context):
    if not update.message or not update.message.text:
        return
    text = update.message.text
    user_id = update.effective_user.id

    if text in ["✅ Verify Both Channels", "✅ Try Verifying Again"]:
        await verify_callback(update, context)
        return
    if text in ["💰 Balance", "💰 Check Balance"]:
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
        if user_id not in ADMIN_IDS:
            await update.message.reply_text("⛔ Admin only!", reply_markup=get_verified_keyboard(user_id))
            return
        await admin_command(update, context)
        return
    if text in ["📊 Stats", "📈 Analytics", "👥 All Users", "👥 Users", "🔍 Check Channels", "💰 Balance Config", "💵 Top Balances", "📢 Broadcast", "💾 Export Users", "💰 Export Balance", "🗑️ Purge Inactive", "⚠️ Delete All"]:
        if user_id in ADMIN_IDS:
            await admin_command(update, context)
        else:
            await update.message.reply_text("⛔ Admin only!")
        return
    if text == "◀️ Back":
        if user_id in ADMIN_IDS:
            await admin_command(update, context)
        else:
            await start(update, context)
        return
    if text == "❌ Cancel":
        await update.message.reply_text("Cancelled.", reply_markup=get_back_keyboard())
        return


# ──────────────────────────────────────────────
#  BROADCAST
# ──────────────────────────────────────────────
async def broadcast_command(update: Update, context):
    if update.effective_user.id not in ADMIN_IDS:
        return ConversationHandler.END
    await update.message.reply_text(
        "📢 <b>Broadcast Mode</b>\n\nSend me the message you want to broadcast to all users.\nSend /cancel to abort.",
        parse_mode=ParseMode.HTML,
    )
    return WAITING_BROADCAST


async def broadcast_message(update: Update, context):
    users = load_user_ids()
    if not users:
        await update.message.reply_text("❌ No users in the database yet.")
        return ConversationHandler.END
    sent, failed = 0, 0
    status_msg = await update.message.reply_text(f"📤 Broadcasting to <b>{len(users)}</b> users...", parse_mode=ParseMode.HTML)
    for user_id in users:
        try:
            await context.bot.copy_message(chat_id=user_id, from_chat_id=update.message.chat_id, message_id=update.message.message_id)
            sent += 1
        except Exception as e:
            logger.warning(f"Failed to send to {user_id}: {e}")
            failed += 1
        await asyncio.sleep(0.05)
    await status_msg.edit_text(f"✅ <b>Broadcast Complete!</b>\n\n📨 Sent: <b>{sent}</b>\n❌ Failed: <b>{failed}</b>", parse_mode=ParseMode.HTML)
    return ConversationHandler.END


async def cancel_broadcast(update: Update, context):
    await update.message.reply_text("❌ Broadcast cancelled.")
    return ConversationHandler.END


# ──────────────────────────────────────────────
#  MAIN
# ──────────────────────────────────────────────
def main():
    if not TOKEN:
        raise ValueError("Set the BOT_TOKEN environment variable!")

    app = Application.builder().token(TOKEN).build()

    # Broadcast conversation
    broadcast_handler = ConversationHandler(
        entry_points=[CommandHandler("broadcast", broadcast_command)],
        states={WAITING_BROADCAST: [MessageHandler(filters.ALL & ~filters.COMMAND, broadcast_message)]},
        fallbacks=[CommandHandler("cancel", cancel_broadcast)],
    )
    app.add_handler(broadcast_handler)

    # Withdrawal conversation
    withdrawal_handler = ConversationHandler(
        entry_points=[CommandHandler("withdraw", withdraw_command)],
        states={1: [MessageHandler(filters.TEXT & ~filters.COMMAND, withdrawal_amount)]},
        fallbacks=[CommandHandler("cancel", cancel_withdrawal)],
    )
    app.add_handler(withdrawal_handler)

    # Command handlers
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("admin", admin_command))
    app.add_handler(CommandHandler("balance", balance_command))
    app.add_handler(CommandHandler("referral", referral_command))
    app.add_handler(CallbackQueryHandler(admin_panel_callback, pattern="^admin_"))

    # Button handler (must be last)
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_button_press))

    if RENDER_URL:
        webhook_url = f"{RENDER_URL}/webhook"
        logger.info(f"Starting webhook → {webhook_url}")
        app.run_webhook(listen="0.0.0.0", port=PORT, url_path="/webhook", webhook_url=webhook_url)
    else:
        logger.info("Polling mode (local dev)")
        app.run_polling(drop_pending_updates=True)


if __name__ == "__main__":
    main()