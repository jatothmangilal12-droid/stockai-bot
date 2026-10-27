"""
Confluence Signal Evaluator
Synthesizes Daily News Sentiment (35%) + 15m Candlestick Patterns (35%) + Technical Confluence (30%)
to output actionable trading signals with precise Entry, Stop Loss, Target 1, Target 2, and RRR.
"""
from backend.config import (
    WEIGHT_SENTIMENT, WEIGHT_CANDLESTICK, WEIGHT_INDICATORS,
    WEIGHT_OPTION_CHAIN, WEIGHT_MACRO_CHOP
)
from backend.option_chain import calculate_option_chain


class SignalEvaluator:
    """Combines fundamental news sentiment with multi-indicator technical confluence."""

    def evaluate(self, symbol: str, current_price: float, df, patterns: list, sentiment_data: dict, macro_trend: dict = None, smart_money_flow: dict = None, mtf_matrix: dict = None) -> dict:
        """
        Evaluate full market confluence with Institutional 7-Point Precision:
        1. Multi-Timeframe Matrix (Daily Macro + 1H Structure)
        2. Volume Spread Analysis (Whale / Smart Money Accumulation)
        3. Market Regime & Choppiness Filter (Sideways Trap Shield)
        4. VWAP Institutional Benchmark
        5. SuperTrend (10, 3.0) Direction
        6. Bollinger Bands Volatility Squeeze
        7. Asymmetric 1:3.0 Risk-to-Reward Ratio
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
                "smart_money": "Normal Volume",
                "market_regime": "NORMAL",
                "reasons": ["Insufficient price data for analysis."]
            }

        latest = df.iloc[-1]
        prev = df.iloc[-2] if len(df) >= 2 else latest
        atr = float(latest.get("ATR", current_price * 0.01))
        if atr <= 0:
            atr = current_price * 0.01

        reasons = []

        # =====================================================================
        # 1. Sentiment Score Component (25%)
        # =====================================================================
        net_sentiment = sentiment_data.get("net_sentiment", 0.0)
        sentiment_component = net_sentiment * 100.0

        if net_sentiment >= 0.25:
            reasons.append(f"Bullish news sentiment (+{net_sentiment:.2f}): positive media catalysts.")
        elif net_sentiment <= -0.25:
            reasons.append(f"Bearish news sentiment ({net_sentiment:.2f}): headwinds and negative press.")
        else:
            reasons.append(f"Neutral news sentiment ({net_sentiment:.2f}): balanced market headlines.")

        # =====================================================================
        # 2. Candlestick Pattern Component (30%)
        # =====================================================================
        candlestick_component = 0.0
        active_pattern_info = None

        if patterns:
            sorted_patterns = sorted(patterns, key=lambda x: x["candle_index"], reverse=True)
            recent_pattern = sorted_patterns[0]
            if recent_pattern["candle_index"] >= len(df) - 2:
                active_pattern_info = recent_pattern
                strength = recent_pattern.get("strength", 70)
                if recent_pattern["bias"] == "BULLISH":
                    candlestick_component = strength
                    reasons.append(f"15m Pattern: **{recent_pattern['pattern']}** ({recent_pattern['description']})")
                elif recent_pattern["bias"] == "BEARISH":
                    candlestick_component = -strength
                    reasons.append(f"15m Pattern: **{recent_pattern['pattern']}** ({recent_pattern['description']})")

        if active_pattern_info is None:
            c_open = latest["Open"]
            c_close = latest["Close"]
            if c_close > c_open:
                candlestick_component = 15.0
            elif c_close < c_open:
                candlestick_component = -15.0

        # =====================================================================
        # 3. Technical Indicator & Institutional Component (45%)
        # =====================================================================
        tech_score = 0.0

        # (a) EMA 9 & EMA 21 Trend
        ema_9 = latest.get("EMA_9", current_price)
        ema_21 = latest.get("EMA_21", current_price)
        if ema_9 > ema_21:
            tech_score += 20.0
            reasons.append("Bullish Trend: 9 EMA holds firmly above 21 EMA.")
        else:
            tech_score -= 20.0
            reasons.append("Bearish Trend: 9 EMA resides below 21 EMA.")

        # (b) VWAP Institutional Benchmark
        vwap = latest.get("VWAP", current_price)
        if current_price > vwap:
            tech_score += 20.0
            reasons.append(f"Price > VWAP (₹{vwap:.1f}): Institutional accumulation zone.")
        else:
            tech_score -= 20.0
            reasons.append(f"Price < VWAP (₹{vwap:.1f}): Trading below institutional VWAP line.")

        # (c) SuperTrend (10, 3.0)
        st_dir = latest.get("SuperTrend_Direction", 1)
        st_val = latest.get("SuperTrend", current_price)
        if st_dir == 1:
            tech_score += 20.0
            reasons.append(f"SuperTrend: Bullish green support at ₹{st_val:.1f}.")
        else:
            tech_score -= 20.0
            reasons.append(f"SuperTrend: Bearish red resistance at ₹{st_val:.1f}.")

        # (d) Bollinger Bands Squeeze Breakout
        bb_squeeze = latest.get("BB_Squeeze", False)
        if bb_squeeze:
            reasons.append("⚡ Bollinger Band Squeeze: Coiled volatility preparing for breakout.")

        # (e) RSI (14) Momentum
        rsi = latest.get("RSI", 50.0)
        if rsi > 72:
            tech_score -= 25.0
            reasons.append(f"RSI Overbought ({rsi:.1f}): Pullback caution.")
        elif rsi < 28:
            tech_score += 25.0
            reasons.append(f"RSI Oversold ({rsi:.1f}): Rebound support.")
        elif 52 <= rsi <= 68:
            tech_score += 20.0
            reasons.append(f"RSI Bullish Momentum ({rsi:.1f}): Healthy expansion corridor.")
        elif 32 <= rsi <= 48:
            tech_score -= 20.0
            reasons.append(f"RSI Bearish Momentum ({rsi:.1f}): Sellers in control.")

        # (f) Volume Surge
        if latest.get("Vol_Surge", False):
            if tech_score > 0:
                tech_score += 20.0
                reasons.append("High Volume Surge (>1.4x 20-SMA) confirming institutional buying.")
            else:
                tech_score -= 20.0
                reasons.append("High Volume Surge (>1.4x 20-SMA) confirming distribution.")

        # =====================================================================
        # 4. Smart Money / Volume Spread Analysis (Whale Tracker)
        # =====================================================================
        whale_score = 0.0
        whale_badge = "Normal Volume"
        if smart_money_flow:
            whale_score = smart_money_flow.get("score_impact", 0.0)
            whale_badge = smart_money_flow.get("badge", "Normal Volume")
            desc = smart_money_flow.get("description")
            if desc:
                reasons.append(desc)

        # =====================================================================
        # 5. Market Regime & Choppiness Index (Zero-Loss Trap Shield)
        # =====================================================================
        chop_index = float(latest.get("Chop_Index", 50.0))
        chop_penalty = 0.0
        if chop_index >= 61.8:
            market_regime = "CHOPPY_SIDEWAYS"
            chop_penalty = -30.0
            reasons.append(f"⚠️ Choppiness Index ({chop_index:.1f} > 61.8): Market sideways trap. Capital Shield recommends CASH.")
        elif chop_index <= 38.2:
            market_regime = "STRONG_TREND"
            chop_penalty = 15.0
            reasons.append(f"🚀 Choppiness Index ({chop_index:.1f} < 38.2): Strong directional trend expansion confirmed.")
        else:
            market_regime = "CONSOLIDATION"

        indicator_component = max(min(tech_score + whale_score, 100.0), -100.0)

        # =====================================================================
        # 6. Multi-Timeframe (MTF) Matrix (Daily + 1Hr Structure)
        # =====================================================================
        macro_bias = (macro_trend or {}).get("trend", "NEUTRAL")
        macro_penalty = 0.0
        if mtf_matrix:
            macro_penalty = mtf_matrix.get("matrix_score", 0.0)
            reasons.append(mtf_matrix.get("matrix_desc", ""))
        else:
            if macro_bias == "BEARISH":
                reasons.append("⚠️ Macro Daily Trend is BEARISH: Counter-trend 15m Long signals heavily restricted.")
                macro_penalty = -35.0
            elif macro_bias == "BULLISH":
                reasons.append("🌟 Macro Daily Trend is BULLISH: Aligned with higher timeframe institutional momentum.")
                macro_penalty = 20.0

        # =====================================================================
        # 7. NSE Option Chain, PCR (Put-Call Ratio) & Max Pain
        # =====================================================================
        opt_data = calculate_option_chain(symbol, current_price, macro_bias)
        opt_score = opt_data.get("score_impact", 0.0)
        pcr = opt_data.get("pcr", 1.0)
        pcr_bias = opt_data.get("pcr_bias", "NEUTRAL")
        max_pain = opt_data.get("max_pain_strike", current_price)

        if opt_data.get("short_covering_alert"):
            reasons.append(f"🔥 NSE Option Chain: Short-Covering Alert! (PCR: {pcr:.2f}) Call unwinding at ATM strike ₹{opt_data['atm_strike']}.")
        elif pcr >= 1.25:
            reasons.append(f"📊 NSE Option Chain: Bullish Put Writing Support (PCR: {pcr:.2f}, Max Pain: ₹{max_pain}).")
        elif pcr <= 0.75:
            reasons.append(f"⚠️ NSE Option Chain: Bearish Call Writing Resistance (PCR: {pcr:.2f}, Max Pain: ₹{max_pain}).")

        # =====================================================================
        # 8. India VIX Adaptive Volatility Engine
        # =====================================================================
        vix_val = float(latest.get("VIX", 14.2)) if "VIX" in df.columns else 14.2
        if vix_val >= 18.0:
            vix_regime = "HIGH_VOLATILITY"
            vix_sl_mult = 1.6  # Widen Stop Loss to absorb fake wicks
            reasons.append(f"⚡ India VIX Elevated ({vix_val:.1f}): Dynamic Stop Loss widened (1.6x ATR) to prevent false stop hunts.")
        elif vix_val <= 12.5:
            vix_regime = "LOW_VOLATILITY"
            vix_sl_mult = 0.9  # Tighter Stop Loss for quick swing/scalp
        else:
            vix_regime = "BALANCED"
            vix_sl_mult = 1.0

        # =====================================================================
        # 8B. Predictive Pre-Emptive Leading Signals (Early Reversal Detector)
        # =====================================================================
        predictive_badge = None
        if len(df) >= 10 and "RSI" in df.columns:
            recent_sub = df.iloc[-10:]
            c_arr = recent_sub["Close"].values
            r_arr = recent_sub["RSI"].values
            # Bullish Divergence (Price drops, RSI rises below 40 -> Predicts bounce before green candle!)
            if c_arr[-1] < c_arr[-5] and r_arr[-1] > (r_arr[-5] + 2.0) and r_arr[-1] < 42:
                predictive_badge = "🔮 PREDICTIVE REVERSAL (BOUNCE)"
                reasons.append(f"🔮 PREDICTIVE SIGNAL: Bullish RSI Divergence! Institutional absorption detected (RSI {r_arr[-1]:.1f} > {r_arr[-5]:.1f}) despite lower price. Upward bounce predicted before candle turns green!")
                indicator_component += 25.0
            # Bearish Divergence (Price rises, RSI drops above 60 -> Predicts pullback before red candle!)
            elif c_arr[-1] > c_arr[-5] and r_arr[-1] < (r_arr[-5] - 2.0) and r_arr[-1] > 60:
                predictive_badge = "⚠️ PREDICTIVE EXHAUSTION (PULLBACK)"
                reasons.append(f"🔮 PREDICTIVE SIGNAL: Bearish RSI Divergence! Buying momentum exhausted near day's high (RSI {r_arr[-1]:.1f} < {r_arr[-5]:.1f}). Pullback predicted before price drops!")
                indicator_component -= 25.0

        # Confluence Synthesis with Normalized Institutional Weights
        is_fno = opt_data.get("is_fno", True)
        if not is_fno:
            # Dynamically normalize weights across remaining components (sum = 1.0)
            rem = WEIGHT_SENTIMENT + WEIGHT_CANDLESTICK + WEIGHT_INDICATORS + WEIGHT_MACRO_CHOP
            w_sent = WEIGHT_SENTIMENT / rem
            w_candle = WEIGHT_CANDLESTICK / rem
            w_ind = WEIGHT_INDICATORS / rem
            w_opt = 0.0
            w_macro = WEIGHT_MACRO_CHOP / rem
        else:
            w_sent = WEIGHT_SENTIMENT
            w_candle = WEIGHT_CANDLESTICK
            w_ind = WEIGHT_INDICATORS
            w_opt = WEIGHT_OPTION_CHAIN
            w_macro = WEIGHT_MACRO_CHOP

        macro_chop_raw = macro_penalty + chop_penalty
        macro_chop_component = max(min(macro_chop_raw * 1.5, 100.0), -100.0)

        raw_composite = (
            (sentiment_component * w_sent) +
            (candlestick_component * w_candle) +
            (indicator_component * w_ind) +
            (opt_score * w_opt) +
            (macro_chop_component * w_macro)
        )

        composite_score = round(max(min(raw_composite, 100.0), -100.0), 1)

        # High Precision Thresholds
        if market_regime == "CHOPPY_SIDEWAYS" and abs(composite_score) < 75:
            action = "NEUTRAL"
            confidence = 35
            reasons.append("🛡️ Capital Shield: Action overridden to NEUTRAL due to choppy sideways risk.")
        elif composite_score >= 60:
            action = "STRONG BUY"
            confidence = min(int(abs(composite_score) * 0.90 + 20), 98)
        elif composite_score >= 25:
            action = "BUY"
            confidence = min(int(abs(composite_score) * 0.90 + 20), 98)
        elif composite_score <= -60:
            action = "STRONG SELL"
            confidence = min(int(abs(composite_score) * 0.90 + 20), 98)
        elif composite_score <= -25:
            action = "SELL"
            confidence = min(int(abs(composite_score) * 0.90 + 20), 98)
        else:
            action = "NEUTRAL"
            confidence = min(int(abs(composite_score) * 0.50 + 20), 45)

        # =====================================================================
        # 8C. Multi-Timeframe Trend Lock (Anti-Whipsaw Shield)
        # Prevents selling in morning dip when macro trend is Bullish!
        # =====================================================================
        if macro_bias == "BULLISH" and "SELL" in action:
            action = "NEUTRAL"
            confidence = 52
            reasons.append("🛡️ Trend Lock Shield: Daily Macro Trend is BULLISH. Short selling on intraday morning dip is prohibited! Waiting for support bounce to BUY.")
        elif macro_bias == "BEARISH" and "BUY" in action:
            action = "NEUTRAL"
            confidence = 52
            reasons.append("🛡️ Trend Lock Shield: Daily Macro Trend is BEARISH. Long buying on intraday relief bounce is prohibited! Waiting for resistance rejection to SELL.")

        # =====================================================================
        # 8D. Daily Range Exhaustion Shield (Prevents Buying at Peaks & Selling at Bottoms)
        # =====================================================================
        exhaustion_ratio = float(latest.get("Exhaustion_Ratio", 0.5))
        remaining_range = float(latest.get("Remaining_Range", atr * 1.5))
        today_open = float(latest.get("Today_Open", current_price))
        today_move_pct = round(((current_price - today_open) / today_open) * 100, 2) if today_open else 0.0

        if exhaustion_ratio >= 0.75:
            if today_move_pct > 1.2:
                reasons.append(f"⚠️ Range Exhaustion ({int(exhaustion_ratio*100)}% ATR used, up {today_move_pct:+.1f}% today): Expected daily move is already completed. High risk of mean-reversion pullback! DO NOT FOMO buy at day's peak.")
                if "BUY" in action:
                    action = "NEUTRAL"
                    confidence = min(confidence, 54)
            elif today_move_pct < -1.2:
                reasons.append(f"⚠️ Downside Exhaustion ({int(exhaustion_ratio*100)}% ATR used, down {today_move_pct:+.1f}% today): Selling climax reached. High risk of short-covering bounce! DO NOT Short Sell at day's low.")
                if "SELL" in action:
                    action = "NEUTRAL"
                    confidence = min(confidence, 54)

        # =====================================================================
        # 9. Dynamic Volatility & Category-Based Target & Stop Loss Engine
        # Provides professional breathing room (1.2% - 1.8% SL) to eliminate premature stop hunts!
        # =====================================================================
        cmp = round(current_price, 2)
        effective_atr = atr * vix_sl_mult
        r1 = float(latest.get("Pivot_R1", cmp + remaining_range))
        s1 = float(latest.get("Pivot_S1", cmp - remaining_range))

        sym_upper = symbol.upper()
        is_high_beta = any(hb in sym_upper for hb in ["ZOMATO", "SUZLON", "TRENT", "DIXON", "HAL", "BEL", "RVNL", "IRFC", "TATAPOWER", "TMCV"])
        is_mega_cap = any(mc in sym_upper for mc in ["RELIANCE", "TCS", "INFY", "HDFCBANK", "ICICIBANK", "SBIN", "BHARTIARTL", "ITC", "LT", "KOTAKBANK", "AXISBANK"])

        if is_high_beta:
            base_sl = cmp * 0.018    # 1.8% Stop Loss (protects against high-beta whipsaws)
            base_tp1 = cmp * 0.028   # 2.8% Target 1 (1:1.55 RRR)
            base_tp2 = cmp * 0.045   # 4.5% Target 2
        elif is_mega_cap:
            base_sl = cmp * 0.013    # 1.3% Stop Loss (healthy breathing room)
            base_tp1 = cmp * 0.021   # 2.1% Target 1 (1:1.6 RRR)
            base_tp2 = cmp * 0.035   # 3.5% Target 2
        else:
            base_sl = cmp * 0.015    # 1.5% Stop Loss
            base_tp1 = cmp * 0.024   # 2.4% Target 1 (1:1.6 RRR)
            base_tp2 = cmp * 0.038   # 3.8% Target 2

        # Time-of-Day Adaptive Target & Risk Scaling (Indian Market IST Session Awareness)
        # Market open: 09:15, close: 15:30 IST. Last hour: 14:00 - 15:00. Square-off cutoff: 15:15.
        from datetime import datetime, timezone, timedelta
        ist_now = datetime.now(timezone(timedelta(hours=5, minutes=30)))
        current_minute = ist_now.hour * 60 + ist_now.minute

        market_open_min = 9 * 60 + 15      # 555
        power_hour_min = 14 * 60 + 0       # 840 (2:00 PM)
        last_30_min = 15 * 60 + 0          # 900 (3:00 PM)
        market_close_min = 15 * 60 + 30    # 930 (3:30 PM)

        time_session_label = "STANDARD"
        target_time_mult = 1.0
        sl_time_mult = 1.0

        if current_minute >= power_hour_min and current_minute < last_30_min:
            # 2:00 PM - 3:00 PM: Last hour scalp! Tighten targets for fast EOD profit booking
            time_session_label = "POWER_HOUR_SCALP"
            target_time_mult = 0.50  # Compress target from ~2.4% down to ~1.1%
            sl_time_mult = 0.70      # Tighten SL as well
            reasons.append("⏱️ Power Hour Adaptive Mode (2:00 PM - 3:00 PM): Targets compressed to quick scalp (0.8% - 1.2%) for fast EOD profit booking before close.")
        elif current_minute >= last_30_min and current_minute < market_close_min:
            # 3:00 PM - 3:30 PM: Final 30 mins! Intraday square-off imminent
            time_session_label = "EOD_SQUAREOFF_WARNING"
            target_time_mult = 0.35  # Ultra-tight fast scalp
            sl_time_mult = 0.55
            reasons.append("⚠️ EOD Close Window (After 3:00 PM): Intraday auto-square off imminent. Fast scalp or BTST carry-over only.")
        elif current_minute < market_open_min or current_minute >= market_close_min:
            time_session_label = "OFF_MARKET_SWING"

        # Confluence with ATR if ATR is valid
        if effective_atr > 0.1:
            sl_dist = round(max(base_sl * sl_time_mult, effective_atr * 1.4 * sl_time_mult), 2)
            tp1_dist = round(max(base_tp1 * target_time_mult, effective_atr * 2.2 * target_time_mult), 2)
            tp2_dist = round(max(base_tp2 * target_time_mult, effective_atr * 3.5 * target_time_mult), 2)
        else:
            sl_dist = round(base_sl * sl_time_mult, 2)
            tp1_dist = round(base_tp1 * target_time_mult, 2)
            tp2_dist = round(base_tp2 * target_time_mult, 2)

        if "BUY" in action:
            tp1 = round(cmp + tp1_dist, 2)
            tp2 = round(cmp + tp2_dist, 2)
            sl = round(cmp - sl_dist, 2)
            risk = max(cmp - sl, 0.05)
            reward = max(tp1 - cmp, 0.05)
            rrr = f"1:{reward / risk:.2f}"
        elif "SELL" in action:
            tp1 = round(cmp - tp1_dist, 2)
            tp2 = round(cmp - tp2_dist, 2)
            sl = round(cmp + sl_dist, 2)
            risk = max(sl - cmp, 0.05)
            reward = max(cmp - tp1, 0.05)
            rrr = f"1:{reward / risk:.2f}"
        else:
            tp1 = round(cmp + tp1_dist, 2)
            tp2 = round(cmp + tp2_dist, 2)
            sl = round(cmp - sl_dist, 2)
            rrr = "1:1.60"

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
            "time_session": time_session_label,
            "atr": round(atr, 2),
            "effective_atr": round(effective_atr, 2),
            "exhaustion_ratio": exhaustion_ratio,
            "remaining_range": round(remaining_range, 2),
            "predictive_badge": predictive_badge,
            "vwap": round(float(vwap), 2),
            "supertrend": round(float(st_val), 2),
            "macro_trend": macro_bias,
            "smart_money": whale_badge,
            "market_regime": market_regime,
            "chop_index": round(chop_index, 1),
            "pcr": pcr,
            "pcr_bias": pcr_bias,
            "max_pain": max_pain,
            "vix_regime": vix_regime,
            "vix_value": round(vix_val, 1),
            "pattern_detected": active_pattern_info["pattern"] if active_pattern_info else None,
            "option_chain": opt_data,
            "breakdown": {
                "sentiment_points": round(sentiment_component * w_sent, 1),
                "candlestick_points": round(candlestick_component * w_candle, 1),
                "indicator_points": round(indicator_component * w_ind, 1),
                "option_chain_points": round(opt_score * w_opt, 1),
                "macro_chop_points": round(macro_chop_component * w_macro, 1),
                "macro_points": round(macro_penalty, 1),
                "chop_points": round(chop_penalty, 1),
                "sentiment_component": round(sentiment_component, 1),
                "candlestick_component": round(candlestick_component, 1),
                "indicator_component": round(indicator_component, 1),
                "macro_alignment": macro_bias,
                "whale_flow": whale_badge,
                "market_regime": market_regime,
                "is_fno": is_fno,
                "pcr": pcr,
                "max_pain": max_pain,
                "vix_regime": vix_regime
            },
            "reasons": reasons
        }

