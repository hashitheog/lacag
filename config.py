# Configuration for Meme Coin Analyzer

# DexScreener Scraper
BASE_URL = "https://dexscreener.com"
NEW_PAIRS_URL = "https://dexscreener.com/new-pairs?rankBy=pairAge&order=asc"
HEADLESS = True # Set to False to watch the browser

# Filter Settings
# Filter Settings
MIN_PAIR_AGE_MINUTES = 0.75 # Rule 1: >= 45s
MAX_PAIR_AGE_MINUTES = 15   # Rule 1: <= 15m

MIN_LIQUIDITY_USD = 2500    # Rule 2: >= 2,500
MAX_LIQUIDITY_USD = 9999999 # No max hard cap, but penalized if > 150k

# Scoring Thresholds (Gatekeeper for GoPlus)
# Increased to -1 to ignore Micro-Caps (< 6k) and save API Credits.
MIN_SCORE_TO_CHECK_SECURITY = -1

# Penalties
PENALTY_MC_LOW = -2       # MC < 6k
PENALTY_MC_HIGH = -1      # MC > 150k
PENALTY_LIQ_HIGH = -1     # Liq > 150k
PENALTY_NO_SOCIAL = 0     # Disabled by User Request

# Security Hard Rules
MAX_TAX_BUY = 8           # Rule 6
MAX_TAX_SELL = 8          # Rule 6
MIN_HOLDERS = 20          # Rule 12 (Used in post-security scoring)
MAX_TOP_HOLDER_PCT = 15   # Rule 11 (Used in post-security scoring)


# Analyzer Settings
RISK_TOLERANCE = "conservative" # conservative | degen (not implemented yet)

# System
SCAN_INTERVAL_SECONDS = 10

# ----------------------------------------
# GOD MODE CONFIGURATION
# ----------------------------------------

import os

# 1. Security (GoPlus)
# Free tier doesn't always need a key, but good to have if user has one
GOPLUS_API_URL = "https://api.gopluslabs.io/api/v1/token_security"
# GOPLUS_CHAIN_ID map: 1=ETH, 56=BSC, 137=Polygon, 101=Solana (Check docs for Sol)
# Solana chain ID for GoPlus is often 'solana' string in some eps or check ID. 
TARGET_CHAIN_ID = os.getenv("TARGET_CHAIN_ID", "solana")
GOPLUS_API_KEY = os.getenv("GOPLUS_API_KEY", "u1Ut8H6KJbuB2dvs60MC")
GOPLUS_APP_SECRET = os.getenv("GOPLUS_APP_SECRET", "CHqpsGN7EdPmxr7wej1Vhsxc6SsjD7CQ")

# 2. AI Brain (DeepSeek)
DEEPSEEK_API_KEY = os.getenv("DEEPSEEK_API_KEY", "sk-cf63e9d7e92a42218d8880cf14c6f49a")
DEEPSEEK_BASE_URL = os.getenv("DEEPSEEK_BASE_URL", "https://api.deepseek.com") # Standard base
DEEPSEEK_MODEL = os.getenv("DEEPSEEK_MODEL", "deepseek-chat")

# 3. Alerting (Telegram)
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "8184933111:AAHfEfXPUrAwmz64MOkmBubF1XeMbV_lGyY")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", "7944897949")

