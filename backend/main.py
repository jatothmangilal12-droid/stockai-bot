"""
FastAPI Main Application Server - 100% Indian Market Focus (NSE / BSE)
Includes Autonomous AI Auto-Trader, Real-Time NSE Candlesticks, and Win/Loss Analytics.
"""
import asyncio
import os
import sys
import warnings
import json
import urllib.request
from pathlib import Path
from typing import Optional

# Suppress 3rd party deprecation warnings
warnings.filterwarnings("ignore")

from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from pydantic import BaseModel
import yfinance as yf

from backend.config import DEFAULT_STOCKS, BASE_DIR
from backend.news_sentiment import NewsSentimentAnalyzer
from backend.technical_engine import TechnicalEngine
from backend.signal_evaluator import SignalEvaluator
from backend.paper_trading import PaperTradingEngine
from backend.angel_one import AngelOneClient
from backend.database import get_connection

app = FastAPI(title="StockAI - Indian Market 15m Pattern & Sentiment Bot", version="2.0.0")

# Enable CORS for mobile app and web access
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Core Quantitative Engines
news_analyzer = NewsSentimentAnalyzer()
technical_engine = TechnicalEngine()
signal_evaluator = SignalEvaluator()
paper_trading = PaperTradingEngine()
angel_client = AngelOneClient()

# Active Watchlist - 100% Indian NSE Stocks
CURRENT_WATCHLIST = list(DEFAULT_STOCKS)
CACHE_ANALYSIS = {}

LATEST_PRICES = {}

# Active WebSocket Connections
active_connections: list[WebSocket] = []


class OrderRequest(BaseModel):
    symbol: str
    side: str  # 'BUY' or 'SELL'
    quantity: int
    price: float
    stop_loss: Optional[float] = None
    target_price: Optional[float] = None
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


def fetch_live_nse_quote(symbol: str) -> dict:
    """Fetch high-speed real-time NSE quote from Angel One or direct Yahoo chart."""
    # 1. Check Angel One SmartAPI first if configured
    if angel_client.is_configured():
        quote = angel_client.get_live_quote(symbol)
        if quote and quote.get("price", 0) > 0:
            return {
                "price": round(float(quote["price"]), 2),
                "change_pct": 0.0,
                "currency": "₹",
                "source": "AngelOne"
            }

    # 2. Direct high-speed Yahoo chart quote
    url = f"https://query1.finance.yahoo.com/v8/finance/chart/{symbol}?interval=15m&range=2d"
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"})
    try:
        with urllib.request.urlopen(req, timeout=4) as resp:
            data = json.loads(resp.read().decode())
            meta = data["chart"]["result"][0]["meta"]
            cmp = meta.get("regularMarketPrice") or meta.get("chartPreviousClose") or 0.0
            prev_close = meta.get("chartPreviousClose") or meta.get("previousClose") or cmp
            change_pct = round(((cmp - prev_close) / prev_close) * 100, 2) if prev_close else 0.0
            return {
                "price": round(cmp, 2),
                "change_pct": change_pct,
                "currency": "₹",
                "source": "NSE_Direct"
            }
    except Exception as e:
        return {"price": 0.0, "change_pct": 0.0, "currency": "₹", "source": "None"}



@app.get("/api/stocks")
def get_stocks():
    """Returns watchlist with 100% live real-time NSE prices."""
    results = []
    for item in CURRENT_WATCHLIST:
        sym = item["symbol"]
        quote = fetch_live_nse_quote(sym)
        price = quote["price"]
        change_pct = quote["change_pct"]

        if price > 0:
            LATEST_PRICES[sym] = price
        else:
            price = LATEST_PRICES.get(sym, 0.0)

        results.append({
            "symbol": sym,
            "name": item.get("name", sym),
            "market": "NSE",
            "currency": "₹",
            "price": price,
            "change_pct": change_pct
        })
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

    # 4. Confluence Signal Generation
    signal = signal_evaluator.evaluate(symbol, latest_close, df, patterns, sentiment_data)

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
        "signal": signal
    }
    CACHE_ANALYSIS[symbol] = result
    return result


def pd_isna(val):
    """Check for NaN safely."""
    try:
        import math
        return val is None or math.isnan(float(val))
    except (ValueError, TypeError):
        return True



@app.get("/api/screener")
def get_market_screener():
    """Scan all top Indian NSE stocks for real-time 15m confluence signals."""
    screener_results = []
    for item in CURRENT_WATCHLIST:
        sym = item["symbol"]
        try:
            df = technical_engine.fetch_candlesticks(sym, period="3d", interval="15m")
            if df.empty or len(df) < 5:
                continue
            df = technical_engine.calculate_indicators(df)
            patterns = technical_engine.detect_candlestick_patterns(df)
            latest_close = float(df["Close"].iloc[-1])
            LATEST_PRICES[sym] = round(latest_close, 2)

            news_items = news_analyzer.fetch_news(sym, item["name"], limit=5)
            total_score = sum(news_analyzer.score_headline(n["title"])["score"] for n in news_items)
            net_sent = round(total_score / len(news_items), 2) if news_items else 0.0

            sentiment_data = {"net_sentiment": net_sent}
            signal = signal_evaluator.evaluate(sym, latest_close, df, patterns, sentiment_data)

            screener_results.append({
                "symbol": sym,
                "name": item["name"],
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
                "reasons": signal.get("reasons", [])
            })
        except Exception as e:
            print(f"[Screener] Error for {sym}: {e}")

    screener_results.sort(key=lambda x: abs(x["confluence_score"]), reverse=True)
    return screener_results


# =============================================================================
# Paper Trading & Autonomous AI Auto-Trader Endpoints
# =============================================================================
@app.get("/api/paper/portfolio")
def get_paper_portfolio():
    """Retrieve full portfolio metrics with Win / Loss breakdown."""
    return paper_trading.get_portfolio(LATEST_PRICES)


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


@app.post("/api/ai/auto-trade")
def trigger_ai_auto_trade():
    """
    Autonomous AI Trigger:
    Scans the market, finds high-confidence setups, sets SL & Target, and enters trades!
    """
    signals = get_market_screener()
    executed = paper_trading.ai_autonomous_trade_step(signals, LATEST_PRICES)
    portfolio = paper_trading.get_portfolio(LATEST_PRICES)
    return {
        "success": True,
        "executed_count": len(executed),
        "executed_trades": executed,
        "portfolio": portfolio
    }


@app.get("/api/settings/angel-one")
def get_angel_settings():
    """Check Angel One connection status."""
    return {
        "configured": angel_client.is_configured(),
        "client_code": angel_client.client_code,
        "authenticated": angel_client.is_authenticated
    }


@app.post("/api/settings/angel-one")
def update_angel_settings(req: AngelSettingsRequest):
    """Save credentials and authenticate with Angel One SmartAPI."""
    global angel_client
    angel_client = AngelOneClient(
        api_key=req.api_key.strip(),
        client_code=req.client_code.strip(),
        password=req.password.strip(),
        totp_secret=req.totp_secret.strip()
    )
    success = angel_client.login()
    return {
        "success": success,
        "message": "Connected to Angel One SmartAPI successfully!" if success else "Authentication failed. Check API key, PIN, and TOTP secret.",
        "configured": angel_client.is_configured(),
        "authenticated": angel_client.is_authenticated
    }


# =============================================================================
# WebSocket Real-Time Stream & Background Worker
# =============================================================================
@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    """Stream live updates, triggers, and AI trades."""
    await websocket.accept()
    active_connections.append(websocket)
    try:
        while True:
            data = await websocket.receive_text()
            if data == "ping":
                await websocket.send_text("pong")
    except WebSocketDisconnect:
        if websocket in active_connections:
            active_connections.remove(websocket)


async def background_market_scanner():
    """Periodically scans Indian markets, checks SL/TP auto-triggers, and runs AI Auto-Trader."""
    while True:
        try:
            await asyncio.sleep(30)  # Every 30 seconds
            # 1. Check SL / TP Triggers on active positions
            triggered = paper_trading.check_sl_tp_triggers(LATEST_PRICES)
            if triggered:
                for ws in active_connections:
                    try:
                        await ws.send_json({"type": "SL_TP_TRIGGER", "data": triggered})
                    except Exception:
                        pass

            # 2. Execute AI Auto-Trading step
            signals = []
            for item in CURRENT_WATCHLIST[:8]:
                sym = item["symbol"]
                cmp = LATEST_PRICES.get(sym, 0)
                if cmp > 0 and sym in CACHE_ANALYSIS:
                    cached = CACHE_ANALYSIS[sym]
                    signals.append({
                        "symbol": sym,
                        "name": item["name"],
                        "action": cached["signal"]["action"],
                        "confidence": cached["signal"]["confidence"],
                        "stop_loss": cached["signal"]["stop_loss"],
                        "target_1": cached["signal"]["target_1"],
                        "price": cmp,
                        "reasons": cached["signal"].get("reasons", [])
                    })

            if signals:
                ai_executed = paper_trading.ai_autonomous_trade_step(signals, LATEST_PRICES)
                if ai_executed:
                    for ws in active_connections:
                        try:
                            await ws.send_json({"type": "AI_AUTO_TRADE_EXECUTED", "data": ai_executed})
                        except Exception:
                            pass
        except Exception as e:
            print(f"[Background Scanner] error: {e}")
            await asyncio.sleep(10)


@app.on_event("startup")
async def startup_event():
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
