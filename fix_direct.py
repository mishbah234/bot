#!/usr/bin/env python3
import sys

with open('bot.py', 'r', encoding='utf-8') as f:
    lines = f.readlines()

output = []
i = 0
while i < len(lines):
    line = lines[i]
    if 'def get_verified_keyboard()' in line:
        print(f"Found target at line {i}: {repr(line)}")
        # Write the new function
        output.append('def get_verified_keyboard(user_id=None):\n')
        output.append('    buttons = [\n')
        output.append('        [KeyboardButton("' + chr(0x1F4B0) + ' Balance"), KeyboardButton("' + chr(0x1F517) + ' Referral Link")],\n')
        output.append('        [KeyboardButton("' + chr(0x1F4B8) + ' Withdraw"), KeyboardButton("' + chr(0x1F465) + ' My Referrals")],\n')
        output.append('        [KeyboardButton("' + chr(0x2699) + chr(0xFE0F) + ' Settings"), KeyboardButton("' + chr(0x1F4DE) + ' Help")],\n')
        output.append('    ]\n')
        output.append('    if user_id and user_id in ADMIN_IDS:\n')
        output.append('        buttons.append([KeyboardButton("' + chr(0x2699) + chr(0xFE0F) + ' Admin Panel")])\n')
        output.append('    return ReplyKeyboardMarkup(buttons, resize_keyboard=True)\n')
        
        # Skip old lines
        i += 1
        while i < len(lines):
            if lines[i].strip().startswith('def ') or (lines[i].startswith('# ') and lines[i].startswith('#  ')):
                break
            i += 1
        i -= 1
    else:
        output.append(line)
    i += 1

with open('bot.py', 'w', encoding='utf-8') as f:
    f.writelines(output)

print("✅ Successfully fixed get_verified_keyboard!")
