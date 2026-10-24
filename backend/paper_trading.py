"""
Paper Trading Simulation & Autonomous AI Auto-Trading Engine
Executes virtual trades, manages dynamic SL & TP targets, monitors positions,
and computes detailed Win vs Loss analytics and performance statistics.
"""
from datetime import datetime
from backend.database import get_connection
from backend.config import (
    DEFAULT_PAPER_BALANCE,
    AI_AUTO_TRADE_ENABLED,
    AI_MIN_CONFIDENCE,
    AI_RISK_PER_TRADE,
    AI_MAX_OPEN_POSITIONS
)


class PaperTradingEngine:
    """Simulates real-time paper trading and autonomous AI auto-trading."""

    def get_portfolio(self, current_prices: dict = None) -> dict:
        """Calculate complete portfolio metrics including win/loss trade statistics."""
        conn = get_connection()
        cursor = conn.cursor()

        # Fetch cash balance
        cursor.execute("SELECT * FROM portfolio ORDER BY id DESC LIMIT 1")
        port = cursor.fetchone()
        cash = port["cash_balance"] if port else DEFAULT_PAPER_BALANCE
        initial = port["initial_balance"] if port else DEFAULT_PAPER_BALANCE
        currency = port["currency"] if port else "₹"

        # Fetch open positions
        cursor.execute("SELECT * FROM positions WHERE status = 'OPEN' ORDER BY entry_time DESC")
        raw_open = cursor.fetchall()

        open_positions = []
        total_invested = 0.0
        total_unrealized_pnl = 0.0

        for r in raw_open:
            pos = dict(r)
            sym = pos["symbol"]
            curr_price = (current_prices or {}).get(sym, pos["current_price"])
            if curr_price and curr_price > 0:
                pos["current_price"] = curr_price

            invested = pos["entry_price"] * pos["quantity"]
            total_invested += invested

            if pos["side"] == "BUY":
                pnl = (pos["current_price"] - pos["entry_price"]) * pos["quantity"]
            else:  # SHORT SELL
                pnl = (pos["entry_price"] - pos["current_price"]) * pos["quantity"]

            pnl_pct = (pnl / invested) * 100 if invested > 0 else 0.0
            pos["unrealized_pnl"] = round(pnl, 2)
            pos["unrealized_pnl_pct"] = round(pnl_pct, 2)
            total_unrealized_pnl += pnl
            open_positions.append(pos)

        # Fetch closed positions for Win / Loss analytics
        cursor.execute("SELECT * FROM positions WHERE status = 'CLOSED' ORDER BY close_time DESC")
        raw_closed = cursor.fetchall()
        closed_positions = [dict(r) for r in raw_closed]

        total_closed = len(closed_positions)
        winning_positions = [p for p in closed_positions if (p["realized_pnl"] or 0) > 0]
        losing_positions = [p for p in closed_positions if (p["realized_pnl"] or 0) < 0]

        winning_trades = len(winning_positions)
        losing_trades = len(losing_positions)

        total_profit = sum(p["realized_pnl"] for p in winning_positions)
        total_loss = sum(abs(p["realized_pnl"]) for p in losing_positions)
        total_realized_pnl = sum((p["realized_pnl"] or 0) for p in closed_positions)

        win_rate = (winning_trades / total_closed * 100) if total_closed > 0 else 0.0
        profit_factor = (total_profit / total_loss) if total_loss > 0 else (total_profit if total_profit > 0 else 1.0)

        total_equity = cash + total_invested + total_unrealized_pnl
        net_return_pct = ((total_equity - initial) / initial) * 100 if initial > 0 else 0.0

        conn.close()

        return {
            "cash_balance": round(cash, 2),
            "initial_balance": round(initial, 2),
            "currency": currency,
            "total_equity": round(total_equity, 2),
            "total_invested": round(total_invested, 2),
            "unrealized_pnl": round(total_unrealized_pnl, 2),
            "realized_pnl": round(total_realized_pnl, 2),
            "net_return_pct": round(net_return_pct, 2),
            "win_rate": round(win_rate, 1),
            "total_trades": total_closed,
            "winning_trades": winning_trades,
            "losing_trades": losing_trades,
            "total_profit": round(total_profit, 2),
            "total_loss": round(total_loss, 2),
            "profit_factor": round(profit_factor, 2),
            "ai_auto_trade_enabled": AI_AUTO_TRADE_ENABLED,
            "open_positions": open_positions,
            "closed_positions": closed_positions[:50]
        }

    def execute_order(self, symbol: str, side: str, quantity: int, price: float,
                      stop_loss: float = None, target_price: float = None,
                      company_name: str = "", trade_type: str = "MANUAL",
                      ai_confidence: float = 0.0, ai_reasons: str = "") -> dict:
        """Execute simulated Buy or Sell order."""
        if quantity <= 0 or price <= 0:
            return {"success": False, "message": "Invalid quantity or price"}

        conn = get_connection()
        cursor = conn.cursor()

        cursor.execute("SELECT cash_balance FROM portfolio ORDER BY id DESC LIMIT 1")
        row = cursor.fetchone()
        cash = row["cash_balance"] if row else DEFAULT_PAPER_BALANCE

        order_cost = price * quantity

        if side.upper() == "BUY":
            if cash < order_cost:
                conn.close()
                return {"success": False, "message": f"Insufficient virtual funds. Need ₹{order_cost:,.2f}, available ₹{cash:,.2f}"}

            # Deduct cash
            new_cash = cash - order_cost
            cursor.execute("UPDATE portfolio SET cash_balance = ?, updated_at = CURRENT_TIMESTAMP", (new_cash,))

            # Insert position
            cursor.execute("""
            INSERT INTO positions (symbol, company_name, side, quantity, entry_price, current_price,
                                  stop_loss, target_price, status, trade_type, ai_confidence, ai_reasons)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'OPEN', ?, ?, ?)
            """, (symbol, company_name or symbol, "BUY", quantity, price, price, stop_loss, target_price,
                  trade_type, ai_confidence, ai_reasons))
            pos_id = cursor.lastrowid

            # Log trade
            cursor.execute("""
            INSERT INTO trade_logs (symbol, action, quantity, price, trade_type, notes)
            VALUES (?, 'BUY', ?, ?, ?, ?)
            """, (symbol, quantity, price, trade_type, f"[{trade_type}] Entered Long #{pos_id}"))

            conn.commit()
            conn.close()
            return {"success": True, "message": f"Bought {quantity} shares of {symbol} at ₹{price:.2f}", "position_id": pos_id}

        elif side.upper() == "SELL":
            # Check if there is an existing OPEN long position to exit
            cursor.execute("SELECT * FROM positions WHERE symbol = ? AND side = 'BUY' AND status = 'OPEN' ORDER BY entry_time ASC", (symbol,))
            existing_pos = cursor.fetchone()

            if existing_pos:
                pos_id = existing_pos["id"]
                conn.close()
                return self.close_position(pos_id, price, reason="MANUAL_EXIT")
            else:
                # Open Short position
                if cash < order_cost:
                    conn.close()
                    return {"success": False, "message": f"Insufficient margin to short. Need ₹{order_cost:,.2f}, available ₹{cash:,.2f}"}

                new_cash = cash - order_cost
                cursor.execute("UPDATE portfolio SET cash_balance = ?, updated_at = CURRENT_TIMESTAMP", (new_cash,))

                cursor.execute("""
                INSERT INTO positions (symbol, company_name, side, quantity, entry_price, current_price,
                                      stop_loss, target_price, status, trade_type, ai_confidence, ai_reasons)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'OPEN', ?, ?, ?)
                """, (symbol, company_name or symbol, "SELL", quantity, price, price, stop_loss, target_price,
                      trade_type, ai_confidence, ai_reasons))
                pos_id = cursor.lastrowid

                cursor.execute("""
                INSERT INTO trade_logs (symbol, action, quantity, price, trade_type, notes)
                VALUES (?, 'SHORT_SELL', ?, ?, ?, ?)
                """, (symbol, quantity, price, trade_type, f"[{trade_type}] Entered Short #{pos_id}"))

                conn.commit()
                conn.close()
                return {"success": True, "message": f"Short sold {quantity} shares of {symbol} at ₹{price:.2f}", "position_id": pos_id}

    def close_position(self, position_id: int, current_price: float, reason: str = "MANUAL") -> dict:
        """Close an open position, realize P&L, determine WIN/LOSS result, and credit back funds."""
        conn = get_connection()
        cursor = conn.cursor()

        cursor.execute("SELECT * FROM positions WHERE id = ? AND status = 'OPEN'", (position_id,))
        pos = cursor.fetchone()
        if not pos:
            conn.close()
            return {"success": False, "message": "Position not found or already closed."}

        qty = pos["quantity"]
        entry_price = pos["entry_price"]
        side = pos["side"]
        initial_invested = entry_price * qty

        if side == "BUY":
            realized_pnl = (current_price - entry_price) * qty
        else:  # SHORT SELL
            realized_pnl = (entry_price - current_price) * qty

        trade_result = "WIN" if realized_pnl > 0 else ("LOSS" if realized_pnl < 0 else "BREAKEVEN")
        returned_cash = initial_invested + realized_pnl

        # Update position
        cursor.execute("""
        UPDATE positions
        SET status = 'CLOSED',
            close_time = CURRENT_TIMESTAMP,
            close_price = ?,
            realized_pnl = ?,
            close_reason = ?,
            trade_result = ?
        WHERE id = ?
        """, (current_price, round(realized_pnl, 2), reason, trade_result, position_id))

        # Update portfolio cash
        cursor.execute("SELECT cash_balance FROM portfolio ORDER BY id DESC LIMIT 1")
        cash_row = cursor.fetchone()
        curr_cash = cash_row["cash_balance"] if cash_row else DEFAULT_PAPER_BALANCE
        new_cash = curr_cash + returned_cash
        cursor.execute("UPDATE portfolio SET cash_balance = ?, updated_at = CURRENT_TIMESTAMP", (new_cash,))

        # Log trade exit
        cursor.execute("""
        INSERT INTO trade_logs (symbol, action, quantity, price, pnl, trade_type, trade_result, notes)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, (pos["symbol"], f"CLOSE_{reason}", qty, current_price, round(realized_pnl, 2),
              pos["trade_type"], trade_result, f"Closed #{position_id} ({reason}) Result: {trade_result}"))

        conn.commit()
        conn.close()

        return {
            "success": True,
            "message": f"Closed {pos['symbol']} at ₹{current_price:.2f}. Result: {trade_result} ({realized_pnl:+.2f})",
            "realized_pnl": round(realized_pnl, 2),
            "trade_result": trade_result
        }

    def check_sl_tp_triggers(self, current_prices: dict) -> list:
        """Check all open positions against current market prices for auto Stop Loss or Target hits."""
        conn = get_connection()
        cursor = conn.cursor()

        cursor.execute("SELECT * FROM positions WHERE status = 'OPEN'")
        open_positions = cursor.fetchall()
        conn.close()

        triggered = []
        for p in open_positions:
            sym = p["symbol"]
            cmp = current_prices.get(sym)
            if not cmp or cmp <= 0:
                continue

            sl = p["stop_loss"]
            tp = p["target_price"]
            side = p["side"]
            pos_id = p["id"]

            if side == "BUY":
                if sl and cmp <= sl:
                    res = self.close_position(pos_id, cmp, reason="STOP_LOSS_HIT")
                    triggered.append({"position_id": pos_id, "symbol": sym, "type": "STOP_LOSS_HIT", "price": cmp, "pnl": res.get("realized_pnl", 0), "result": "LOSS"})
                elif tp and cmp >= tp:
                    res = self.close_position(pos_id, cmp, reason="TARGET_HIT")
                    triggered.append({"position_id": pos_id, "symbol": sym, "type": "TARGET_HIT", "price": cmp, "pnl": res.get("realized_pnl", 0), "result": "WIN"})
            elif side == "SELL":
                if sl and cmp >= sl:
                    res = self.close_position(pos_id, cmp, reason="STOP_LOSS_HIT")
                    triggered.append({"position_id": pos_id, "symbol": sym, "type": "STOP_LOSS_HIT", "price": cmp, "pnl": res.get("realized_pnl", 0), "result": "LOSS"})
                elif tp and cmp <= tp:
                    res = self.close_position(pos_id, cmp, reason="TARGET_HIT")
                    triggered.append({"position_id": pos_id, "symbol": sym, "type": "TARGET_HIT", "price": cmp, "pnl": res.get("realized_pnl", 0), "result": "WIN"})

        return triggered

    def ai_autonomous_trade_step(self, screener_signals: list, current_prices: dict) -> list:
        """
        Autonomous AI Trader:
        Scans generated 15m confluence signals. If a signal qualifies as STRONG BUY or STRONG SELL
        with high confidence, the AI autonomously executes the paper trade with automated SL & TP!
        """
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT symbol FROM positions WHERE status = 'OPEN'")
        open_symbols = set(row[0] for row in cursor.fetchall())
        conn.close()

        executed = []

        if len(open_symbols) >= AI_MAX_OPEN_POSITIONS:
            return executed

        for sig in screener_signals:
            if len(open_symbols) >= AI_MAX_OPEN_POSITIONS:
                break

            sym = sig["symbol"]
            action = sig.get("action", "")
            confidence = sig.get("confidence", 0)
            cmp = current_prices.get(sym, sig.get("price", 0))

            if cmp <= 0 or sym in open_symbols:
                continue

            # Only enter if confidence is >= AI_MIN_CONFIDENCE
            if confidence < AI_MIN_CONFIDENCE:
                continue

            # Calculate safe position size (e.g., allocating ~₹15,000 per trade)
            qty = max(1, int(AI_RISK_PER_TRADE / cmp))
            sl = sig.get("stop_loss")
            tp = sig.get("target_1")
            reasons_summary = "; ".join(sig.get("reasons", [])[:3])

            if "BUY" in action:
                res = self.execute_order(
                    symbol=sym,
                    side="BUY",
                    quantity=qty,
                    price=cmp,
                    stop_loss=sl,
                    target_price=tp,
                    company_name=sig.get("name", sym),
                    trade_type="AI_AUTONOMOUS",
                    ai_confidence=confidence,
                    ai_reasons=reasons_summary
                )
                if res.get("success"):
                    open_symbols.add(sym)
                    executed.append({
                        "symbol": sym,
                        "side": "BUY",
                        "quantity": qty,
                        "price": cmp,
                        "stop_loss": sl,
                        "target": tp,
                        "confidence": confidence,
                        "action": action
                    })
            elif "SELL" in action:
                res = self.execute_order(
                    symbol=sym,
                    side="SELL",
                    quantity=qty,
                    price=cmp,
                    stop_loss=sl,
                    target_price=tp,
                    company_name=sig.get("name", sym),
                    trade_type="AI_AUTONOMOUS",
                    ai_confidence=confidence,
                    ai_reasons=reasons_summary
                )
                if res.get("success"):
                    open_symbols.add(sym)
                    executed.append({
                        "symbol": sym,
                        "side": "SELL",
                        "quantity": qty,
                        "price": cmp,
                        "stop_loss": sl,
                        "target": tp,
                        "confidence": confidence,
                        "action": action
                    })

        return executed

    def reset_portfolio(self, initial_balance: float = DEFAULT_PAPER_BALANCE) -> dict:
        """Reset paper trading portfolio and clear active positions."""
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("DELETE FROM positions")
        cursor.execute("DELETE FROM trade_logs")
        cursor.execute("UPDATE portfolio SET cash_balance = ?, initial_balance = ?, updated_at = CURRENT_TIMESTAMP", (initial_balance, initial_balance))
        conn.commit()
        conn.close()
        return {"success": True, "message": f"Portfolio reset successfully to balance ₹{initial_balance:,.2f}"}
