import re

with open('bot.py', 'r', encoding='utf-8') as f:
    content = f.read()

# Find the function and replace
start_marker = "def get_verified_keyboard(user_id=None):"
section_end = "# ──────────────────────────────────────"

start_idx = content.find(start_marker)
if start_idx == -1:
    print("ERROR: Could not find function definition")
    exit(1)

# Find end of function (next section marker or next def)
end_marker_pos = content.find("\n\ndef ", start_idx + 1)
if end_marker_pos == -1:
    end_marker_pos = len(content)

# Extract the parts
before = content[:start_idx]
after = content[end_marker_pos:]

# New function
new_func = '''def get_verified_keyboard(user_id=None):
    buttons = [
        [KeyboardButton("💰 Balance"), KeyboardButton("🔗 Referral Link")],
        [KeyboardButton("💸 Withdraw"), KeyboardButton("👥 My Referrals")],
        [KeyboardButton("⚙️ Settings"), KeyboardButton("📞 Help")],
    ]
    if user_id and user_id in ADMIN_IDS:
        buttons.append([KeyboardButton("⚙️ Admin Panel")])
    return ReplyKeyboardMarkup(buttons, resize_keyboard=True)
'''

new_content = before + new_func + after

with open('bot.py', 'w', encoding='utf-8') as f:
    f.write(new_content)

print("✅ Function updated successfully!")
