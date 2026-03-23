import subprocess

result = subprocess.run(['git', 'show', '165fc68:bot.py'], capture_output=True, text=True)
if result.returncode == 0:
    content = result.stdout
    start_idx = content.find('async def start(')
    if start_idx != -1:
        end_idx = content.find('\nasync def ', start_idx + 1)
        if end_idx == -1:
            end_idx = len(content)
        func = content[start_idx:end_idx].rstrip()
        print(func)
    else:
        print('NOT FOUND')
else:
    print(f'Error: {result.stderr}')
