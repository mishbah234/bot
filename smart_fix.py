import re

# Read the entire file
with open('bot.py', 'rb') as f:
    data = f.read()

# Convert to string for easier manipulation
content = data.decode('utf-8', errors='replace')

# Use regex to find and replace the entire function
# Looking for: def get_verified_keyboard(user_id=None):  ... return ReplyKeyboardMarkup...

pattern = r'def get_verified_keyboard\(user_id=None\):\s+return ReplyKeyboardMarkup\(\[[\s\S]*?\], resize_keyboard=True\)'

replacement = '''def get_verified_keyboard(user_id=None):
    buttons = [
        [KeyboardButton("💰 Balance"), KeyboardButton("🔗 Referral Link")],
        [KeyboardButton("💸 Withdraw"), KeyboardButton("👥 My Referrals")],
        [KeyboardButton("⚙️ Settings"), KeyboardButton("📞 Help")],
    ]
    if user_id and user_id in ADMIN_IDS:
        buttons.append([KeyboardButton("⚙️ Admin Panel")])
    return ReplyKeyboardMarkup(buttons, resize_keyboard=True)'''

# Do the replacement
new_content = re.sub(pattern, replacement, content)

# Check if replacement was successful
if new_content != content:
    # Write back to file
    with open('bot.py', 'wb') as f:
        f.write(new_content.encode('utf-8'))
    print("✅ Successfully updated get_verified_keyboard!")
else:
    print("❌ Could not find pattern to replace")
    # Try simpler pattern
    if 'def get_verified_keyboard(user_id=None):' in content:
        print("Found function signature, trying simpler approach...")
        # Find start and end of function
        start = content.find('def get_verified_keyboard(user_id=None):')
        if start != -1:
            # Find next function definition
            next_def = content.find('\ndef ', start + 1)
            if next_def == -1:
                next_def = content.find('\n# ──', start + 1)
            
            if next_def != -1:
                # Extract before function
                before = content[:start]
                after = content[next_def:]
                
                # Create new function
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
                with open('bot.py', 'wb') as f:
                    f.write(new_content.encode('utf-8'))
                print("✅ Successfully updated get_verified_keyboard using fallback method!")
