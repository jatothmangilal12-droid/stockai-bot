"""
Application Configuration - 100% Indian Market Focus (NSE / BSE)
"""
import os
from pathlib import Path
from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent
DB_PATH = BASE_DIR / "stock_ai.db"

# Load environment variables from .env if present
load_dotenv(BASE_DIR / ".env")

# Top Indian Stocks Watchlist (NSE) - Exclusively Indian Market with realistic baseline prices
DEFAULT_STOCKS = [
    {"symbol": "^NSEI", "name": "NIFTY 50 Index", "market": "NSE", "currency": "₹", "price": 24450.0},
    {"symbol": "^NSEBANK", "name": "BANK NIFTY Index", "market": "NSE", "currency": "₹", "price": 51300.0},
    {"symbol": "RELIANCE.NS", "name": "Reliance Industries", "market": "NSE", "currency": "₹", "price": 1200.0},
    {"symbol": "HDFCBANK.NS", "name": "HDFC Bank", "market": "NSE", "currency": "₹", "price": 1740.0},
    {"symbol": "TCS.NS", "name": "Tata Consultancy Services", "market": "NSE", "currency": "₹", "price": 4050.0},
    {"symbol": "HAL.NS", "name": "Hindustan Aeronautics", "market": "NSE", "currency": "₹", "price": 4520.0},
    {"symbol": "BEL.NS", "name": "Bharat Electronics", "market": "NSE", "currency": "₹", "price": 295.0},
    {"symbol": "TATAPOWER.NS", "name": "Tata Power", "market": "NSE", "currency": "₹", "price": 415.0},
    {"symbol": "SUZLON.NS", "name": "Suzlon Energy", "market": "NSE", "currency": "₹", "price": 62.0},
    {"symbol": "IRFC.NS", "name": "IRFC Ltd", "market": "NSE", "currency": "₹", "price": 148.0},
    {"symbol": "RVNL.NS", "name": "Rail Vikas Nigam Ltd", "market": "NSE", "currency": "₹", "price": 430.0},
    {"symbol": "ZOMATO.NS", "name": "Zomato Ltd", "market": "NSE", "currency": "₹", "price": 265.0},
    {"symbol": "TRENT.NS", "name": "Trent Limited", "market": "NSE", "currency": "₹", "price": 7100.0},
    {"symbol": "DIXON.NS", "name": "Dixon Technologies", "market": "NSE", "currency": "₹", "price": 14200.0},
    {"symbol": "SBIN.NS", "name": "State Bank of India", "market": "NSE", "currency": "₹", "price": 820.0},
    {"symbol": "BHARTIARTL.NS", "name": "Bharti Airtel", "market": "NSE", "currency": "₹", "price": 1850.0},
    {"symbol": "ITC.NS", "name": "ITC Limited", "market": "NSE", "currency": "₹", "price": 475.0},
    {"symbol": "TMCV.NS", "name": "Tata Motors CV", "market": "NSE", "currency": "₹", "price": 395.0}
]

# NIFTY 100+ Broader Universe for Dynamic Stock Discovery Across Hot Sectors
NIFTY_UNIVERSE = [
    # Indices
    {"symbol": "^NSEI", "name": "NIFTY 50 Index", "sector": "Index"},
    {"symbol": "^NSEBANK", "name": "BANK NIFTY Index", "sector": "Index"},

    # Mega Caps
    {"symbol": "RELIANCE.NS", "name": "Reliance Industries", "sector": "Energy/Conglomerate"},
    {"symbol": "TCS.NS", "name": "Tata Consultancy Services", "sector": "IT"},
    {"symbol": "HDFCBANK.NS", "name": "HDFC Bank", "sector": "Banking"},
    {"symbol": "ICICIBANK.NS", "name": "ICICI Bank", "sector": "Banking"},
    {"symbol": "INFY.NS", "name": "Infosys", "sector": "IT"},
    {"symbol": "SBIN.NS", "name": "State Bank of India", "sector": "Banking"},
    {"symbol": "BHARTIARTL.NS", "name": "Bharti Airtel", "sector": "Telecom"},
    {"symbol": "ITC.NS", "name": "ITC Limited", "sector": "FMCG"},
    {"symbol": "LT.NS", "name": "Larsen & Toubro", "sector": "Infrastructure"},
    {"symbol": "KOTAKBANK.NS", "name": "Kotak Mahindra Bank", "sector": "Banking"},
    {"symbol": "AXISBANK.NS", "name": "Axis Bank", "sector": "Banking"},

    # Defence & Aerospace (High Buzz Momentum)
    {"symbol": "HAL.NS", "name": "Hindustan Aeronautics", "sector": "Defence"},
    {"symbol": "BEL.NS", "name": "Bharat Electronics", "sector": "Defence"},
    {"symbol": "MAZDOCK.NS", "name": "Mazagon Dock Shipbuilders", "sector": "Defence"},
    {"symbol": "COCHINSHIP.NS", "name": "Cochin Shipyard", "sector": "Defence"},
    {"symbol": "BDL.NS", "name": "Bharat Dynamics", "sector": "Defence"},
    {"symbol": "DATAPATTNS.NS", "name": "Data Patterns", "sector": "Defence"},

    # Railways & PSU Infrastructure
    {"symbol": "IRFC.NS", "name": "Indian Railway Finance Corp", "sector": "Railways"},
    {"symbol": "RVNL.NS", "name": "Rail Vikas Nigam Ltd", "sector": "Railways"},
    {"symbol": "IRCON.NS", "name": "Ircon International", "sector": "Railways"},
    {"symbol": "RAILTEL.NS", "name": "RailTel Corporation", "sector": "Railways"},
    {"symbol": "BHEL.NS", "name": "Bharat Heavy Electricals", "sector": "Infrastructure"},
    {"symbol": "NBCC.NS", "name": "NBCC India", "sector": "Infrastructure"},
    {"symbol": "ADANIPORTS.NS", "name": "Adani Ports", "sector": "Infrastructure"},

    # Green Energy, Power & Utilities
    {"symbol": "TATAPOWER.NS", "name": "Tata Power", "sector": "Energy"},
    {"symbol": "SUZLON.NS", "name": "Suzlon Energy", "sector": "Energy"},
    {"symbol": "IREDA.NS", "name": "Indian Renewable Energy Dev", "sector": "Energy"},
    {"symbol": "JSWENERGY.NS", "name": "JSW Energy", "sector": "Energy"},
    {"symbol": "NTPC.NS", "name": "NTPC Limited", "sector": "Power"},
    {"symbol": "POWERGRID.NS", "name": "Power Grid Corporation", "sector": "Power"},
    {"symbol": "ADANIGREEN.NS", "name": "Adani Green Energy", "sector": "Energy"},
    {"symbol": "NHPC.NS", "name": "NHPC Limited", "sector": "Power"},
    {"symbol": "SJVN.NS", "name": "SJVN Limited", "sector": "Power"},

    # High-Beta Midcaps & Multi-Baggers
    {"symbol": "ZOMATO.NS", "name": "Zomato Ltd", "sector": "New-Age"},
    {"symbol": "TRENT.NS", "name": "Trent Limited", "sector": "Retail"},
    {"symbol": "DIXON.NS", "name": "Dixon Technologies", "sector": "Electronics"},
    {"symbol": "POLYCAB.NS", "name": "Polycab India", "sector": "Industrial"},
    {"symbol": "KALYANKJIL.NS", "name": "Kalyan Jewellers", "sector": "Consumer"},
    {"symbol": "CDSL.NS", "name": "Central Depository Services", "sector": "Finance"},
    {"symbol": "BSE.NS", "name": "BSE Limited", "sector": "Finance"},
    {"symbol": "ANGELONE.NS", "name": "Angel One", "sector": "Finance"},
    {"symbol": "MCX.NS", "name": "Multi Commodity Exchange", "sector": "Finance"},
    {"symbol": "KAYNES.NS", "name": "Kaynes Technology", "sector": "Electronics"},

    # Automobile & EV
    {"symbol": "TMCV.NS", "name": "Tata Motors CV", "sector": "Automobile"},
    {"symbol": "TMPV.NS", "name": "Tata Motors PV", "sector": "Automobile"},
    {"symbol": "MARUTI.NS", "name": "Maruti Suzuki", "sector": "Automobile"},
    {"symbol": "M&M.NS", "name": "Mahindra & Mahindra", "sector": "Automobile"},
    {"symbol": "BAJAJ-AUTO.NS", "name": "Bajaj Auto", "sector": "Automobile"},
    {"symbol": "EICHERMOT.NS", "name": "Eicher Motors", "sector": "Automobile"},
    {"symbol": "HEROMOTOCO.NS", "name": "Hero MotoCorp", "sector": "Automobile"},
    {"symbol": "TVSMOTOR.NS", "name": "TVS Motor Company", "sector": "Automobile"},
    {"symbol": "BHARATFORG.NS", "name": "Bharat Forge", "sector": "Automobile"},
    {"symbol": "EXIDEIND.NS", "name": "Exide Industries", "sector": "Automobile"},

    # PSU & Private Banking & Finance
    {"symbol": "BANKBARODA.NS", "name": "Bank of Baroda", "sector": "Banking"},
    {"symbol": "PNB.NS", "name": "Punjab National Bank", "sector": "Banking"},
    {"symbol": "CANBK.NS", "name": "Canara Bank", "sector": "Banking"},
    {"symbol": "UNIONBANK.NS", "name": "Union Bank of India", "sector": "Banking"},
    {"symbol": "BAJFINANCE.NS", "name": "Bajaj Finance", "sector": "Finance"},
    {"symbol": "JIOFIN.NS", "name": "Jio Financial Services", "sector": "Finance"},
    {"symbol": "RECLTD.NS", "name": "REC Limited", "sector": "Finance"},
    {"symbol": "PFC.NS", "name": "Power Finance Corporation", "sector": "Finance"},
    {"symbol": "SHRIRAMFIN.NS", "name": "Shriram Finance", "sector": "Finance"},
    {"symbol": "CHOLAFIN.NS", "name": "Cholamandalam Investment", "sector": "Finance"},

    # Metals & Mining
    {"symbol": "TATASTEEL.NS", "name": "Tata Steel", "sector": "Metals"},
    {"symbol": "JSWSTEEL.NS", "name": "JSW Steel", "sector": "Metals"},
    {"symbol": "VEDL.NS", "name": "Vedanta Limited", "sector": "Metals"},
    {"symbol": "HINDALCO.NS", "name": "Hindalco Industries", "sector": "Metals"},
    {"symbol": "COALINDIA.NS", "name": "Coal India", "sector": "Mining"},
    {"symbol": "NMDC.NS", "name": "NMDC Limited", "sector": "Mining"},
    {"symbol": "NATIONALUM.NS", "name": "National Aluminium", "sector": "Metals"},
    {"symbol": "SAIL.NS", "name": "Steel Authority of India", "sector": "Metals"},

    # Pharma & Healthcare
    {"symbol": "SUNPHARMA.NS", "name": "Sun Pharma", "sector": "Pharma"},
    {"symbol": "DRREDDY.NS", "name": "Dr Reddy's Laboratories", "sector": "Pharma"},
    {"symbol": "CIPLA.NS", "name": "Cipla Limited", "sector": "Pharma"},
    {"symbol": "LUPIN.NS", "name": "Lupin Limited", "sector": "Pharma"},
    {"symbol": "APOLLOHOSP.NS", "name": "Apollo Hospitals", "sector": "Healthcare"},
    {"symbol": "MANKIND.NS", "name": "Mankind Pharma", "sector": "Pharma"},
    {"symbol": "ZYDUSLIFE.NS", "name": "Zydus Lifesciences", "sector": "Pharma"},
    {"symbol": "AUROPHARMA.NS", "name": "Aurobindo Pharma", "sector": "Pharma"},

    # Consumer, FMCG & Retail
    {"symbol": "TITAN.NS", "name": "Titan Company", "sector": "Consumer"},
    {"symbol": "DMART.NS", "name": "Avenue Supermarts (DMart)", "sector": "Retail"},
    {"symbol": "HINDUNILVR.NS", "name": "Hindustan Unilever", "sector": "FMCG"},
    {"symbol": "NESTLEIND.NS", "name": "Nestle India", "sector": "FMCG"},
    {"symbol": "BRITANNIA.NS", "name": "Britannia Industries", "sector": "FMCG"},
    {"symbol": "TATACONSUM.NS", "name": "Tata Consumer Products", "sector": "FMCG"},
    {"symbol": "VBL.NS", "name": "Varun Beverages", "sector": "FMCG"},
    {"symbol": "DABUR.NS", "name": "Dabur India", "sector": "FMCG"},
    {"symbol": "MARICO.NS", "name": "Marico Limited", "sector": "FMCG"},
    {"symbol": "ASIANPAINT.NS", "name": "Asian Paints", "sector": "Consumer"},

    # IT & Software Services
    {"symbol": "HCLTECH.NS", "name": "HCL Technologies", "sector": "IT"},
    {"symbol": "WIPRO.NS", "name": "Wipro Limited", "sector": "IT"},
    {"symbol": "TECHM.NS", "name": "Tech Mahindra", "sector": "IT"},
    {"symbol": "LTIM.NS", "name": "LTIMindtree", "sector": "IT"},
    {"symbol": "PERSISTENT.NS", "name": "Persistent Systems", "sector": "IT"},
    {"symbol": "COFORGE.NS", "name": "Coforge Limited", "sector": "IT"},
    {"symbol": "KPITTECH.NS", "name": "KPIT Technologies", "sector": "IT"},
    {"symbol": "TATAELXSI.NS", "name": "Tata Elxsi", "sector": "IT"},

    # Oil & Gas / Energy
    {"symbol": "ONGC.NS", "name": "Oil & Natural Gas Corp", "sector": "Energy"},
    {"symbol": "BPCL.NS", "name": "Bharat Petroleum", "sector": "Energy"},
    {"symbol": "IOC.NS", "name": "Indian Oil Corporation", "sector": "Energy"},
    {"symbol": "GAIL.NS", "name": "GAIL India", "sector": "Energy"},
    {"symbol": "PETRONET.NS", "name": "Petronet LNG", "sector": "Energy"},
    {"symbol": "ADANIENT.NS", "name": "Adani Enterprises", "sector": "Conglomerate"},
    {"symbol": "ULTRACEMCO.NS", "name": "UltraTech Cement", "sector": "Materials"},

    # Top Liquid F&O Large & Midcap Market Movers
    {"symbol": "AMBUJACEM.NS", "name": "Ambuja Cements Ltd", "sector": "Materials"},
    {"symbol": "PIDILITIND.NS", "name": "Pidilite Industries Ltd", "sector": "Chemicals"},
    {"symbol": "GRASIM.NS", "name": "Grasim Industries Ltd", "sector": "Materials"},
    {"symbol": "POWERINDIA.NS", "name": "Hitachi Energy India Ltd", "sector": "Capital Goods"},
    {"symbol": "DIVISLAB.NS", "name": "Divi's Laboratories Ltd", "sector": "Pharma"},
    {"symbol": "ADANIENSOL.NS", "name": "Adani Energy Solutions Ltd", "sector": "Energy"},
    {"symbol": "CUMMINSIND.NS", "name": "Cummins India Ltd", "sector": "Capital Goods"},
    {"symbol": "ENRIN.NS", "name": "Siemens Energy India Ltd", "sector": "Capital Goods"}
]

# Angel One SmartAPI Credentials (Optional - can be configured in app Settings)
ANGELONE_API_KEY = os.getenv("ANGELONE_API_KEY", "")
ANGELONE_CLIENT_CODE = os.getenv("ANGELONE_CLIENT_CODE", "")
ANGELONE_PASSWORD = os.getenv("ANGELONE_PASSWORD", "")
ANGELONE_TOTP_SECRET = os.getenv("ANGELONE_TOTP_SECRET", "")


# 15-Minute Analysis Configuration
CANDLESTICK_INTERVAL = "15m"
CANDLESTICK_PERIOD = "5d"

# Confluence Weights (Institutional 5-Pillar Model: Sum = 1.00 / 100%)
WEIGHT_SENTIMENT = 0.18
WEIGHT_CANDLESTICK = 0.22
WEIGHT_INDICATORS = 0.35
WEIGHT_OPTION_CHAIN = 0.15
WEIGHT_MACRO_CHOP = 0.10

# Initial Virtual Capital (₹1,00,000 INR)
DEFAULT_PAPER_BALANCE = 100000.0

# Autonomous AI Auto-Trader Settings (Institutional Precision Mode)
AI_AUTO_TRADE_ENABLED = True
AI_MIN_CONFIDENCE = 78.0        # High precision 78% threshold (filters out weak chop)
AI_RISK_PER_TRADE = 15000.0      # Virtual capital per trade (₹15,000)
AI_MAX_OPEN_POSITIONS = 6        # Up to 6 diversified open positions across sectors

# Hedge-Fund Capital Shield & Circuit Breaker Rules (Zero-Loss Philosophy)
CIRCUIT_BREAKER_MAX_DAILY_LOSS_PCT = 2.0     # Max 2% loss of initial balance in a single day (₹2,000)
CIRCUIT_BREAKER_MAX_CONSECUTIVE_LOSSES = 2   # 2 consecutive losses freezes AI trading for cooldown
BREAK_EVEN_TRIGGER_RATIO = 1.0               # At 1:1 risk-reward, move SL to Break-Even immediately
SMART_MONEY_VOLUME_MULTIPLIER = 2.2          # 2.2x 20-period volume SMA signals institutional whale flow
CHOP_INDEX_THRESHOLD = 61.8                  # Choppiness Index > 61.8 indicates choppy trap zone (No-Trade)

# Institutional 6-Pillar Trading Engines (Maximum Profit & Minimum Loss)
PARTIAL_PROFIT_BOOK_RATIO = 0.60             # Book 60% profit immediately at Target 1
FREE_RIDE_RUNNER_RATIO = 0.40                # Leave 40% as a zero-risk free-ride runner for Target 2
REVERSAL_SNIPER_MIN_RRR = 5.0                # 1:5 Asymmetric Payoff on Momentum Exhaustion reversals
SECTOR_MOMENTUM_BOOST = 15.0                 # Confluence boost for stocks aligned with leading sector
ADAPTIVE_ATR_TRAILING_MULT = 1.5             # 1.5x ATR trailing buffer prevents market shakeouts
INSTITUTIONAL_DELIVERY_SPIKE_RATIO = 2.0     # 2.0x volume surge with narrow spread signals delivery accumulation

# Optional Gemini API key
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")
