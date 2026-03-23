import sys

# Read the file
with open('bot.py', 'rb') as f:
    content = f.read()

# Find the function
start = content.find(b'def get_verified_keyboard():')
if start != -1:
    # Find the end - look for the next 'def ' or '# ' at the start of a line
    end = content.find(b'\ndef ', start + 1)
    if end == -1:
        end = content.find(b'\n# ', start + 1)
    
    print(f"Found function at {start}-{end}")
    print("Current function signature:")
    print(content[start:start+100])
    
    # Create new function
    new_func = b'''def get_verified_keyboard(user_id=None):
    buttons = [
        [KeyboardButton("\xf0\x9f\x92\xb0 Balance"), KeyboardButton("\xf0\x9f\x94\x97 Referral Link")],
        [KeyboardButton("\xf0\x9f\x92\xb8 Withdraw"), KeyboardButton("\xf0\x9f\x91\xa5 My Referrals")],
        [KeyboardButton("\xe2\x9a\x99\xef\xb8\x8f Settings"), KeyboardButton("\xf0\x9f\x93\žž Help")],
    ]
    
    # Add admin panel button for admins only
    if user_id and user_id in ADMIN_IDS:
        buttons.append([KeyboardButton("\xe2\x9a\x99\xef\xb8\x8f Admin Panel")])
    
    return ReplyKeyboardMarkup(buttons, resize_keyboard=True)
'''
    
    # Replace
    content = content[:start] + new_func + content[end:]
    
    with open('bot.py', 'wb') as f:
        f.write(content)
    
    print("✅ Fixed!")
else:
    print("❌ Function not found!")
