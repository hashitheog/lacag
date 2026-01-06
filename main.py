import asyncio
import sys
from datetime import datetime
from colorama import init, Fore, Style

from app.analyzer import MemeLaunchAnalyzer
from app.scraper import DexScreenerScraper
from app.security import SecurityEngine
from app.ai import DeepSeekBrain
from app.observer import MarketObserver
from app.trading import TradeManager
from app.data_source import DataSource
from app.telegram_bot import TelegramBot
from app.alerts import send_telegram_alert, send_startup_message, send_trade_update
import config

init(autoreset=True)

async def main():
    print(f"{Fore.CYAN}=== GOD MODE ANALYZER: ACITVATED ==={Style.RESET_ALL}")
    send_startup_message()
    print(f"Mode: {config.RISK_TOLERANCE.upper()}")
    print("Browser: Chromium (Headless)" if config.HEADLESS else "Browser: Chromium (Headed)")
    print("-" * 50)

    # Initialize Engines
    scraper = DexScreenerScraper()
    algo_analyzer = MemeLaunchAnalyzer()
    security = SecurityEngine()
    brain = DeepSeekBrain()
    observer = MarketObserver()
    
    # NEW: Trade Execution Engine
    trade_manager = TradeManager()
    data_source_monitor = DataSource()
    telegram_bot = TelegramBot()
    
    seen_pairs = set()

    try:
        await scraper.start()
        
        while True:
            # 0. CHECK USER COMMANDS
            telegram_bot.check_updates(trade_manager)
            
            # 1. MONITOR ACTIVE TRADES
            if trade_manager.active_trades:
                print(f"\n{Fore.BLUE}[MONITOR]{Style.RESET_ALL} Checking {len(trade_manager.active_trades)} active positions...")
                
                # Active Trades Loop
                for symbol in list(trade_manager.active_trades.keys()):
                    trade = trade_manager.active_trades[symbol]
                    
                    # Fetch Current Price
                    # Note: We need chain_id. Assuming passed in open_trade.
                    pid = trade.get('pair_address')
                    chain = trade.get('chain_id', 'solana') # Default to solana if missing
                    
                    if pid:
                        cur_price = data_source_monitor.fetch_current_price(pid, chain)
                        if cur_price:
                             msg, closed = trade_manager.update_trade(symbol, cur_price)
                             if msg:
                                 print(msg)
                                 send_trade_update(msg)
                                 if closed:
                                     # Notify Logic could go here (Telegram PnL)
                                     pass
                        else:
                             print(f"{Fore.YELLOW}[WARN]{Style.RESET_ALL} Could not fetch price for {symbol}")

            print(f"\n[{datetime.now().strftime('%H:%M:%S')}] Scraping DexScreener Live...")
            
            candidates = await scraper.scrape_candidates()
            new_candidates = [c for c in candidates if c['pair_address'] not in seen_pairs]
            
            if not new_candidates:
                print("No new pairs matching filter criteria.")
            else:
                print(f"Found {len(new_candidates)} candidates. running pipeline...")
                
                for pair in new_candidates:
                    seen_pairs.add(pair['pair_address'])
                    addr = pair['pair_address']
                    symbol = pair['pair_name']
                    
                for pair in new_candidates:
                    seen_pairs.add(pair['pair_address'])
                    addr = pair['pair_address']
                    symbol = pair['pair_name']
                    
                    # -------------------------------------------------------------
                    # 1. FETCH FULL METADATA
                    # -------------------------------------------------------------
                    chain_id = pair.get('chain', config.TARGET_CHAIN_ID)
                    print(f"{Fore.YELLOW}[METADATA]{Style.RESET_ALL} Fetching details for {symbol}...")
                    
                    details = await scraper.get_pair_details(addr, chain=chain_id)
                    if not details: 
                        print(f"{Fore.RED}[SKIP]{Style.RESET_ALL} API Fetch Failed for {symbol}")
                        continue
                        
                    token_address = details.get('token_address')
                    if not token_address:
                         print(f"{Fore.RED}[SKIP]{Style.RESET_ALL} No Token Address Resolved")
                         continue

                    # -------------------------------------------------------------
                    # 2. HARD FILTERS (Instant Reject)
                    # -------------------------------------------------------------
                    liq = float(details.get('liquidity', 0))
                    if liq < config.MIN_LIQUIDITY_USD:
                         print(f"{Fore.RED}[REJECT]{Style.RESET_ALL} Liquidity ${liq:,.0f} < ${config.MIN_LIQUIDITY_USD}")
                         continue
                         
                    # Age is filtered by Scraper list generally, but we could double check here if needed.

                    # -------------------------------------------------------------
                    # 3. SCORING ENGINE (Stage 1: Metadata)
                    # -------------------------------------------------------------
                    score = 0
                    score_reasons = []
                    
                    mc = float(details.get('fdv', 0))
                    
                    # Rule 8: MC < 6k (-2)
                    if mc < 6000:
                        score += config.PENALTY_MC_LOW
                        score_reasons.append("MC < 6k (-2)")
                        
                    # Rule 9: MC > 150k (-1)
                    if mc > 150000:
                        score += config.PENALTY_MC_HIGH
                        score_reasons.append("MC > 150k (-1)")
                        
                    # Rule 10: Liq > 150k (-1)
                    if liq > 150000:
                        score += config.PENALTY_LIQ_HIGH
                        score_reasons.append("Liq > 150k (-1)")
                        
                    # Rule 13/14: Socials Check (DISABLED)
                    # User requested to ignore social media presence completely.
                    # socials = details.get('socials', [])
                    # has_tg = any(s.get('type') == 'telegram' for s in socials)
                    # has_twitter = any(s.get('type') == 'twitter' for s in socials)
                    # if not has_tg: score += config.PENALTY_NO_SOCIAL
                    # if not has_twitter: score += config.PENALTY_NO_SOCIAL
                        
                    # GATEKEEPER CHECK
                    print(f"{Fore.BLUE}[SCORE]{Style.RESET_ALL} {symbol} Score: {score} ({', '.join(score_reasons)})")
                    
                    if score < config.MIN_SCORE_TO_CHECK_SECURITY:
                        print(f"{Fore.RED}[REJECT]{Style.RESET_ALL} Score {score} too low. Skipping Security.")
                        continue

                    # -------------------------------------------------------------
                    # 4. SECURITY ENGINE (Stage 2: Hard Checks + Holder Score)
                    # -------------------------------------------------------------
                    print(f"{Fore.YELLOW}[SECURITY]{Style.RESET_ALL} Scanning Contract {token_address}...")
                    is_safe, reason, security_data = security.check_token(token_address)
                    
                    if not is_safe:
                        print(f"{Fore.RED}[UNSAFE]{Style.RESET_ALL} {symbol}: {reason}")
                        continue
                        
                    # Post-Security Scoring (Holders)
                    # Rule 11: Top Holder > 15% (-1)
                    holders = security_data.get('holders', [])
                    if holders:
                         # GoPlus returns percent as string or float depending on provider.
                         # Fix: Convert to float FIRST, then multiply.
                         raw_pct = holders[0].get('percent', 0)
                         try:
                             top1 = float(raw_pct) * 100
                         except ValueError:
                             top1 = 0.0
                             
                         if top1 > 30:
                             print(f"{Fore.RED}[REJECT]{Style.RESET_ALL} Top Holder {top1:.1f}% > 30% (Critical Concentration)")
                             continue
                             
                         if top1 > config.MAX_TOP_HOLDER_PCT:
                            score -= 1
                            score_reasons.append(f"Top Holder {top1:.1f}% (-1)")
                            
                    # Rule 12: Holders (Strict Hard Filter)
                    holder_count = int(security_data.get('holder_count', 0))
                    
                    if holder_count < config.MIN_HOLDERS:
                         print(f"{Fore.RED}[REJECT]{Style.RESET_ALL} Holders {holder_count} < {config.MIN_HOLDERS} (Too Risky)")
                         continue
                    
                    # Final Score Check
                    if score < config.MIN_SCORE_TO_CHECK_SECURITY:
                         print(f"{Fore.RED}[REJECT]{Style.RESET_ALL} Final Score {score} too low: {', '.join(score_reasons)}")
                         continue
                    
                    # -------------------------------------------------------------
                    # 5. BEHAVIORAL OBSERVATION
                    # -------------------------------------------------------------
                    print(f"{Fore.CYAN}[OBSERVE]{Style.RESET_ALL} Passing Score {score}. Monitoring {symbol}...")
                    observer_data = await observer.observe(addr, chain=chain_id)
                    
                    # -------------------------------------------------------------
                    # 6. AI ANALYSIS
                    # -------------------------------------------------------------
                    payload = scraper.get_analysis_payload(pair, observer_data)
                    payload['market_cap'] = mc
                    payload['score'] = score
                    
                    print(f"{Fore.MAGENTA}[AI]{Style.RESET_ALL} Asking DeepSeek for a Grade...")
                    ai_result = brain.analyze_token(payload, security_data)
                    
                    decision = ai_result.get('decision', 'IGNORE')
                    grade = ai_result.get('grade_score', 0)
                    summary = ai_result.get('reasoning', 'No reasoning provided')
                    
                    if decision == "WATCH":
                         # User Rule: if percentage (grade) >= 80, send signal.
                         if grade >= 80:
                             _print_success(symbol, payload, security_data, ai_result)
                             send_telegram_alert(symbol, payload, security_data, ai_result)
                             
                             # OPEN PAPER TRADE
                             # Extract Price from raw DexScreener pair data
                             price_usd = float(pair.get('priceUsd', 0))
                             
                             # Get AI Forecast
                             potential_mc = ai_result.get('potential_mc')
                             
                             trade_manager.open_trade(
                                 symbol=symbol,
                                 entry_price=price_usd,
                                 market_cap=mc,
                                 pair_address=payload['pair_address'],
                                 chain_id=config.TARGET_CHAIN_ID,
                                 potential_target_mc=potential_mc
                             )
                         else:
                             # It said WATCH but grade was low? DeepSeek might be confused, treat as weak.
                             print(f"{Fore.YELLOW}[AI WEAK]{Style.RESET_ALL} {symbol} (Grade: {grade}/100) - {summary}")
                    else:
                        print(f"{Fore.RED}[AI REJECT]{Style.RESET_ALL} {symbol} (Grade: {grade}/100): {summary}")
                        
            await asyncio.sleep(config.SCAN_INTERVAL_SECONDS)
            
    except (KeyboardInterrupt, asyncio.CancelledError):
        print(f"\n{Fore.YELLOW}Stopping God Mode...{Style.RESET_ALL}")
    except Exception as e:
        print(f"Fatal Pipeline Error: {e}")
        import traceback
        traceback.print_exc()
    finally:
        try:
             # Gracefully stop scraper
             await scraper.stop()
        except:
             pass
        # sys.exit(0) # Not needed here if we return cleaner

def _print_success(symbol, market, security, ai):
    print(f"\n{Fore.GREEN}>>> 💎 GOD MODE MATCH: {symbol} <<<")
    print(f"AI Grade: {ai.get('grade_score', 0)}/100")
    print(f"Reasoning: {ai.get('reasoning')}")
    print(f"Security: Clean (Tax: {security.get('buy_tax')}/{security.get('sell_tax')}%)")
    print(f"Link: {config.BASE_URL}/{config.TARGET_CHAIN_ID}/{market['pair_address']}")
    print(f"{Style.RESET_ALL}")

if __name__ == "__main__":
    asyncio.run(main())
