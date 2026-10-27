"""
15-Minute Candlestick Pattern Recognition & Technical Indicator Engine
Detects major reversal and continuation candlestick formations, RSI, MACD, EMAs, and ATR.
"""
import numpy as np
import pandas as pd
import yfinance as yf
from backend.config import CANDLESTICK_INTERVAL, CANDLESTICK_PERIOD


class TechnicalEngine:
    """Computes 15-minute indicators and detects candlestick patterns."""

    def fetch_candlesticks(self, symbol: str, period: str = CANDLESTICK_PERIOD, interval: str = CANDLESTICK_INTERVAL) -> pd.DataFrame:
        """Fetch 15m OHLCV data using yfinance."""
        try:
            ticker = yf.Ticker(symbol)
            df = ticker.history(period=period, interval=interval)
            if df.empty:
                # Fallback to 1mo period if 5d has limited data
                df = ticker.history(period="1mo", interval=interval)
            
            if df.empty:
                return pd.DataFrame()

            # Clean and normalize columns
            df.reset_index(inplace=True)
            # Find datetime column
            date_col = "Datetime" if "Datetime" in df.columns else "Date"
            df["time"] = pd.to_datetime(df[date_col]).astype("int64") // 10**6  # ms timestamp
            df["formatted_time"] = pd.to_datetime(df[date_col]).dt.strftime("%Y-%m-%d %H:%M")

            cols_needed = ["time", "formatted_time", "Open", "High", "Low", "Close", "Volume"]
            df = df[[c for c in cols_needed if c in df.columns]].copy()
            df.dropna(subset=["Open", "High", "Low", "Close"], inplace=True)
            return df
        except Exception as e:
            print(f"[Technical] Error fetching data for {symbol}: {e}")
            return pd.DataFrame()

    def calculate_indicators(self, df: pd.DataFrame) -> pd.DataFrame:
        """Calculate EMAs (9, 21, 50, 200), RSI 14, MACD, and ATR 14."""
        if len(df) < 20:
            return df

        close = df["Close"]
        high = df["High"]
        low = df["Low"]

        # 1. EMAs
        df["EMA_9"] = close.ewm(span=9, adjust=False).mean()
        df["EMA_21"] = close.ewm(span=21, adjust=False).mean()
        df["EMA_50"] = close.ewm(span=50, adjust=False).mean()
        if len(df) >= 200:
            df["EMA_200"] = close.ewm(span=200, adjust=False).mean()
        else:
            df["EMA_200"] = close.ewm(span=len(df), adjust=False).mean()

        # 2. RSI (14 periods)
        delta = close.diff()
        gain = delta.clip(lower=0)
        loss = -delta.clip(upper=0)
        avg_gain = gain.ewm(com=13, adjust=False).mean()
        avg_loss = loss.ewm(com=13, adjust=False).mean()
        rs = avg_gain / avg_loss.replace(0, np.nan)
        df["RSI"] = 100 - (100 / (1 + rs))
        df["RSI"] = df["RSI"].fillna(50)

        # 3. MACD (12, 26, 9)
        ema_12 = close.ewm(span=12, adjust=False).mean()
        ema_26 = close.ewm(span=26, adjust=False).mean()
        df["MACD"] = ema_12 - ema_26
        df["MACD_Signal"] = df["MACD"].ewm(span=9, adjust=False).mean()
        df["MACD_Hist"] = df["MACD"] - df["MACD_Signal"]

        # 4. Average True Range (ATR 14) for Stop Loss & Take Profit
        prev_close = close.shift(1)
        tr1 = high - low
        tr2 = (high - prev_close).abs()
        tr3 = (low - prev_close).abs()
        tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
        df["ATR"] = tr.rolling(window=14, min_periods=1).mean()

        # 5. Volume 20 SMA & Volume Spike Flag
        df["Vol_SMA20"] = df["Volume"].rolling(window=20, min_periods=1).mean()
        df["Vol_Surge"] = df["Volume"] > (df["Vol_SMA20"] * 1.4)

        # 6. Intraday VWAP (Volume-Weighted Average Price) with daily 09:15 AM reset
        dt_dates = pd.to_datetime(df["time"], unit="ms").dt.date
        df["_date"] = dt_dates
        typical_price = (high + low + close) / 3.0
        tp_vol = typical_price * df["Volume"]
        cum_vol = df.groupby("_date")["Volume"].cumsum()
        cum_tp_vol = tp_vol.groupby(df["_date"]).cumsum()
        df["VWAP"] = np.where(cum_vol > 0, cum_tp_vol / cum_vol, close)
        df.drop(columns=["_date"], inplace=True)

        # 7. Bollinger Bands (20, 2) & Volatility Squeeze Detection
        df["BB_Mid"] = close.rolling(window=20, min_periods=1).mean()
        bb_std = close.rolling(window=20, min_periods=1).std().fillna(0)
        df["BB_Upper"] = df["BB_Mid"] + (2.0 * bb_std)
        df["BB_Lower"] = df["BB_Mid"] - (2.0 * bb_std)
        # Squeeze detected when bandwidth < 3.8% (coiled spring before explosive breakout)
        bb_width = np.where(df["BB_Mid"] > 0, (df["BB_Upper"] - df["BB_Lower"]) / df["BB_Mid"], 0.05)
        df["BB_Squeeze"] = bb_width < 0.038

        # 8. SuperTrend (10, 3.0) - High Precision Trend Following
        hl2 = (high + low) / 2.0
        st_atr = tr.rolling(window=10, min_periods=1).mean()
        basic_upper = hl2 + (3.0 * st_atr)
        basic_lower = hl2 - (3.0 * st_atr)
        
        final_upper = basic_upper.copy()
        final_lower = basic_lower.copy()
        trend = np.ones(len(df), dtype=int)  # +1 Bullish, -1 Bearish
        st_val = np.zeros(len(df))

        for idx in range(1, len(df)):
            if basic_lower.iloc[idx] > final_lower.iloc[idx - 1] or close.iloc[idx - 1] < final_lower.iloc[idx - 1]:
                final_lower.iloc[idx] = basic_lower.iloc[idx]
            else:
                final_lower.iloc[idx] = final_lower.iloc[idx - 1]

            if basic_upper.iloc[idx] < final_upper.iloc[idx - 1] or close.iloc[idx - 1] > final_upper.iloc[idx - 1]:
                final_upper.iloc[idx] = basic_upper.iloc[idx]
            else:
                final_upper.iloc[idx] = final_upper.iloc[idx - 1]

            if close.iloc[idx] > final_upper.iloc[idx - 1]:
                trend[idx] = 1
            elif close.iloc[idx] < final_lower.iloc[idx - 1]:
                trend[idx] = -1
            else:
                trend[idx] = trend[idx - 1]

            st_val[idx] = final_lower.iloc[idx] if trend[idx] == 1 else final_upper.iloc[idx]

        df["SuperTrend_Direction"] = trend
        df["SuperTrend"] = st_val

        # 9. Classical Support & Resistance Pivot Points (Previous Day's True High, Low, Close)
        prev_high, prev_low, prev_close = None, None, None
        today_open = float(df["Open"].iloc[0])
        today_high = float(high.max())
        today_low = float(low.min())

        # Extract calendar dates accurately from timestamp column
        dt_series = pd.to_datetime(df["time"], unit="ms")
        dates_list = dt_series.dt.date.drop_duplicates().tolist()
        if len(dates_list) >= 2:
            prev_date = dates_list[-2]
            prev_day_mask = (dt_series.dt.date == prev_date)
            prev_day_df = df[prev_day_mask]
            if not prev_day_df.empty:
                prev_high = float(prev_day_df["High"].max())
                prev_low = float(prev_day_df["Low"].min())
                prev_close = float(prev_day_df["Close"].iloc[-1])

            today_date = dates_list[-1]
            today_mask = (dt_series.dt.date == today_date)
            today_df = df[today_mask]
            if not today_df.empty:
                today_open = float(today_df["Open"].iloc[0])
                today_high = float(today_df["High"].max())
                today_low = float(today_df["Low"].min())

        p_high = prev_high if prev_high else float(high.iloc[-1])
        p_low = prev_low if prev_low else float(low.iloc[-1])
        p_close = prev_close if prev_close else float(close.iloc[-1])
        pivot = (p_high + p_low + p_close) / 3.0
        df["Pivot_P"] = pivot
        df["Pivot_R1"] = (2.0 * pivot) - p_low
        df["Pivot_S1"] = (2.0 * pivot) - p_high
        df["Pivot_R2"] = pivot + (p_high - p_low)
        df["Pivot_S2"] = pivot - (p_high - p_low)

        # 9B. Intraday Daily Range Exhaustion & Remaining Range Calculator
        cmp = float(close.iloc[-1])
        used_range = max(today_high - today_low, 0.05)
        c_atr = float(df["ATR"].iloc[-1]) if "ATR" in df else (cmp * 0.015)
        # Institutional Daily ATR (standard 1.4% to 2.2% daily capability for Indian equities)
        daily_atr = max(c_atr * 3.5, cmp * 0.015)
        
        exhaustion_ratio = round(min(used_range / daily_atr, 1.8), 2)
        remaining_range = max(daily_atr * 0.30, daily_atr - used_range)

        df["Daily_ATR"] = daily_atr
        df["Today_Used_Range"] = used_range
        df["Exhaustion_Ratio"] = exhaustion_ratio
        df["Remaining_Range"] = remaining_range
        df["Today_High"] = today_high
        df["Today_Low"] = today_low
        df["Today_Open"] = today_open

        # 10. Choppiness Index (14-period Market Regime / Sideways Trap Filter)
        if len(df) >= 15:
            # Use true range (tr) to account for overnight and intraday gaps
            tr_sum14 = tr.rolling(window=14).sum()
            max_high14 = high.rolling(window=14).max()
            min_low14 = low.rolling(window=14).min()
            hl_range14 = (max_high14 - min_low14).replace(0, np.nan)
            chop_ratio = (tr_sum14 / hl_range14).clip(lower=0.001)
            df["Chop_Index"] = (100.0 * np.log10(chop_ratio) / np.log10(14)).fillna(50.0)
        else:
            df["Chop_Index"] = 50.0

        # 11. Smart Money / Volume Spread Analysis (VSA Whale Flow)
        vol_ratio = np.where(df["Vol_SMA20"] > 0, df["Volume"] / df["Vol_SMA20"], 1.0)
        df["Vol_Ratio"] = np.round(vol_ratio, 2)
        c_range = (high - low).replace(0, np.nan)
        df["Close_Position"] = np.round(((close - low) / c_range).fillna(0.5), 2)

        return df

    def detect_smart_money_flow(self, df: pd.DataFrame) -> dict:
        """
        Volume Spread Analysis (VSA): Detects institutional whale buying, distribution, or absorption.
        """
        if df.empty or len(df) < 5:
            return {"flow": "NEUTRAL", "badge": "Normal Volume", "description": "Insufficient data"}

        latest = df.iloc[-1]
        vol_ratio = float(latest.get("Vol_Ratio", 1.0))
        close_pos = float(latest.get("Close_Position", 0.5))
        is_bullish = latest["Close"] > latest["Open"]
        c_body = abs(latest["Close"] - latest["Open"])
        c_range = latest["High"] - latest["Low"]
        lower_shadow = min(latest["Open"], latest["Close"]) - latest["Low"]

        # Institutional Whale Accumulation
        if vol_ratio >= 2.0 and close_pos >= 0.70:
            return {
                "flow": "INSTITUTIONAL_ACCUMULATION",
                "badge": "🐋 Whale Accumulation",
                "score_impact": 25.0,
                "description": f"Massive volume surge ({vol_ratio:.1f}x 20-SMA) with aggressive close near high. Institutional buying detected!"
            }
        # Whale Absorption Pin Bar (Buying panic dips)
        elif vol_ratio >= 1.7 and lower_shadow >= (0.55 * c_range):
            return {
                "flow": "WHALE_ABSORPTION",
                "badge": "🛡️ Whale Dip Absorption",
                "score_impact": 20.0,
                "description": f"Institutions absorbing selling pressure at lows ({vol_ratio:.1f}x Vol) with heavy lower rejection wick."
            }
        # Institutional Whale Distribution (Smart money dumping into retail)
        elif vol_ratio >= 2.0 and close_pos <= 0.30:
            return {
                "flow": "INSTITUTIONAL_DISTRIBUTION",
                "badge": "⚠️ Whale Distribution",
                "score_impact": -25.0,
                "description": f"Heavy volume dump ({vol_ratio:.1f}x 20-SMA) with weak close near low. Smart money distribution caution!"
            }
        elif vol_ratio >= 1.4 and is_bullish:
            return {
                "flow": "ABOVE_AVERAGE_BUYING",
                "badge": "📈 Strong Volume Expansion",
                "score_impact": 10.0,
                "description": f"Healthy volume expansion ({vol_ratio:.1f}x 20-SMA) supporting upward momentum."
            }
        else:
            return {
                "flow": "NORMAL_RETAIL",
                "badge": "Normal Retail Flow",
                "score_impact": 0.0,
                "description": f"Standard market volume ({vol_ratio:.1f}x 20-SMA)."
            }

    def fetch_multi_timeframe_matrix(self, symbol: str) -> dict:
        """
        Multi-Timeframe Confluence Matrix: Daily Macro + 1-Hour Intermediate + 15m Execution.
        """
        macro = self.fetch_macro_trend(symbol)
        daily_trend = macro.get("trend", "NEUTRAL")

        # Fetch 1-Hour intermediate trend
        hourly_trend = "NEUTRAL"
        try:
            ticker = yf.Ticker(symbol)
            h_df = ticker.history(period="1mo", interval="1h")
            if not h_df.empty and len(h_df) >= 20:
                h_close = h_df["Close"]
                h_cmp = float(h_close.iloc[-1])
                h_ema20 = float(h_close.ewm(span=20).mean().iloc[-1])
                h_ema50 = float(h_close.ewm(span=50).mean().iloc[-1])
                if h_cmp > h_ema20 and h_ema20 >= h_ema50:
                    hourly_trend = "BULLISH"
                elif h_cmp < h_ema20 and h_ema20 <= h_ema50:
                    hourly_trend = "BEARISH"
                else:
                    hourly_trend = "CONSOLIDATION"
        except Exception:
            hourly_trend = daily_trend

        # Multi-Timeframe Alignment
        if daily_trend == "BULLISH" and hourly_trend == "BULLISH":
            matrix_status = "TRIPLE_CONFLUENCE_BULLISH"
            matrix_score = 30.0
            matrix_desc = "🌟 Perfect Multi-Timeframe Alignment: Daily & 1-Hour institutional trends are both BULLISH."
        elif daily_trend == "BEARISH" and hourly_trend == "BEARISH":
            matrix_status = "TRIPLE_CONFLUENCE_BEARISH"
            matrix_score = -30.0
            matrix_desc = "⚠️ Multi-Timeframe Bearish Alignment: Both Daily & 1-Hour trends are downward. Avoid long trades."
        else:
            matrix_status = "MIXED_CONFLUENCE"
            matrix_score = -10.0
            matrix_desc = f"Timeframes Divergent: Daily is {daily_trend}, Hourly is {hourly_trend}. Reduced confidence."

        return {
            "daily_trend": daily_trend,
            "hourly_trend": hourly_trend,
            "matrix_status": matrix_status,
            "matrix_score": matrix_score,
            "matrix_desc": matrix_desc
        }

    def fetch_macro_trend(self, symbol: str) -> dict:
        """
        Fetch Daily Higher-Timeframe trend to filter out false breakouts and counter-trend traps.
        """
        try:
            ticker = yf.Ticker(symbol)
            daily = ticker.history(period="3mo", interval="1d")
            if daily.empty or len(daily) < 15:
                return {"trend": "NEUTRAL", "confidence": 50, "description": "Insufficient daily data"}

            close = daily["Close"]
            cmp = float(close.iloc[-1])
            ema_20 = float(close.ewm(span=20).mean().iloc[-1])
            ema_50 = float(close.ewm(span=50).mean().iloc[-1]) if len(daily) >= 30 else ema_20

            if cmp > ema_20 and ema_20 >= ema_50:
                return {
                    "trend": "BULLISH",
                    "confidence": 88,
                    "description": f"Daily Macro Trend is Bullish (Price ₹{cmp:.1f} > 20 EMA ₹{ema_20:.1f} > 50 EMA)"
                }
            elif cmp < ema_20 and ema_20 <= ema_50:
                return {
                    "trend": "BEARISH",
                    "confidence": 88,
                    "description": f"Daily Macro Trend is Bearish (Price ₹{cmp:.1f} < 20 EMA ₹{ema_20:.1f} < 50 EMA)"
                }
            else:
                return {
                    "trend": "CONSOLIDATION",
                    "confidence": 60,
                    "description": f"Daily Macro Trend is Consolidating between ₹{ema_50:.1f} and ₹{ema_20:.1f}"
                }
        except Exception as e:
            return {"trend": "NEUTRAL", "confidence": 50, "description": f"Macro scan fallback: {e}"}


    def detect_candlestick_patterns(self, df: pd.DataFrame) -> list:
        """
        Scan candles for key candlestick patterns.
        Returns a list of detected pattern dicts for recent candles.
        """
        patterns = []
        if len(df) < 5:
            return patterns

        # We analyze the latest 5 candles
        start_idx = max(2, len(df) - 5)
        
        for i in range(start_idx, len(df)):
            curr = df.iloc[i]
            prev = df.iloc[i - 1]
            prev2 = df.iloc[i - 2] if i >= 2 else None

            c_open, c_high, c_low, c_close = curr["Open"], curr["High"], curr["Low"], curr["Close"]
            p_open, p_high, p_low, p_close = prev["Open"], prev["High"], prev["Low"], prev["Close"]

            c_range = c_high - c_low
            if c_range <= 0:
                continue

            c_body = abs(c_close - c_open)
            c_upper_shadow = c_high - max(c_open, c_close)
            c_lower_shadow = min(c_open, c_close) - c_low
            c_is_bullish = c_close > c_open
            c_is_bearish = c_close < c_open

            p_body = abs(p_close - p_open)
            p_is_bearish = p_close < p_open
            p_is_bullish = p_close > p_open

            candle_time = int(curr["time"])
            candle_formatted_time = str(curr["formatted_time"])

            # 1. Hammer (Bullish Reversal)
            if c_lower_shadow >= (2.0 * c_body) and c_upper_shadow <= (0.25 * c_body) and c_body > (0.1 * c_range):
                patterns.append({
                    "candle_index": int(i),
                    "time": candle_time,
                    "formatted_time": candle_formatted_time,
                    "pattern": "Hammer",
                    "bias": "BULLISH",
                    "strength": 75,
                    "description": "Bullish reversal pin bar with strong buying rejection from lows."
                })

            # 2. Inverted Hammer (Bullish Reversal)
            elif c_upper_shadow >= (2.0 * c_body) and c_lower_shadow <= (0.25 * c_body) and p_is_bearish:
                patterns.append({
                    "candle_index": int(i),
                    "time": candle_time,
                    "formatted_time": candle_formatted_time,
                    "pattern": "Inverted Hammer",
                    "bias": "BULLISH",
                    "strength": 65,
                    "description": "Bulls attempted an upward breakout; follow-through can trigger rally."
                })

            # 3. Shooting Star (Bearish Reversal)
            elif c_upper_shadow >= (2.0 * c_body) and c_lower_shadow <= (0.25 * c_body) and p_is_bullish:
                patterns.append({
                    "candle_index": int(i),
                    "time": candle_time,
                    "formatted_time": candle_formatted_time,
                    "pattern": "Shooting Star",
                    "bias": "BEARISH",
                    "strength": 75,
                    "description": "Bearish rejection from peak with heavy selling pressure at high."
                })

            # 4. Bullish Engulfing
            elif p_is_bearish and c_is_bullish and c_close > p_open and c_open < p_close and c_body > p_body:
                patterns.append({
                    "candle_index": int(i),
                    "time": candle_time,
                    "formatted_time": candle_formatted_time,
                    "pattern": "Bullish Engulfing",
                    "bias": "BULLISH",
                    "strength": 85,
                    "description": "Strong green candle completely engulfs prior red candle body."
                })

            # 5. Bearish Engulfing
            elif p_is_bullish and c_is_bearish and c_close < p_open and c_open > p_close and c_body > p_body:
                patterns.append({
                    "candle_index": int(i),
                    "time": candle_time,
                    "formatted_time": candle_formatted_time,
                    "pattern": "Bearish Engulfing",
                    "bias": "BEARISH",
                    "strength": 85,
                    "description": "Strong red candle completely engulfs prior green candle body."
                })

            # 6. Morning Star (3 candles)
            elif prev2 is not None and prev2["Close"] < prev2["Open"]:
                p2_body = abs(prev2["Close"] - prev2["Open"])
                # Middle candle small body, current candle closes > 50% into first candle
                if p_body < (p2_body * 0.4) and c_is_bullish and c_close > (prev2["Close"] + p2_body * 0.5):
                    patterns.append({
                        "candle_index": int(i),
                        "time": candle_time,
                        "formatted_time": candle_formatted_time,
                        "pattern": "Morning Star",
                        "bias": "BULLISH",
                        "strength": 90,
                        "description": "Premier 3-candle bullish reversal after downtrend indecision."
                    })

            # 7. Evening Star (3 candles)
            elif prev2 is not None and prev2["Close"] > prev2["Open"]:
                p2_body = abs(prev2["Close"] - prev2["Open"])
                if p_body < (p2_body * 0.4) and c_is_bearish and c_close < (prev2["Close"] - p2_body * 0.5):
                    patterns.append({
                        "candle_index": int(i),
                        "time": candle_time,
                        "formatted_time": candle_formatted_time,
                        "pattern": "Evening Star",
                        "bias": "BEARISH",
                        "strength": 90,
                        "description": "Premier 3-candle bearish reversal after uptrend indecision."
                    })

            # 8. Doji (Indecision)
            elif c_body <= (0.1 * c_range):
                if c_lower_shadow > (0.6 * c_range):
                    pattern_name = "Dragonfly Doji"
                    bias = "BULLISH"
                elif c_upper_shadow > (0.6 * c_range):
                    pattern_name = "Gravestone Doji"
                    bias = "BEARISH"
                else:
                    pattern_name = "Doji"
                    bias = "NEUTRAL"

                patterns.append({
                    "candle_index": int(i),
                    "time": candle_time,
                    "formatted_time": candle_formatted_time,
                    "pattern": pattern_name,
                    "bias": bias,
                    "strength": 60,
                    "description": f"{pattern_name} signaling equilibrium and impending directional shift."
                })

            # 9. Piercing Line (Bullish)
            elif p_is_bearish and c_is_bullish and c_open < p_low and c_close > (p_open + p_close) / 2:
                patterns.append({
                    "candle_index": int(i),
                    "time": candle_time,
                    "formatted_time": candle_formatted_time,
                    "pattern": "Piercing Line",
                    "bias": "BULLISH",
                    "strength": 75,
                    "description": "Bullish thrust recovering more than 50% into prior bearish territory."
                })

            # 10. Dark Cloud Cover (Bearish)
            elif p_is_bullish and c_is_bearish and c_open > p_high and c_close < (p_open + p_close) / 2:
                patterns.append({
                    "candle_index": int(i),
                    "time": candle_time,
                    "formatted_time": candle_formatted_time,
                    "pattern": "Dark Cloud Cover",
                    "bias": "BEARISH",
                    "strength": 75,
                    "description": "Bearish cloud opening at peak and piercing deep into buyers' line."
                })

        return patterns

    def detect_momentum_exhaustion(self, df: pd.DataFrame) -> dict:
        """
        1:5 High Asymmetric Payoff Reversal Sniper:
        Detects RSI Divergence + Volume Climax where selling or buying is completely exhausted.
        """
        if df.empty or len(df) < 18:
            return {"is_reversal_setup": False, "type": "NONE"}

        recent = df.iloc[-15:]
        latest = df.iloc[-1]
        cmp = float(latest["Close"])
        atr = float(latest.get("ATR", cmp * 0.01))
        vol_ratio = float(latest.get("Vol_Ratio", 1.0))
        rsi_vals = recent["RSI"].values
        close_vals = recent["Close"].values

        # 1. Bullish Divergence (Sellers Exhausted - High Payoff Reversal Long)
        # Price makes Lower Low, but RSI makes Higher Low below 35
        p_min_idx = np.argmin(close_vals)
        r_min_idx = np.argmin(rsi_vals)

        rem_range = float(latest.get("Remaining_Range", atr * 1.5))

        if p_min_idx > len(close_vals) - 4 and rsi_vals[-1] > rsi_vals[r_min_idx] and rsi_vals[r_min_idx] < 36:
            if vol_ratio >= 1.5 or latest["Close"] > latest["Open"]:
                tp_gain = min(max(rem_range * 0.85, cmp * 0.008), cmp * 0.020)
                sl_risk = min(max(rem_range * 0.45, cmp * 0.004), cmp * 0.010)
                sl = round(cmp - sl_risk, 2)
                tp = round(cmp + tp_gain, 2)
                risk = max(cmp - sl, 0.05)
                reward = max(tp - cmp, 0.05)
                return {
                    "is_reversal_setup": True,
                    "type": "BULLISH_EXHAUSTION_SNIPER",
                    "badge": "🎯 1:2 Reversal Sniper (Bottom)",
                    "action": "STRONG BUY",
                    "entry_price": cmp,
                    "stop_loss": sl,
                    "target": tp,
                    "risk_reward_ratio": f"1:{reward / risk:.1f}",
                    "confidence": 92,
                    "description": f"Sellers exhausted! Bullish RSI divergence ({rsi_vals[-1]:.1f}) with heavy volume absorption at bottom. Target ₹{tp} (+{(tp_gain/cmp)*100:.1f}%) within remaining daily range."
                }

        # 2. Bearish Divergence (Buyers Exhausted - High Payoff Reversal Short)
        # Price makes Higher High, but RSI makes Lower High above 65
        p_max_idx = np.argmax(close_vals)
        r_max_idx = np.argmax(rsi_vals)

        if p_max_idx > len(close_vals) - 4 and rsi_vals[-1] < rsi_vals[r_max_idx] and rsi_vals[r_max_idx] > 64:
            if vol_ratio >= 1.5 or latest["Close"] < latest["Open"]:
                tp_gain = min(max(rem_range * 0.85, cmp * 0.008), cmp * 0.020)
                sl_risk = min(max(rem_range * 0.45, cmp * 0.004), cmp * 0.010)
                sl = round(cmp + sl_risk, 2)
                tp = round(cmp - tp_gain, 2)
                risk = max(sl - cmp, 0.05)
                reward = max(cmp - tp, 0.05)
                return {
                    "is_reversal_setup": True,
                    "type": "BEARISH_EXHAUSTION_SNIPER",
                    "badge": "🎯 1:2 Reversal Sniper (Top)",
                    "action": "STRONG SELL",
                    "entry_price": cmp,
                    "stop_loss": sl,
                    "target": tp,
                    "risk_reward_ratio": f"1:{reward / risk:.1f}",
                    "confidence": 92,
                    "description": f"Buyers exhausted! Bearish RSI divergence ({rsi_vals[-1]:.1f}) with heavy selling climax at peak. Target ₹{tp} (-{(tp_gain/cmp)*100:.1f}%) within remaining daily range."
                }

        return {"is_reversal_setup": False, "type": "NONE"}

    def detect_delivery_spike(self, df: pd.DataFrame) -> dict:
        """
        Institutional Delivery Volume Spike Tracker:
        Identifies whether large institutions are buying shares for long-term delivery accumulation.
        """
        if df.empty or len(df) < 5:
            return {"is_delivery_spike": False, "badge": "Normal Delivery"}

        latest = df.iloc[-1]
        vol_ratio = float(latest.get("Vol_Ratio", 1.0))
        close_pos = float(latest.get("Close_Position", 0.5))
        is_bullish = latest["Close"] > latest["Open"]

        if vol_ratio >= 2.2 and is_bullish and close_pos >= 0.65:
            return {
                "is_delivery_spike": True,
                "badge": "📦 Institutional Delivery Inflow",
                "score_bonus": 20.0,
                "description": f"Massive delivery accumulation spike ({vol_ratio:.1f}x 20-SMA). Institutional funds parking capital for holding."
            }
        else:
            return {"is_delivery_spike": False, "badge": "Normal Retail Flow", "score_bonus": 0.0}

    def compute_sector_rotation(self, quotes: list) -> dict:
        """
        Sector Rotation & Capital Inflow Heatmap:
        Identifies leading vs lagging sectors so AI only trades in the direction of institutional money flow.
        """
        sector_map = {}
        for q in quotes:
            sec = q.get("sector", "Other")
            if sec not in sector_map:
                sector_map[sec] = []
            sector_map[sec].append(q.get("change_pct", 0.0))

        sector_rankings = []
        for sec, changes in sector_map.items():
            avg_change = round(sum(changes) / len(changes), 2) if changes else 0.0
            status = "LEADER (INFLOW)" if avg_change > 0.4 else ("LAGGING (OUTFLOW)" if avg_change < -0.4 else "NEUTRAL")
            sector_rankings.append({
                "sector": sec,
                "avg_change_pct": avg_change,
                "status": status,
                "stocks_count": len(changes)
            })

        sector_rankings.sort(key=lambda x: x["avg_change_pct"], reverse=True)
        leading = sector_rankings[0]["sector"] if sector_rankings else "Broad Market"
        lagging = sector_rankings[-1]["sector"] if sector_rankings else "Broad Market"

        return {
            "sectors": sector_rankings,
            "leading_sector": leading,
            "lagging_sector": lagging,
            "flow_summary": f"Institutional capital is flowing heavily into **{leading}**, while rotating out of **{lagging}**."
        }
