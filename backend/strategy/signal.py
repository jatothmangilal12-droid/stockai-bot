"""
Breakout-from-consolidation entry rule.
Called on the CLOSE of a bar; entry is executed at the NEXT bar's open (backtest and live).
"""
from typing import Optional, Dict, Any
import numpy as np
import pandas as pd
from backend.config import (
    VOL_BREAKOUT_MULT, MAX_CHASE_PCT, STOP_BUFFER_PCT,
    RR_TARGET, RISK_PER_TRADE_RS, REQUIRE_SQUEEZE
)


def _nan(x) -> bool:
    return x is None or (isinstance(x, float) and np.isnan(x))


def breakout_signal(row: pd.Series) -> Optional[Dict[str, Any]]:
    needed = ["consol_high", "consol_low", "vwap", "vol_ratio", "rs", "day_move_pct"]
    if any(_nan(row[c]) for c in needed):
        return None
    if row["state"] == "EXTENDED":
        return None                        # never chase a stock already moved >= 2.5%
    if REQUIRE_SQUEEZE and not bool(row.get("squeeze", False)):
        return None
    if row["vol_ratio"] < VOL_BREAKOUT_MULT:
        return None

    close = float(row["close"])
    date_str = str(row.name.date())

    # LONG: breakout above consolidation high
    if (close > row["consol_high"]
            and (close - row["consol_high"]) / close * 100.0 <= MAX_CHASE_PCT
            and close > row["vwap"]
            and row["rs"] > 0):
        sl = round(float(row["consol_low"]) * (1.0 - STOP_BUFFER_PCT / 100.0), 2)
        risk = round(close - sl, 2)
        if risk <= 0:
            return None
        qty = int(RISK_PER_TRADE_RS // risk)
        if qty < 1:
            return None
        tp = round(close + RR_TARGET * risk, 2)
        return {
            "side": "BUY",
            "sl": sl,
            "tp": tp,
            "consol_level": round(float(row["consol_high"]), 2),
            "risk": risk,
            "qty": qty,
            "date": date_str,
            "signal_close": close
        }

    # SHORT: breakdown below consolidation low
    if (close < row["consol_low"]
            and (row["consol_low"] - close) / close * 100.0 <= MAX_CHASE_PCT
            and close < row["vwap"]
            and row["rs"] < 0):
        sl = round(float(row["consol_high"]) * (1.0 + STOP_BUFFER_PCT / 100.0), 2)
        risk = round(sl - close, 2)
        if risk <= 0:
            return None
        qty = int(RISK_PER_TRADE_RS // risk)
        if qty < 1:
            return None
        tp = round(close - RR_TARGET * risk, 2)
        return {
            "side": "SELL",
            "sl": sl,
            "tp": tp,
            "consol_level": round(float(row["consol_low"]), 2),
            "risk": risk,
            "qty": qty,
            "date": date_str,
            "signal_close": close
        }

    return None
