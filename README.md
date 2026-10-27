# 📈 StockAI: 15-Minute Candlestick Pattern & News Sentiment Trading Bot

A high-performance quantitative stock analysis and paper trading system designed for **Indian (NSE/BSE)** and **US (NASDAQ/NYSE)** markets. It fuses **Daily News Sentiment (35%)**, **15-Minute Candlestick Pattern Recognition (35%)**, and **Multi-Indicator Technical Confluence (30%)** to generate high-probability trade setups with precise Entry, Stop Loss, and Targets, complete with a dark trading terminal UI and **Android Mobile App (APK)** support.

---

## 🌟 Key Features

### 1. 📰 Real-Time News & Financial Sentiment Engine (35% Weight)
- Fetches real-time financial breaking news from **Google News RSS** and **Yahoo Finance** without requiring paid API keys.
- Domain-specific **Loughran-McDonald Financial Lexicon** scoring for market terms (*surge, rally, beat, plunge, probe, scam, breakout*).
- Calculates Net Sentiment (-1.0 to +1.0), sentiment breakdown (Positive/Neutral/Negative), and momentum.
- Optional **Gemini AI** integration for deep executive market synthesis.

### 2. 🕯️ 15-Minute Candlestick Pattern Detector (35% Weight)
- Evaluates real-time 15m OHLCV data using `yfinance`.
- Automatically detects classic reversal and continuation candlestick formations:
  - **Hammer & Inverted Hammer** (Bullish Reversal)
  - **Bullish & Bearish Engulfing** (Strong Trend Shift)
  - **Morning Star & Evening Star** (3-Candle Institutional Reversal)
  - **Shooting Star** (Bearish Peak Rejection)
  - **Doji, Dragonfly Doji, Gravestone Doji** (Indecision & Reversals)
  - **Piercing Line & Dark Cloud Cover**
- Pinpoints patterns directly onto the 15m chart canvas.

### 3. 🎯 Multi-Indicator Technical Confluence (30% Weight)
- **EMA Trend Alignment**: 9 EMA & 21 EMA Golden / Death Crosses + 50 EMA baseline.
- **RSI (14)**: Momentum expansion vs. overbought (>70) & oversold (<30) exhaustion zones.
- **MACD (12, 26, 9)**: Histogram acceleration and signal line crossovers.
- **Volume Surge**: Detects volume spikes (>1.4x 20-period SMA) confirming institutional participation.
- **ATR 14**: Dynamic volatility-adjusted Stop Loss (1.5x ATR) and Take Profit (2.0x & 3.2x ATR) with favorable Risk-to-Reward Ratios (1:1.5 to 1:2.5+).

### 4. 💼 Real-Time Paper Trading Simulator
- Virtual wallet pre-funded with **₹100,000 / $10,000**.
- One-click Buy/Sell order execution with SL and TP.
- Real-time tracking of:
  - Live Unrealized P&L
  - Realized P&L
  - Total Portfolio Equity
  - Win Rate % and trade history
- Automatic Stop Loss (SL) and Take Profit (TP) trigger execution in the background!

### 5. 📱 Android Application (APK) & Mobile PWA
- **1-Tap PWA**: Open on any Android phone browser, tap *"Add to Home Screen"* and use it as a standalone app with native look and feel.
- **Capacitor Android Project**: Native Android Studio and Gradle project included inside `android_app/` to compile a standalone `.apk` file.

---

## 📁 Project Architecture

```
stock ai/
├── backend/
│   ├── config.py             # Watchlists, confluence weights, and settings
│   ├── database.py           # SQLite layer for virtual portfolio and trade logs
│   ├── news_sentiment.py     # Real-time RSS news scraper + Financial NLP engine
│   ├── technical_engine.py   # 15m Candlestick pattern detector + RSI, MACD, EMAs, ATR
│   ├── signal_evaluator.py   # Multi-factor confluence scoring algorithm
│   ├── paper_trading.py      # Virtual portfolio and SL/TP auto execution
│   └── main.py               # FastAPI server + WebSockets + Static file server
│
├── frontend/
│   ├── index.html            # Mobile-first dark trading terminal UI
│   ├── manifest.json         # PWA Manifest for Android installation
│   ├── sw.js                 # Service worker for offline caching
│   ├── css/
│   │   └── style.css         # TradingView/Bloomberg inspired dark theme
│   └── js/
│       ├── charts.js         # Canvas 15m candlestick & RSI chart renderer
│       └── app.js            # Frontend reactive controller & WebSockets
│
├── android_app/              # Native Android APK packaging folder
│   ├── capacitor.config.json # Capacitor configuration
│   ├── package.json          # Node dependencies for Android build
│   ├── build_apk.bat         # 1-Click Android APK build script
│   └── build_apk_guide.md    # Step-by-step guide in Telugu and English
│
├── run_app.py                # Python launcher with automatic LAN IP discovery
├── run_bot.bat               # Windows 1-click batch launcher
├── requirements.txt          # Python dependencies
└── README.md
```

---

## ⚡ Quick Start Guide (Telugu & English)

### 1. Run the Bot on PC
Double-click **`run_bot.bat`** (or open terminal and run):
```bash
python run_app.py
```
This will automatically launch the terminal in your browser at `http://localhost:8000`.

### 2. Open on Android Phone
1. Connect your phone and PC to the same Wi-Fi / Hotspot.
2. In your terminal output, find the phone URL: `http://<YOUR_PC_IP>:8000` (e.g. `http://192.168.1.15:8000`).
3. Open Google Chrome on your Android phone, enter that URL.
4. Tap Chrome menu (⋮) -> **"Install app"** or **"Add to Home screen"**. It will install immediately with an app icon on your phone!

### 3. Compile Native Android APK
Go to `android_app` folder and double-click `build_apk.bat` to compile `app-debug.apk`.
See `android_app/build_apk_guide.md` for full details.

---

## 🛡️ Confluence Decision Matrix

| AI Confluence Score | Signal Action | Actionable Setup |
| :--- | :--- | :--- |
| **+55 to +100** | **STRONG BUY** | Bullish Sentiment + Reversal Pattern (e.g. Engulfing/Hammer) + EMA/RSI confluence |
| **+20 to +54** | **BUY** | Upward bias confirmed by 2 of 3 components |
| **-19 to +19** | **NEUTRAL / WATCH** | Consolidating or conflicting signals |
| **-20 to -54** | **SELL** | Downward bias confirmed by 2 of 3 components |
| **-55 to -100** | **STRONG SELL** | Bearish Sentiment + Shooting Star/Bearish Engulfing + EMA death cross |
