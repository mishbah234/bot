with open('bot.py', 'r', encoding='utf-8') as f:
    lines = f.readlines()

# Find the line number where get_verified_keyboard is defined
for i, line in enumerate(lines):
    if 'def get_verified_keyboard()' in line:
        # Replace the function
        # Find the end of the function (the closing bracket)
        j = i + 1
        while j < len(lines) and not lines[j].startswith('def ') and not lines[j].startswith('# '):
            j += 1
        
        # Replace lines[i:j] with new function
        new_func = '''def get_verified_keyboard(user_id=None):
    buttons = [
        [KeyboardButton("💰 Balance"), KeyboardButton("🔗 Referral Link")],
        [KeyboardButton("💸 Withdraw"), KeyboardButton("👥 My Referrals")],
        [KeyboardButton("⚙️ Settings"), KeyboardButton("📞 Help")],
    ]
    
    # Add admin panel button for admins only
    if user_id and user_id in ADMIN_IDS:
        buttons.append([KeyboardButton("⚙️ Admin Panel")])
    
    return ReplyKeyboardMarkup(buttons, resize_keyboard=True)

'''
        lines[i:j] = [new_func]
        break

with open('bot.py', 'w', encoding='utf-8') as f:
    f.writelines(lines)

print("✅ get_verified_keyboard fixed!")
