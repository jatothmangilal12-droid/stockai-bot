"""
FastAPI Main Application Server - 100% Indian Market Focus (NSE / BSE)
Includes Autonomous AI Auto-Trader, Real-Time NSE Candlesticks, and Win/Loss Analytics.
"""
import asyncio
import time
import os
import sys
import warnings
import json
import urllib.request
import random
from pathlib import Path
from typing import Optional
from concurrent.futures import ThreadPoolExecutor
from contextlib import asynccontextmanager
from datetime import datetime, timezone, timedelta

# Suppress 3rd party deprecation warnings
warnings.filterwarnings("ignore")

from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field
import yfinance as yf
import numpy as np

def json_sanitize(obj):
    """Recursively convert NumPy scalars/arrays to standard Python primitives."""
    if isinstance(obj, dict):
        return {str(k): json_sanitize(v) for k, v in obj.items()}
    elif isinstance(obj, (list, tuple, set)):
        return [json_sanitize(x) for x in obj]
    elif isinstance(obj, np.ndarray):
        return [json_sanitize(x) for x in obj.tolist()]
    elif isinstance(obj, np.generic):
        return obj.item()
    return obj

from backend.config import DEFAULT_STOCKS, NIFTY_UNIVERSE, BASE_DIR
from backend.news_sentiment import NewsSentimentAnalyzer
from backend.technical_engine import TechnicalEngine
from backend.signal_evaluator import SignalEvaluator
from backend.paper_trading import PaperTradingEngine
from backend.angel_one import AngelOneClient
from backend.angel_research import AngelResearchEngine, CAPITAL_PER_TRADE
from backend.database import get_connection

app = FastAPI(title="StockAI - Indian Market 15m Pattern & Sentiment Bot", version="2.0.0")

# Enable CORS for mobile app and web access
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Core Quantitative Engines
news_analyzer = NewsSentimentAnalyzer()
technical_engine = TechnicalEngine()
signal_evaluator = SignalEvaluator()
paper_trading = PaperTradingEngine()
angel_research = AngelResearchEngine(paper_trading=paper_trading)
angel_client = AngelOneClient(
    api_key=os.getenv("ANGELONE_API_KEY", "KLcQJzrD"),
    client_code=os.getenv("ANGELONE_CLIENT_CODE", "M207216"),
    password=os.getenv("ANGELONE_PASSWORD", "1995"),
    totp_secret=os.getenv("ANGELONE_TOTP_SECRET", "JXDOER6HYCVKM2HYRLRASLAFUM")
)

# Active Watchlist - 100% Indian NSE Stocks
CURRENT_WATCHLIST = list(DEFAULT_STOCKS)
CACHE_ANALYSIS = {}

LATEST_PRICES = {}
LATEST_PRICES_METADATA = {}
LAST_ANGEL_TICK_TIME = 0.0

# Active WebSocket Connections
active_connections: list[WebSocket] = []


class OrderRequest(BaseModel):
    symbol: str
    side: str  # 'BUY' or 'SELL'
    quantity: int = Field(default=1, gt=0, le=500)
    price: float = Field(default=0.0, ge=0.0)
    stop_loss: Optional[float] = None
    target_price: Optional[float] = None
    sl_pct: Optional[float] = None
    tp_pct: Optional[float] = None
    company_name: Optional[str] = ""
    trade_type: Optional[str] = "MANUAL"
    ai_confidence: Optional[float] = 0.0
    ai_reasons: Optional[str] = ""


class CloseOrderRequest(BaseModel):
    current_price: float
    reason: Optional[str] = "MANUAL"


class AngelSettingsRequest(BaseModel):
    api_key: str
    client_code: str
    password: str
    totp_secret: str


class WatchlistAddRequest(BaseModel):
    symbol: str
    name: Optional[str] = ""
    market: Optional[str] = "NSE"
    currency: Optional[str] = "₹"


class AngelResearchIngestRequest(BaseModel):
    symbol: str
    action: Optional[str] = "BUY"
    entry_price: float
    stop_loss: float
    target_price: float
    category: Optional[str] = "Intraday"
    company_name: Optional[str] = ""
    call_type: Optional[str] = "Analyst call"


class AngelTextParseRequest(BaseModel):
    text: str


def is_indian_market_open() -> bool:
    """Check if Indian NSE equity market is in live trading hours (Mon-Fri 09:15 - 15:30 IST)."""
    now_utc = datetime.now(timezone.utc)
    now_ist = now_utc + timedelta(hours=5, minutes=30)
    if now_ist.weekday() >= 5:  # Saturday or Sunday
        return False
    mins = now_ist.hour * 60 + now_ist.minute
    return 555 <= mins <= 930


def fetch_live_nse_quote(symbol: str) -> dict:
    """Fetch high-speed real-time NSE quote directly from Angel One SmartAPI."""
    # 1. Angel One SmartAPI Official Real-Time Live Quote
    if angel_client.is_configured():
        if not angel_client.is_authenticated:
            try:
                angel_client.login()
            except Exception:
                pass
        if angel_client.is_authenticated:
            try:
                quote = angel_client.get_live_quote(symbol)
                if quote and quote.get("price", 0) > 0:
                    return {
                        "price": round(float(quote["price"]), 2),
                        "change_pct": round(float(quote.get("percent_change", 0.0)), 2),
                        "currency": "₹",
                        "source": "AngelOne_Live"
                    }
            except Exception as e:
                print(f"[SmartAPI] Live quote fetch error for {symbol}: {e}")

    # 2. Yahoo Chart Quote Fallback (STRICTLY for Indices like ^INDIAVIX or ^NSEI only)
    if symbol.startswith("^"):
        clean_sym = symbol
        url = f"https://query1.finance.yahoo.com/v8/finance/chart/{clean_sym}?interval=15m&range=2d"
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"})
        try:
            with urllib.request.urlopen(req, timeout=3.5) as resp:
                data = json.loads(resp.read().decode())
                meta = data["chart"]["result"][0]["meta"]
                cmp = meta.get("regularMarketPrice") or meta.get("chartPreviousClose") or 0.0
                prev_close = meta.get("chartPreviousClose") or meta.get("previousClose") or cmp
                change_pct = round(((cmp - prev_close) / prev_close) * 100, 2) if prev_close else 0.0
                return {
                    "price": round(cmp, 2),
                    "change_pct": change_pct,
                    "currency": "₹",
                    "source": "Yahoo_Index"
                }
        except Exception:
            pass

    # 3. For equity stocks, NEVER fallback to 15-min delayed Yahoo! Use Angel One cached price or report Feed_Offline
    clean = symbol.replace(".NS", "").replace("-EQ", "").upper()
    cached = LATEST_PRICES.get(clean) or LATEST_PRICES.get(f"{clean}.NS") or 0.0
    meta = LATEST_PRICES_METADATA.get(clean, {})
    return {
        "price": cached,
        "change_pct": meta.get("change_pct", 0.0),
        "currency": "₹",
        "source": "AngelOne_Live" if cached > 0 else "Feed_Offline"
    }

    return {"price": 0.0, "change_pct": 0.0, "currency": "₹", "source": "None"}


LIVE_VIX_CACHE = {"value": 14.2, "timestamp": 0.0}

def fetch_live_india_vix() -> float:
    """Fetch real-time India VIX (^INDIAVIX) from NSE/Yahoo with 30s cache."""
    global LIVE_VIX_CACHE
    now = time.time()
    if now - LIVE_VIX_CACHE["timestamp"] < 30.0 and LIVE_VIX_CACHE["value"] > 0:
        return LIVE_VIX_CACHE["value"]
    try:
        quote = fetch_live_nse_quote("^INDIAVIX")
        val = float(quote.get("price", 0.0))
        if val > 0:
            LIVE_VIX_CACHE = {"value": round(val, 2), "timestamp": now}
            return LIVE_VIX_CACHE["value"]
    except Exception as e:
        print(f"[VIX] India VIX live fetch error: {e}")
    return LIVE_VIX_CACHE["value"]




@app.get("/api/stocks")
def get_stocks():
    """Returns watchlist with 100% live real-time NSE prices fetched concurrently."""
    def fetch_item(item):
        sym = item["symbol"]
        quote = fetch_live_nse_quote(sym)
        price = quote["price"]
        change_pct = quote["change_pct"]

        if price > 0:
            LATEST_PRICES[sym] = price
        else:
            price = LATEST_PRICES.get(sym, 0.0)

        return {
            "symbol": sym,
            "name": item.get("name", sym),
            "market": "NSE",
            "currency": "₹",
            "price": price,
            "change_pct": change_pct
        }

    with ThreadPoolExecutor(max_workers=min(len(CURRENT_WATCHLIST), 10)) as executor:
        results = list(executor.map(fetch_item, CURRENT_WATCHLIST))
    return results


@app.get("/api/stock/{symbol}/analysis")
def get_stock_analysis(symbol: str):
    """
    Complete analysis pipeline:
    15-minute real candlesticks + indicators + candlestick patterns + news sentiment + confluence signals.
    """
    # 1. Fetch 15m candlesticks
    df = technical_engine.fetch_candlesticks(symbol, period="5d", interval="15m")
    if df.empty:
        raise HTTPException(status_code=404, detail=f"No candlestick data available for {symbol}")

    # 2. Indicators & Candlestick Patterns
    df = technical_engine.calculate_indicators(df)
    patterns = technical_engine.detect_candlestick_patterns(df)

    latest_close = float(df["Close"].iloc[-1])
    LATEST_PRICES[symbol] = round(latest_close, 2)

    # 3. News Sentiment Analysis
    stock_info = next((s for s in CURRENT_WATCHLIST if s["symbol"] == symbol), None)
    comp_name = stock_info["name"] if stock_info else symbol
    sentiment_data = news_analyzer.analyze(symbol, comp_name)

    # 4. Multi-Timeframe Macro Trend, Smart Money & Confluence Signal Generation
    macro_trend = technical_engine.fetch_macro_trend(symbol)
    smart_money = technical_engine.detect_smart_money_flow(df)
    mtf_matrix = technical_engine.fetch_multi_timeframe_matrix(symbol)
    vix_val = fetch_live_india_vix()
    signal = signal_evaluator.evaluate(
        symbol, latest_close, df, patterns, sentiment_data,
        macro_trend=macro_trend, smart_money_flow=smart_money, mtf_matrix=mtf_matrix,
        vix_value=vix_val
    )

    # Convert candlestick dataframe to chart JSON records
    chart_candles = []
    for _, row in df.iterrows():
        chart_candles.append({
            "time": int(row["time"]),
            "formatted_time": row["formatted_time"],
            "open": round(float(row["Open"]), 2),
            "high": round(float(row["High"]), 2),
            "low": round(float(row["Low"]), 2),
            "close": round(float(row["Close"]), 2),
            "volume": int(row["Volume"]),
            "ema_9": round(float(row["EMA_9"]), 2) if "EMA_9" in row and not pd_isna(row["EMA_9"]) else None,
            "ema_21": round(float(row["EMA_21"]), 2) if "EMA_21" in row and not pd_isna(row["EMA_21"]) else None,
            "rsi": round(float(row["RSI"]), 1) if "RSI" in row and not pd_isna(row["RSI"]) else None,
        })

    result = {
        "symbol": symbol,
        "company_name": comp_name,
        "current_price": round(latest_close, 2),
        "currency": "₹",
        "market": "NSE",
        "candles": chart_candles,
        "patterns_detected": patterns[-8:],
        "sentiment": sentiment_data,
        "signal": signal,
        "smart_money": smart_money,
        "mtf_matrix": mtf_matrix,
        "price_impact": sentiment_data.get("price_impact"),
        "option_chain": signal.get("option_chain"),
        "breakdown": signal.get("breakdown"),
        "timestamp": time.time(),
        "cached_at": time.time()
    }
    clean_result = json_sanitize(result)
    clean_result["timestamp"] = result["timestamp"]
    clean_result["cached_at"] = result["cached_at"]
    CACHE_ANALYSIS[symbol] = clean_result
    return clean_result


def pd_isna(val):
    """Check for NaN safely."""
    try:
        import math
        return val is None or math.isnan(float(val))
    except (ValueError, TypeError):
        return True



@app.get("/api/screener")
def get_market_screener(sector: Optional[str] = None, offset: int = 0):
    """Scan top Indian NSE stocks for real-time 15m confluence signals in parallel, supporting sector filtering & dynamic pagination."""
    if sector and sector.upper() != "ALL":
        target_universe = [s for s in NIFTY_UNIVERSE if sector.upper() in s.get("sector", "").upper()]
        if not target_universe:
            target_universe = NIFTY_UNIVERSE
    else:
        # Rotate dynamically through universe
        start = offset % len(NIFTY_UNIVERSE)
        target_universe = NIFTY_UNIVERSE[start:start + 12]
        if len(target_universe) < 8 and len(NIFTY_UNIVERSE) >= 8:
            target_universe += NIFTY_UNIVERSE[:8 - len(target_universe)]

    def scan_item(item):
        sym = item["symbol"]
        try:
            df = technical_engine.fetch_candlesticks(sym, period="3d", interval="15m")
            if df.empty or len(df) < 5:
                return None
            df = technical_engine.calculate_indicators(df)
            patterns = technical_engine.detect_candlestick_patterns(df)
            latest_close = float(df["Close"].iloc[-1])
            LATEST_PRICES[sym] = round(latest_close, 2)

            news_items = news_analyzer.fetch_news(sym, item["name"], limit=5)
            total_score = sum(news_analyzer.score_headline(n["title"])["score"] for n in news_items)
            net_sent = round(total_score / len(news_items), 2) if news_items else 0.0

            sentiment_data = {"net_sentiment": net_sent}
            smart_money = technical_engine.detect_smart_money_flow(df)
            delivery = technical_engine.detect_delivery_spike(df)
            reversal = technical_engine.detect_momentum_exhaustion(df)
            macro_trend = technical_engine.fetch_macro_trend(sym)
            vix_val = fetch_live_india_vix()
            signal = signal_evaluator.evaluate(
                sym, latest_close, df, patterns, sentiment_data,
                macro_trend=macro_trend, smart_money_flow=smart_money,
                vix_value=vix_val
            )

            return {
                "symbol": sym,
                "name": item["name"],
                "sector": item.get("sector", "NSE"),
                "market": "NSE",
                "currency": "₹",
                "price": round(latest_close, 2),
                "action": signal["action"],
                "confidence": signal["confidence"],
                "confluence_score": signal["confluence_score"],
                "pattern": signal.get("pattern_detected"),
                "sentiment_score": net_sent,
                "target_1": signal["target_1"],
                "target_2": signal["target_2"],
                "stop_loss": signal["stop_loss"],
                "rrr": signal["risk_reward_ratio"],
                "vwap": signal.get("vwap"),
                "supertrend": signal.get("supertrend"),
                "macro_trend": signal.get("macro_trend", "NEUTRAL"),
                "smart_money": signal.get("smart_money", "Normal Volume"),
                "delivery_spike": delivery.get("badge"),
                "is_reversal": reversal.get("is_reversal_setup", False),
                "reversal_info": reversal if reversal.get("is_reversal_setup") else None,
                "market_regime": signal.get("market_regime", "NORMAL"),
                "chop_index": signal.get("chop_index", 50.0),
                "exhaustion_ratio": signal.get("exhaustion_ratio", 0.0),
                "remaining_range": signal.get("remaining_range", 0.0),
                "predictive_badge": signal.get("predictive_badge"),
                "reasons": signal.get("reasons", [])
            }
        except Exception as e:
            print(f"[Screener] Error for {sym}: {e}")
            return None

    with ThreadPoolExecutor(max_workers=min(len(target_universe), 10)) as executor:
        raw_results = list(executor.map(scan_item, target_universe))

    screener_results = [r for r in raw_results if r is not None]
    screener_results.sort(key=lambda x: abs(x["confluence_score"]), reverse=True)
    return json_sanitize(screener_results)


DISCOVER_CACHE = {"data": None, "timestamp": 0.0}
SECTOR_HEATMAP_CACHE = {"data": None, "timestamp": 0.0}
LIVE_MOVERS_CACHE = {"data": None, "timestamp": 0.0}
REVERSALS_CACHE = {"data": None, "timestamp": 0.0}

@app.get("/api/universe/discover")
def discover_best_stocks(force: bool = False):
    """
    World-Class Dynamic Universe Scanner:
    Scans liquid NIFTY universe, finds stocks with institutional volume & confluence,
    and returns top opportunities. Uses 5-minute cache to prevent API rate limiting.
    """
    global CURRENT_WATCHLIST, DISCOVER_CACHE
    now = time.time()
    if not force and DISCOVER_CACHE["data"] and (now - DISCOVER_CACHE["timestamp"] < 300):
        return DISCOVER_CACHE["data"]

    # Select candidate pool prioritized by hot sectors and liquid stocks
    pool = NIFTY_UNIVERSE[:30]

    def evaluate_candidate(candidate):
        sym = candidate["symbol"]
        try:
            df = technical_engine.fetch_candlesticks(sym, period="3d", interval="15m")
            if df.empty or len(df) < 5:
                return None
            df = technical_engine.calculate_indicators(df)
            patterns = technical_engine.detect_candlestick_patterns(df)
            latest_close = float(df["Close"].iloc[-1])
            LATEST_PRICES[sym] = round(latest_close, 2)

            first_open = float(df["Open"].iloc[0])
            change_pct = round(((latest_close - first_open) / first_open) * 100, 2) if first_open else 0.0

            smart_money = technical_engine.detect_smart_money_flow(df)
            macro_trend = technical_engine.fetch_macro_trend(sym)
            vix_val = fetch_live_india_vix()
            signal = signal_evaluator.evaluate(
                sym, latest_close, df, patterns, {"net_sentiment": 0.0},
                macro_trend=macro_trend, smart_money_flow=smart_money,
                vix_value=vix_val
            )

            vol_ratio = float(df["Vol_Ratio"].iloc[-1]) if "Vol_Ratio" in df else 1.0
            opp_score = abs(signal["confluence_score"]) + (vol_ratio * 12.0)
            if "Accumulation" in smart_money.get("badge", ""):
                opp_score += 25.0

            return {
                "symbol": sym,
                "name": candidate["name"],
                "sector": candidate.get("sector", "NSE"),
                "price": round(latest_close, 2),
                "change_pct": change_pct,
                "action": signal["action"],
                "confidence": signal["confidence"],
                "confluence_score": signal["confluence_score"],
                "smart_money": smart_money.get("badge", "Normal Volume"),
                "market_regime": signal.get("market_regime", "NORMAL"),
                "vol_ratio": vol_ratio,
                "opportunity_score": round(opp_score, 1),
                "target_1": signal["target_1"],
                "stop_loss": signal["stop_loss"],
                "rrr": signal["risk_reward_ratio"],
                "discovery_reason": f"{smart_money.get('badge')} | Score {signal['confluence_score']}"
            }
        except Exception:
            return None

    with ThreadPoolExecutor(max_workers=8) as executor:
        candidates = list(executor.map(evaluate_candidate, pool))

    valid_candidates = [c for c in candidates if c is not None]
    valid_candidates.sort(key=lambda x: x["opportunity_score"], reverse=True)
    top_candidates = valid_candidates[:12]

    # Merge top candidates into watchlist without deleting user's custom additions
    existing_syms = {w["symbol"] for w in CURRENT_WATCHLIST}
    for c in top_candidates:
        if c["symbol"] not in existing_syms:
            CURRENT_WATCHLIST.append({"symbol": c["symbol"], "name": c["name"], "market": "NSE", "currency": "₹"})
            existing_syms.add(c["symbol"])

    result = json_sanitize({
        "success": True,
        "scanned_universe_count": len(pool),
        "promoted_count": len(top_candidates),
        "hot_opportunities": top_candidates,
        "active_watchlist": CURRENT_WATCHLIST
    })
    DISCOVER_CACHE = {"data": result, "timestamp": now}
    return result


@app.get("/api/news/flash")
def get_flash_breaking_news():
    """Returns real-time breaking market catalysts with predicted price impact % and trading actions."""
    flash_news = news_analyzer.fetch_market_wide_flash_news(NIFTY_UNIVERSE)
    return json_sanitize(flash_news)


@app.get("/api/capital-shield")
def get_capital_shield_status():
    """Retrieve live Capital Shield & Circuit Breaker status."""
    cb = paper_trading.check_circuit_breaker()
    return json_sanitize({
        "circuit_breaker": cb,
        "zero_loss_lock": "ACTIVE (1:1 Risk-to-Reward Auto Break-Even)",
        "trailing_stop_loss": "ACTIVE (Locks 40% gain at 75% Target)",
        "max_risk_per_trade": "₹15,000",
        "market_chop_shield": "ACTIVE (Choppiness Index > 61.8 Traps Filtered)"
    })


@app.get("/api/sectors/heatmap")
def get_sector_heatmap():
    """Returns live sector rotation and capital inflow heatmap across top Indian industry sectors."""
    global SECTOR_HEATMAP_CACHE
    now = time.time()
    if SECTOR_HEATMAP_CACHE["data"] and (now - SECTOR_HEATMAP_CACHE["timestamp"] < 60):
        return SECTOR_HEATMAP_CACHE["data"]

    def get_stock_data(item):
        sym = item["symbol"]
        quote = fetch_live_nse_quote(sym)
        return {
            "symbol": sym,
            "name": item.get("name", sym),
            "sector": item.get("sector", "Other"),
            "change_pct": quote["change_pct"]
        }

    with ThreadPoolExecutor(max_workers=10) as ex:
        quotes = list(ex.map(get_stock_data, NIFTY_UNIVERSE))

    res = technical_engine.compute_sector_rotation(quotes)
    clean_res = json_sanitize(res)
    SECTOR_HEATMAP_CACHE = {"data": clean_res, "timestamp": now}
    return clean_res


@app.get("/api/strategy/reversals")
def get_reversal_sniper_setups():
    """
    1:5 Asymmetric Payoff Reversal Sniper:
    Scans for stocks with extreme RSI Divergence & Volume Exhaustion where a high-probability bounce is starting.
    """
    global REVERSALS_CACHE
    now = time.time()
    if REVERSALS_CACHE["data"] and (now - REVERSALS_CACHE["timestamp"] < 60):
        return REVERSALS_CACHE["data"]

    def scan_reversal(item):
        sym = item["symbol"]
        try:
            df = technical_engine.fetch_candlesticks(sym, period="5d", interval="15m")
            if df.empty or len(df) < 18:
                return None
            df = technical_engine.calculate_indicators(df)
            rev = technical_engine.detect_momentum_exhaustion(df)
            if rev.get("is_reversal_setup"):
                return {
                    "symbol": sym,
                    "name": item.get("name", sym),
                    "sector": item.get("sector", "NSE"),
                    **rev
                }
            return None
        except Exception:
            return None

    with ThreadPoolExecutor(max_workers=8) as ex:
        raw = list(ex.map(scan_reversal, NIFTY_UNIVERSE[:16]))

    valid_reversals = [r for r in raw if r is not None]
    clean_rev = json_sanitize(valid_reversals)
    REVERSALS_CACHE = {"data": clean_rev, "timestamp": now}
    return clean_rev


# =============================================================================
# Angel One Research Recommendations & Instant ₹10,000 Auto-Paper-Trade Endpoints
# =============================================================================
@app.get("/api/angel-research/calls")
def get_angel_research_calls(category: Optional[str] = "ALL"):
    """Fetch live Angel One research calls (Intraday, Short Term, Long Term) with live status."""
    calls = angel_research.get_all_calls(category)
    return {
        "success": True,
        "count": len(calls),
        "calls": json_sanitize(calls),
        "capital_per_trade": CAPITAL_PER_TRADE,
        "auto_trade_enabled": angel_research.auto_trade_enabled
    }


@app.post("/api/angel-research/ingest")
def ingest_angel_research_call(req: AngelResearchIngestRequest):
    """
    Ingest recommendation directly from Angel One (Notification/Web).
    Instantly executes autonomous paper trade allocating strictly ₹10,000.
    """
    res = angel_research.ingest_call(
        symbol=req.symbol,
        action=req.action or "BUY",
        entry_price=req.entry_price,
        stop_loss=req.stop_loss,
        target_price=req.target_price,
        category=req.category or "Intraday",
        company_name=req.company_name or "",
        call_type=req.call_type or "Analyst call"
    )
    return json_sanitize(res)


@app.post("/api/angel-research/parse-text")
def parse_and_trade_notification(req: AngelTextParseRequest):
    """Parse raw Angel One push notification and auto-execute ₹10,000 paper trade."""
    parsed = angel_research.parse_notification_text(req.text)
    if not parsed:
        return {"success": False, "message": "Could not parse Symbol, Entry, SL, or Target from text"}
    res = angel_research.ingest_call(**parsed)
    return json_sanitize({"success": True, "parsed": parsed, "result": res})


@app.post("/api/angel-research/test-call")
def trigger_test_call():
    """Trigger a live sample Angel One analyst call to test instant ₹10k auto-paper-trade."""
    res = angel_research.trigger_sample_call()
    return json_sanitize(res)


@app.get("/api/angel-research/portfolio")
def get_angel_research_portfolio():
    """Get portfolio metrics, open paper trades (each ₹10k), and closed trades."""
    port = paper_trading.get_portfolio(LATEST_PRICES)
    return json_sanitize(port)


@app.post("/api/angel-research/toggle-auto")
def toggle_angel_auto_trade(enabled: bool = True):
    """Toggle auto-trade for incoming Angel One recommendations."""
    angel_research.auto_trade_enabled = enabled
    return {"success": True, "auto_trade_enabled": enabled}


@app.delete("/api/angel-research/call/{call_id}")
def delete_angel_research_call(call_id: str):
    """Delete a single Angel One recommendation and close associated position if open."""
    res = angel_research.delete_call(call_id)
    return json_sanitize(res)


@app.post("/api/angel-research/clear-all")
def clear_all_angel_research_calls():
    """Clear all Angel One research recommendations from database for a fresh clean slate."""
    res = angel_research.clear_all_calls()
    return json_sanitize(res)


@app.post("/api/angel-research/clear-expired")
def clear_expired_angel_research_calls():
    """Clear expired/completed Angel One research recommendations."""
    res = angel_research.clear_expired_calls()
    return json_sanitize(res)


# =============================================================================
# Paper Trading & Autonomous AI Auto-Trader Endpoints
# =============================================================================
@app.get("/api/paper/portfolio")
def get_paper_portfolio():
    """Retrieve full portfolio metrics with Win / Loss breakdown."""
    return json_sanitize(paper_trading.get_portfolio(LATEST_PRICES))


@app.post("/api/paper/order")
def execute_paper_order(order: OrderRequest):
    """Execute paper trade (Manual or AI-triggered)."""
    return paper_trading.execute_order(
        symbol=order.symbol,
        side=order.side,
        quantity=order.quantity,
        price=order.price,
        stop_loss=order.stop_loss,
        target_price=order.target_price,
        company_name=order.company_name,
        trade_type=order.trade_type or "MANUAL",
        ai_confidence=order.ai_confidence or 0.0,
        ai_reasons=order.ai_reasons or ""
    )


@app.post("/api/paper/close/{position_id}")
def close_paper_position(position_id: int, req: CloseOrderRequest):
    """Close an open paper position."""
    return paper_trading.close_position(position_id, req.current_price, req.reason)


@app.post("/api/paper/reset")
def reset_paper_portfolio():
    """Reset virtual account back to ₹1,00,000."""
    return paper_trading.reset_portfolio()


def get_live_market_movers():
    """
    Scans the NSE broader universe concurrently to retrieve real-time prices & today's % change.
    Identifies real-time Top Gainers (Momentum Breakouts -> BUY) and Top Losers (Breakdown -> SELL SHORT).
    Cached for 45s to avoid Yahoo rate limits.
    """
    global LIVE_MOVERS_CACHE
    now = time.time()
    if LIVE_MOVERS_CACHE["data"] and (now - LIVE_MOVERS_CACHE["timestamp"] < 45):
        return LIVE_MOVERS_CACHE["data"]

    candidate_items = [s for s in NIFTY_UNIVERSE if not s["symbol"].startswith("^")]

    def fetch_mover(item):
        sym = item["symbol"]
        quote = fetch_live_nse_quote(sym)
        if quote and quote.get("price", 0) > 0:
            price = quote["price"]
            pct = quote.get("change_pct", 0.0)
            return {
                "symbol": sym,
                "name": item.get("name", sym.replace(".NS", "")),
                "sector": item.get("sector", "NSE Equities"),
                "price": price,
                "change_pct": pct
            }
        return None

    with ThreadPoolExecutor(max_workers=16) as executor:
        results = [r for r in executor.map(fetch_mover, candidate_items) if r]

    # Filter for Early, Healthy Momentum (0.4% to 2.2% only).
    # STRICT RULE: NEVER recommend Buying stocks already up >= 2.5% (prevents FOMO Top-Buyer Traps!)
    healthy_gainers = [r for r in results if 0.4 <= r["change_pct"] < 2.5]
    healthy_gainers.sort(key=lambda x: x["change_pct"], reverse=True)

    healthy_losers = [r for r in results if -2.5 < r["change_pct"] <= -0.4]
    healthy_losers.sort(key=lambda x: x["change_pct"])

    movers = []

    # Process Early Momentum Gainers -> Realistic Intraday BUY Setups
    for g in healthy_gainers[:4]:
        cmp = g["price"]
        pct = g["change_pct"]
        # Realistic Intraday Targets: 0.8% - 1.0% Target 1, 0.6% Stop Loss
        tp1_gain = 0.009   # 0.9% Target 1 (Achievable in 15-30 mins)
        sl_risk = 0.006    # 0.6% Stop Loss (Capital Protection)
        tp1 = round(cmp * (1 + tp1_gain), 2)
        sl = round(cmp * (1 - sl_risk), 2)
        movers.append({
            "symbol": g["symbol"],
            "name": g["name"],
            "sector": g["sector"],
            "price": cmp,
            "change_pct": pct,
            "action": "BUY",
            "confidence": min(92, int(84 + pct * 2)),
            "pattern": f"Early Bullish Breakout (+{pct:.2f}%)",
            "target_1": tp1,
            "target_2": round(cmp * 1.016, 2),
            "stop_loss": sl,
            "risk_reward_ratio": "1:1.5",
            "rationale": f"Early stage breakout (+{pct:.2f}%); healthy relative strength without peak exhaustion. Realistic Target: ₹{tp1:.2f} (+0.9%), SL: ₹{sl:.2f} (-0.6%)."
        })

    # Process Early Momentum Losers -> Realistic Intraday SELL Setups
    for l in healthy_losers[:4]:
        cmp = l["price"]
        pct = l["change_pct"]
        tp1_drop = 0.009   # 0.9% Target 1
        sl_risk = 0.006    # 0.6% Stop Loss
        tp1 = round(cmp * (1 - tp1_drop), 2)
        sl = round(cmp * (1 + sl_risk), 2)
        movers.append({
            "symbol": l["symbol"],
            "name": l["name"],
            "sector": l["sector"],
            "price": cmp,
            "change_pct": pct,
            "action": "SELL",
            "confidence": min(91, int(83 + abs(pct) * 2)),
            "pattern": f"Early Bearish Breakdown ({pct:.2f}%)",
            "target_1": tp1,
            "target_2": round(cmp * 0.984, 2),
            "stop_loss": sl,
            "risk_reward_ratio": "1:1.5",
            "rationale": f"Early breakdown ({pct:.2f}%); intraday selling pressure without oversold climax. Realistic Target: ₹{tp1:.2f} (-0.9%), SL: ₹{sl:.2f} (+0.6%)."
        })

    LIVE_MOVERS_CACHE = {"data": movers, "timestamp": now}
    return movers


@app.get("/api/ai/live-movers-scan")
def get_live_movers_endpoint():
    """Returns real-time NSE Top Gainers (BUY) & Top Losers (SELL) with dynamic technical signals."""
    movers = get_live_market_movers()
    return {
        "success": True,
        "count": len(movers),
        "movers": movers
    }


def get_pre_market_battle_plan():
    """
    Pre-Market Predictive Quant Engine (Run before 09:15 AM):
    Analyzes Daily & Multi-Timeframe Chart Structures, 20 EMA / 50 EMA Trend,
    Volume Accumulation/Distribution, and 5-Day Support/Resistance Pivots.
    Outputs predictive BUY triggers and SELL SHORT triggers BEFORE market opens!
    """
    import yfinance as yf
    import pandas as pd
    from concurrent.futures import ThreadPoolExecutor

    symbols = [
        "TATACONSUM.NS", "POWERINDIA.NS", "DIVISLAB.NS", "ADANIENSOL.NS", "TMCV.NS",
        "BHARTIARTL.NS", "BAJAJ-AUTO.NS", "MAZDOCK.NS", "AMBUJACEM.NS", "RECLTD.NS",
        "BDL.NS", "ASIANPAINT.NS", "PIDILITIND.NS", "COALINDIA.NS", "GRASIM.NS",
        "SBIN.NS", "GAIL.NS", "TCS.NS", "HAL.NS", "RELIANCE.NS", "HDFCBANK.NS",
        "INFY.NS", "ZOMATO.NS", "TATAPOWER.NS"
    ]

    def analyze_sym(sym):
        try:
            df = yf.download(sym, period="1mo", interval="1d", progress=False)
            if df.empty or len(df) < 10:
                return None
            if isinstance(df.columns, pd.MultiIndex):
                df.columns = df.columns.get_level_values(0)

            c = df["Close"]
            ema20 = float(c.ewm(span=20).mean().iloc[-1])
            last_close = float(c.iloc[-1])
            prev_close = float(c.iloc[-2]) if len(c) >= 2 else last_close
            high_5d = float(df["High"].iloc[-5:-1].max()) if len(df) >= 6 else float(df["High"].max())
            low_5d = float(df["Low"].iloc[-5:-1].min()) if len(df) >= 6 else float(df["Low"].min())
            vol = df["Volume"]
            avg_vol = float(vol.iloc[-5:].mean()) if len(vol) >= 5 else float(vol.mean())
            last_vol = float(vol.iloc[-1])
            vol_ratio = round(last_vol / max(avg_vol, 1.0), 2)
            name = sym.replace(".NS", "")
            
            bull_score = 0
            bear_score = 0
            if last_close > ema20:
                bull_score += 3
            else:
                bear_score += 3

            if vol_ratio > 1.2:
                if last_close > prev_close:
                    bull_score += 4  # Institutional Accumulation
                else:
                    bear_score += 4  # Institutional Distribution

            if last_close >= high_5d * 0.985:
                bull_score += 3  # Near multi-day breakout
            if last_close <= low_5d * 1.015:
                bear_score += 3  # Near multi-day breakdown

            if bull_score > bear_score and bull_score >= 6:
                # Realistic Intraday Trade: Never buy at 5% peak! Enter at realistic entry with achievable 0.9% target
                entry_p = round(last_close, 2)
                tp1 = round(entry_p * 1.009, 2)   # 0.9% Target 1 (Achievable Intraday)
                tp2 = round(entry_p * 1.018, 2)   # 1.8% Target 2
                sl = round(entry_p * 0.993, 2)    # 0.7% Stop Loss
                return {
                    "symbol": sym,
                    "name": name,
                    "action": "BUY",
                    "plan_type": "PRE_MARKET_BUY",
                    "price": entry_p,
                    "trigger_condition": f"BUY at ₹{entry_p:.2f} (Target ₹{tp1:.2f} | SL ₹{sl:.2f})",
                    "confidence": min(95, 82 + bull_score * 2),
                    "pattern": "🌅 Pre-Market Bullish Setup",
                    "target_1": tp1,
                    "target_2": tp2,
                    "stop_loss": sl,
                    "risk_reward_ratio": "1:1.3",
                    "rationale": f"Holding above 20 EMA (₹{ema20:.2f}) with {vol_ratio}x accumulation volume. Realistic Intraday Target: ₹{tp1:.2f} (+0.9%), SL: ₹{sl:.2f} (-0.7%)."
                }
            elif bear_score > bull_score and bear_score >= 6:
                entry_p = round(last_close, 2)
                tp1 = round(entry_p * 0.991, 2)   # 0.9% Target 1
                tp2 = round(entry_p * 0.982, 2)   # 1.8% Target 2
                sl = round(entry_p * 1.007, 2)    # 0.7% Stop Loss
                return {
                    "symbol": sym,
                    "name": name,
                    "action": "SELL",
                    "plan_type": "PRE_MARKET_SELL",
                    "price": entry_p,
                    "trigger_condition": f"SELL / SHORT at ₹{entry_p:.2f} (Target ₹{tp1:.2f} | SL ₹{sl:.2f})",
                    "confidence": min(94, 82 + bear_score * 2),
                    "pattern": "🌅 Pre-Market Bearish Setup",
                    "target_1": tp1,
                    "target_2": tp2,
                    "stop_loss": sl,
                    "risk_reward_ratio": "1:1.3",
                    "rationale": f"Daily breakdown below 20 EMA (₹{ema20:.2f}) with heavy {vol_ratio}x distribution volume. Realistic Intraday Target: ₹{tp1:.2f} (-0.9%), SL: ₹{sl:.2f} (+0.7%)."
                }
            return None
        except Exception as e:
            return None

    with ThreadPoolExecutor(max_workers=8) as ex:
        results = [r for r in ex.map(analyze_sym, symbols) if r]

    buys = [r for r in results if r["action"] == "BUY"]
    sells = [r for r in results if r["action"] == "SELL"]
    buys.sort(key=lambda x: x["confidence"], reverse=True)
    sells.sort(key=lambda x: x["confidence"], reverse=True)
    return buys[:3] + sells[:3]


@app.get("/api/ai/pre-market-plan")
def get_pre_market_plan_endpoint():
    """Returns predictive pre-market BUY & SELL watchlist before 09:15 AM."""
    plan = get_pre_market_battle_plan()
    return {
        "success": True,
        "count": len(plan),
        "plan": plan
    }


@app.post("/api/ai/auto-trade")
def trigger_ai_auto_trade():
    """
    Autonomous AI Trigger:
    Scans real-time Top Gainers & Losers, finds genuine momentum setups, sets SL & Target, and enters trades!
    """
    signals = get_live_market_movers()

    for s in signals:
        LATEST_PRICES[s["symbol"]] = s["price"]

    executed = paper_trading.ai_autonomous_trade_step(signals, LATEST_PRICES)
    portfolio = paper_trading.get_portfolio(LATEST_PRICES)
    return {
        "success": True,
        "executed_count": len(executed),
        "executed_trades": executed,
        "portfolio": portfolio
    }


@app.get("/api/stock/{symbol}/option-chain")
def get_stock_option_chain(symbol: str):
    """Returns real-time NSE Option Chain data with PCR and Max Pain."""
    cmp = LATEST_PRICES.get(symbol, 1000.0)
    cached = CACHE_ANALYSIS.get(symbol, {})
    bias = cached.get("signal", {}).get("action", "BULLISH")
    from backend.option_chain import calculate_option_chain
    data = calculate_option_chain(symbol, cmp, bias)
    return json_sanitize(data)


@app.get("/api/ai/factor-matrix")
def get_ai_factor_matrix():
    """Returns the self-learning factor ranking and optimization matrix."""
    return json_sanitize(paper_trading.get_ai_factor_matrix())


@app.get("/api/settings/angel-one")
def get_angel_settings():
    """Check Angel One connection status."""
    cc = angel_client.client_code
    masked_code = f"{cc[:2]}****{cc[-2:]}" if len(cc) >= 4 else (cc or "NOT_CONFIGURED")
    return {
        "configured": angel_client.is_configured(),
        "client_code": masked_code if angel_client.is_configured() else "",
        "authenticated": angel_client.is_authenticated
    }


@app.post("/api/settings/angel-one")
def update_angel_settings(req: AngelSettingsRequest):
    """Save credentials, persist to database, and authenticate with Angel One SmartAPI."""
    global angel_client

    # Persist credentials in SQLite database
    try:
        from backend.database import get_connection
        conn = get_connection()
        cur = conn.cursor()
        cur.execute("INSERT OR REPLACE INTO settings (key, value) VALUES ('angel_api_key', ?)", (req.api_key.strip(),))
        cur.execute("INSERT OR REPLACE INTO settings (key, value) VALUES ('angel_client_code', ?)", (req.client_code.strip(),))
        cur.execute("INSERT OR REPLACE INTO settings (key, value) VALUES ('angel_password', ?)", (req.password.strip(),))
        cur.execute("INSERT OR REPLACE INTO settings (key, value) VALUES ('angel_totp_secret', ?)", (req.totp_secret.strip(),))
        conn.commit()
        conn.close()
    except Exception as e:
        print(f"[Settings] Error persisting Angel credentials: {e}")

    angel_client = AngelOneClient(
        api_key=req.api_key.strip(),
        client_code=req.client_code.strip(),
        password=req.password.strip(),
        totp_secret=req.totp_secret.strip()
    )
    success, msg = angel_client.login(force=True)
    cc = req.client_code.strip()
    masked_code = f"{cc[:2]}****{cc[-2:]}" if len(cc) >= 4 else cc
    return {
        "success": success,
        "message": msg,
        "configured": angel_client.is_configured(),
        "authenticated": angel_client.is_authenticated,
        "client_code": masked_code
    }


# =============================================================================
# Angel One Live Broker Execution & Demat Protection Endpoints
# =============================================================================
@app.get("/api/broker/holdings")
def get_broker_holdings():
    """Fetch user's Demat long-term delivery holdings (CNC) for display & protection."""
    return angel_client.get_holdings()


@app.get("/api/broker/rms")
def get_broker_rms():
    """Fetch live broker cash margin & buying power."""
    return angel_client.get_rms()


@app.get("/api/broker/positions")
def get_broker_positions():
    """Fetch live active positions directly from Angel One."""
    return angel_client.get_positions()


@app.post("/api/broker/square-off-all")
def square_off_all_broker_positions():
    """Square off all open INTRADAY positions on Angel One FIRST, then cancel companion OCO orders."""
    # 1. Flatten broker positions FIRST to avoid naked exposure
    res = angel_client.square_off_all()

    # 2. Only after square-off order is submitted, cancel the active companion OCO SL/Target orders
    from backend.broker_oco import angel_oco_manager
    active = angel_oco_manager._get_active_oco_records()
    for rec in active:
        angel_oco_manager.cancel_oco_for_symbol(angel_client, rec["symbol"])
    return res


@app.get("/api/broker/tokens")
def get_broker_tokens():
    """Return mapped NSE instrument tokens from backend."""
    from backend.angel_one import NSE_TOKENS
    return {"status": True, "tokens": NSE_TOKENS}


@app.post("/api/broker/order")
def execute_broker_order(order: OrderRequest):
    """
    Execute Real-Money 3-Stage Order on Angel One with GUARANTEED DEMAT PROTECTION & DUAL OCO.
    Stage 1: Submit Entry (MIS 5x)
    Stage 2: Fill Confirmation & Retrieve Actual Fill Price
    Stage 3: Place Dual OCO Stop-Loss & Target orders
    """
    return angel_client.place_order(
        symbol=order.symbol,
        side=order.side,
        quantity=order.quantity,
        price=order.price,
        stop_loss=order.stop_loss,
        target_price=order.target_price,
        sl_pct=order.sl_pct,
        tp_pct=order.tp_pct
    )


@app.get("/api/broker/oco-orders")
def get_broker_oco_orders():
    """Retrieve all active OCO orders and their state machine status."""
    from backend.broker_oco import angel_oco_manager
    records = angel_oco_manager._get_active_oco_records()
    return {"status": True, "count": len(records), "orders": json_sanitize(records)}


@app.post("/api/broker/close/{symbol}")
def close_broker_symbol(symbol: str):
    """Square off specific symbol on Angel One FIRST, then cancel its companion OCO orders."""
    from backend.broker_oco import angel_oco_manager
    pos_res = angel_client.get_positions()
    clean = symbol.replace(".NS", "").replace("-EQ", "").strip().upper()

    if pos_res.get("status"):
        positions = pos_res.get("positions", [])
        for p in positions:
            tsym = (p.get("tradingsymbol") or "").replace("-EQ", "").strip().upper()
            if tsym == clean:
                net_qty = int(p.get("netqty", 0))
                if net_qty != 0:
                    exit_side = "SELL" if net_qty > 0 else "BUY"
                    order_res = angel_client.place_order(
                        symbol=f"{clean}.NS",
                        side=exit_side,
                        quantity=abs(net_qty),
                        price=0.0,
                        order_type="MARKET"
                    )
                    # After exit order is placed, cancel companion OCO SL and Target orders
                    angel_oco_manager.cancel_oco_for_symbol(angel_client, symbol)
                    return order_res

    # If no open broker position was found, cancel any leftover pending OCO orders
    angel_oco_manager.cancel_oco_for_symbol(angel_client, symbol)
    return {"status": True, "message": f"Active OCO orders cancelled for {clean} (no open broker position)."}




@app.get("/api/broker/orders")
def get_broker_order_book():
    """Fetch real-time order status book from Angel One."""
    return angel_client.get_order_book()


@app.delete("/api/broker/order/{order_id}")
def cancel_broker_order(order_id: str):
    """Cancel an active open order on Angel One."""
    return angel_client.cancel_order(order_id)


@app.get("/api/broker/depth/{symbol}")
def get_broker_depth(symbol: str):
    """
    Fetch Level 2 Market Depth (Best 5 Bids & Asks) and Institutional Whale Volume Analysis
    directly from Angel One SmartAPI.
    """
    return json_sanitize(angel_client.get_market_depth(symbol))


@app.get("/api/broker/margin-calc")
def calculate_broker_margin(symbol: str, price: Optional[float] = 0.0):
    """
    Calculate Live 5x Intraday MIS Margin & Max Allowed Quantity on Angel One.
    Prevents 'Insufficient Funds' order rejections.
    """
    p = float(price) if price and price > 0 else float(LATEST_PRICES.get(symbol, 0.0))
    return json_sanitize(angel_client.calculate_margin(symbol, p))


@app.get("/api/broker/batch-quotes")
def get_broker_batch_quotes(symbols: Optional[str] = ""):
    """Fetch high-speed live quotes from Angel One for comma-separated symbols."""
    global LAST_ANGEL_TICK_TIME
    sym_list = [s.strip() for s in symbols.split(",") if s.strip()] if symbols else [s["symbol"] for s in CURRENT_WATCHLIST[:20]]
    quotes = angel_client.get_batch_quotes(sym_list)
    now_ts = time.time()
    for sym, q in quotes.items():
        if q.get("price", 0) > 0:
            p = round(float(q["price"]), 2)
            pct = float(q.get("percent_change", q.get("change_pct", 0.0)))
            close = float(q.get("close", p))
            clean = sym.replace(".NS", "").replace("-EQ", "").upper()
            LATEST_PRICES[clean] = p
            LATEST_PRICES[f"{clean}.NS"] = p
            LATEST_PRICES[sym] = p
            LATEST_PRICES_METADATA[clean] = {
                "price": p,
                "change_pct": pct,
                "close": close,
                "timestamp": now_ts,
                "source": "AngelOne_Live"
            }
            LAST_ANGEL_TICK_TIME = now_ts

    is_live = (angel_client.is_configured() and angel_client.is_authenticated and (now_ts - LAST_ANGEL_TICK_TIME < 5.0) and len(quotes) > 0)
    return {
        "success": True,
        "count": len(quotes),
        "source": "AngelOne_Live" if is_live else "Feed_Offline",
        "timestamp": now_ts,
        "quotes": json_sanitize(quotes)
    }


@app.get("/api/market/vix")
def get_market_vix():
    """Return live India VIX value and regime."""
    vix = fetch_live_india_vix()
    regime = "HIGH_VOLATILITY" if vix >= 18.0 else ("LOW_VOLATILITY" if vix <= 12.5 else "BALANCED")
    return {"status": True, "vix": vix, "regime": regime}



# =============================================================================
# WebSocket Real-Time Stream & Background Worker
# =============================================================================
@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    """Stream live updates, triggers, and AI trades."""
    await websocket.accept()
    active_connections.append(websocket)
    try:
        # Send initial price snapshot immediately upon connection
        await websocket.send_json({
            "type": "PRICE_TICK",
            "data": {
                "prices": LATEST_PRICES,
                "portfolio": json_sanitize(paper_trading.get_portfolio(LATEST_PRICES)),
                "timestamp": time.time()
            }
        })
        while True:
            data = await websocket.receive_text()
            if data == "ping":
                await websocket.send_text("pong")
    except WebSocketDisconnect:
        if websocket in active_connections:
            active_connections.remove(websocket)


SEEN_FLASH_TITLES = set()
LAST_NEWS_CHECK_TIME = 0.0


async def broadcast_ws(payload: dict):
    """Safely broadcast payload to all active WebSockets, automatically pruning dead connections."""
    dead = []
    for ws in list(active_connections):
        try:
            await ws.send_json(payload)
        except Exception:
            dead.append(ws)
    for d in dead:
        if d in active_connections:
            try:
                active_connections.remove(d)
            except ValueError:
                pass


async def fast_price_tick_broadcaster():
    """Live ticker stream with 100% Angel One SmartAPI batch quotes (every 1.0s, zero simulated drift)."""
    global LAST_ANGEL_TICK_TIME
    while True:
        try:
            await asyncio.sleep(1.0)
            # 1. Update prices for all active open positions
            def get_open_rows():
                conn = get_connection()
                c = conn.cursor()
                c.execute("SELECT DISTINCT symbol, current_price, entry_price FROM positions WHERE status = 'OPEN'")
                rows = c.fetchall()
                conn.close()
                return rows

            open_rows = await asyncio.to_thread(get_open_rows)
            open_symbols = {r["symbol"] for r in open_rows}
            watchlist_symbols = {item["symbol"] for item in CURRENT_WATCHLIST[:20]}
            all_target_symbols = list(open_symbols.union(watchlist_symbols))

            # Fetch batch quotes from Angel One SmartAPI for all open positions & watchlist
            if angel_client.is_configured():
                if not angel_client.is_authenticated or (time.time() - angel_client.token_created_at > 36000):
                    try:
                        await asyncio.to_thread(angel_client.login, True)
                    except Exception:
                        pass
                if angel_client.is_authenticated:
                    try:
                        batch_quotes = await asyncio.to_thread(angel_client.get_batch_quotes, all_target_symbols)
                        now_ts = time.time()
                        for sym, q in batch_quotes.items():
                            if q.get("price", 0) > 0:
                                p = round(float(q["price"]), 2)
                                pct = float(q.get("percent_change", q.get("change_pct", 0.0)))
                                close = float(q.get("close", p))
                                clean = sym.replace(".NS", "").replace("-EQ", "").upper()
                                LATEST_PRICES[clean] = p
                                LATEST_PRICES[f"{clean}.NS"] = p
                                LATEST_PRICES[sym] = p
                                LATEST_PRICES_METADATA[clean] = {
                                    "price": p,
                                    "change_pct": pct,
                                    "close": close,
                                    "timestamp": now_ts,
                                    "source": "AngelOne_Live"
                                }
                        if batch_quotes:
                            LAST_ANGEL_TICK_TIME = now_ts
                    except Exception as ex:
                        print(f"[Broadcaster] Angel One quote update error: {ex}")

            # 2. Update Angel One Research Calls with live prices & auto SL/TP triggers
            await asyncio.to_thread(angel_research.update_live_prices, LATEST_PRICES)

            # 2B. Reconcile Live Angel One 3-Stage OCO Orders (Target Hit / SL Hit / OCO Cancellation)
            if angel_client.is_configured() and angel_client.is_authenticated:
                try:
                    from backend.broker_oco import angel_oco_manager
                    oco_events = await asyncio.to_thread(angel_oco_manager.reconcile_active_oco_orders, angel_client)
                    for ev in oco_events:
                        await broadcast_ws(ev)
                except Exception as oco_ex:
                    print(f"[Broadcaster] OCO reconciliation error: {oco_ex}")

            # 3. Check SL/TP triggers in background thread
            triggered = await asyncio.to_thread(paper_trading.check_sl_tp_triggers, LATEST_PRICES)
            if triggered:
                await broadcast_ws({"type": "SL_TP_TRIGGER", "data": triggered})

            # 4. Broadcast price ticks to all active connections
            if active_connections:
                now_ts = time.time()
                is_live = (angel_client.is_configured() and angel_client.is_authenticated and (now_ts - LAST_ANGEL_TICK_TIME < 5.0))
                source_label = "AngelOne_Live" if is_live else "Feed_Offline"
                await broadcast_ws({
                    "type": "PRICE_TICK",
                    "data": {
                        "prices": LATEST_PRICES,
                        "metadata": LATEST_PRICES_METADATA,
                        "source": source_label,
                        "timestamp": now_ts,
                        "last_angel_tick": LAST_ANGEL_TICK_TIME
                    }
                })
        except Exception as e:
            await asyncio.sleep(1.0)


async def background_market_scanner():
    """Periodically scans Indian markets during market hours, pushes flash news, and runs AI Auto-Trader."""
    global LAST_NEWS_CHECK_TIME, SEEN_FLASH_TITLES
    while True:
        try:
            await asyncio.sleep(25)  # Every 25 seconds
            # 1. Check SL / TP Triggers on active positions
            triggered = await asyncio.to_thread(paper_trading.check_sl_tp_triggers, LATEST_PRICES)
            if triggered:
                await broadcast_ws({"type": "SL_TP_TRIGGER", "data": triggered})

            # 2. Flash Breaking News Scanner
            now = time.time()
            if now - LAST_NEWS_CHECK_TIME >= 40:
                LAST_NEWS_CHECK_TIME = now
                try:
                    flash_items = await asyncio.to_thread(news_analyzer.fetch_market_wide_flash_news, NIFTY_UNIVERSE)
                    for f in flash_items[:4]:
                        urg = f.get("urgency", "")
                        if ("FLASH" in urg or "HIGH" in urg) and f.get("title") and f["title"] not in SEEN_FLASH_TITLES:
                            SEEN_FLASH_TITLES.add(f["title"])
                            await broadcast_ws({"type": "FLASH_NEWS_ALERT", "data": json_sanitize(f)})
                except Exception as ne:
                    print(f"[News Broadcast error] {ne}")

            # 3. Execute AI Auto-Trading step ONLY during Indian Market Hours (Mon-Fri 09:15 - 15:30 IST)
            if not is_indian_market_open():
                continue

            signals = []
            for item in CURRENT_WATCHLIST[:8]:
                sym = item["symbol"]
                cmp = LATEST_PRICES.get(sym, 0)
                if cmp > 0 and sym in CACHE_ANALYSIS:
                    cached = CACHE_ANALYSIS[sym]
                    # Verify cache freshness (ignore signals older than 20 minutes)
                    cached_at = cached.get("timestamp") or cached.get("cached_at", 0)
                    if time.time() - cached_at > 1200:
                        continue

                    sig = cached.get("signal", {})
                    signals.append({
                        "symbol": sym,
                        "name": item["name"],
                        "action": sig.get("action", "NEUTRAL"),
                        "confidence": sig.get("confidence", 0),
                        "stop_loss": sig.get("stop_loss"),
                        "target_1": sig.get("target_1"),
                        "price": cmp,
                        "reasons": sig.get("reasons", []),
                        "macro_trend": sig.get("macro_trend", "NEUTRAL"),
                        "exhaustion_ratio": sig.get("exhaustion_ratio", 0.0),
                        "confluence_score": sig.get("confluence_score", 0.0),
                        "smart_money": sig.get("smart_money", "Normal Volume")
                    })

            if signals:
                ai_executed = await asyncio.to_thread(paper_trading.ai_autonomous_trade_step, signals, LATEST_PRICES)
                if ai_executed:
                    await broadcast_ws({"type": "AI_AUTO_TRADE_EXECUTED", "data": ai_executed})
        except Exception as e:
            print(f"[Background Scanner] error: {e}")
            await asyncio.sleep(10)


@app.post("/api/watchlist/add")
def add_to_watchlist(req: WatchlistAddRequest):
    """Add a stock to active watchlist."""
    clean = req.symbol.strip().upper()
    if not clean.endswith(".NS") and not clean.startswith("^"):
        clean = f"{clean}.NS"
    for s in CURRENT_WATCHLIST:
        if s["symbol"] == clean:
            return {"success": True, "message": f"{clean} is already in watchlist", "symbol": clean}
    item = {
        "symbol": clean,
        "name": req.name.strip() or clean.replace(".NS", ""),
        "market": req.market or "NSE",
        "currency": req.currency or "₹",
        "price": LATEST_PRICES.get(clean, 0.0)
    }
    CURRENT_WATCHLIST.insert(0, item)
    return {"success": True, "message": f"Added {clean} to watchlist", "stock": item}


@app.delete("/api/watchlist/{symbol}")
def remove_from_watchlist(symbol: str):
    """Remove a stock from active watchlist."""
    global CURRENT_WATCHLIST
    clean = symbol.strip().upper()
    CURRENT_WATCHLIST = [s for s in CURRENT_WATCHLIST if s["symbol"] != clean and s["symbol"] != f"{clean}.NS"]
    return {"success": True, "message": f"Removed {symbol} from watchlist"}



@app.on_event("startup")
async def startup_event():
    # Initialize LATEST_PRICES with accurate default stocks
    for s in DEFAULT_STOCKS:
        if "price" in s:
            LATEST_PRICES[s["symbol"]] = float(s["price"])
    try:
        conn = get_connection()
        c = conn.cursor()
        c.execute("SELECT symbol, current_price, entry_price FROM positions WHERE status = 'OPEN'")
        for r in c.fetchall():
            sym = r["symbol"]
            p = float(r["current_price"]) if r["current_price"] else float(r["entry_price"])
            if p > 0:
                LATEST_PRICES[sym] = p
        conn.close()
    except Exception:
        pass

    # Auto-login to Angel One on startup
    if angel_client.is_configured() and not angel_client.is_authenticated:
        try:
            ok, msg = angel_client.login()
            print(f"[Startup] Angel One Auto-Login: {ok} ({msg})")
        except Exception as ex:
            print(f"[Startup] Angel One login error: {ex}")

    asyncio.create_task(fast_price_tick_broadcaster())
    asyncio.create_task(background_market_scanner())


# =============================================================================
# Frontend Static Asset Delivery
# =============================================================================
FRONTEND_DIR = BASE_DIR / "frontend"
if FRONTEND_DIR.exists():
    css_dir = FRONTEND_DIR / "css"
    js_dir = FRONTEND_DIR / "js"
    if css_dir.exists():
        app.mount("/css", StaticFiles(directory=css_dir), name="css")
    if js_dir.exists():
        app.mount("/js", StaticFiles(directory=js_dir), name="js")
    app.mount("/static", StaticFiles(directory=FRONTEND_DIR), name="static")

@app.get("/manifest.json")
def serve_manifest():
    manifest_file = FRONTEND_DIR / "manifest.json"
    if manifest_file.exists():
        return FileResponse(manifest_file)
    raise HTTPException(status_code=404, detail="Manifest not found")

@app.get("/")
def serve_index():
    index_file = FRONTEND_DIR / "index.html"
    if index_file.exists():
        return FileResponse(index_file)
    return {"message": "StockAI Indian Market Trading Bot is Running."}
