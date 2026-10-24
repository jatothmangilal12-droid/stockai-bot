"""
Confluence Signal Evaluator
Synthesizes Daily News Sentiment (35%) + 15m Candlestick Patterns (35%) + Technical Confluence (30%)
to output actionable trading signals with precise Entry, Stop Loss, Target 1, Target 2, and RRR.
"""
from backend.config import WEIGHT_SENTIMENT, WEIGHT_CANDLESTICK, WEIGHT_INDICATORS


class SignalEvaluator:
    """Combines fundamental news sentiment with multi-indicator technical confluence."""

    def evaluate(self, symbol: str, current_price: float, df, patterns: list, sentiment_data: dict) -> dict:
        """
        Evaluate full market confluence.
        Returns signal object containing action, levels, confidence %, and reasoning.
        """
        if df is None or len(df) < 5 or current_price <= 0:
            return {
                "symbol": symbol,
                "action": "NEUTRAL",
                "confidence": 0,
                "confluence_score": 0,
                "entry_price": current_price,
                "stop_loss": 0.0,
                "target_1": 0.0,
                "target_2": 0.0,
                "risk_reward_ratio": "1:1",
                "reasons": ["Insufficient price data for analysis."]
            }

        latest = df.iloc[-1]
        prev = df.iloc[-2] if len(df) >= 2 else latest
        atr = float(latest.get("ATR", current_price * 0.01))
        if atr <= 0:
            atr = current_price * 0.01

        reasons = []

        # =====================================================================
        # 1. Sentiment Score Component (35%)
        # =====================================================================
        net_sentiment = sentiment_data.get("net_sentiment", 0.0)
        # Scale -1.0 to +1.0 -> -100 to +100
        sentiment_component = net_sentiment * 100.0

        if net_sentiment >= 0.25:
            reasons.append(f"Bullish news sentiment (+{net_sentiment:.2f}): positive media catalysts.")
        elif net_sentiment <= -0.25:
            reasons.append(f"Bearish news sentiment ({net_sentiment:.2f}): headwinds and negative press.")
        else:
            reasons.append(f"Neutral news sentiment ({net_sentiment:.2f}): balanced market headlines.")

        # =====================================================================
        # 2. Candlestick Pattern Component (35%)
        # =====================================================================
        candlestick_component = 0.0
        active_pattern_info = None

        # Check latest detected patterns (favor the most recent 2 candles)
        if patterns:
            # Sort by candle_index descending
            sorted_patterns = sorted(patterns, key=lambda x: x["candle_index"], reverse=True)
            recent_pattern = sorted_patterns[0]
            # If pattern occurred in the last 2 candles
            if recent_pattern["candle_index"] >= len(df) - 2:
                active_pattern_info = recent_pattern
                strength = recent_pattern.get("strength", 70)
                if recent_pattern["bias"] == "BULLISH":
                    candlestick_component = strength
                    reasons.append(f"15m Pattern: **{recent_pattern['pattern']}** ({recent_pattern['description']})")
                elif recent_pattern["bias"] == "BEARISH":
                    candlestick_component = -strength
                    reasons.append(f"15m Pattern: **{recent_pattern['pattern']}** ({recent_pattern['description']})")
                else:
                    candlestick_component = 0.0
                    reasons.append(f"15m Pattern: {recent_pattern['pattern']} indicates consolidation.")

        if active_pattern_info is None:
            # Evaluate basic candle body direction
            c_open = latest["Open"]
            c_close = latest["Close"]
            if c_close > c_open:
                candlestick_component = 15.0
            elif c_close < c_open:
                candlestick_component = -15.0

        # =====================================================================
        # 3. Technical Indicator Component (30%)
        # =====================================================================
        tech_score = 0.0
        tech_count = 0

        # (a) EMA 9 & EMA 21 Trend alignment
        ema_9 = latest.get("EMA_9", current_price)
        ema_21 = latest.get("EMA_21", current_price)
        if ema_9 > ema_21:
            tech_score += 30.0
            if prev.get("EMA_9", 0) <= prev.get("EMA_21", 0):
                reasons.append("EMA Golden Cross: 9 EMA just crossed above 21 EMA.")
            else:
                reasons.append("Bullish Trend: 9 EMA holds firmly above 21 EMA.")
        else:
            tech_score -= 30.0
            if prev.get("EMA_9", 0) >= prev.get("EMA_21", 0):
                reasons.append("EMA Death Cross: 9 EMA just crossed below 21 EMA.")
            else:
                reasons.append("Bearish Trend: 9 EMA resides below 21 EMA.")
        tech_count += 1

        # (b) RSI (14) Momentum
        rsi = latest.get("RSI", 50.0)
        if rsi > 72:
            tech_score -= 20.0
            reasons.append(f"RSI is Overbought ({rsi:.1f}): High risk of mean reversion.")
        elif rsi < 28:
            tech_score += 20.0
            reasons.append(f"RSI is Oversold ({rsi:.1f}): Value buying rejection area.")
        elif 52 <= rsi <= 68:
            tech_score += 25.0
            reasons.append(f"RSI Bullish Momentum ({rsi:.1f}): Healthy expansion corridor.")
        elif 32 <= rsi <= 48:
            tech_score -= 25.0
            reasons.append(f"RSI Bearish Momentum ({rsi:.1f}): Sellers in control.")
        tech_count += 1

        # (c) MACD Histogram
        macd_hist = latest.get("MACD_Hist", 0.0)
        prev_macd_hist = prev.get("MACD_Hist", 0.0)
        if macd_hist > 0:
            if macd_hist > prev_macd_hist:
                tech_score += 25.0
                reasons.append("MACD Bullish Histogram accelerating upwards.")
            else:
                tech_score += 10.0
        else:
            if macd_hist < prev_macd_hist:
                tech_score -= 25.0
                reasons.append("MACD Bearish Histogram accelerating downwards.")
            else:
                tech_score -= 10.0
        tech_count += 1

        # (d) Volume Surge confirmation
        vol_surge = latest.get("Vol_Surge", False)
        if vol_surge:
            if tech_score > 0:
                tech_score += 20.0
                reasons.append("High Volume Surge (>1.4x 20-SMA) confirming institutional buying.")
            else:
                tech_score -= 20.0
                reasons.append("High Volume Surge (>1.4x 20-SMA) confirming heavy distribution.")

        indicator_component = max(min(tech_score, 100.0), -100.0)

        # =====================================================================
        # Confluence Synthesis
        # =====================================================================
        composite_score = (
            (sentiment_component * WEIGHT_SENTIMENT) +
            (candlestick_component * WEIGHT_CANDLESTICK) +
            (indicator_component * WEIGHT_INDICATORS)
        )

        composite_score = round(max(min(composite_score, 100.0), -100.0), 1)

        # Determine Signal Action
        if composite_score >= 55:
            action = "STRONG BUY"
        elif composite_score >= 20:
            action = "BUY"
        elif composite_score <= -55:
            action = "STRONG SELL"
        elif composite_score <= -20:
            action = "SELL"
        else:
            action = "NEUTRAL"

        # Calculate Confidence %
        confidence = min(int(abs(composite_score) * 0.95 + 15), 98)

        # Dynamic Stop Loss and Take Profit levels via ATR
        cmp = round(current_price, 2)
        if "BUY" in action:
            sl = round(cmp - (1.5 * atr), 2)
            tp1 = round(cmp + (2.0 * atr), 2)
            tp2 = round(cmp + (3.2 * atr), 2)
            risk = max(cmp - sl, 0.01)
            reward = max(tp1 - cmp, 0.01)
            rrr = f"1:{reward / risk:.2f}"
        elif "SELL" in action:
            sl = round(cmp + (1.5 * atr), 2)
            tp1 = round(cmp - (2.0 * atr), 2)
            tp2 = round(cmp - (3.2 * atr), 2)
            risk = max(sl - cmp, 0.01)
            reward = max(cmp - tp1, 0.01)
            rrr = f"1:{reward / risk:.2f}"
        else:
            sl = round(cmp - (1.5 * atr), 2)
            tp1 = round(cmp + (1.5 * atr), 2)
            tp2 = round(cmp + (2.5 * atr), 2)
            rrr = "1:1.00"

        return {
            "symbol": symbol,
            "action": action,
            "confidence": confidence,
            "confluence_score": composite_score,
            "entry_price": cmp,
            "stop_loss": sl,
            "target_1": tp1,
            "target_2": tp2,
            "risk_reward_ratio": rrr,
            "atr": round(atr, 2),
            "pattern_detected": active_pattern_info["pattern"] if active_pattern_info else None,
            "breakdown": {
                "sentiment_component": round(sentiment_component, 1),
                "candlestick_component": round(candlestick_component, 1),
                "indicator_component": round(indicator_component, 1)
            },
            "reasons": reasons
        }
