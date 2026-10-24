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

        return df

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

            # 1. Hammer (Bullish Reversal)
            if c_lower_shadow >= (2.0 * c_body) and c_upper_shadow <= (0.25 * c_body) and c_body > (0.1 * c_range):
                patterns.append({
                    "candle_index": i,
                    "time": curr["time"],
                    "formatted_time": curr["formatted_time"],
                    "pattern": "Hammer",
                    "bias": "BULLISH",
                    "strength": 75,
                    "description": "Bullish reversal pin bar with strong buying rejection from lows."
                })

            # 2. Inverted Hammer (Bullish Reversal)
            elif c_upper_shadow >= (2.0 * c_body) and c_lower_shadow <= (0.25 * c_body) and p_is_bearish:
                patterns.append({
                    "candle_index": i,
                    "time": curr["time"],
                    "formatted_time": curr["formatted_time"],
                    "pattern": "Inverted Hammer",
                    "bias": "BULLISH",
                    "strength": 65,
                    "description": "Bulls attempted an upward breakout; follow-through can trigger rally."
                })

            # 3. Shooting Star (Bearish Reversal)
            elif c_upper_shadow >= (2.0 * c_body) and c_lower_shadow <= (0.25 * c_body) and p_is_bullish:
                patterns.append({
                    "candle_index": i,
                    "time": curr["time"],
                    "formatted_time": curr["formatted_time"],
                    "pattern": "Shooting Star",
                    "bias": "BEARISH",
                    "strength": 75,
                    "description": "Bearish rejection from peak with heavy selling pressure at high."
                })

            # 4. Bullish Engulfing
            elif p_is_bearish and c_is_bullish and c_close > p_open and c_open < p_close and c_body > p_body:
                patterns.append({
                    "candle_index": i,
                    "time": curr["time"],
                    "formatted_time": curr["formatted_time"],
                    "pattern": "Bullish Engulfing",
                    "bias": "BULLISH",
                    "strength": 85,
                    "description": "Strong green candle completely engulfs prior red candle body."
                })

            # 5. Bearish Engulfing
            elif p_is_bullish and c_is_bearish and c_close < p_open and c_open > p_close and c_body > p_body:
                patterns.append({
                    "candle_index": i,
                    "time": curr["time"],
                    "formatted_time": curr["formatted_time"],
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
                        "candle_index": i,
                        "time": curr["time"],
                        "formatted_time": curr["formatted_time"],
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
                        "candle_index": i,
                        "time": curr["time"],
                        "formatted_time": curr["formatted_time"],
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
                    "candle_index": i,
                    "time": curr["time"],
                    "formatted_time": curr["formatted_time"],
                    "pattern": pattern_name,
                    "bias": bias,
                    "strength": 60,
                    "description": f"{pattern_name} signaling equilibrium and impending directional shift."
                })

            # 9. Piercing Line (Bullish)
            elif p_is_bearish and c_is_bullish and c_open < p_low and c_close > (p_open + p_close) / 2:
                patterns.append({
                    "candle_index": i,
                    "time": curr["time"],
                    "formatted_time": curr["formatted_time"],
                    "pattern": "Piercing Line",
                    "bias": "BULLISH",
                    "strength": 75,
                    "description": "Bullish thrust recovering more than 50% into prior bearish territory."
                })

            # 10. Dark Cloud Cover (Bearish)
            elif p_is_bullish and c_is_bearish and c_open > p_high and c_close < (p_open + p_close) / 2:
                patterns.append({
                    "candle_index": i,
                    "time": curr["time"],
                    "formatted_time": curr["formatted_time"],
                    "pattern": "Dark Cloud Cover",
                    "bias": "BEARISH",
                    "strength": 75,
                    "description": "Bearish cloud opening at peak and piercing deep into buyers' line."
                })

        return patterns
