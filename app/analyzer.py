import json

class MemeLaunchAnalyzer:
    """
    Analyzes early-stage meme coin launches based on on-chain behavior.
    Strictly follows conservative risk-avoidance logic.
    """

    def analyze(self, data: dict) -> dict:
        """
        Main entry point for analysis.
        
        Args:
            data (dict): JSON object containing market behavior metrics.
            
        Returns:
            dict: JSON object with decision, confidence, and reasoning.
        """
        # Step 1: Safety First - Hard Constraints
        is_safe, refuse_reason = self._check_hard_constraints(data)
        if not is_safe:
            return self._build_output(
                decision="IGNORE",
                confidence=0.0,
                positive_patterns=[],
                negative_patterns=[refuse_reason],
                summary=f"Risk Guard: {refuse_reason}"
            )

        # Behavioral Analysis (Steps 2-6)
        scores = {}
        positive_patterns = []
        negative_patterns = []

        # Step 2: Demand Quality
        dq_score, dq_pos, dq_neg = self._analyze_demand_quality(data)
        scores['demand_quality'] = dq_score
        positive_patterns.extend(dq_pos)
        negative_patterns.extend(dq_neg)

        # Step 3: Sell Absorption
        sa_score, sa_pos, sa_neg = self._analyze_sell_absorption(data)
        scores['sell_absorption'] = sa_score
        positive_patterns.extend(sa_pos)
        negative_patterns.extend(sa_neg)

        # Step 4: Liquidity Stability
        ls_score, ls_pos, ls_neg = self._analyze_liquidity(data)
        scores['liquidity'] = ls_score
        positive_patterns.extend(ls_pos)
        negative_patterns.extend(ls_neg)

        # Step 5: Holder Growth & Distribution
        hg_score, hg_pos, hg_neg = self._analyze_holders(data)
        scores['holders'] = hg_score
        positive_patterns.extend(hg_pos)
        negative_patterns.extend(hg_neg)

        # Step 6: Market Activity Strength
        ma_score, ma_pos, ma_neg = self._analyze_activity(data)
        scores['activity'] = ma_score
        positive_patterns.extend(ma_pos)
        negative_patterns.extend(ma_neg)

        # Calculate Final Confidence Score
        confidence = self._calculate_confidence(scores)

        # Decision Logic based on confidence
        if confidence >= 0.75:
            decision = "WATCH"
        elif confidence >= 0.6:
            # Conservative approach: < 0.75 is risky
            decision = "WATCH" # We will let the final confidence score speak, but default to WATCH if high enough
        else:
            decision = "IGNORE"
            
        # Refine decision: If ANY critical sub-score is very low, force ignore
        if min(scores.values()) < 0.4:
            decision = "IGNORE"
            negative_patterns.append("Critical weakness detected in one or more metrics")
            
        if confidence < 0.75 and decision == "WATCH":
             decision = "IGNORE" # Strictly enforcing high quality for WATCH

        # Summary Generation
        summary = self._generate_summary(decision, confidence, positive_patterns, negative_patterns)

        return self._build_output(decision, confidence, positive_patterns, negative_patterns, summary)

    def _check_hard_constraints(self, data: dict):
        """Step 1: Check for early red flags."""
        # 1. Liquidity Removal
        if data.get("liquidity_change_pct", 0) < -5.0:
            return False, "Liquidity removed (>5%)"
        
        # 2. Extreme Holder Concentration
        if data.get("top_5_holder_pct", 0) > 40:
            return False, "Extreme holder concentration (>40%)"

        # 3. Weak Transaction Activity
        if data.get("tx_per_min", 0) < 5:
            return False, "insufficient transaction volume (<5 tx/min)"

        return True, ""

    def _analyze_demand_quality(self, data: dict):
        """Step 2: Buy vs Sell behavior."""
        score = 0.5
        pos = []
        neg = []

        buy_sell = data.get("buy_sell_ratio", 1.0)
        consistency = data.get("buy_consistency", "neutral")

        if buy_sell > 2.5:
            score += 0.2
            pos.append("Strong buy dominance")
        elif buy_sell > 1.2:
            score += 0.1
            pos.append("Healthy buy pressure")
        elif buy_sell < 0.5:
            score -= 0.3
            neg.append("Heavy sell pressure")

        if consistency == "steady":
            score += 0.2
            pos.append("Steady buying (organic signal)")
        elif consistency == "spiky":
            score -= 0.2
            neg.append("Spiky buying patterns (bot-like)")
        
        return min(max(score, 0.0), 1.0), pos, neg

    def _analyze_sell_absorption(self, data: dict):
        """Step 3: Recovery after sells."""
        score = 0.5
        pos = []
        neg = []

        recovery_sec = data.get("avg_price_recovery_seconds", 999)

        if recovery_sec < 45:
            score += 0.3
            pos.append("Rapid sell absorption (<45s)")
        elif recovery_sec < 120:
            score += 0.1
            pos.append("Moderate sell absorption")
        else:
            score -= 0.2
            neg.append("Slow price recovery")

        return min(max(score, 0.0), 1.0), pos, neg

    def _analyze_liquidity(self, data: dict):
        """Step 4: Liquidity Stability."""
        score = 0.5
        pos = []
        neg = []
        
        liq_usd = data.get("liquidity_usd", 0)
        liq_change = data.get("liquidity_change_pct", 0.0)

        if liq_usd < 5000:
            score -= 0.2
            neg.append("Very low liquidity")
        elif liq_usd > 20000:
            score += 0.1
            pos.append("Deep liquidity base")

        if abs(liq_change) < 2.0:
            score += 0.2
            pos.append("Liquidity locked/stable")
        elif liq_change < 0:
            score -= 0.3
            neg.append("Liquidity reduction detected")

        return min(max(score, 0.0), 1.0), pos, neg

    def _analyze_holders(self, data: dict):
        """Step 5: Holder patterns."""
        score = 0.5
        pos = []
        neg = []

        growth = data.get("holder_growth_pattern", "neutral")
        top_trend = data.get("top_5_trend", "stable")

        if growth == "smooth":
            score += 0.2
            pos.append("Organic holder growth")
        elif growth == "bursty":
            score -= 0.2
            neg.append("Artificial/bot holder inflation")
        
        if top_trend == "decreasing":
            score += 0.1
            pos.append("Improving distribution")
        elif top_trend == "increasing":
            score -= 0.2
            neg.append("Whale accumulation risk")

        return min(max(score, 0.0), 1.0), pos, neg

    def _analyze_activity(self, data: dict):
        """Step 6: Transaction metrics."""
        score = 0.5
        pos = []
        neg = []

        tx_min = data.get("tx_per_min", 0)
        
        if tx_min > 30:
            score += 0.2
            pos.append("High transaction velocity")
        elif tx_min > 10:
            score += 0.1
        
        avg_size = data.get("avg_tx_size_usd", 0)
        if avg_size < 10:
             score -= 0.2
             neg.append("Micro-transaction spam suspected")
        elif avg_size > 100:
            score += 0.1
            pos.append("Healthy trade sizing")

        return min(max(score, 0.0), 1.0), pos, neg


    def _calculate_confidence(self, scores: dict):
        """Weighted average of sub-scores."""
        weights = {
            'demand_quality': 0.25,
            'sell_absorption': 0.25,
            'liquidity': 0.20,
            'holders': 0.15,
            'activity': 0.15
        }
        
        total_score = sum(scores[k] * weights[k] for k in weights)
        return round(total_score, 2)

    def _generate_summary(self, decision, confidence, positives, negatives):
        if decision == "IGNORE":
            if confidence == 0.0:
                return negatives[0] if negatives else "Safety violations."
            return f"Metrics display instability (Score: {confidence}). {negatives[0] if negatives else 'Insufficient quality'}."
        
        return f"Behavior aligns with organic launch patterns (Score: {confidence}). Strengths: {', '.join(positives[:2])}."

    def _build_output(self, decision, confidence, positive_patterns, negative_patterns, summary):
        return {
            "decision": decision,
            "confidence": confidence,
            "positive_patterns": positive_patterns,
            "negative_patterns": negative_patterns,
            "summary": summary
        }
