#!/usr/bin/env python3
import re

with open('bot.py', 'r', encoding='utf-8') as f:
    content = f.read()

# Replace the old function with the new one
old_func = r'def get_verified_keyboard\(\):\s+return ReplyKeyboardMarkup\(\[\s+\[KeyboardButton\([^]]+\), KeyboardButton\([^]]+\)\],\s+\[KeyboardButton\([^]]+\), KeyboardButton\([^]]+\)\],\s+\[KeyboardButton\([^]]+\), KeyboardButton\([^]]+\)\],\s+\], resize_keyboard=True\)'

new_func = '''def get_verified_keyboard(user_id=None):
    buttons = [
        [KeyboardButton("💰 Balance"), KeyboardButton("🔗 Referral Link")],
        [KeyboardButton("💸 Withdraw"), KeyboardButton("👥 My Referrals")],
        [KeyboardButton("⚙️ Settings"), KeyboardButton("📞 Help")],
    ]
    
    # Add admin panel button for admins only
    if user_id and user_id in ADMIN_IDS:
        buttons.append([KeyboardButton("⚙️ Admin Panel")])
    
    return ReplyKeyboardMarkup(buttons, resize_keyboard=True)'''

content = re.sub(old_func, new_func, content, flags=re.DOTALL)

with open('bot.py', 'w', encoding='utf-8') as f:
    f.write(content)

print("✅ Function fixed!")
