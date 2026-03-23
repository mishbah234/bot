$content = Get-Content 'bot.py' -Raw
$pattern = 'def get_verified_keyboard\(\):\s+return ReplyKeyboardMarkup\(\[\s+\[KeyboardButton\([^]]*Balance[^]]*\), KeyboardButton\([^]]*\]\],[\s\S]*?\], resize_keyboard=True\)'
$replacement = @'
def get_verified_keyboard(user_id=None):
    buttons = [
        [KeyboardButton("💰 Balance"), KeyboardButton("🔗 Referral Link")],
        [KeyboardButton("💸 Withdraw"), KeyboardButton("👥 My Referrals")],
        [KeyboardButton("⚙️ Settings"), KeyboardButton("📞 Help")],
    ]
    
    # Add admin panel button for admins only
    if user_id and user_id in ADMIN_IDS:
        buttons.append([KeyboardButton("⚙️ Admin Panel")])
    
    return ReplyKeyboardMarkup(buttons, resize_keyboard=True)
'@

$content = [regex]::Replace($content, $pattern, $replacement)
Set-Content 'bot.py' $content
Write-Host "✅ Fixed!"
