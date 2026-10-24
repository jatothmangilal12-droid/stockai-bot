"""
Application Configuration - 100% Indian Market Focus (NSE / BSE)
"""
import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
DB_PATH = BASE_DIR / "stock_ai.db"

# Top Indian Stocks Watchlist (NSE) - Exclusively Indian Market
DEFAULT_STOCKS = [
    {"symbol": "^NSEI", "name": "NIFTY 50 Index", "market": "NSE", "currency": "₹"},
    {"symbol": "^NSEBANK", "name": "BANK NIFTY Index", "market": "NSE", "currency": "₹"},
    {"symbol": "RELIANCE.NS", "name": "Reliance Industries", "market": "NSE", "currency": "₹"},
    {"symbol": "HDFCBANK.NS", "name": "HDFC Bank", "market": "NSE", "currency": "₹"},
    {"symbol": "TCS.NS", "name": "Tata Consultancy Services", "market": "NSE", "currency": "₹"},
    {"symbol": "ICICIBANK.NS", "name": "ICICI Bank", "market": "NSE", "currency": "₹"},
    {"symbol": "INFY.NS", "name": "Infosys", "market": "NSE", "currency": "₹"},
    {"symbol": "TMCV.NS", "name": "Tata Motors CV", "market": "NSE", "currency": "₹"},
    {"symbol": "TMPV.NS", "name": "Tata Motors PV", "market": "NSE", "currency": "₹"},
    {"symbol": "SBIN.NS", "name": "State Bank of India", "market": "NSE", "currency": "₹"},
    {"symbol": "BHARTIARTL.NS", "name": "Bharti Airtel", "market": "NSE", "currency": "₹"},
    {"symbol": "ITC.NS", "name": "ITC Limited", "market": "NSE", "currency": "₹"},
    {"symbol": "LT.NS", "name": "Larsen & Toubro", "market": "NSE", "currency": "₹"},
    {"symbol": "BAJFINANCE.NS", "name": "Bajaj Finance", "market": "NSE", "currency": "₹"},
    {"symbol": "KOTAKBANK.NS", "name": "Kotak Mahindra Bank", "market": "NSE", "currency": "₹"},
    {"symbol": "MARUTI.NS", "name": "Maruti Suzuki", "market": "NSE", "currency": "₹"},
    {"symbol": "AXISBANK.NS", "name": "Axis Bank", "market": "NSE", "currency": "₹"}
]

# Angel One SmartAPI Credentials (Optional - can be configured in app Settings)
ANGELONE_API_KEY = os.getenv("ANGELONE_API_KEY", "")
ANGELONE_CLIENT_CODE = os.getenv("ANGELONE_CLIENT_CODE", "")
ANGELONE_PASSWORD = os.getenv("ANGELONE_PASSWORD", "")
ANGELONE_TOTP_SECRET = os.getenv("ANGELONE_TOTP_SECRET", "")


# 15-Minute Analysis Configuration
CANDLESTICK_INTERVAL = "15m"
CANDLESTICK_PERIOD = "5d"

# Confluence Weights
WEIGHT_SENTIMENT = 0.35
WEIGHT_CANDLESTICK = 0.35
WEIGHT_INDICATORS = 0.30

# Initial Virtual Capital (₹1,00,000 INR)
DEFAULT_PAPER_BALANCE = 100000.0

# Autonomous AI Auto-Trader Settings
AI_AUTO_TRADE_ENABLED = True
AI_MIN_CONFIDENCE = 70.0        # Minimum 70% confidence for AI to execute trade
AI_RISK_PER_TRADE = 15000.0      # Virtual capital per trade (₹15,000)
AI_MAX_OPEN_POSITIONS = 5        # Maximum 5 concurrent positions for safe risk management

# Optional Gemini API key
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")
