"""
SQLite Database Layer for Paper Trading, AI Autonomous Trade Logs, and Win/Loss Analytics.
"""
import sqlite3
from pathlib import Path
from backend.config import DB_PATH, DEFAULT_PAPER_BALANCE


def get_connection():
    """Get SQLite database connection with row factory and WAL concurrency enabled."""
    conn = sqlite3.connect(DB_PATH, timeout=15.0)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL;")
    conn.execute("PRAGMA busy_timeout=10000;")
    conn.execute("PRAGMA synchronous=NORMAL;")
    return conn


def init_db():
    """Initialize SQLite database tables and run schema migrations."""
    conn = get_connection()
    cursor = conn.cursor()

    # Portfolio table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS portfolio (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        cash_balance REAL NOT NULL,
        initial_balance REAL NOT NULL,
        currency TEXT DEFAULT '₹',
        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
    """)

    # Positions table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS positions (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        symbol TEXT NOT NULL,
        company_name TEXT,
        side TEXT NOT NULL,           -- 'BUY' or 'SELL'
        quantity INTEGER NOT NULL,
        entry_price REAL NOT NULL,
        current_price REAL NOT NULL,
        stop_loss REAL,
        target_price REAL,
        status TEXT DEFAULT 'OPEN',   -- 'OPEN' or 'CLOSED'
        entry_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        close_time TIMESTAMP,
        close_price REAL,
        realized_pnl REAL DEFAULT 0.0,
        close_reason TEXT,            -- 'TARGET_HIT', 'STOP_LOSS_HIT', 'MANUAL'
        trade_type TEXT DEFAULT 'AI_AUTONOMOUS', -- 'AI_AUTONOMOUS' or 'MANUAL'
        ai_confidence REAL DEFAULT 0.0,
        ai_reasons TEXT,
        trade_result TEXT,            -- 'WIN' or 'LOSS'
        notes TEXT,
        post_mortem TEXT,
        lesson_learned TEXT
    )
    """)

    # Trade Logs
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS trade_logs (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        symbol TEXT NOT NULL,
        action TEXT NOT NULL,
        quantity INTEGER NOT NULL,
        price REAL NOT NULL,
        pnl REAL DEFAULT 0.0,
        trade_type TEXT DEFAULT 'AI_AUTONOMOUS',
        trade_result TEXT,
        notes TEXT,
        post_mortem TEXT,
        lesson_learned TEXT,
        timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
    """)

    # User Settings
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS settings (
        key TEXT PRIMARY KEY,
        value TEXT
    )
    """)

    # Check for missing columns in existing positions table (Auto Migration)
    cursor.execute("PRAGMA table_info(positions)")
    existing_cols = [c[1] for c in cursor.fetchall()]
    if "trade_type" not in existing_cols:
        cursor.execute("ALTER TABLE positions ADD COLUMN trade_type TEXT DEFAULT 'AI_AUTONOMOUS'")
    if "ai_confidence" not in existing_cols:
        cursor.execute("ALTER TABLE positions ADD COLUMN ai_confidence REAL DEFAULT 0.0")
    if "ai_reasons" not in existing_cols:
        cursor.execute("ALTER TABLE positions ADD COLUMN ai_reasons TEXT")
    if "trade_result" not in existing_cols:
        cursor.execute("ALTER TABLE positions ADD COLUMN trade_result TEXT")
    if "notes" not in existing_cols:
        cursor.execute("ALTER TABLE positions ADD COLUMN notes TEXT")
    if "post_mortem" not in existing_cols:
        cursor.execute("ALTER TABLE positions ADD COLUMN post_mortem TEXT")
    if "lesson_learned" not in existing_cols:
        cursor.execute("ALTER TABLE positions ADD COLUMN lesson_learned TEXT")

    # Check for missing columns in existing trade_logs table (Auto Migration)
    cursor.execute("PRAGMA table_info(trade_logs)")
    existing_log_cols = [c[1] for c in cursor.fetchall()]
    if "trade_type" not in existing_log_cols:
        cursor.execute("ALTER TABLE trade_logs ADD COLUMN trade_type TEXT DEFAULT 'AI_AUTONOMOUS'")
    if "trade_result" not in existing_log_cols:
        cursor.execute("ALTER TABLE trade_logs ADD COLUMN trade_result TEXT")
    if "pnl" not in existing_log_cols:
        cursor.execute("ALTER TABLE trade_logs ADD COLUMN pnl REAL DEFAULT 0.0")
    if "post_mortem" not in existing_log_cols:
        cursor.execute("ALTER TABLE trade_logs ADD COLUMN post_mortem TEXT")
    if "lesson_learned" not in existing_log_cols:
        cursor.execute("ALTER TABLE trade_logs ADD COLUMN lesson_learned TEXT")

    # Insert default portfolio if empty
    cursor.execute("SELECT COUNT(*) FROM portfolio")
    if cursor.fetchone()[0] == 0:
        cursor.execute(
            "INSERT INTO portfolio (cash_balance, initial_balance, currency) VALUES (?, ?, ?)",
            (DEFAULT_PAPER_BALANCE, DEFAULT_PAPER_BALANCE, '₹')
        )

    conn.commit()
    conn.close()


init_db()
