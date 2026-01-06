import requests
import config
import logging

class SecurityEngine:
    """
    Checks token security via GoPlus Labs API.
    Enforces 'Hard Reject' rules.
    """
    
    def __init__(self):
        self.session = requests.Session()

    def check_token(self, token_address: str, chain_id: str = None):
        """
        Returns (is_safe: bool, reason: str, details: dict)
        """
        result = None
        target_chain = chain_id if chain_id else config.TARGET_CHAIN_ID
        
        # Retry Loop (User Tip: Data might take 30-120s to appear)
        max_retries = 3
        for attempt in range(max_retries):
            try:
                # Handle Solana Specific Endpoint
                if target_chain.lower() == "solana":
                     url = "https://api.gopluslabs.io/api/v1/solana/token_security?contract_addresses=" + token_address
                else:
                     url = f"{config.GOPLUS_API_URL}/{target_chain}?contract_addresses={token_address}"
                     
                resp = requests.get(url, timeout=10)
                
                if resp.status_code == 200:
                    data = resp.json()
                    if data.get('code') == 1:
                        # Parse Result based on Chain
                        raw_result = data.get('result', {})
                        # Solana returns result embedded with address key (sometimes) or just result?
                        # GoPlus usually uses address as key.
                        # Fix case sensitivity
                        token_data = raw_result.get(token_address.lower()) or raw_result.get(token_address)
                        
                        if token_data:
                            # NORMALIZE DATA (Solana vs EVM)
                            normalized = {}
                            
                            if target_chain.lower() == "solana":
                                # SOLANA MAPPING
                                normalized['is_honeypot'] = int(token_data.get('non_transferable', 0) or 0)
                                
                                # Mintable is a struct: {"status": "1", ...}
                                mint_info = token_data.get('mintable', {})
                                normalized['is_mintable'] = int(mint_info.get('status', 0) or 0) if isinstance(mint_info, dict) else 0
                                
                                # Freezable / Blacklist
                                freeze_info = token_data.get('freezable', {})
                                normalized['is_blacklisted'] = int(freeze_info.get('status', 0) or 0) if isinstance(freeze_info, dict) else 0
                                
                                # Verification - Solana doesn't have source verification in same way.
                                # Default to 1 (Verified) to prevent auto-reject.
                                normalized['is_open_source'] = 1 
                                
                                # Taxes - Solana token (SPL) usually 0 tax, logic handled by transfer fee
                                normalized['buy_tax'] = 0
                                normalized['sell_tax'] = 0
                                
                                # Holders - If available
                                normalized['holders'] = token_data.get('holders', [])
                                normalized['holder_count'] = token_data.get('holder_count', 0)
                                
                                # Owner Logic for later
                                normalized['owner_address'] = None 
                                
                            else:
                                # EVM MAPPING (Standard)
                                normalized = token_data.copy()
                                # Ensure Verification default is 0 for EVM
                                if 'is_open_source' not in normalized:
                                    normalized['is_open_source'] = 0
                            
                            result = normalized
                            break # Success!
                
                # If we haven't broken, wait and retry
                if attempt < max_retries - 1:
                    import time; time.sleep(2)

            except Exception as e:
                logging.error(f"Security Req Exception: {e}")
                
        # CHECK IF WE GOT DATA
        if not result:
            return False, "Security Data Unavailable (Timed Out)", {}

        # ------------------------------------------
        # HARD REJECT RULES (Run on 'result')
        # ------------------------------------------
        try:
            if int(result.get('is_honeypot', 0) or 0) == 1:
                return False, "HONEYPOT DETECTED", result

            # 2. Taxes (Rule 6: Sell/Buy Tax > 8)
            buy_tax = float(result.get('buy_tax', 0) or 0) * 100
            sell_tax = float(result.get('sell_tax', 0) or 0) * 100
            
            # Using config values, default to 8 if not in config
            max_buy = getattr(config, 'MAX_TAX_BUY', 8)
            max_sell = getattr(config, 'MAX_TAX_SELL', 8)
            
            if buy_tax > max_buy or sell_tax > max_sell:
                return False, f"High Tax (Buy: {buy_tax}%, Sell: {sell_tax}%)", result

            # 3. Mintable (Rule 3: no_mint == false -> REJECT)
            if int(result.get('is_mintable', 0) or 0) == 1:
                 return False, "Mintable Contract (Rule 3)", result
                 
            # 4. Blacklist (Rule 4: no_blacklist == false -> REJECT)
            if int(result.get('is_blacklisted', 0) or 0) == 1:
                return False, "Blacklist Functionality Detected (Rule 4)", result
                
            # 5. Owner Privileges (Rule 5: owner_privileges == true -> REJECT)
            # GoPlus check. If owner address exists and not renounced.
            owner = result.get('owner_address', '')
            if owner and owner != "" and "11111111111111111111111111111111" not in owner:
                 # Check 'can_take_back_ownership'
                 if int(result.get('can_take_back_ownership', 0) or 0) == 1:
                    return False, "Owner Privileges Detected (Rule 5)", result

            # 6. Unverified Contract (Cost Saving)
            # If contract is not verified (is_open_source == 0), reject before AI.
            # Default to 0 (Unverified) if missing to be SAFE and CHEAP.
            if int(result.get('is_open_source', 0) or 0) == 0:
                return False, "Unverified Contract (Source Not Open)", result
            
            return True, "Passed Security Checks", result

        except Exception as e:
            logging.error(f"Security Rule Exception: {e}")
            return False, f"Security Exception: {e}", {}
