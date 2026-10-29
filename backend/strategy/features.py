"""
Lookahead-free intraday features on 5-minute bars.
Input df: columns open, high, low, close, volume; DatetimeIndex in Asia/Kolkata; sorted ascending.
Every value at row t uses only bars <= t.
"""
from typing import Optional
import numpy as np
import pandas as pd
from backend.config import CONSOL_BARS, VOL_LOOKBACK, SQUEEZE_PCTILE, EXTENDED_MOVE_PCT


def build_features(df: pd.DataFrame, index_df: Optional[pd.DataFrame] = None) -> pd.DataFrame:
    d = df.copy()
    day = d.index.date

    # Session VWAP (resets each day, cumulative up to current bar)
    tpv = ((d["high"] + d["low"] + d["close"]) / 3.0) * d["volume"]
    cum_vol = d["volume"].groupby(day).cumsum()
    # Avoid div by zero if zero volume
    cum_vol = cum_vol.replace(0, np.nan)
    d["vwap"] = (tpv.groupby(day).cumsum() / cum_vol).fillna(d["close"])

    # Day open = first bar of today (past relative to current bar)
    d["day_open"] = d["open"].groupby(day).transform("first")
    d["day_move_pct"] = (d["close"] - d["day_open"]) / d["day_open"] * 100.0

    # Consolidation range from PRIOR bars only (shift(1) excludes current bar)
    d["consol_high"] = d["high"].shift(1).rolling(CONSOL_BARS).max()
    d["consol_low"] = d["low"].shift(1).rolling(CONSOL_BARS).min()
    d["range_pct"] = (d["consol_high"] - d["consol_low"]) / d["close"] * 100.0

    # Squeeze: current range rank inside its own last 100 values
    d["range_rank"] = d["range_pct"].rolling(100, min_periods=min(30, len(d))).rank(pct=True)
    d["squeeze"] = d["range_rank"] <= SQUEEZE_PCTILE

    # Volume ratio vs average of PRIOR bars
    prior_vol_avg = d["volume"].shift(1).rolling(VOL_LOOKBACK, min_periods=5).mean().replace(0, np.nan)
    d["vol_ratio"] = (d["volume"] / prior_vol_avg).fillna(1.0)

    # Relative strength vs index over same window (past only)
    if index_df is not None and not index_df.empty:
        idx_close = index_df["close"].reindex(d.index, method="ffill")
        stock_ret = d["close"].pct_change(CONSOL_BARS) * 100.0
        idx_ret = idx_close.pct_change(CONSOL_BARS) * 100.0
        d["rs"] = (stock_ret - idx_ret).fillna(0.0)
    else:
        d["rs"] = 0.0

    extended = d["day_move_pct"].abs() >= EXTENDED_MOVE_PCT
    d["state"] = np.where(extended, "EXTENDED",
                 np.where(d["squeeze"].fillna(False), "COMPRESSING", "NEUTRAL"))
    return d
