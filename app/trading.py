import logging
import time
from colorama import Fore, Style

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

class TradeManager:
    """
    Manages active trades, position sizing, and exit logic (SL/TP).
    Constraint: Max 4 Concurrent Trades.
    Risk: 5% of Capital per Trade.
    """
    def __init__(self, initial_capital=200.0):
        self.capital = initial_capital
        self.active_trades = {} # Key: symbol, Value: Trade Dict
        self.trade_history = []
        self.max_trades = 4
        self.risk_per_trade = 0.05 # 5%

    def can_open_trade(self):
        """Check if we have a slot open."""
        return len(self.active_trades) < self.max_trades

    def open_trade(self, symbol, entry_price, market_cap, pair_address, chain_id, potential_target_mc=None):
        """
        Opens a new paper trade.
        """
        if not self.can_open_trade():
            logging.warning(f"Trade Rejected: Max slots ({self.max_trades}) full.")
            return False

        # Position Sizing
        position_size = self.capital * self.risk_per_trade
        
        # Determine Potential Price (TP2) based on input or default (e.g., 5x)
        # If user didn't provide specific target, assume 10x for now or let signals drive it.
        # User prompt implies "signal called potential price".
        target_mc = potential_target_mc if potential_target_mc else market_cap * 10
        target_price = entry_price * (target_mc / market_cap)

        trade = {
            "symbol": symbol,
            "pair_address": pair_address,
            "chain_id": chain_id,
            "entry_price": entry_price,
            "entry_mc": market_cap,
            "current_price": entry_price,
            "highest_price": entry_price, # START TRAILING
            "position_size": position_size,
            "tokens_held": position_size / entry_price,
            "start_time": time.time(),
            "target_price": target_price,
            "target_mc": target_mc,
            
            # State Flags
            "target_hit": False,
            "next_tp_price": entry_price * 2.0, # Start at 2x
            
            # PnL
            "realized_pnl": 0.0
        }
        
        self.active_trades[symbol] = trade
        self.capital -= position_size # Deduct "Locked" capital (Paper)
        
        print(f"\n{Fore.GREEN}[TRADE OPEN]{Style.RESET_ALL} {symbol}")
        print(f"Size: ${position_size:.2f} (5% of Cap)")
        print(f"Entry: ${entry_price:.6f} | MC: ${market_cap:,.0f}")
        print(f"Target: ${target_price:.6f} (MC: ${target_mc:,.0f})")
        print(f"Slots: {len(self.active_trades)}/{self.max_trades}")
        return True

    def update_trade(self, symbol, current_price):
        """
        Updates a trade with new price data and checks exits.
        Returns: (status_message, is_closed)
        """
        trade = self.active_trades.get(symbol)
        if not trade:
            return None, False

        trade['current_price'] = current_price
        
        # Update High Water Mark
        if current_price > trade['highest_price']:
            trade['highest_price'] = current_price
            
        # ---------------------------
        # 1. TRAILING STOP LOSS (-50% from High)
        # ---------------------------
        # "rid[e] [...] till coin makes 50 percent drop then we sell all"
        
        # Calculate drop from peak
        peak = trade['highest_price']
        drop_pct = ((current_price - peak) / peak) * 100
        
        if drop_pct <= -50.0:
             self._close_full(symbol, current_price, f"TRAILING STOP (-50% from ${peak:.6f})")
             return f"{Fore.RED}[TRAILING STOP]{Style.RESET_ALL} {symbol} dropped 50% from Peak. RUG PROTECTED.", True

        # ---------------------------
        # 2. TARGET PRICE (70% Sell)
        # ---------------------------
        # Check if we hit Potential Price
        if current_price >= trade['target_price'] and not trade['target_hit']:
             self._sell_partial(symbol, 0.70, current_price, "TP TARGET (Potential Reached)")
             trade['target_hit'] = True
             return f"{Fore.GREEN}[TARGET HIT]{Style.RESET_ALL} {symbol} reached Potential Price! Sold 70%.", False
             
        # ---------------------------
        # 3. DOUBLING LADDER (50% Sell every 2x)
        # ---------------------------
        # "sell 50 percent when ever the mc doubles"
        if current_price >= trade['next_tp_price']:
             # Determine multiplier
             mult = current_price / trade['entry_price']
             
             self._sell_partial(symbol, 0.50, current_price, f"TP LADDER ({mult:.1f}x)")
             trade['next_tp_price'] *= 2.0 # Schedule next double
             return f"{Fore.GREEN}[PUMP]{Style.RESET_ALL} {symbol} Doubled! Sold 50%. Next Lvl: ${trade['next_tp_price']:.6f}", False

        return None, False

    def _sell_partial(self, symbol, percent, price, reason):
        """Executes a partial sell."""
        trade = self.active_trades[symbol]
        
        amount_to_sell = trade['tokens_held'] * percent
        proceeds = amount_to_sell * price
        
        # Update State
        trade['tokens_held'] -= amount_to_sell
        trade['realized_pnl'] += proceeds # Add to "Cash Back" pile
        
        # Note: We don't add back to self.capital until trade closes fully?
        # Or we add recycled capital immediately.
        # "we can only take when one of them closes" implies slots are locked.
        # But capital is free.
        self.capital += proceeds 
        
        print(f"{Fore.CYAN}[SELL]{Style.RESET_ALL} {symbol} ({reason})")
        print(f"Sold: {percent*100}% | Cash Back: ${proceeds:.2f}")
        print(f"Remaining Bag: ${trade['tokens_held']*price:.2f}")

    def _close_full(self, symbol, price, reason):
        """Closes the entire position."""
        trade = self.active_trades[symbol]
        
        proceeds = trade['tokens_held'] * price
        trade['realized_pnl'] += proceeds
        
        # Calculate Total PnL
        total_in = trade['position_size']
        total_out = trade['realized_pnl']
        net = total_out - total_in
        
        self.capital += proceeds 
        
        # Log History
        completed_trade = trade.copy()
        completed_trade['exit_reason'] = reason
        completed_trade['net_pnl'] = net
        completed_trade['close_time'] = time.time()
        self.trade_history.append(completed_trade)
        
        del self.active_trades[symbol]
        
        print(f"{Fore.MAGENTA}[CLOSED]{Style.RESET_ALL} {symbol} ({reason})")
        print(f"Net PnL: ${net:.2f}")
        print(f"Capital Available: ${self.capital:.2f}")
        print(f"Slots Open: {self.max_trades - len(self.active_trades)}")

