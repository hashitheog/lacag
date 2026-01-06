import requests
import config
from colorama import Fore, Style

class TelegramBot:
    """
    Lightweight Telegram Bot for handling User Commands via polling.
    Supported Commands:
    /balance - View Capital and PnL.
    /active - View Active Trades.
    """
    def __init__(self):
        self.token = config.TELEGRAM_BOT_TOKEN
        self.chat_id = config.TELEGRAM_CHAT_ID
        self.offset = 0
        self.base_url = f"https://api.telegram.org/bot{self.token}"

    def check_updates(self, trade_manager):
        """
        Polls for new messages and processes commands.
        Should be called in the main loop (non-blocking if timeout is low).
        """
        if not self.token: return

        url = f"{self.base_url}/getUpdates"
        params = {
            "offset": self.offset + 1,
            "timeout": 1 # Very short timeout to not block main scraper loop
        }
        
        try:
            resp = requests.get(url, params=params, timeout=2) # 2s max wait
            if resp.status_code == 200:
                data = resp.json()
                if data.get('ok'):
                    results = data.get('result', [])
                    for update in results:
                        self._process_message(update, trade_manager)
                        self.offset = max(self.offset, update.get('update_id', 0))
        except Exception:
            pass # Ignore connection errors to keep loop alive

    def _process_message(self, update, trade_manager):
        message = update.get('message', {})
        text = message.get('text', '').strip()
        chat_id = str(message.get('chat', {}).get('id', ''))
        
        # Security: Only respond to admin chat
        if chat_id != str(self.chat_id):
            return

        if text == '/balance':
            self._send_balance(trade_manager)
        elif text == '/active':
            self._send_active(trade_manager)

    def _send_balance(self, tm):
        """Replies with Capital Stats."""
        active_count = len(tm.active_trades)
        
        # Calculate Total Net PnL from History
        total_pnl = sum(t.get('net_pnl', 0) for t in tm.trade_history)
        
        msg = (
            f"💰 **WALLET STATUS**\n\n"
            f"💵 **Capital**: ${tm.capital:.2f}\n"
            f"📈 **Realized PnL**: ${total_pnl:+.2f}\n"
            f"🔄 **Active Trades**: {active_count}/{tm.max_trades}\n"
            f"🛡️ **Mode**: {config.RISK_TOLERANCE.upper()}"
        )
        self._send(msg)

    def _send_active(self, tm):
        """Replies with Active Trade Details."""
        if not tm.active_trades:
            self._send("💤 No active trades.")
            return

        msg = "🚀 **ACTIVE TRADES**\n"
        for symbol, t in tm.active_trades.items():
            entry = t['entry_price']
            curr = t['current_price']
            
            # ROI
            roi = ((curr - entry) / entry) * 100
            
            msg += (
                f"\n**{symbol}**\n"
                f"Entry: ${entry:.6f}\n"
                f"Current: ${curr:.6f}\n"
                f"PnL: {roi:+.2f}%\n"
                f"Value: ${t['tokens_held']*curr:.2f}\n"
            )
        
        self._send(msg)

    def _send(self, text):
        url = f"{self.base_url}/sendMessage"
        payload = {
            "chat_id": self.chat_id,
            "text": text,
            "parse_mode": "Markdown"
        }
        try:
            requests.post(url, json=payload, timeout=5)
        except:
            pass
