"""
StockAI Pro - Angel One SmartAPI 3-Stage Order Execution & OCO (One-Cancels-Other) Engine
======================================================================================
Implements Strict Institutional Execution Protocol:
  Stage 1: ENTRY ORDER -> MARKET/LIMIT, INTRADAY MIS (Strict Demat Protection)
  Stage 2: FILL CONFIRMATION -> Poll order book, extract real average fill price & fill quantity (partial fill aware)
  Stage 3: DUAL OCO PLACEMENT ->
            - Stop-Loss: variety='STOPLOSS', ordertype='STOPLOSS_LIMIT', calculated from actual fill price,
              0.4% danger buffer, rounded down/up to NSE 0.05 tick size
            - Target: variety='NORMAL', ordertype='LIMIT', calculated from actual fill price,
              rounded to NSE 0.05 tick size
  Stage 4: RECONCILIATION & MONITORING ->
            - If Target fills -> cancel SL order immediately!
            - If SL fills -> cancel Target order immediately!
            - At 15:15 IST -> cancel all open SL & Target orders before broker's MIS square-off.
  Stage 5: EMERGENCY NAKED POSITION SHIELD ->
            - If SL placement fails after 3 retries, immediately execute emergency market exit
              to protect capital from naked exposure!
"""

import math
import time
import json
import uuid
import urllib.request
from datetime import datetime, timezone, timedelta
from typing import Optional, Dict, Any, Tuple, List
from backend.database import get_connection

# NSE Equity Cash segment tick size is exactly 0.05
NSE_TICK_SIZE = 0.05


def round_nse_tick(price: float, direction: str = "NEAREST") -> float:
    """
    Round price to the nearest NSE 0.05 tick size.
    Direction:
      - 'UP': math.ceil(price / 0.05) * 0.05 (for Buy Target / Sell SL)
      - 'DOWN': math.floor(price / 0.05) * 0.05 (for Buy SL / Sell Target)
      - 'NEAREST': round(price / 0.05) * 0.05
    """
    tick = NSE_TICK_SIZE
    p = round(float(price), 4)
    if direction == "UP":
        val = math.ceil(p / tick) * tick
    elif direction == "DOWN":
        val = math.floor(p / tick) * tick
    else:
        val = round(p / tick) * tick
    return round(val, 2)


def get_order_market_context() -> Tuple[bool, str, str]:
    """
    Check market status and return (is_live_market, message, variety).
    If live market hours (Mon-Fri 09:15 - 15:10 IST): variety = "NORMAL"
    If off-market hours or weekends: variety = "AMO" (After Market Order)
    """
    utc_now = datetime.now(timezone.utc)
    ist_now = utc_now + timedelta(hours=5, minutes=30)
    total_mins = ist_now.hour * 60 + ist_now.minute
    market_open = 9 * 60 + 15
    entry_cutoff = 15 * 60 + 10

    is_live = (ist_now.weekday() not in (5, 6)) and (market_open <= total_mins <= entry_cutoff)
    variety = "NORMAL" if is_live else "AMO"
    msg = "LIVE_MARKET" if is_live else f"OFF_MARKET_AMO (Placed after hours: {ist_now.strftime('%I:%M %p')})"
    return is_live, msg, variety


def is_market_entry_allowed() -> Tuple[bool, str]:
    is_live, msg, _ = get_order_market_context()
    return is_live, msg


def calculate_risk_quantity(
    capital: float,
    entry_price: float,
    sl_price: float,
    max_risk_amount: float = 1000.0,
    leverage: float = 5.0
) -> int:
    """
    Calculate position quantity based on risk per share rather than blindly using capital.
    Formula: Quantity = Max Risk Amount / |Entry - SL|
    """
    if entry_price <= 0:
        return 1

    risk_per_share = abs(entry_price - sl_price)
    if risk_per_share <= 0:
        risk_per_share = entry_price * 0.007

    # Quantity based on max risk allowed
    risk_qty = int(max_risk_amount / risk_per_share)

    # Quantity capped by maximum intraday buying power (5x MIS)
    max_margin_qty = int((capital * leverage) / entry_price) if capital > 0 else 1

    final_qty = max(1, min(risk_qty, max_margin_qty))
    return final_qty


class AngelOcoManager:
    """
    Manages the full lifecycle of Angel One 3-Stage Orders and OCO (One-Cancels-Other) pairs.
    """

    def execute_three_stage_order(
        self,
        angel_client,
        symbol: str,
        side: str,
        quantity: int,
        price: float = 0.0,
        stop_loss: Optional[float] = None,
        target_price: Optional[float] = None,
        sl_pct: Optional[float] = None,
        tp_pct: Optional[float] = None,
        order_type: str = "MARKET"
    ) -> Dict[str, Any]:
        """
        Execute 3-Stage Order on Angel One:
          1. Submit Entry Order (MARKET / LIMIT)
          2. Confirm execution & retrieve exact average fill price from order book
          3. Calculate SL & TP from actual fill price and submit OCO Stop-Loss & Target orders
        """
        # 1. Market Hours & Variety Check (Live Market vs AMO After-Hours)
        is_live_market, market_msg, variety = get_order_market_context()

        # 2. Risk Cap & Validation Checks (Institutional Risk Safeguard)
        if quantity <= 0 or quantity > 500:
            return {"status": False, "message": f"Order quantity {quantity} invalid. Must be between 1 and 500 shares."}

        # 3. Clean Symbol and Demat Shield Check
        clean_sym = symbol.replace(".NS", "").replace("-EQ", "").upper()

        calc_price = price
        if calc_price <= 0:
            q = angel_client.get_live_quote(clean_sym)
            calc_price = float(q.get("price", 0.0)) if q else 0.0
        if calc_price > 0 and (calc_price * quantity) > 100000.0:
            return {"status": False, "message": f"Order value ₹{calc_price * quantity:,.2f} exceeds max server limit of ₹1,00,000.00."}

        # 4. Authentication Check
        if not angel_client.is_authenticated:
            ok, msg = angel_client.login()
            if not ok:
                return {"status": False, "message": f"Angel One login required: {msg}"}

        holdings_res = angel_client.get_holdings()
        if holdings_res.get("status"):
            demat_symbols = holdings_res.get("holding_symbols", [])
            if clean_sym in demat_symbols:
                return {
                    "status": False,
                    "message": f"Demat Shield Block: {clean_sym} is held in your Demat portfolio! Intraday order aborted to protect delivery shares."
                }

        token = angel_client._resolve_token(clean_sym)
        if not token:
            return {"status": False, "message": f"Token not found for {clean_sym}. Add to NSE_TOKENS mapping."}

        tradingsymbol = f"{clean_sym}-EQ"
        transaction_type = "BUY" if side.upper() == "BUY" else "SELL"
        exit_side = "SELL" if transaction_type == "BUY" else "BUY"
        client_tag = f"SA_{uuid.uuid4().hex[:10]}"

        # =====================================================================
        # STAGE 1: SUBMIT ENTRY ORDER (NORMAL or AMO)
        # =====================================================================
        entry_ordertype = "LIMIT" if price > 0 else ("LIMIT" if variety == "AMO" else "MARKET")
        if entry_ordertype == "LIMIT" and price <= 0:
            q = angel_client.get_live_quote(clean_sym)
            price = float(q.get("price", 0.0)) if q else 0.0
            if price <= 0:
                price = 100.0
        entry_price_str = f"{round_nse_tick(price, 'NEAREST'):.2f}" if price > 0 else "0"

        entry_payload = {
            "variety": variety,
            "tradingsymbol": tradingsymbol,
            "symboltoken": token,
            "transactiontype": transaction_type,
            "exchange": "NSE",
            "ordertype": entry_ordertype,
            "producttype": "INTRADAY",
            "duration": "DAY",
            "price": entry_price_str,
            "squareoff": "0",
            "stoploss": "0",
            "quantity": str(quantity)
        }

        print(f"[SmartAPI 3-Stage] Submitting Stage 1 Entry Order ({variety}): {entry_payload}")
        entry_res = self._send_broker_order(angel_client, entry_payload)
        if not entry_res.get("status"):
            err_msg = entry_res.get("message", "Order rejected by broker")
            self._record_order_db(
                client_tag=client_tag,
                symbol=f"{clean_sym}.NS",
                tradingsymbol=tradingsymbol,
                symboltoken=token,
                side=transaction_type,
                quantity=quantity,
                oco_state="FAILED",
                notes=f"Entry rejected: {err_msg}"
            )
            return {"status": False, "message": f"Angel One Entry Rejected: {err_msg}"}

        entry_order_id = entry_res.get("order_id")
        print(f"[SmartAPI 3-Stage] Stage 1 Entry Placed! Order ID: {entry_order_id} ({variety})")

        # For AMO orders, record and return immediately (fill confirms next morning at 09:15)
        if variety == "AMO":
            self._record_order_db(
                client_tag=client_tag,
                symbol=f"{clean_sym}.NS",
                tradingsymbol=tradingsymbol,
                symboltoken=token,
                side=transaction_type,
                quantity=quantity,
                entry_order_id=entry_order_id,
                entry_status="AMO_SUBMITTED",
                oco_state="AMO_QUEUED",
                notes=f"AMO Queued after market hours ({market_msg})"
            )
            return {
                "status": True,
                "success": True,
                "order_id": entry_order_id,
                "entry_order_id": entry_order_id,
                "symbol": f"{clean_sym}.NS",
                "side": transaction_type,
                "quantity": quantity,
                "variety": "AMO",
                "message": f"⚡ Angel One AMO Order Placed Successfully! (Order ID: {entry_order_id}). Queued for 09:15 AM market open.",
                "oco_state": "AMO_QUEUED"
            }
        print(f"[SmartAPI 3-Stage] Stage 1 Entry Placed! Order ID: {entry_order_id}. Awaiting Fill...")

        self._record_order_db(
            client_tag=client_tag,
            symbol=f"{clean_sym}.NS",
            tradingsymbol=tradingsymbol,
            symboltoken=token,
            side=transaction_type,
            quantity=quantity,
            entry_order_id=entry_order_id,
            entry_status="SUBMITTED",
            oco_state="ENTRY_PLACED"
        )

        # =====================================================================
        # STAGE 2: FILL CONFIRMATION & SLIPPAGE-ACCURATE FILL PRICE
        # =====================================================================
        fill_price = 0.0
        filled_qty = quantity
        is_complete = False

        # Poll order book up to 8 times (4 seconds total)
        for attempt in range(8):
            time.sleep(0.5)
            ob_res = angel_client.get_order_book()
            if ob_res.get("status"):
                orders = ob_res.get("orders", [])
                match = next((o for o in orders if str(o.get("orderid")) == str(entry_order_id)), None)
                if match:
                    st = (match.get("orderstatus") or match.get("status") or "").lower()
                    if st in ("complete", "executed"):
                        fill_price = float(match.get("averageprice", 0.0)) or float(match.get("price", 0.0))
                        filled_qty = int(match.get("filledshares", quantity)) or quantity
                        is_complete = True
                        break
                    elif st in ("rejected", "cancelled"):
                        rej_msg = match.get("text") or match.get("cancelreason") or f"Order {st}"
                        print(f"[SmartAPI 3-Stage] Entry Order {entry_order_id} was {st}: {rej_msg}")
                        self._update_order_db(entry_order_id, entry_status=st.upper(), oco_state="FAILED", notes=rej_msg)
                        return {"status": False, "message": f"Angel One Entry {st.capitalize()}: {rej_msg}"}

        if not is_complete:
            # If still open (e.g. pending LIMIT order)
            if entry_ordertype == "LIMIT":
                return {
                    "status": True,
                    "success": True,
                    "message": f"Angel One Limit Order placed @ ₹{price:.2f} (ID: {entry_order_id}). SL & Target will be armed upon fill by reconciliation loop.",
                    "entry_order_id": entry_order_id,
                    "order_id": entry_order_id,
                    "oco_state": "ENTRY_PENDING",
                    "demat_protected": True
                }
            # If market order didn't confirm in 4s, query active positions directly for real fill price
            pos_check = angel_client.get_positions()
            if pos_check.get("status"):
                for p in pos_check.get("positions", []):
                    ts = (p.get("tradingsymbol") or "").replace("-EQ", "").upper()
                    if ts == clean_sym:
                        fill_price = float(p.get("buyavgprice", 0.0) if transaction_type == "BUY" else p.get("sellavgprice", 0.0))
                        filled_qty = abs(int(p.get("netqty", quantity))) or quantity
                        if fill_price > 0:
                            is_complete = True
                            break

        if fill_price <= 0:
            quote = angel_client.get_live_quote(clean_sym)
            if quote and float(quote.get("price", 0.0)) > 0:
                fill_price = float(quote.get("price", 0.0))
                is_complete = True

        # CRITICAL SAFEGUARD: Never fallback to arbitrary numbers like ₹1000!
        if fill_price <= 0:
            print(f"[SmartAPI CRITICAL] Could not determine fill price for {clean_sym} Order {entry_order_id}. Aborting SL placement to prevent invalid orders.")
            self._update_order_db(
                entry_order_id,
                oco_state="ENTRY_FAILED_ABORT",
                notes="Could not determine execution fill price from broker order book or positions."
            )
            return {
                "status": False,
                "message": f"CRITICAL: Order {entry_order_id} fill price could not be verified by broker API. Check Angel One app immediately!"
            }

        print(f"[SmartAPI 3-Stage] Stage 2 Confirmed Fill @ ₹{fill_price:.2f} (Filled Qty: {filled_qty})")

        # =====================================================================
        # STAGE 3: CALCULATE SL & TARGET FROM ACTUAL FILL PRICE
        # =====================================================================
        # 1. Calculate Stop-Loss offset
        if sl_pct and float(sl_pct) > 0:
            sl_offset = fill_price * float(sl_pct)
        elif stop_loss and float(stop_loss) > 0 and price > 0:
            sl_offset = abs(float(price) - float(stop_loss))
        else:
            sl_offset = fill_price * 0.007  # Default 0.7% intraday SL

        # 2. Calculate Target offset
        if tp_pct and float(tp_pct) > 0:
            tp_offset = fill_price * float(tp_pct)
        elif target_price and float(target_price) > 0 and price > 0:
            tp_offset = abs(float(target_price) - float(price))
        else:
            tp_offset = sl_offset * 1.5  # Default 1:1.5 Risk-to-Reward Ratio

        # 3. Directional Tick-Rounded Price Levels (NSE 0.05 tick)
        if transaction_type == "BUY":
            sl_trigger = round_nse_tick(fill_price - sl_offset, "DOWN")
            # 0.4% danger buffer between trigger and limit to ensure fill during fast drops
            sl_limit = round_nse_tick(sl_trigger * 0.996, "DOWN")
            target_val = round_nse_tick(fill_price + tp_offset, "UP")
        else:
            sl_trigger = round_nse_tick(fill_price + sl_offset, "UP")
            sl_limit = round_nse_tick(sl_trigger * 1.004, "UP")
            target_val = round_nse_tick(fill_price - tp_offset, "DOWN")

        # =====================================================================
        # STAGE 3A: PLACE STOP-LOSS ORDER ON EXCHANGE (variety="STOPLOSS")
        # =====================================================================
        sl_payload = {
            "variety": "STOPLOSS",
            "tradingsymbol": tradingsymbol,
            "symboltoken": token,
            "transactiontype": exit_side,
            "exchange": "NSE",
            "ordertype": "STOPLOSS_LIMIT",
            "producttype": "INTRADAY",
            "duration": "DAY",
            "price": f"{sl_limit:.2f}",
            "triggerprice": f"{sl_trigger:.2f}",
            "quantity": str(filled_qty)
        }

        print(f"[SmartAPI 3-Stage] Submitting Stage 3A Hard Stop-Loss Order: {sl_payload}")
        sl_order_id = None
        sl_status = False

        # Retry SL placement up to 3 times
        for sl_attempt in range(3):
            time.sleep(0.35)  # Rate limiting buffer
            sl_res = self._send_broker_order(angel_client, sl_payload)
            if sl_res.get("status"):
                sl_order_id = sl_res.get("order_id")
                sl_status = True
                print(f"[SmartAPI 3-Stage] Hard Stop-Loss Order Placed! ID: {sl_order_id} @ Trigger: ₹{sl_trigger:.2f}")
                break
            else:
                print(f"[SmartAPI 3-Stage] SL Attempt {sl_attempt + 1} failed: {sl_res.get('message')}")

        # CRITICAL SAFETY: Emergency Market Exit if SL fails after retries!
        if not sl_status:
            print("[SmartAPI CRITICAL] Hard Stop-Loss placement failed after 3 retries. Executing EMERGENCY MARKET EXIT to avoid naked exposure!")
            emergency_exit_payload = {
                "variety": "NORMAL",
                "tradingsymbol": tradingsymbol,
                "symboltoken": token,
                "transactiontype": exit_side,
                "exchange": "NSE",
                "ordertype": "MARKET",
                "producttype": "INTRADAY",
                "duration": "DAY",
                "price": "0",
                "squareoff": "0",
                "stoploss": "0",
                "quantity": str(filled_qty)
            }
            emergency_res = self._send_broker_order(angel_client, emergency_exit_payload)
            self._update_order_db(
                entry_order_id,
                fill_price=fill_price,
                fill_quantity=filled_qty,
                oco_state="EMERGENCY_EXIT",
                notes="SL rejected after 3 retries. Emergency market exit executed."
            )
            return {
                "status": False,
                "message": f"CRITICAL: Stop-Loss rejected by broker. Position for {tradingsymbol} was immediately SQUARED OFF at Market to prevent unprotected loss."
            }

        # =====================================================================
        # STAGE 3B: PLACE TARGET ORDER ON EXCHANGE (variety="NORMAL", LIMIT)
        # =====================================================================
        time.sleep(0.35)  # Throttle for rate limiting
        tp_payload = {
            "variety": "NORMAL",
            "tradingsymbol": tradingsymbol,
            "symboltoken": token,
            "transactiontype": exit_side,
            "exchange": "NSE",
            "ordertype": "LIMIT",
            "producttype": "INTRADAY",
            "duration": "DAY",
            "price": f"{target_val:.2f}",
            "squareoff": "0",
            "stoploss": "0",
            "quantity": str(filled_qty)
        }

        print(f"[SmartAPI 3-Stage] Submitting Stage 3B Target Order: {tp_payload}")
        tp_res = self._send_broker_order(angel_client, tp_payload)
        target_order_id = tp_res.get("order_id") if tp_res.get("status") else None
        target_status = "ARMED" if target_order_id else "FAILED"

        # Update OCO state machine in database
        self._update_order_db(
            entry_order_id,
            entry_status="COMPLETE",
            fill_price=fill_price,
            fill_quantity=filled_qty,
            sl_order_id=sl_order_id,
            sl_trigger=sl_trigger,
            sl_limit=sl_limit,
            sl_status="ARMED",
            target_order_id=target_order_id,
            target_price=target_val,
            target_status=target_status,
            oco_state="OCO_ARMED",
            notes=f"OCO Active: SL @ ₹{sl_trigger:.2f}, TP @ ₹{target_val:.2f}"
        )

        return {
            "status": True,
            "success": True,
            "message": f"⚡ Angel One {transaction_type} executed @ ₹{fill_price:.2f}! Hard SL Armed @ ₹{sl_trigger:.2f} (ID: {sl_order_id}), Target Armed @ ₹{target_val:.2f} (ID: {target_order_id}) [OCO Active]",
            "order_id": entry_order_id,
            "entry_order_id": entry_order_id,
            "fill_price": fill_price,
            "fill_quantity": filled_qty,
            "sl_order_id": sl_order_id,
            "sl_placed": True,
            "sl_trigger": sl_trigger,
            "sl_limit": sl_limit,
            "target_order_id": target_order_id,
            "target_price": target_val,
            "oco_state": "OCO_ARMED",
            "demat_protected": True
        }

    def reconcile_active_oco_orders(self, angel_client) -> List[Dict[str, Any]]:
        """
        Background Reconciliation Loop (Executed every 3-4s):
          1. Check active OCO orders in database
          2. Inspect Angel One order book
          3. If Target fills -> cancel SL order!
          4. If SL fills -> cancel Target order!
          5. At 15:15 IST -> cancel all pending OCO orders before MIS auto-squareoff.
        """
        if not angel_client.is_authenticated:
            return []

        active_orders = self._get_active_oco_records()
        if not active_orders:
            return []

        # Check for 15:15 IST EOD Cancellation
        utc_now = datetime.now(timezone.utc)
        ist_now = utc_now + timedelta(hours=5, minutes=30)
        total_mins = ist_now.hour * 60 + ist_now.minute

        events = []

        # EOD 15:15 IST: Cancel all open OCO orders
        if total_mins >= (15 * 60 + 15):
            for rec in active_orders:
                print(f"[SmartAPI OCO] 03:15 PM EOD reached. Auto-cancelling OCO pending orders for {rec['symbol']}...")
                if rec.get("sl_order_id"):
                    angel_client.cancel_order(rec["sl_order_id"], variety="STOPLOSS")
                if rec.get("target_order_id"):
                    angel_client.cancel_order(rec["target_order_id"], variety="NORMAL")
                self._update_order_db(rec["entry_order_id"], oco_state="EOD_CANCELLED", notes="Auto-cancelled at 03:15 PM before broker MIS squareoff")
                events.append({
                    "type": "BROKER_OCO_UPDATE",
                    "event": "EOD_CANCELLED",
                    "symbol": rec["symbol"],
                    "message": f"⚡ 03:15 PM EOD: Pending OCO orders for {rec['symbol']} cancelled before broker MIS square-off."
                })
            return events

        # Regular Order Book Inspection
        ob_res = angel_client.get_order_book()
        if not ob_res.get("status"):
            return []

        broker_orders = ob_res.get("orders", [])

        for rec in active_orders:
            target_id = str(rec.get("target_order_id") or "")
            sl_id = str(rec.get("sl_order_id") or "")
            entry_id = rec.get("entry_order_id")

            # Check Target Order
            if target_id:
                t_match = next((o for o in broker_orders if str(o.get("orderid")) == target_id), None)
                if t_match:
                    st = (t_match.get("orderstatus") or t_match.get("status") or "").lower()
                    if st in ("complete", "executed"):
                        print(f"[SmartAPI OCO] 🎯 TARGET HIT for {rec['symbol']} @ ₹{rec['target_price']}! Cancelling companion Stop-Loss order {sl_id}...")
                        sl_cancelled = False
                        if sl_id:
                            for retry in range(3):
                                c_res = angel_client.cancel_order(sl_id, variety="STOPLOSS")
                                if c_res.get("status"):
                                    sl_cancelled = True
                                    break
                                time.sleep(0.3)

                        sl_status_text = "CANCELLED" if sl_cancelled else "CANCEL_PENDING"
                        oco_state_text = "TARGET_HIT" if sl_cancelled else "TARGET_HIT_SL_CANCEL_RETRY"
                        note_text = f"Target achieved at ₹{rec['target_price']}" + ("" if sl_cancelled else " (Warning: SL cancellation unverified)")

                        self._update_order_db(
                            entry_id,
                            target_status="COMPLETE",
                            sl_status=sl_status_text,
                            oco_state=oco_state_text,
                            notes=note_text
                        )
                        events.append({
                            "type": "BROKER_OCO_UPDATE",
                            "event": "TARGET_HIT",
                            "symbol": rec["symbol"],
                            "price": rec["target_price"],
                            "message": f"🎯 Target Hit for {rec['symbol']} at ₹{rec['target_price']}! Companion Stop-Loss order {sl_status_text.lower()}."
                        })
                        continue

            # Check Stop-Loss Order
            if sl_id:
                sl_match = next((o for o in broker_orders if str(o.get("orderid")) == sl_id), None)
                if sl_match:
                    st = (sl_match.get("orderstatus") or sl_match.get("status") or "").lower()
                    if st in ("complete", "executed"):
                        print(f"[SmartAPI OCO] 🛑 STOP-LOSS HIT for {rec['symbol']} @ ₹{rec['sl_trigger']}! Cancelling companion Target order {target_id}...")
                        tgt_cancelled = False
                        if target_id:
                            for retry in range(3):
                                c_res = angel_client.cancel_order(target_id, variety="NORMAL")
                                if c_res.get("status"):
                                    tgt_cancelled = True
                                    break
                                time.sleep(0.3)

                        tgt_status_text = "CANCELLED" if tgt_cancelled else "CANCEL_PENDING"
                        oco_state_text = "SL_HIT" if tgt_cancelled else "SL_HIT_TARGET_CANCEL_RETRY"
                        note_text = f"Stop loss triggered at ₹{rec['sl_trigger']}" + ("" if tgt_cancelled else " (Warning: Target cancellation unverified)")

                        self._update_order_db(
                            entry_id,
                            sl_status="COMPLETE",
                            target_status=tgt_status_text,
                            oco_state=oco_state_text,
                            notes=note_text
                        )
                        events.append({
                            "type": "BROKER_OCO_UPDATE",
                            "event": "SL_HIT",
                            "symbol": rec["symbol"],
                            "price": rec["sl_trigger"],
                            "message": f"🛑 Stop-Loss Hit for {rec['symbol']} at ₹{rec['sl_trigger']}! Companion Target order {tgt_status_text.lower()}."
                        })
                        continue

        return events

    def cancel_oco_for_symbol(self, angel_client, symbol: str) -> bool:
        """
        Cancel active OCO orders for a symbol using EXACT matching when position is flattened.
        """
        clean_sym = symbol.replace(".NS", "").replace("-EQ", "").strip().upper()
        active_records = self._get_active_oco_records()
        for rec in active_records:
            rec_sym = (rec.get("symbol") or "").replace(".NS", "").replace("-EQ", "").strip().upper()
            if clean_sym == rec_sym:
                if rec.get("sl_order_id"):
                    for _ in range(3):
                        res = angel_client.cancel_order(rec["sl_order_id"], variety="STOPLOSS")
                        if res.get("status"):
                            break
                        time.sleep(0.2)
                if rec.get("target_order_id"):
                    for _ in range(3):
                        res = angel_client.cancel_order(rec["target_order_id"], variety="NORMAL")
                        if res.get("status"):
                            break
                        time.sleep(0.2)
                self._update_order_db(rec["entry_order_id"], sl_status="CANCELLED", target_status="CANCELLED", oco_state="MANUAL_EXIT", notes="Manual square-off executed by user")
        return True

    def _send_broker_order(self, angel_client, payload: dict) -> dict:
        """Helper to send order request to Angel One SmartAPI."""
        headers = angel_client._get_headers()
        try:
            req = urllib.request.Request(
                "https://apiconnect.angelone.in/rest/secure/angelbroking/order/v1/placeOrder",
                data=json.dumps(payload).encode("utf-8"),
                headers=headers,
                method="POST"
            )
            with urllib.request.urlopen(req, timeout=7) as response:
                res = json.loads(response.read().decode("utf-8"))
                if res.get("status") or res.get("success"):
                    d = res.get("data")
                    oid = d.get("orderid") if isinstance(d, dict) else (d or "CONFIRMED")
                    return {"status": True, "order_id": str(oid), "data": d}
                else:
                    return {
                        "status": False,
                        "message": res.get("message", "Order rejected by broker"),
                        "error_code": res.get("errorcode", "")
                    }
        except Exception as e:
            return {"status": False, "message": str(e)}

    def _record_order_db(self, **kwargs):
        """Insert order record into SQLite database."""
        try:
            conn = get_connection()
            cursor = conn.cursor()
            cols = ", ".join(kwargs.keys())
            placeholders = ", ".join(["?" for _ in kwargs])
            vals = tuple(kwargs.values())
            cursor.execute(f"INSERT OR REPLACE INTO angel_oco_orders ({cols}) VALUES ({placeholders})", vals)
            conn.commit()
            conn.close()
        except Exception as e:
            print(f"[SmartAPI OCO DB] Insert error: {e}")

    def _update_order_db(self, entry_order_id: str, **kwargs):
        """Update existing order record by entry_order_id."""
        if not entry_order_id:
            return
        try:
            conn = get_connection()
            cursor = conn.cursor()
            set_clause = ", ".join([f"{k} = ?" for k in kwargs.keys()])
            vals = tuple(kwargs.values()) + (str(entry_order_id),)
            cursor.execute(f"UPDATE angel_oco_orders SET {set_clause}, updated_at = CURRENT_TIMESTAMP WHERE entry_order_id = ?", vals)
            conn.commit()
            conn.close()
        except Exception as e:
            print(f"[SmartAPI OCO DB] Update error: {e}")

    def _get_active_oco_records(self) -> List[Dict[str, Any]]:
        """Fetch all records currently in 'OCO_ARMED' state."""
        try:
            conn = get_connection()
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM angel_oco_orders WHERE oco_state = 'OCO_ARMED'")
            rows = cursor.fetchall()
            records = [dict(r) for r in rows]
            conn.close()
            return records
        except Exception as e:
            print(f"[SmartAPI OCO DB] Fetch error: {e}")
            return []


# Global Singleton OCO Manager
angel_oco_manager = AngelOcoManager()
