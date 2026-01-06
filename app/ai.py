import requests
import json
import config

class DeepSeekBrain:
    """
    AI decision engine using DeepSeek API.
    Analyzes only 'Safe' tokens.
    """
    
    def __init__(self):
        self.api_key = config.DEEPSEEK_API_KEY
        self.base_url = config.DEEPSEEK_BASE_URL

    def _build_prompt(self, market, security):
        # Merging Observational and Security Metrics for the "Exam"
        # The user wants a "Grade" based on Priority.
        # Socials Removed by User Request.
        
        exam_data = {
            "1_PRIORITY_SECURITY": {
                 "tax_buy": security.get("buy_tax"),
                 "tax_sell": security.get("sell_tax"),
                 "honeypot": security.get("is_honeypot", 0),
                 "mintable": security.get("is_mintable", 0),
                 "contract_verified": security.get("is_open_source", 0),
                 "blacklist": security.get("is_blacklisted", 0)
            },
            "2_PRIORITY_BEHAVIOR": {
                 "buy_sell_ratio": market.get("buy_sell_ratio", 1.0),
                 "tx_per_min": market.get("tx_per_min", 0),
                 "price_trend": market.get("price_trend", "unknown"),
                 "volatility": market.get("volatility", 0)
            },
            "3_PRIORITY_MARKET": {
                 "liquidity_usd": market.get("liquidity_usd"),
                 "market_cap_fdv": market.get("market_cap"),
                 "pair_age": f"{market.get('pair_age_minutes')}m",
                 "volume_h1": market.get("volume_h1", 0)
            },
            "4_PRIORITY_HOLDERS": {
                 "holder_count": security.get("holder_count"),
                 "top_10_pct": security.get("top_10_holders_percent") # If available, else inferred
            }
        }

        return f"""
ACT AS A STRICT CRYPTO PROFESSOR. Grade this token launch.

GRADING CRITERIA (Weighted):
1. SECURITY (35%): Must be tax <= 8%, not mintable, verified.
2. BEHAVIOR (35%): High transaction count, Buying pressure > Selling.
3. MARKET (20%): Liquidity $5k-$80k, MC $8k-$40k.
4. HOLDERS (10%): Spread out, not concentrated.

CRITICAL FAIL CONDITIONS (Instant Fail - Max Grade 40):
- If Security measures are suspicious (Honeypot, High Tax > 50%, Blacklist).
- If Liquidity is actively being REMOVED or is suspiciously Low (< $1000).
- If BEHAVIOR IS DEAD: (Zero volume in last minute).
- If PRICE IS RUGGING: (Crash > 90%).
- DIP LOGIC: Allow dips ONLY IF "Absorption" is detected (High Vol + Buy/Sell Ratio > 0.4).
- REJECT DIPS IF: "Panic Dump" detected (Buy/Sell Ratio < 0.2 OR Crash > 60%).
- DO NOT AVERAGE. If a critical pillar fails, the WHOLE PROJECT FAILS.

TASK:
- Calculate a "Realistic Potential Market Cap" (usd) based on quality/hype.
- If grade < 80, set potential_mc to 0.

RETURN JSON ONLY:
{{
  "grade_score": number (0-100),
  "decision": "WATCH" | "IGNORE",
  "reasoning": "Brief explanation of grade (Mention the fatal flaw if low)",
  "potential_mc": number (Estimated Peak USD Market Cap, e.g. 500000)
}}

DATA:
{json.dumps(exam_data, indent=2)}
"""

    def analyze_token(self, market_data: dict, security_data: dict) -> dict:
        if not self.api_key or "sk-" not in self.api_key:
             return {"decision": "WATCH", "confidence": 0.5, "summary": "AI Skipped (No Key)", "positive_patterns": [], "negative_patterns": []}

        prompt = self._build_prompt(market_data, security_data)
        
        # User Specific System Prompt
        system_prompt = """You are a quantitative crypto analyst specializing in early-stage meme coin behavior.
Your task is to assess whether a token's early on-chain and market behavior resembles historically successful launches.
Be conservative. Avoid speculative optimism."""

        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.api_key}"
        }
        
        payload = {
            "model": config.DEEPSEEK_MODEL,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": prompt}
            ],
            "temperature": 0.3, 
            "max_tokens": 500
        }
        
        try:
            resp = requests.post(f"{self.base_url}/chat/completions", headers=headers, json=payload, timeout=20)
            if resp.status_code == 200:
                content = resp.json()['choices'][0]['message']['content']
                content = content.replace("```json", "").replace("```", "").strip()
                return json.loads(content)
            else:
                print(f"AI API Error: {resp.text}")
                return {"decision": "WATCH", "confidence": 0.0, "summary": "AI Offline", "positive_patterns": [], "negative_patterns": []}
        except Exception as e:
            print(f"AI Exception: {e}")
            return {"decision": "WATCH", "confidence": 0.0, "summary": f"AI Error: {e}", "positive_patterns": [], "negative_patterns": []}
