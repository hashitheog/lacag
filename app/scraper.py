import asyncio
from playwright.async_api import async_playwright
import config
import re
import time
import os
import subprocess

class DexScreenerScraper:
    def __init__(self):
        self.browser = None
        self.context = None
        self.history = {}

    async def start(self):
        """Initializes the browser. Self-heals if browser missing."""
        
        # 1. Force Local Path
        local_browser_path = os.path.join(os.getcwd(), "pw-browsers")
        os.environ["PLAYWRIGHT_BROWSERS_PATH"] = local_browser_path
        
        # 2. Check & Install if missing
        print("Checking browser installation...")
        
        # BRUTE FORCE: Just run install. It's fast if already present.
        print(f"Ensuring Chromium exists in {local_browser_path}...")
        try:
             subprocess.run(["playwright", "install", "chromium"], check=True)
        except Exception as e:
             print(f"Browser Install Warning: {e}")

        # 3. Launch
        self.playwright = await async_playwright().start()
        self.browser = await self.playwright.chromium.launch(headless=config.HEADLESS)
        self.context = await self.browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        )
        print("Browser launched successfully.")

    async def stop(self):
        if self.browser:
            await self.browser.close()
        if self.playwright:
            await self.playwright.stop()

    async def scrape_candidates(self) -> list:
        """Navigates to New Pairs and extracts rows."""
        page = await self.context.new_page()
        try:
            # Navigate
            # Note: We append filtering query params if needed, but 'new-pairs' is a good start
            await page.goto(config.NEW_PAIRS_URL, timeout=30000)
            
            # Wait for table
            try:
                # Selector for the main pairs list.
                await page.wait_for_selector("a.ds-dex-table-row", timeout=10000)
                
                # URL param 'rankBy=pairAge' is handling validity. 
                # Removed manual click to save 2s per loop and avoid timeouts.
                
            except:
                print("Timeout waiting for table. Page might be blocked or loading.")
                return []

            # Get Rows (Link elements with strict class)
            row_elements = await page.query_selector_all("a.ds-dex-table-row")
            print(f"DEBUG: Found {len(row_elements)} raw table rows.")
            
            candidates = []
            
            for row in row_elements[:60]: # Scan top 60 to verify older tokens (up to 5h window)
                text_content = await row.inner_text()
                href = await row.get_attribute("href")
                
                # Basic Parsing
                parsed = self._parse_row_text(text_content, href)
                
                if parsed:
                    # Silence the spammy per-row debug unless needed
                    # print(f"DEBUG: Parsed {parsed['pair_name']} -> Age: {parsed['age_str']} ({self._parse_age_to_minutes(parsed['age_str'])}m), Liq: {parsed['liq_str']} (${self._parse_money(parsed['liq_str'])})")
                    if self._passes_filters(parsed):
                        candidates.append(parsed)
                else:
                    print(f"DEBUG: FALIED PARSE. Raw text start: {text_content[:50]}...")
            
            return candidates
            
        except Exception as e:
            print(f"Scrape Error: {e}")
            return []
        finally:
            await page.close()

    def _parse_row_text(self, text, href):
        """
        Parses the raw row text from DexScreener.
        Text usually contains: RANK, TOKEN, PRICE, AGE, TXNS, VOL, LIQ, FDV
        """
        try:
            lines = [l.strip() for l in text.split('\n') if l.strip()]
            # print(f"DEBUG LINES: {lines}") # <--- Uncomment to debug specific line layout
            
            if len(lines) < 3: return None
            
            # AGE: Look for small strings ending in m/h/d, possibly composite like "1h 30m"
            age_str = next((l for l in lines if re.match(r'^(\d+[dhms])(\s+\d+[dhms])*$', l)), None)
            
            # LIQUIDITY: Look for money with K/M/B suffix.
            # Usually Liq is NOT the first money value (Price is first). 
            # We look for the line explicitly containing 'K', 'M', or 'B' after the price.
            
            money_values = [l for l in lines if l.startswith('$')]
            liq_str = None
            
            if money_values:
                # Filter for ones with K/M/B (Volume/Liq/FDV)
                large_values = [m for m in money_values if any(x in m for x in ['K', 'M', 'B'])]
                
                if large_values:
                    # Heuristic: Pick the one with K/M/B.
                    # Usually the first large value after price.
                    liq_str = large_values[0]
            
            # Name usually early
            name = lines[0] if lines else "Unknown"

            return {
                "pair_address": href.split('/')[-1] if href else "unknown",
                "chain": href.split('/')[-2] if href else "unknown",
                "pair_name": name,
                "age_str": age_str,
                "liq_str": liq_str,
                # "raw_lines": lines # for debug
            }
        except Exception as e:
            # print(f"Parse Error: {e}")
            return None

    def _passes_filters(self, data):
        # Age Check
        age_str = data.get('age_str', '99h')
        if not age_str: return False
        
        minutes = self._parse_age_to_minutes(age_str)
        
        # Range: 2 mins < Age < 30 mins
        if minutes < config.MIN_PAIR_AGE_MINUTES:
            return False
        if minutes > config.MAX_PAIR_AGE_MINUTES:
            return False

        # Liquidity Check
        liq_str = data.get('liq_str', '$0')
        usd = self._parse_money(liq_str)
        if usd < config.MIN_LIQUIDITY_USD:
            return False
            
        # Chain Check (Ignore EVM/Base/etc if targeting Solana)
        chain = data.get('chain', 'unknown')
        if config.TARGET_CHAIN_ID.lower() not in chain.lower():
            # e.g. target="solana", chain="solana" -> pass
            return False

        return True

    def _parse_age_to_minutes(self, age_str):
        if not age_str: return 999
        total = 0
        parts = age_str.split()
        for p in parts:
            if 's' in p: pass
            elif 'm' in p: total += int(p.replace('m', ''))
            elif 'h' in p: total += int(p.replace('h', '')) * 60
            elif 'd' in p: total += int(p.replace('d', '')) * 1440
        return total

    def _parse_money(self, money_str):
        if not money_str: return 0
        s = money_str.replace('$', '').replace(',', '')
        mult = 1
        if 'K' in s:
            mult = 1000
            s = s.replace('K', '')
        elif 'M' in s:
            mult = 1000000
            s = s.replace('M', '')
        try:
            return float(s) * mult
        except:
            return 0

    async def get_pair_details(self, pair_address: str, chain: str = "solana") -> dict:
        """
        Fetches FULL pair details from DexScreener API.
        Returns dict with:
        - token_address (baseToken.address)
        - liquidity (usd)
        - fdv (market cap proxy)
        - volume (h1, m5)
        - priceChange (h1, m5)
        - info (socials)
        """
        url = f"https://api.dexscreener.com/latest/dex/pairs/{chain}/{pair_address}"
        try:
             import requests
             loop = asyncio.get_event_loop()
             def _fetch():
                 return requests.get(url, timeout=5).json()
             
             data = await loop.run_in_executor(None, _fetch)
             
             if data and data.get('pairs'):
                 pair = data['pairs'][0]
                 return {
                     "token_address": pair.get('baseToken', {}).get('address'),
                     "liquidity": pair.get('liquidity', {}).get('usd', 0),
                     "fdv": pair.get('fdv', 0), # Market Cap
                     "volume_h1": pair.get('volume', {}).get('h1', 0),
                     "volume_m5": pair.get('volume', {}).get('m5', 0),
                     "price_change_h1": pair.get('priceChange', {}).get('h1', 0),
                     "price_change_m5": pair.get('priceChange', {}).get('m5', 0),
                     "socials": pair.get('info', {}).get('socials', []) # List of {type: 'telegram', ...}
                 }
             return None
        except Exception as e:
            print(f"Details Fetch Error: {e}")
            return None

    def get_analysis_payload(self, data: dict, observer_data: dict = None) -> dict:
        """
        Adapts scraped data + Observed data for the analyzer.
        """
        # Base Scraped Data
        payload = {
            "pair_name": data.get("pair_name"),
            "pair_address": data.get("pair_address"),
            "pair_age_minutes": self._parse_age_to_minutes(data.get("age_str")),
            "liquidity_usd": self._parse_money(data.get("liq_str")),
        }

        # Merge Observer Data if available (The "Real" Behavioral Data)
        if observer_data:
            payload.update({
                "liquidity_change_pct": observer_data.get('liquidity_change_pct', 0),
                "buy_sell_ratio": observer_data.get('buy_sell_ratio_5m', 1.0),
                "buy_consistency": observer_data.get('activity_level', 'moderate'),
                "avg_price_recovery_seconds": 0, # Hard to calc perfectly without tick data
                "price_trend": observer_data.get('price_trend'),
                "tx_per_min": (observer_data.get('buys_5m',0) + observer_data.get('sells_5m',0)) / 5,
                "volatility": observer_data.get('volatility_score')
            })
        else:
            # Fallback Placeholders (If observation skipped)
            payload.update({
                "liquidity_change_pct": 0.0,
                "buy_sell_ratio": 1.5,
                "buy_consistency": "unknown",
                "price_trend": "unknown"
            })
            
        # Additional estimations
        payload.update({
            "holder_growth_per_min": 5, # Placeholder (Can't fetch without heavy scrape)
            "top_5_holder_pct": 20,     # Placeholder
            "avg_tx_size_usd": 100      # Placeholder
        })
        
        return payload
