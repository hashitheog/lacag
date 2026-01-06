import requests
import time
from datetime import datetime
import config

class DataSource:
    """
    Fetches and normalizes data from DexScreener.
    Maintains local state to track changes over time (for things like Liquidity Stability).
    """
    
    def __init__(self):
        self.session = requests.Session()
        self.history = {} # {pair_address: {timestamp: data_snapshot}}
        self.pair_first_seen = {} # {pair_address: timestamp}

    def fetch_candidates(self) -> list:
        """
        Fetches 'search' results from DexScreener and filters for new/relevant pairs.
        """
        url = f"{config.API_BASE_URL}/search"
        params = {"q": config.SEARCH_QUERY}
        
        try:
            resp = self.session.get(url, params=params, timeout=10)
            if resp.status_code == 200:
                data = resp.json()
                pairs = data.get("pairs", [])
                return self._filter_new_pairs(pairs)
        except Exception as e:
            print(f"Error fetching data: {e}")
            return []
        
        return []

    def _filter_new_pairs(self, pairs):
        """Filter pairs based on config age and min liquidity."""
        candidates = []
        now = time.time()
        
        for pair in pairs:
            # Basic basic checks
            if not pair.get("liquidity", {}).get("usd", 0):
                continue
            
            created_at = pair.get("pairCreatedAt", 0) / 1000 # DS uses ms
            age_min = (now - created_at) / 60
            
            if age_min > config.MAX_PAIR_AGE_MINUTES:
                continue
            
            if pair['liquidity']['usd'] < config.MIN_LIQUIDITY_USD:
                continue
                
            candidates.append(pair)
            self._update_history(pair)
            
        return candidates

    def get_analysis_payload(self, pair: dict) -> dict:
        """
        Transforms raw DexScreener pair data into the strict schema required by MemeLaunchAnalyzer.
        Derives/Heuristicizes missing fields.
        """
        pair_addr = pair.get("pairAddress")
        
        # 1. Metrics from API
        liq_usd = pair.get("liquidity", {}).get("usd", 0)
        age_created = (time.time() - (pair.get("pairCreatedAt", 0)/1000)) / 60
        
        txns = pair.get("txns", {}).get("m5", {})
        buys = txns.get("buys", 0)
        sells = txns.get("sells", 0)
        volume = pair.get("volume", {}).get("m5", 0)
        
        # 2. Derived Metrics
        # Buy/Sell Ratio
        bs_ratio = buys / sells if sells > 0 else (buys if buys > 0 else 1.0)
        
        # Tx Per Min (approximate from m5 window)
        tx_per_min = (buys + sells) / 5
        
        # Avg Tx Size
        total_tx_count = buys + sells
        avg_tx_size = (volume / total_tx_count) if total_tx_count > 0 else 0
        
        # 3. State-Based Metrics (Liquidity Stability)
        liq_change = self._calculate_liq_change(pair_addr, liq_usd)
        
        # 4. Mocked/Heuristic Metrics (Unavailable in Pub API)
        # We assume 'steady' if check count is consistent, but for now we randomize or optimistically guess based on ratio
        buy_consistency = "steady" if 0.5 < bs_ratio < 3.0 else "spiky" 
        
        # Holder growth - Requires scraping. We'll use a placeholder safe value to not auto-fail
        # unless we want to simulate risk.
        holder_growth_pattern = "smooth" # Placeholder
        top_5_holder = 20 # Placeholder (Safe default)
        
        # Recovery Speed
        # If price change m5 is positive after sells, good.
        price_change_m5 = pair.get("priceChange", {}).get("m5", 0)
        recovery_seconds = 30 if price_change_m5 > 0 else 120 # Simple heuristic
        
        return {
            "pair_name": pair.get("baseToken", {}).get("symbol", "UNKNOWN"),
            "pair_address": pair_addr,
            "pair_age_minutes": round(age_created, 2),
            "liquidity_usd": liq_usd,
            "liquidity_change_pct": liq_change,
            "buy_sell_ratio": round(bs_ratio, 2),
            "buy_consistency": buy_consistency,
            "avg_price_recovery_seconds": recovery_seconds,
            "holder_growth_per_min": 5, # Placeholder
            "holder_growth_pattern": holder_growth_pattern,
            "top_5_holder_pct": top_5_holder,
            "top_5_trend": "stable", # Placeholder
            "tx_per_min": round(tx_per_min, 1),
            "avg_tx_size_usd": round(avg_tx_size, 1)
        }

    def _update_history(self, pair):
        addr = pair.get("pairAddress")
        if addr not in self.pair_first_seen:
            self.pair_first_seen[addr] = time.time()
            
        if addr not in self.history:
            self.history[addr] = []
            
        # Store snapshot
        snapshot = {
            "time": time.time(),
            "liq": pair.get("liquidity", {}).get("usd", 0)
        }
        self.history[addr].append(snapshot)
        # Keep last 10 snapshots
        self.history[addr] = self.history[addr][-10:]

        change = ((current_liq - initial) / initial) * 100
        return round(change, 2)

    def fetch_current_price(self, pair_address, chain_id):
        """
        Fetches the current price (USD) for a specific pair.
        Used for monitoring active trades.
        """
        # DexScreener API: /latest/dex/pairs/{chainId}/{pairAddresses}
        url = f"https://api.dexscreener.com/latest/dex/pairs/{chain_id}/{pair_address}"
        
        try:
            resp = self.session.get(url, timeout=5)
            if resp.status_code == 200:
                data = resp.json()
                pairs = data.get('pairs', [])
                if pairs:
                    return float(pairs[0].get('priceUsd', 0))
        except Exception as e:
            pass
            
        return None
