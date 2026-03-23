with open('bot.py', 'r', encoding='utf-8') as f:
    lines = f.readlines()

# Find the line with 'def get_admin_keyboard():'
for i, line in enumerate(lines):
    if 'def get_admin_keyboard()' in line:
        print(f"Found at line {i}: {line.strip()}")
        # Print the next 15 lines
        for j in range(i, min(i+15, len(lines))):
            print(f"{j}: {repr(lines[j])}")
