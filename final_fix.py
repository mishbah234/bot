with open('bot.py', 'r', encoding='utf-8') as f:
    content = f.read()

# Simple string replacement
old = '''def get_verified_keyboard():
    return ReplyKeyboardMarkup([
        [KeyboardButton("💰 Balance"), KeyboardButton("🔗 Referral Link")],
        [KeyboardButton("💸 Withdraw"), KeyboardButton("👥 My Referrals")],
        [KeyboardButton("⚙️ Settings"), KeyboardButton("📞 Help")],
    ], resize_keyboard=True)'''

new = '''def get_verified_keyboard(user_id=None):
    buttons = [
        [KeyboardButton("💰 Balance"), KeyboardButton("🔗 Referral Link")],
        [KeyboardButton("💸 Withdraw"), KeyboardButton("👥 My Referrals")],
        [KeyboardButton("⚙️ Settings"), KeyboardButton("📞 Help")],
    ]
    if user_id and user_id in ADMIN_IDS:
        buttons.append([KeyboardButton("⚙️ Admin Panel")])
    return ReplyKeyboardMarkup(buttons, resize_keyboard=True)'''

if old in content:
    content = content.replace(old, new)
    with open('bot.py', 'w', encoding='utf-8') as f:
        f.write(content)
    print("✅ Fixed!")
else:
    print("❌ Pattern not found, trying alternative...")
    # Try without the emoji
    alt_old = '''def get_verified_keyboard():
    return ReplyKeyboardMarkup(['''
    if alt_old in content:
        print("Found alternative, using line-by-line approach...")
        lines = content.split('\n')
        new_lines = []
        i = 0
        while i < len(lines):
            if lines[i] == 'def get_verified_keyboard():':
                # Add the new function
                new_lines.extend([
                    'def get_verified_keyboard(user_id=None):',
                    '    buttons = [',
                    '        [KeyboardButton("💰 Balance"), KeyboardButton("🔗 Referral Link")],',
                    '        [KeyboardButton("💸 Withdraw"), KeyboardButton("👥 My Referrals")],',
                    '        [KeyboardButton("⚙️ Settings"), KeyboardButton("📞 Help")],',
                    '    ]',
                    '    if user_id and user_id in ADMIN_IDS:',
                    '        buttons.append([KeyboardButton("⚙️ Admin Panel")])',
                    '    return ReplyKeyboardMarkup(buttons, resize_keyboard=True)',
                ])
                # Skip old lines until we find the next function
                i += 1
                while i < len(lines) and not (lines[i].startswith('def ') or lines[i].startswith('# ')):
                    i += 1
                i -= 1  # Back up one so we don't skip the next def
            else:
                new_lines.append(lines[i])
            i += 1
        
        with open('bot.py', 'w', encoding='utf-8') as f:
            f.write('\n'.join(new_lines))
        print("✅ Fixed using line-by-line!")
    else:
        print("❌ Could not find pattern")
