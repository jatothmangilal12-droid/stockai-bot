"""
Angel One Research Recommendations Auto-Catch & Paper Trading Engine.
Specialized for 100% Angel One Analyst Research Calls (Intraday, Short Term, Long Term).
Automatically executes virtual paper trades with exact Entry, Stop Loss, and Target
allocating strictly ₹10,000 per recommended stock.
"""
import re
import time
import threading
from datetime import datetime
from typing import Optional, Dict, List, Any

from backend.database import get_connection
from backend.paper_trading import PaperTradingEngine

# User Mandate: Exactly ₹10,000 allocation per recommended stock
CAPITAL_PER_TRADE = 10000.0


class AngelResearchEngine:
    """
    Manages official Angel One research recommendations, parses incoming calls in real-time,
    and executes instant autonomous paper trades with exact ₹10k allocation.
    """

    def __init__(self, paper_trading: PaperTradingEngine):
        self.paper_trading = paper_trading
        self.auto_trade_enabled = True
        self._lock = threading.Lock()
        self._seed_default_calls()

    def _seed_default_calls(self):
        """Seed initial real Angel One calls from user screenshot if table is empty."""
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM angel_research_calls")
        count = cursor.fetchone()[0]

        if count == 0:
            initial_calls = [
                {
                    "call_id": "CALL_ETERNAL_001",
                    "symbol": "ETERNAL",
                    "company_name": "Zomato / Eternal Ltd",
                    "call_type": "Analyst call",
                    "category": "Intraday",
                    "action": "BUY",
                    "entry_price": 326.30,
                    "stop_loss": 323.00,
                    "target_price": 331.50,
                    "current_price": 326.85,
                    "potential_pct": 1.42,
                    "achieved_pct": 0.17,
                    "status": "ACTIVE"
                },
                {
                    "call_id": "CALL_PRESTIGE_002",
                    "symbol": "PRESTIGE",
                    "company_name": "Prestige Estates Projects Ltd",
                    "call_type": "Analyst call",
                    "category": "Intraday",
                    "action": "BUY",
                    "entry_price": 1395.00,
                    "stop_loss": 1380.00,
                    "target_price": 1410.00,
                    "current_price": 1398.90,
                    "potential_pct": 0.79,
                    "achieved_pct": 0.42,
                    "status": "TARGET_ACHIEVED"
                },
                {
                    "call_id": "CALL_KAYNES_003",
                    "symbol": "KAYNES",
                    "company_name": "Kaynes Technology India Ltd",
                    "call_type": "Analyst call",
                    "category": "Intraday",
                    "action": "BUY",
                    "entry_price": 3125.00,
                    "stop_loss": 3080.00,
                    "target_price": 3165.00,
                    "current_price": 3160.50,
                    "potential_pct": 0.14,
                    "achieved_pct": 1.19,
                    "status": "TARGET_ACHIEVED"
                }
            ]

            for c in initial_calls:
                cursor.execute("""
                    INSERT INTO angel_research_calls (
                        call_id, symbol, company_name, call_type, category, action,
                        entry_price, stop_loss, target_price, current_price,
                        potential_pct, achieved_pct, status, auto_traded, allocated_amount, quantity
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 0, 10000.0, 0)
                """, (
                    c["call_id"], c["symbol"], c["company_name"], c["call_type"], c["category"],
                    c["action"], c["entry_price"], c["stop_loss"], c["target_price"],
                    c["current_price"], c["potential_pct"], c["achieved_pct"], c["status"]
                ))
            conn.commit()

        conn.close()

        # Auto-execute paper trade for active seeded call (ETERNAL) if not already traded
        self.auto_trade_active_calls()

    def get_all_calls(self, category: Optional[str] = None) -> List[Dict[str, Any]]:
        """Retrieve Angel One research calls with live stats & paper trade status."""
        conn = get_connection()
        cursor = conn.cursor()

        if category and category.upper() != "ALL":
            cursor.execute("""
                SELECT * FROM angel_research_calls 
                WHERE UPPER(category) = UPPER(?) 
                ORDER BY id DESC
            """, (category,))
        else:
            cursor.execute("SELECT * FROM angel_research_calls ORDER BY id DESC")

        rows = cursor.fetchall()
        calls = [dict(r) for r in rows]
        conn.close()
        return calls

    def ingest_call(
        self,
        symbol: str,
        action: str,
        entry_price: float,
        stop_loss: float,
        target_price: float,
        category: str = "Intraday",
        company_name: str = "",
        call_type: str = "Analyst call"
    ) -> Dict[str, Any]:
        """
        Ingest a new recommendation from Angel One (via notification, scraper, or user).
        Instantly triggers autonomous Paper Trade with exact ₹10,000 capital.
        """
        clean_sym = symbol.replace(".NS", "").replace("-EQ", "").strip().upper()
        clean_action = "BUY" if action.upper() == "BUY" else "SELL"
        call_id = f"CALL_{clean_sym}_{int(time.time())}"

        # Potential % calculation
        if clean_action == "BUY" and entry_price > 0:
            potential_pct = round(((target_price - entry_price) / entry_price) * 100, 2)
        else:
            potential_pct = round(((entry_price - target_price) / entry_price) * 100, 2) if entry_price > 0 else 0.0

        conn = get_connection()
        cursor = conn.cursor()

        cursor.execute("""
            INSERT INTO angel_research_calls (
                call_id, symbol, company_name, call_type, category, action,
                entry_price, stop_loss, target_price, current_price,
                potential_pct, achieved_pct, status, auto_traded, allocated_amount, quantity
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 0.0, 'ACTIVE', 0, 10000.0, 0)
        """, (
            call_id, clean_sym, company_name or clean_sym, call_type, category,
            clean_action, entry_price, stop_loss, target_price, entry_price, potential_pct
        ))
        call_db_id = cursor.lastrowid
        conn.commit()
        conn.close()

        # Instant Auto Paper Trade Execution
        trade_result = None
        if self.auto_trade_enabled:
            trade_result = self._execute_paper_trade_for_call(call_db_id)

        return {
            "success": True,
            "call_id": call_id,
            "id": call_db_id,
            "symbol": clean_sym,
            "action": clean_action,
            "entry_price": entry_price,
            "stop_loss": stop_loss,
            "target_price": target_price,
            "potential_pct": potential_pct,
            "auto_traded": bool(trade_result and trade_result.get("success")),
            "trade_info": trade_result
        }

    def _execute_paper_trade_for_call(self, call_db_id: int) -> Optional[Dict[str, Any]]:
        """Execute simulated paper trade allocating strictly ₹10,000 for this Angel One call."""
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM angel_research_calls WHERE id = ?", (call_db_id,))
        row = cursor.fetchone()

        if not row:
            conn.close()
            return None

        call = dict(row)
        if call.get("auto_traded") == 1:
            conn.close()
            return {"success": False, "message": "Already auto-traded"}

        entry_price = float(call["entry_price"])
        if entry_price <= 0:
            conn.close()
            return {"success": False, "message": "Invalid entry price"}

        # Calculate exact quantity for ₹10,000 allocation
        quantity = max(1, int(CAPITAL_PER_TRADE // entry_price))
        actual_invested = round(quantity * entry_price, 2)

        res = self.paper_trading.execute_order(
            symbol=f"{call['symbol']}.NS" if not call['symbol'].endswith(".NS") else call['symbol'],
            side=call["action"],
            quantity=quantity,
            price=entry_price,
            stop_loss=float(call["stop_loss"]),
            target_price=float(call["target_price"]),
            company_name=call["company_name"],
            trade_type="ANGEL_RESEARCH_AUTO",
            ai_confidence=100.0,
            ai_reasons=f"Angel One {call['category']} Recommendation: Target ₹{call['target_price']} | SL ₹{call['stop_loss']} (₹10k Virtual Capital)"
        )

        if res.get("success"):
            pos_id = res.get("position_id")
            cursor.execute("""
                UPDATE angel_research_calls
                SET auto_traded = 1,
                    allocated_amount = ?,
                    quantity = ?,
                    position_id = ?,
                    updated_at = CURRENT_TIMESTAMP
                WHERE id = ?
            """, (actual_invested, quantity, pos_id, call_db_id))
            conn.commit()

        conn.close()
        return res

    def auto_trade_active_calls(self):
        """Scan active Angel One calls and execute paper trade if not yet traded."""
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT id FROM angel_research_calls WHERE status = 'ACTIVE' AND auto_traded = 0")
        rows = cursor.fetchall()
        conn.close()

        for r in rows:
            self._execute_paper_trade_for_call(r["id"])

    def parse_notification_text(self, text: str) -> Optional[Dict[str, Any]]:
        """
        Intelligently parse raw Angel One mobile push notification text.
        Example: 'Analyst call: Buy ETERNAL at 326.30, SL 323.00, Target 331.50'
        """
        try:
            # Action (BUY / SELL)
            action = "BUY"
            if re.search(r'\b(sell|short)\b', text, re.IGNORECASE):
                action = "SELL"

            # Symbol pattern
            sym_match = re.search(r'\b([A-Z]{3,15})\b', text)
            symbol = sym_match.group(1).upper() if sym_match else ""

            # Entry price pattern
            entry_match = re.search(r'(?:entry|at|buy\s+at|price)\s*[:₹\s]*([0-9]+(?:\.[0-9]+)?)', text, re.IGNORECASE)
            entry_price = float(entry_match.group(1)) if entry_match else 0.0

            # Stop loss pattern
            sl_match = re.search(r'(?:sl|stop\s*loss)\s*[:₹\s]*([0-9]+(?:\.[0-9]+)?)', text, re.IGNORECASE)
            stop_loss = float(sl_match.group(1)) if sl_match else 0.0

            # Target price pattern
            tgt_match = re.search(r'(?:target|tgt|tp)\s*[:₹\s]*([0-9]+(?:\.[0-9]+)?)', text, re.IGNORECASE)
            target_price = float(tgt_match.group(1)) if tgt_match else 0.0

            if symbol and entry_price > 0 and stop_loss > 0 and target_price > 0:
                return {
                    "symbol": symbol,
                    "action": action,
                    "entry_price": entry_price,
                    "stop_loss": stop_loss,
                    "target_price": target_price,
                    "category": "Intraday",
                    "company_name": symbol
                }
        except Exception as e:
            print(f"[AngelResearch] Notification parse error: {e}")
        return None

    def update_live_prices(self, price_map: Dict[str, float]):
        """
        Update live market price for all active Angel One calls,
        compute achieved % / potential %, and auto-exit if Target or SL is touched.
        """
        if not price_map:
            return

        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM angel_research_calls WHERE status = 'ACTIVE'")
        rows = cursor.fetchall()

        for r in rows:
            call = dict(r)
            sym = call["symbol"]
            sym_ns = f"{sym}.NS" if not sym.endswith(".NS") else sym
            ltp = price_map.get(sym) or price_map.get(sym_ns)

            if not ltp or ltp <= 0:
                continue

            entry = float(call["entry_price"])
            sl = float(call["stop_loss"])
            tgt = float(call["target_price"])
            action = call["action"]

            # Calculate live metrics
            if action == "BUY":
                achieved_pct = round(((ltp - entry) / entry) * 100, 2)
                potential_pct = round(max(0.0, ((tgt - ltp) / ltp) * 100), 2)
            else:
                achieved_pct = round(((entry - ltp) / entry) * 100, 2)
                potential_pct = round(max(0.0, ((ltp - tgt) / ltp) * 100), 2)

            new_status = "ACTIVE"
            # Target Hit check
            if (action == "BUY" and ltp >= tgt) or (action == "SELL" and ltp <= tgt):
                new_status = "TARGET_ACHIEVED"
                if call.get("position_id"):
                    self.paper_trading.close_position(call["position_id"], ltp, reason="TARGET_HIT")

            # Stop Loss Hit check
            elif (action == "BUY" and ltp <= sl) or (action == "SELL" and ltp >= sl):
                new_status = "SL_HIT"
                if call.get("position_id"):
                    self.paper_trading.close_position(call["position_id"], ltp, reason="STOP_LOSS_HIT")

            cursor.execute("""
                UPDATE angel_research_calls
                SET current_price = ?,
                    achieved_pct = ?,
                    potential_pct = ?,
                    status = ?,
                    updated_at = CURRENT_TIMESTAMP
                WHERE id = ?
            """, (ltp, achieved_pct, potential_pct, new_status, call["id"]))

        conn.commit()
        conn.close()

    def trigger_sample_call(self) -> Dict[str, Any]:
        """Trigger an instant live Angel One recommendation test to verify ₹10k paper trade."""
        samples = [
            {"symbol": "TATAMOTORS", "company": "Tata Motors Ltd", "entry": 980.00, "sl": 970.00, "tgt": 1005.00},
            {"symbol": "HDFCBANK", "company": "HDFC Bank Ltd", "entry": 1720.00, "sl": 1705.00, "tgt": 1750.00},
            {"symbol": "RELIANCE", "company": "Reliance Industries Ltd", "entry": 2740.00, "sl": 2715.00, "tgt": 2790.00},
            {"symbol": "INFY", "company": "Infosys Ltd", "entry": 1850.00, "sl": 1830.00, "tgt": 1890.00},
            {"symbol": "BHARTIARTL", "company": "Bharti Airtel Ltd", "entry": 1680.00, "sl": 1660.00, "tgt": 1720.00}
        ]
        import random
        chosen = random.choice(samples)

        return self.ingest_call(
            symbol=chosen["symbol"],
            action="BUY",
            entry_price=chosen["entry"],
            stop_loss=chosen["sl"],
            target_price=chosen["tgt"],
            category="Intraday",
            company_name=chosen["company"],
            call_type="Analyst call"
        )
