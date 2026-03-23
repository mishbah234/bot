import subprocess

# Get the start function from previous commit
result = subprocess.run(['git', 'show', '165fc68:bot.py'], capture_output=True, text=True)
if result.returncode != 0:
    print(f"ERROR: {result.stderr}")
    exit(1)

old_content = result.stdout

# Extract start function
start_idx = old_content.find('async def start(')
if start_idx == -1:
    print("ERROR: Could not find start function in previous commit")
    exit(1)

end_idx = old_content.find('\nasync def ', start_idx + 1)
if end_idx == -1:
    end_idx = len(old_content)

start_function = old_content[start_idx:end_idx].rstrip()

# Read current bot.py
with open('bot.py', 'r', encoding='utf-8') as f:
    current_content = f.read()

# Find where to insert (after get_back_keyboard function)
insert_marker = 'def get_back_keyboard():'
insert_idx = current_content.find(insert_marker)

if insert_idx == -1:
    print("ERROR: Could not find insert marker in current file")
    exit(1)

# Find end of get_back_keyboard function (next def or next async def)
func_end = current_content.find('\ndef ', insert_idx + 1)
if func_end == -1:
    func_end = current_content.find('\nasync def ', insert_idx + 1)
if func_end == -1:
    print("ERROR: Could not find end of get_back_keyboard")
    exit(1)

# Insert the start function
new_content = current_content[:func_end] + '\n\n' + start_function + '\n' + current_content[func_end:]

# Write back
with open('bot.py', 'w', encoding='utf-8') as f:
    f.write(new_content)

print("✅ Successfully restored start function!")
