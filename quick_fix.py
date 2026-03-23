#!/usr/bin/env python3
with open('bot.py', 'r', encoding='utf-8') as f:
    lines = f.readlines()

# Find the line with get_verified_keyboard and replace the function
output = []
i = 0
while i < len(lines):
    if 'def get_verified_keyboard(user_id=None):' in lines[i]:
        # Add the function with proper body
        output.append('def get_verified_keyboard(user_id=None):\n')
        output.append('    buttons = [\n')
        output.append('        [KeyboardButton("💰 Balance"), KeyboardButton("🔗 Referral Link")],\n')
        output.append('        [KeyboardButton("💸 Withdraw"), KeyboardButton("👥 My Referrals")],\n')
        output.append('        [KeyboardButton("⚙️ Settings"), KeyboardButton("📞 Help")],\n')
        output.append('    ]\n')
        output.append('    if user_id and user_id in ADMIN_IDS:\n')
        output.append('        buttons.append([KeyboardButton("⚙️ Admin Panel")])\n')
        output.append('    return ReplyKeyboardMarkup(buttons, resize_keyboard=True)\n')
        
        # Skip old function lines
        i += 1
        while i < len(lines) and not (lines[i].startswith('def ') or lines[i].startswith('# ──')):
            i += 1
        i -= 1  # Back up to not skip next section
    else:
        output.append(lines[i])
    i += 1

with open('bot.py', 'w', encoding='utf-8') as f:
    f.writelines(output)

print("✅ Fixed get_verified_keyboard function!")
