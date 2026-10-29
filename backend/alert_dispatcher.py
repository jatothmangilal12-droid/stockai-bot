"""
Real-Time Push Notification & Background Alert Dispatcher.
Delivers urgent, high-priority notifications to mobile devices via ntfy.sh and Telegram
even when the mobile screen is OFF or the application is CLOSED.
"""
import time
import json
import base64
import logging
import urllib.request
import urllib.parse
from typing import Dict, Any, Optional, List
from backend.config import (
    NTFY_DEFAULT_TOPIC,
    NTFY_SERVER_URL,
    ALERT_COOLDOWN_SECONDS,
    APP_PUBLIC_URL,
    TELEGRAM_BOT_TOKEN,
    TELEGRAM_CHAT_ID
)
from backend.database import get_connection

logger = logging.getLogger("alert_dispatcher")

# In-memory cooldown cache: (symbol, side) -> last_alert_timestamp
_ALERT_COOLDOWN_CACHE: Dict[str, float] = {}


def _safe_header(val: str) -> str:
    """Encode header value using RFC 2047 if it contains non-ASCII/emojis."""
    try:
        val.encode("latin-1")
        return val
    except UnicodeEncodeError:
        encoded = base64.b64encode(val.encode("utf-8")).decode("ascii")
        return f"=?utf-8?b?{encoded}?="


def get_alert_settings() -> Dict[str, Any]:
    """Retrieve current push alert settings from the database."""
    try:
        conn = get_connection()
        c = conn.cursor()
        c.execute("""
            SELECT id, ntfy_topic, ntfy_enabled, telegram_token, telegram_chat_id,
                   telegram_enabled, sound_enabled, auto_scan_enabled, cooldown_minutes
            FROM alert_settings WHERE id = 1
        """)
        row = c.fetchone()
        conn.close()
        if row:
            return dict(row)
    except Exception as ex:
        logger.error(f"Error fetching alert settings: {ex}")

    return {
        "id": 1,
        "ntfy_topic": NTFY_DEFAULT_TOPIC,
        "ntfy_enabled": 1,
        "telegram_token": TELEGRAM_BOT_TOKEN,
        "telegram_chat_id": TELEGRAM_CHAT_ID,
        "telegram_enabled": 1 if TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID else 0,
        "sound_enabled": 1,
        "auto_scan_enabled": 1,
        "cooldown_minutes": 15
    }


def update_alert_settings(data: Dict[str, Any]) -> Dict[str, Any]:
    """Update push alert settings in SQLite database."""
    conn = get_connection()
    c = conn.cursor()
    c.execute("""
        UPDATE alert_settings
        SET ntfy_topic = ?,
            ntfy_enabled = ?,
            telegram_token = ?,
            telegram_chat_id = ?,
            telegram_enabled = ?,
            sound_enabled = ?,
            auto_scan_enabled = ?,
            cooldown_minutes = ?,
            updated_at = CURRENT_TIMESTAMP
        WHERE id = 1
    """, (
        data.get("ntfy_topic", NTFY_DEFAULT_TOPIC).strip(),
        1 if data.get("ntfy_enabled", True) else 0,
        data.get("telegram_token", "").strip(),
        data.get("telegram_chat_id", "").strip(),
        1 if data.get("telegram_enabled", False) else 0,
        1 if data.get("sound_enabled", True) else 0,
        1 if data.get("auto_scan_enabled", True) else 0,
        int(data.get("cooldown_minutes", 15))
    ))
    conn.commit()
    conn.close()
    return get_alert_settings()


def send_ntfy_push(
    topic: str,
    title: str,
    message: str,
    click_url: Optional[str] = None,
    priority: int = 5,
    tags: str = "rotating_light,fire"
) -> Dict[str, Any]:
    """
    Dispatch ultra-high priority notification to ntfy.sh topic.
    Priority 5 ('urgent' / 'max') triggers heads-up alert, loud tone, vibration,
    and wakes up Android screen even when locked / app closed.
    """
    clean_topic = topic.strip() or NTFY_DEFAULT_TOPIC
    url = f"{NTFY_SERVER_URL.rstrip('/')}/{clean_topic}"
    action_url = click_url or f"{APP_PUBLIC_URL}/#view-ai-trade"

    headers = {
        "Title": _safe_header(title[:120]),
        "Priority": str(priority),
        "Tags": tags,
        "Click": action_url,
        "Actions": f"view, Open AI Trade Setup, {action_url}",
        "Content-Type": "text/plain; charset=utf-8"
    }

    try:
        req = urllib.request.Request(
            url,
            data=message.encode("utf-8"),
            headers=headers,
            method="POST"
        )
        with urllib.request.urlopen(req, timeout=8) as resp:
            status = resp.status
            return {"success": status in (200, 201), "status_code": status, "topic": clean_topic}
    except Exception as ex:
        logger.warning(f"[ntfy.sh push failed] {ex}")
        return {"success": False, "error": str(ex), "topic": clean_topic}


def send_telegram_alert(token: str, chat_id: str, text: str) -> Dict[str, Any]:
    """Send alert to Telegram chat via Telegram Bot API."""
    if not token or not chat_id:
        return {"success": False, "error": "Telegram token or chat_id missing"}
    
    api_url = f"https://api.telegram.org/bot{token.strip()}/sendMessage"
    payload = {
        "chat_id": chat_id.strip(),
        "text": text,
        "parse_mode": "HTML",
        "disable_web_page_preview": False
    }
    try:
        data = json.dumps(payload).encode("utf-8")
        req = urllib.request.Request(
            api_url,
            data=data,
            headers={"Content-Type": "application/json"},
            method="POST"
        )
        with urllib.request.urlopen(req, timeout=8) as resp:
            return {"success": resp.status == 200}
    except Exception as ex:
        logger.warning(f"[Telegram alert failed] {ex}")
        return {"success": False, "error": str(ex)}


def log_alert_history(
    symbol: str,
    side: str,
    price: float,
    stop_loss: Optional[float],
    target_price: Optional[float],
    title: str,
    message: str,
    channel: str = "NTFY"
):
    """Persist sent alert into SQLite database."""
    try:
        conn = get_connection()
        c = conn.cursor()
        c.execute("""
            INSERT INTO alert_history (symbol, side, price, stop_loss, target_price, channel, title, message)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            symbol,
            side,
            float(price),
            float(stop_loss) if stop_loss else None,
            float(target_price) if target_price else None,
            channel,
            title,
            message
        ))
        conn.commit()
        conn.close()
    except Exception as ex:
        logger.error(f"Error saving alert history: {ex}")


def get_alert_history(limit: int = 30) -> List[Dict[str, Any]]:
    """Fetch recent alert history from DB."""
    try:
        conn = get_connection()
        c = conn.cursor()
        c.execute("""
            SELECT id, symbol, side, price, stop_loss, target_price, channel, title, message, status, created_at
            FROM alert_history
            ORDER BY id DESC
            LIMIT ?
        """, (limit,))
        rows = [dict(r) for r in c.fetchall()]
        conn.close()
        return rows
    except Exception as ex:
        logger.error(f"Error fetching alert history: {ex}")
        return []


def dispatch_breakout_alert(signal_item: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """
    Main entry point for dispatching a breakout alert.
    Applies anti-spam cooldown, formats urgent alert message,
    and pushes to ntfy (Android screen-wake loud notification) and Telegram.
    """
    settings = get_alert_settings()
    if not settings.get("auto_scan_enabled", 1):
        return None

    symbol = signal_item.get("symbol", "").strip()
    sg = signal_item.get("signal", {})
    if not symbol or not sg:
        return None

    side = sg.get("side", "BUY").upper()
    cache_key = f"{symbol}:{side}"
    now = time.time()
    cooldown_sec = max(60, int(settings.get("cooldown_minutes", 15)) * 60)

    # Check cooldown to prevent duplicate alert spam on the same stock
    last_time = _ALERT_COOLDOWN_CACHE.get(cache_key, 0.0)
    if (now - last_time) < cooldown_sec:
        return None

    _ALERT_COOLDOWN_CACHE[cache_key] = now

    price = float(signal_item.get("price", 0.0))
    sl = float(sg.get("sl", 0.0))
    tp = float(sg.get("tp", 0.0))
    qty = int(sg.get("qty", 1))
    risk = float(sg.get("risk", 0.0))
    state = signal_item.get("state", "COMPRESSING")
    name = signal_item.get("name") or symbol.replace(".NS", "")
    arrow = "🚀" if side == "BUY" else "🔻"
    tags = "rotating_light,chart_with_upwards_trend,fire" if side == "BUY" else "rotating_light,chart_with_downwards_trend,warning"

    title = f"🚨 AI BREAKOUT ALERT: {symbol.replace('.NS', '')} {arrow} {side}!"
    message = (
        f"{arrow} {name} ({symbol}) FRESH 5M BREAKOUT!\n"
        f"• Action: {side}\n"
        f"• Entry Price: ₹{price:,.2f}\n"
        f"• Stop Loss: ₹{sl:,.2f}\n"
        f"• Target (2R): ₹{tp:,.2f}\n"
        f"• Sizing: {qty} shares (Max Risk: ₹{risk:,.0f})\n"
        f"• Setup: 60m Consolidation Breakout with 1.8x Vol Surge!\n\n"
        f"👉 Tap now to review Battle-Plan & execute in StockAI!"
    )

    ntfy_res = None
    if settings.get("ntfy_enabled", 1):
        topic = settings.get("ntfy_topic") or NTFY_DEFAULT_TOPIC
        ntfy_res = send_ntfy_push(
            topic=topic,
            title=title,
            message=message,
            click_url=f"{APP_PUBLIC_URL}/#view-ai-trade",
            priority=5,  # Urgent: wakes device, loud ringtone, heads-up banner
            tags=tags
        )

    tg_res = None
    if settings.get("telegram_enabled", 0):
        tg_token = settings.get("telegram_token")
        tg_chat = settings.get("telegram_chat_id")
        if tg_token and tg_chat:
            tg_html = (
                f"🚨 <b>AI BREAKOUT SNIPER ALERT</b> 🚨\n\n"
                f"<b>Symbol:</b> {symbol} ({name})\n"
                f"<b>Action:</b> <b>{side}</b> {arrow}\n"
                f"<b>CMP / Entry:</b> ₹{price:,.2f}\n"
                f"<b>Stop Loss:</b> ₹{sl:,.2f}\n"
                f"<b>Target (2R):</b> ₹{tp:,.2f}\n"
                f"<b>Qty:</b> {qty} (Risk: ₹{risk:,.0f})\n\n"
                f"<i>60m Consolidation Breakout | 1.8x Volume Expansion</i>\n\n"
                f"<a href='{APP_PUBLIC_URL}/#view-ai-trade'>👉 Click to Open StockAI Bot & Execute</a>"
            )
            tg_res = send_telegram_alert(tg_token, tg_chat, tg_html)

    # Persist in DB
    log_alert_history(
        symbol=symbol,
        side=side,
        price=price,
        stop_loss=sl,
        target_price=tp,
        title=title,
        message=message,
        channel="NTFY+TG" if tg_res and tg_res.get("success") else "NTFY"
    )

    return {
        "symbol": symbol,
        "side": side,
        "price": price,
        "stop_loss": sl,
        "target_price": tp,
        "qty": qty,
        "ntfy": ntfy_res,
        "telegram": tg_res,
        "title": title,
        "message": message,
        "timestamp": now
    }


def send_test_alert(topic: Optional[str] = None) -> Dict[str, Any]:
    """
    Send an immediate test alert to verify mobile phone loud notification,
    vibration, and screen-wake capability.
    """
    settings = get_alert_settings()
    target_topic = (topic or settings.get("ntfy_topic") or NTFY_DEFAULT_TOPIC).strip()

    title = "🚨 TEST: StockAI Loud Breakout Alert!"
    message = (
        "🔊 High-Priority Test Notification!\n"
        "If you see this and heard a loud alarm sound, your phone is 100% READY!\n"
        "Even when your mobile screen is locked/off or app is closed, "
        "StockAI breakout alerts will wake your phone and ring loudly! 🚀"
    )

    res = send_ntfy_push(
        topic=target_topic,
        title=title,
        message=message,
        click_url=f"{APP_PUBLIC_URL}/#view-ai-trade",
        priority=5,
        tags="loudspeaker,rotating_light,fire"
    )

    log_alert_history(
        symbol="TEST_SIGNAL",
        side="BUY",
        price=1000.0,
        stop_loss=990.0,
        target_price=1020.0,
        title=title,
        message=message,
        channel="TEST"
    )

    return {
        "success": res.get("success", False),
        "topic": target_topic,
        "details": res,
        "message": "Test notification dispatched with Priority 5 (Urgent/Max)!"
    }
