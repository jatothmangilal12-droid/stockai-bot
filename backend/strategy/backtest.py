"""
Intraday breakout backtester (5m bars).
Run:  python -m backend.strategy.backtest RELIANCE.NS TCS.NS ...
"""
import sys
from datetime import time as dtime
import pandas as pd
import yfinance as yf

from backend.config import (
    RISK_PER_TRADE_RS, COST_RATE_ROUNDTRIP, TIME_STOP_BARS,
    ENTRY_CUTOFF_HHMM, EOD_EXIT_HHMM
)
from backend.strategy.features import build_features
from backend.strategy.signal import breakout_signal

ENTRY_CUTOFF = dtime(*ENTRY_CUTOFF_HHMM)
EOD_EXIT = dtime(*EOD_EXIT_HHMM)


def load_5m(symbol: str) -> pd.DataFrame:
    """yfinance gives ~60 days of 5m. Live/long history: can also source from Angel historical API."""
    raw = yf.download(symbol, period="60d", interval="5m", progress=False, auto_adjust=False)
    if raw.empty:
        return pd.DataFrame()
    if isinstance(raw.columns, pd.MultiIndex):
        raw.columns = [c[0].lower() for c in raw.columns]
    else:
        raw.columns = [str(c).lower() for c in raw.columns]
    idx = raw.index
    if idx.tz is None:
        idx = idx.tz_localize("UTC")
    raw.index = idx.tz_convert("Asia/Kolkata")
    cols = ["open", "high", "low", "close", "volume"]
    return raw[[c for c in cols if c in raw.columns]].dropna()


def run_backtest(feats: pd.DataFrame) -> list[dict]:
    trades: list[dict] = []
    pos = None
    pending = None

    for i in range(1, len(feats)):
        bar = feats.iloc[i]
        ts = bar.name
        t = ts.time()

        # 1) Execute pending signal at THIS bar's open
        if pos is None and pending is not None:
            same_day = pending["date"] == str(ts.date())
            if same_day and t < ENTRY_CUTOFF:
                entry = float(bar["open"])
                valid = (pending["side"] == "BUY" and entry > pending["sl"]) or \
                        (pending["side"] == "SELL" and entry < pending["sl"])
                if valid:
                    risk_per_share = abs(entry - pending["sl"])
                    if risk_per_share > 0:
                        qty = int(RISK_PER_TRADE_RS // risk_per_share)
                        if qty >= 1:
                            pos = {
                                **pending,
                                "entry": entry,
                                "qty": qty,
                                "risk": risk_per_share,
                                "bars": 0,
                                "entry_time": ts
                            }
        pending = None

        # 2) Manage open position on this bar
        if pos is not None:
            pos["bars"] += 1
            exit_px, reason = None, None
            if pos["side"] == "BUY":
                if bar["low"] <= pos["sl"]:
                    exit_px, reason = pos["sl"], "SL"
                elif bar["high"] >= pos["tp"]:
                    exit_px, reason = pos["tp"], "TP"
                elif bar["close"] < pos["consol_level"]:
                    exit_px, reason = float(bar["close"]), "BREAKOUT_FAIL"
            else:
                if bar["high"] >= pos["sl"]:
                    exit_px, reason = pos["sl"], "SL"
                elif bar["low"] <= pos["tp"]:
                    exit_px, reason = pos["tp"], "TP"
                elif bar["close"] > pos["consol_level"]:
                    exit_px, reason = float(bar["close"]), "BREAKOUT_FAIL"

            if reason is None and pos["bars"] >= TIME_STOP_BARS:
                exit_px, reason = float(bar["close"]), "TIME_STOP"
            if reason is None and (t >= EOD_EXIT or ts.date() != pos["entry_time"].date()):
                exit_px, reason = float(bar["close"]), "EOD"

            if reason is not None:
                sign = 1 if pos["side"] == "BUY" else -1
                gross = (exit_px - pos["entry"]) * pos["qty"] * sign
                turnover = (pos["entry"] + exit_px) * pos["qty"]
                net = gross - turnover * COST_RATE_ROUNDTRIP
                trades.append({
                    "symbol": pos.get("symbol", ""),
                    "side": pos["side"],
                    "entry_time": pos["entry_time"],
                    "exit_time": ts,
                    "entry": round(pos["entry"], 2),
                    "exit": round(exit_px, 2),
                    "qty": pos["qty"],
                    "risk": round(pos["risk"], 2),
                    "gross": round(gross, 2),
                    "net": round(net, 2),
                    "reason": reason,
                })
                pos = None

        # 3) Look for new signal on this bar's CLOSE (entry comes at next bar open)
        if pos is None:
            pending = breakout_signal(bar)

    return trades


def summarize(trades: list[dict]) -> dict:
    if not trades:
        return {"trades": 0, "note": "No trades. Loosen rules or test more symbols."}
    df = pd.DataFrame(trades)
    risk_amt = df["risk"] * df["qty"]
    r_mult = df["net"] / risk_amt.replace(0, 1.0)
    equity = df["net"].cumsum()
    max_dd = float((equity - equity.cummax()).min()) if not equity.empty else 0.0
    return {
        "trades": int(len(df)),
        "win_rate_pct": round(float((df["net"] > 0).mean() * 100), 1),
        "avg_win_rs": round(float(df.loc[df["net"] > 0, "net"].mean() or 0), 2),
        "avg_loss_rs": round(float(df.loc[df["net"] <= 0, "net"].mean() or 0), 2),
        "expectancy_rs": round(float(df["net"].mean()), 2),
        "expectancy_R": round(float(r_mult.mean()), 3),
        "net_pnl_rs": round(float(df["net"].sum()), 2),
        "max_drawdown_rs": round(max_dd, 2),
        "exit_reasons": df["reason"].value_counts().to_dict(),
    }


if __name__ == "__main__":
    symbols = sys.argv[1:] or ["RELIANCE.NS", "HDFCBANK.NS", "ICICIBANK.NS", "SBIN.NS", "TATAPOWER.NS"]
    print(f"Loading 5m bars for ^NSEI benchmark...")
    nifty = load_5m("^NSEI")
    all_trades = []
    for sym in symbols:
        try:
            raw = load_5m(sym)
            if raw.empty:
                print(f"{sym}: No data")
                continue
            feats = build_features(raw, nifty if not nifty.empty else None)
            trades = run_backtest(feats)
            for tr in trades:
                tr["symbol"] = sym
            all_trades.extend(trades)
            print(sym, summarize(trades))
        except Exception as e:
            print(sym, "error:", e)
    print("\n================== PORTFOLIO BACKTEST SUMMARY ==================")
    print(summarize(all_trades))
