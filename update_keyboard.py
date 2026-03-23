import re

with open('bot.py', 'r', encoding='utf-8') as f:
    content = f.read()

# Find and replace the get_admin_keyboard function
old_pattern = r'def get_admin_keyboard\(\):.*?return InlineKeyboardMarkup\(\[.*?\]\)'
new_code = '''def get_admin_keyboard():
    return ReplyKeyboardMarkup([
        [KeyboardButton("📊 Stats"), KeyboardButton("📈 Analytics")],
        [KeyboardButton("👥 All Users"), KeyboardButton("🔍 Check Channels")],
        [KeyboardButton("💰 Balance Config"), KeyboardButton("💵 Top Balances")],
        [KeyboardButton("📢 Broadcast"), KeyboardButton("💾 Export Users")],
        [KeyboardButton("💾 Export Balance"), KeyboardButton("🗑️ Purge Inactive")],
        [KeyboardButton("⚠️ Delete All"), KeyboardButton("◀️ Back")],
    ], resize_keyboard=True)'''

content = re.sub(old_pattern, new_code, content, flags=re.DOTALL)

with open('bot.py', 'w', encoding='utf-8') as f:
    f.write(content)

print("✅ Admin keyboard updated successfully!")
