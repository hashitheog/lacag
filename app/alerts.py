import requests
import config

def send_telegram_alert(token_symbol, market_data, security_data, ai_result):
    if not config.TELEGRAM_BOT_TOKEN or not config.TELEGRAM_CHAT_ID:
        return

    # Emojis based on score
    score = ai_result.get('confidence', 0.5)
    header = "🚨 GEM FOUND" if score > 0.8 else "👀 NEW LAUNCH WATCH"
    
    msg = f"""
{header} | {token_symbol}

🧠 **AI Verdict**: {ai_result.get('decision')} ({int(score*100)}%)
🚀 **Potential**: ${ai_result.get('potential_mc', 0):,.0f} MC
📝 *{ai_result.get('reasoning')}*

📊 **Market**
• Liq: ${market_data.get('liquidity_usd', 0):,.0f}
• Age: {market_data.get('pair_age_minutes')}m

📜 **Contract**: `{market_data.get('pair_address')}`

🛡️ **Security**
• Honeypot: {security_data.get('is_honeypot')}
• Tax: {security_data.get('buy_tax')}% / {security_data.get('sell_tax')}%
• Mintable: {security_data.get('is_mintable')}

[DexScreener]({config.BASE_URL}/solana/{market_data.get('pair_address')})
"""
    
    url = f"https://api.telegram.org/bot{config.TELEGRAM_BOT_TOKEN}/sendMessage"
    payload = {
        "chat_id": config.TELEGRAM_CHAT_ID,
        "text": msg,
        "parse_mode": "Markdown"
    }
    
    try:
        requests.post(url, json=payload, timeout=5)
    except Exception as e:
        print(f"Telegram Fail: {e}")

def send_startup_message():
    if not config.TELEGRAM_BOT_TOKEN or not config.TELEGRAM_CHAT_ID:
        return

    msg = f"🚀 **GOD MODE ACTIVATED**\nMode: {config.RISK_TOLERANCE.upper()}\nChain: {config.TARGET_CHAIN_ID.upper()}\nWaiting for gems..."
    
    url = f"https://api.telegram.org/bot{config.TELEGRAM_BOT_TOKEN}/sendMessage"
    payload = {
        "chat_id": config.TELEGRAM_CHAT_ID,
        "text": msg,
        "parse_mode": "Markdown"
    }
    try:
        requests.post(url, json=payload, timeout=5)
    except:
        pass

def send_trade_update(message):
    """Sends a simple text alert for Trade Updates (TP/SL)."""
    if not config.TELEGRAM_BOT_TOKEN or not config.TELEGRAM_CHAT_ID:
        return

    url = f"https://api.telegram.org/bot{config.TELEGRAM_BOT_TOKEN}/sendMessage"
    payload = {
        "chat_id": config.TELEGRAM_CHAT_ID,
        "text": message
        # "parse_mode": "Markdown" # Disabled due to Error 400 on special chars
    }
    
    # Strip ANSI colors? Telegram doesn't like them.
    # Simple cleaner
    import re
    clean_msg = re.sub(r'\x1b\[[0-9;]*m', '', message)
    payload['text'] = clean_msg
    
    try:
        # print(f"{Fore.BLUE}[TELEGRAM]{Style.RESET_ALL} Sending alert...") # Optional: Debug
        response = requests.post(url, json=payload, timeout=5)
        if response.status_code != 200:
             print(f"Telegram Error {response.status_code}: {response.text}")
        else:
             # print("Telegram Sent.")
             pass
    except Exception as e:
        print(f"Telegram Connection Failed: {e}")
