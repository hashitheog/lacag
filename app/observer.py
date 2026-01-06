import asyncio
import time
import statistics
import requests
from colorama import Fore, Style
import config

class MarketObserver:
    """
    Monitors a token for a set duration (e.g., 60s) to extract behavioral metrics.
    Uses DexScreener API to poll price, volume, and tx data.
    """
    def __init__(self):
        self.interval = 10 # Poll every 10 seconds
        self.duration = 60 # Total observation time

    async def observe(self, pair_address, chain="solana"):
        print(f"{Fore.CYAN}[OBSERVER]{Style.RESET_ALL} Watching {pair_address} for {self.duration}s...")
        
        history = []
        api_url = f"https://api.dexscreener.com/latest/dex/pairs/{chain}/{pair_address}"
        
        start_time = time.time()
        
        while (time.time() - start_time) < self.duration:
            try:
                # Fetch Data
                # Run sync request in executor
                loop = asyncio.get_event_loop()
                def fetch_data():
                    return requests.get(api_url, timeout=5).json()

                data = await loop.run_in_executor(None, fetch_data)
                
                if data and data.get('pairs'):
                    pair_data = data['pairs'][0]
                    
                    snapshot = {
                        "timestamp": time.time(),
                        "price": float(pair_data.get('priceUsd', 0)),
                        "txs": pair_data.get('txns', {}), # Dict of m5, h1, h6...
                        "volume": pair_data.get('volume', {}),
                        "liquidity": pair_data.get('liquidity', {}).get('usd', 0)
                    }
                    history.append(snapshot)
                    # print(f".", end="", flush=True) # Heartbeat
                
            except Exception as e:
                print(f"Observe Error: {e}")
            
            await asyncio.sleep(self.interval)
            
        print(f" Done.")
        return self._calculate_metrics(history)

    def _calculate_metrics(self, history):
        if not history:
            return None

        # 1. Price Stability & Recovery
        prices = [h['price'] for h in history]
        if not prices: return None
        
        start_price = prices[0]
        end_price = prices[-1]
        price_change_pct = ((end_price - start_price) / start_price) * 100 if start_price else 0
        
        # Volatility (Std Dev) using statistics module
        if len(prices) > 1:
            volatility = statistics.stdev(prices)
        else:
            volatility = 0
        
        # Recovery: Did it verify a dip? (Simple heuristic)
        # We'll just report if it trended up or held stable
        trend = "volatile"
        if abs(price_change_pct) < 2.0: trend = "stable"
        elif price_change_pct > 2.0: trend = "uptrend"
        elif price_change_pct < -2.0: trend = "downtrend"

        # 2. Buy/Sell Flow (Using m5 data if available, or diffing snapshots)
        # DexScreener API 'txns' gives { m5: { buys: X, sells: Y } }
        # We can look at the latest snapshot's m5 data
        last_snap = history[-1]['txs'].get('m5', {})
        buys = last_snap.get('buys', 0)
        sells = last_snap.get('sells', 0)
        
        buy_sell_ratio = buys / sells if sells > 0 else (buys if buys > 0 else 1.0)
        
        # 3. Liquidity Stability
        liq_start = history[0]['liquidity']
        liq_end = history[-1]['liquidity']
        liq_change = ((liq_end - liq_start) / liq_start) * 100 if liq_start else 0
        
        # 4. Consistency (Heuristic based on price updates)
        # If we have many distinct price points, it's active
        unique_prices = len(set(prices))
        activity_level = "high" if unique_prices > 3 else "low"

        return {
            "price_trend": trend,
            "volatility_score": volatility,
            "buy_sell_ratio_5m": buy_sell_ratio,
            "liquidity_change_pct": liq_change,
            "activity_level": activity_level,
            "buys_5m": buys,
            "sells_5m": sells,
            "observed_price_change_pct": price_change_pct
        }
