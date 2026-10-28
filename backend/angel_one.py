"""
Angel One SmartAPI Integration Adapter for Indian Markets (NSE / BSE).
Supports official SmartAPI authentication with TOTP, live market quotes, and 15m historical candles.
"""
import base64
import hashlib
import hmac
import json
import os
import socket
import struct
import threading
import time
import urllib.request
from datetime import datetime
from typing import Optional

# SmartAPI official endpoints
SMARTAPI_BASE = "https://apiconnect.angelone.in"
LOGIN_ENDPOINT = f"{SMARTAPI_BASE}/rest/auth/angelbroking/user/v1/loginByPassword"
REFRESH_ENDPOINT = f"{SMARTAPI_BASE}/rest/auth/angelbroking/jwt/v1/generateTokens"
QUOTE_ENDPOINT = f"{SMARTAPI_BASE}/rest/secure/angelbroking/market/v1/quote"
CANDLE_ENDPOINT = f"{SMARTAPI_BASE}/rest/secure/angelbroking/historical/v1/getCandleData"
ORDER_PLACE_ENDPOINT = f"{SMARTAPI_BASE}/rest/secure/angelbroking/order/v1/placeOrder"
ORDER_CANCEL_ENDPOINT = f"{SMARTAPI_BASE}/rest/secure/angelbroking/order/v1/cancelOrder"
ORDER_BOOK_ENDPOINT = f"{SMARTAPI_BASE}/rest/secure/angelbroking/order/v1/getOrderBook"
HOLDINGS_ENDPOINT = f"{SMARTAPI_BASE}/rest/secure/angelbroking/portfolio/v1/getAllHolding"
RMS_ENDPOINT = f"{SMARTAPI_BASE}/rest/secure/angelbroking/user/v1/getRMS"
POSITION_ENDPOINT = f"{SMARTAPI_BASE}/rest/secure/angelbroking/order/v1/getPosition"

# Comprehensive NSE Instrument Tokens for Top 110 Indian F&O & Liquid Stocks
NSE_TOKENS = {
    "ADANIENSOL.NS": "10217",
    "ADANIENT.NS": "25",
    "ADANIGREEN.NS": "3563",
    "ADANIPORTS.NS": "15083",
    "AMBUJACEM.NS": "1270",
    "ANGELONE.NS": "324",
    "APOLLOHOSP.NS": "157",
    "ASIANPAINT.NS": "236",
    "AUROPHARMA.NS": "275",
    "AXISBANK.NS": "5900",
    "BAJAJ-AUTO.NS": "16669",
    "BAJFINANCE.NS": "317",
    "BANKBARODA.NS": "4668",
    "BDL.NS": "2144",
    "BEL.NS": "383",
    "BHARATFORG.NS": "422",
    "BHARTIARTL.NS": "10604",
    "BHEL.NS": "438",
    "BPCL.NS": "526",
    "BRITANNIA.NS": "547",
    "BSE.NS": "19585",
    "CANBK.NS": "10794",
    "CDSL.NS": "21174",
    "CHOLAFIN.NS": "685",
    "CIPLA.NS": "694",
    "COALINDIA.NS": "20374",
    "COCHINSHIP.NS": "21508",
    "COFORGE.NS": "11543",
    "CUMMINSIND.NS": "1901",
    "DABUR.NS": "772",
    "DATAPATTNS.NS": "7358",
    "DIVISLAB.NS": "10940",
    "DIXON.NS": "21690",
    "DMART.NS": "19913",
    "DRREDDY.NS": "881",
    "EICHERMOT.NS": "910",
    "ENRIN.NS": "756871",
    "EXIDEIND.NS": "676",
    "GAIL.NS": "4717",
    "GRASIM.NS": "1232",
    "HAL.NS": "2303",
    "HCLTECH.NS": "7229",
    "HDFCBANK.NS": "1333",
    "HEROMOTOCO.NS": "1348",
    "HINDALCO.NS": "1363",
    "HINDUNILVR.NS": "1394",
    "ICICIBANK.NS": "4963",
    "IDEA.NS": "14366",
    "INFY.NS": "1594",
    "IOC.NS": "1624",
    "IRCON.NS": "4986",
    "IREDA.NS": "20261",
    "IRFC.NS": "2029",
    "ITC.NS": "1660",
    "JIOFIN.NS": "18143",
    "JSWENERGY.NS": "17869",
    "JSWSTEEL.NS": "11723",
    "KALYANKJIL.NS": "2955",
    "KAYNES.NS": "12092",
    "KOTAKBANK.NS": "1922",
    "KPITTECH.NS": "9683",
    "LT.NS": "11483",
    "LUPIN.NS": "10440",
    "M&M.NS": "2031",
    "MANKIND.NS": "15380",
    "MARICO.NS": "4067",
    "MARUTI.NS": "10999",
    "MAZDOCK.NS": "509",
    "MCX.NS": "31181",
    "NATIONALUM.NS": "6364",
    "NATIONALALUM.NS": "6364",
    "NBCC.NS": "31415",
    "NESTLEIND.NS": "17963",
    "NHPC.NS": "17400",
    "NMDC.NS": "15332",
    "NTPC.NS": "11630",
    "ONGC.NS": "2475",
    "PERSISTENT.NS": "18365",
    "PETRONET.NS": "11351",
    "PFC.NS": "14299",
    "PIDILITIND.NS": "2664",
    "PNB.NS": "10666",
    "POLYCAB.NS": "9590",
    "POWERGRID.NS": "14977",
    "POWERINDIA.NS": "18457",
    "RAILTEL.NS": "2431",
    "RECLTD.NS": "15355",
    "RELIANCE.NS": "2885",
    "RVNL.NS": "9552",
    "SAIL.NS": "2963",
    "SBIN.NS": "3045",
    "SHRIRAMFIN.NS": "4306",
    "SJVN.NS": "18883",
    "SUNPHARMA.NS": "3351",
    "SUZLON.NS": "12018",
    "TATACONSUM.NS": "3432",
    "TATAELXSI.NS": "3411",
    "TATAPOWER.NS": "3426",
    "TATASTEEL.NS": "3499",
    "TCS.NS": "11536",
    "TECHM.NS": "13538",
    "TITAN.NS": "3506",
    "TATAMOTORS.NS": "3456",
    "TMCV.NS": "3456",
    "TMPV.NS": "3456",
    "TRENT.NS": "1964",
    "TVSMOTOR.NS": "8479",
    "ULTRACEMCO.NS": "11532",
    "UNIONBANK.NS": "10753",
    "VBL.NS": "18921",
    "VEDL.NS": "3063",
    "WIPRO.NS": "3787",
    "ZOMATO.NS": "5097",
    "ETERNAL.NS": "5097",
    "ZYDUSLIFE.NS": "7929",
    "^NSEI": "99926000",
    "^NSEBANK": "99926009"
}


def generate_totp(secret: str) -> str:
    """Generate RFC 6238 6-digit TOTP code from base32 secret."""
    try:
        raw = secret.upper().replace(" ", "").strip()
        key = base64.b32decode(raw + "=" * (-len(raw) % 8))
        epoch_interval = int(time.time()) // 30
        msg = struct.pack(">Q", epoch_interval)
        h = hmac.new(key, msg, hashlib.sha1).digest()
        offset = h[-1] & 0x0F
        code = (struct.unpack(">I", h[offset:offset + 4])[0] & 0x7FFFFFFF) % 1000000
        return f"{code:06d}"
    except Exception as e:
        print(f"[SmartAPI] TOTP generation failed: {e}")
        return ""


_LOGIN_LOCK = threading.Lock()

class AngelOneClient:
    """Manages SmartAPI session and live NSE data retrieval."""

    def __init__(self, api_key: str = "", client_code: str = "", password: str = "", totp_secret: str = ""):
        self.api_key = api_key or os.getenv("ANGELONE_API_KEY", "KLcQJzrD")
        self.client_code = client_code or os.getenv("ANGELONE_CLIENT_CODE", "M207216")
        self.password = password or os.getenv("ANGELONE_PASSWORD", "1995")
        self.totp_secret = totp_secret or os.getenv("ANGELONE_TOTP_SECRET", "JXDOER6HYCVKM2HYRLRASLAFUM")
        self.jwt_token: Optional[str] = None
        self.feed_token: Optional[str] = None
        self.refresh_token: Optional[str] = None
        self.is_authenticated = False
        self._cached_public_ip: Optional[str] = None
        self._cached_local_ip: Optional[str] = None

    def _get_local_ip(self) -> str:
        if self._cached_local_ip:
            return self._cached_local_ip
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            s.settimeout(0.5)
            s.connect(('8.8.8.8', 80))
            ip = s.getsockname()[0]
            s.close()
            self._cached_local_ip = ip
            return ip
        except Exception:
            return "127.0.0.1"

    def _get_public_ip(self) -> str:
        env_ip = os.getenv("CLIENT_PUBLIC_IP", "").strip()
        if env_ip:
            return env_ip
        if self._cached_public_ip:
            return self._cached_public_ip
        try:
            req = urllib.request.Request("https://api.ipify.org?format=json")
            with urllib.request.urlopen(req, timeout=1.5) as resp:
                data = json.loads(resp.read().decode("utf-8"))
                ip = data.get("ip")
                if ip:
                    self._cached_public_ip = ip
                    return ip
        except Exception:
            pass
        return "15.206.37.199"

    def _get_headers(self, auth: bool = True) -> dict:
        headers = {
            "Content-Type": "application/json",
            "Accept": "application/json",
            "X-UserType": "USER",
            "X-SourceID": "WEB",
            "X-ClientLocalIP": self._get_local_ip(),
            "X-ClientPublicIP": self._get_public_ip(),
            "X-MACAddress": "02:00:00:00:00:00",
            "X-PrivateKey": self.api_key
        }
        if auth and self.jwt_token:
            headers["Authorization"] = f"Bearer {self.jwt_token}"
        return headers

    def is_configured(self) -> bool:
        """Check if all required credentials are present."""
        return bool(self.api_key and self.client_code and self.password and self.totp_secret)

    def login(self, force: bool = False) -> tuple[bool, str]:
        """Authenticate with Angel One SmartAPI using Client Code, PIN, and TOTP."""
        if not self.is_configured():
            return False, "Missing credentials. Configure API Key, Client Code, PIN, and TOTP in Settings."

        with _LOGIN_LOCK:
            if not force and self.is_authenticated and self.jwt_token:
                return True, "Already authenticated."

            totp_raw = self.totp_secret.replace(" ", "").strip()
            if len(totp_raw) == 6 and totp_raw.isdigit():
                totp_code = totp_raw
            else:
                totp_code = generate_totp(totp_raw)

            if not totp_code:
                return False, "Invalid TOTP Secret. Provide a valid Base32 key or current 6-digit OTP code."

            payload = {
                "clientcode": self.client_code,
                "password": self.password,
                "totp": totp_code
            }

            headers = self._get_headers(auth=False)

            try:
                req = urllib.request.Request(
                    LOGIN_ENDPOINT,
                    data=json.dumps(payload).encode("utf-8"),
                    headers=headers,
                    method="POST"
                )
                with urllib.request.urlopen(req, timeout=10) as response:
                    res = json.loads(response.read().decode("utf-8"))
                    if res.get("status") and "data" in res:
                        data = res["data"]
                        self.jwt_token = data.get("jwtToken")
                        self.feed_token = data.get("feedToken")
                        self.refresh_token = data.get("refreshToken")
                        self.is_authenticated = True
                        print(f"[SmartAPI] Successfully logged in to Angel One for client {self.client_code}!")
                        return True, "Connected to Angel One SmartAPI successfully!"
                    else:
                        msg = res.get("message") or "Authentication failed. Check your API Key, PIN, and TOTP."
                        print(f"[SmartAPI] Login rejected: {msg}")
                        return False, msg
            except urllib.error.HTTPError as e:
                try:
                    err_body = json.loads(e.read().decode("utf-8"))
                    msg = err_body.get("message") or str(e)
                except Exception:
                    msg = f"HTTP Error {e.code}: {e.reason}"
                print(f"[SmartAPI] Login HTTP error: {msg}")
                return False, msg
            except Exception as e:
                print(f"[SmartAPI] Login network error: {e}")
                return False, f"Network error connecting to Angel One: {e}"

    def _resolve_token(self, symbol: str) -> Optional[str]:
        """Resolve token from symbol regardless of .NS suffix, aliases, or formatting."""
        clean = symbol.replace("-EQ", "").strip().upper()
        if not clean.endswith(".NS") and not clean.startswith("^"):
            clean = f"{clean}.NS"
        
        # Check direct match
        token = NSE_TOKENS.get(clean) or NSE_TOKENS.get(clean.replace(".NS", ""))
        if token:
            return token
            
        # Check known aliases
        aliases = {
            "TATAMOTORS.NS": "3456",
            "TMCV.NS": "3456",
            "TMPV.NS": "3456",
            "ETERNAL.NS": "5097",
            "ZOMATO.NS": "5097"
        }
        return aliases.get(clean)

    def get_live_quote(self, symbol: str) -> Optional[dict]:
        """Fetch real-time snapshot quote from SmartAPI for given stock."""
        token = self._resolve_token(symbol)
        if not token:
            return None

        if not self.is_authenticated:
            ok, _ = self.login()
            if not ok:
                return None

        headers = self._get_headers()

        payload = {
            "mode": "FULL",
            "exchangeTokens": {
                "NSE": [token]
            }
        }

        try:
            req = urllib.request.Request(
                QUOTE_ENDPOINT,
                data=json.dumps(payload).encode("utf-8"),
                headers=headers,
                method="POST"
            )
            with urllib.request.urlopen(req, timeout=5) as response:
                res = json.loads(response.read().decode("utf-8"))
                if res.get("status") and "data" in res:
                    fetched = res["data"].get("fetched", [])
                    if fetched:
                        item = fetched[0]
                        ltp = float(item.get("ltp", 0.0))
                        pct = float(item.get("percentChange", 0.0))
                        return {
                            "price": ltp,
                            "symbol": symbol,
                            "percent_change": pct,
                            "high": float(item.get("high", 0.0)),
                            "low": float(item.get("low", 0.0)),
                            "volume": int(item.get("tradeVolume", 0)),
                            "source": "AngelOne"
                        }
        except Exception as e:
            print(f"[SmartAPI] Quote fetch error for {symbol}: {e}")
        return None

    def get_batch_quotes(self, symbols: list[str]) -> dict:
        """Fetch ultra-fast batch quotes for multiple NSE symbols in single API request."""
        if not self.is_authenticated:
            ok, _ = self.login()
            if not ok:
                return {}

        token_to_sym = {}
        for s in symbols:
            tok = self._resolve_token(s)
            if tok:
                token_to_sym[tok] = s

        if not token_to_sym:
            return {}

        headers = self._get_headers()

        tokens = list(token_to_sym.keys())[:50]
        payload = {
            "mode": "FULL",
            "exchangeTokens": {
                "NSE": tokens
            }
        }

        results = {}
        try:
            req = urllib.request.Request(
                QUOTE_ENDPOINT,
                data=json.dumps(payload).encode("utf-8"),
                headers=headers,
                method="POST"
            )
            with urllib.request.urlopen(req, timeout=5) as response:
                res = json.loads(response.read().decode("utf-8"))
                if res.get("status") and "data" in res:
                    fetched = res["data"].get("fetched", [])
                    for item in fetched:
                        tok = str(item.get("symbolToken"))
                        sym = token_to_sym.get(tok)
                        if sym:
                            results[sym] = {
                                "price": float(item.get("ltp", 0.0)),
                                "percent_change": float(item.get("percentChange", 0.0)),
                                "open": float(item.get("open", 0.0)),
                                "high": float(item.get("high", 0.0)),
                                "low": float(item.get("low", 0.0)),
                                "close": float(item.get("close", 0.0)),
                                "volume": int(item.get("tradeVolume", 0)),
                                "vwap": float(item.get("avgPrice", 0.0)),
                                "tot_buy": int(item.get("totBuyQuan", 0)),
                                "tot_sell": int(item.get("totSellQuan", 0)),
                                "source": "AngelOne"
                            }
        except Exception as e:
            print(f"[SmartAPI] Batch quote fetch error: {e}")

        return results

    def get_market_depth(self, symbol: str) -> dict:
        """Fetch Level 2 Market Depth (Best 5 Bids and Asks) + Whale institutional volume ratio."""
        token = self._resolve_token(symbol)
        if not token:
            return {"status": False, "message": f"Token not found for {symbol}"}

        if not self.is_authenticated:
            ok, msg = self.login()
            if not ok:
                return {"status": False, "message": f"Angel One authentication failed: {msg}"}

        headers = self._get_headers()

        payload = {
            "mode": "FULL",
            "exchangeTokens": {
                "NSE": [token]
            }
        }

        try:
            req = urllib.request.Request(
                QUOTE_ENDPOINT,
                data=json.dumps(payload).encode("utf-8"),
                headers=headers,
                method="POST"
            )
            with urllib.request.urlopen(req, timeout=6) as response:
                res = json.loads(response.read().decode("utf-8"))
                if res.get("status") and "data" in res:
                    fetched = res["data"].get("fetched", [])
                    if fetched:
                        item = fetched[0]
                        depth = item.get("depth", {})
                        bids = depth.get("buy", [])
                        asks = depth.get("sell", [])
                        tot_buy = float(item.get("totBuyQuan", 0.0))
                        tot_sell = float(item.get("totSellQuan", 0.0))
                        total_vol = tot_buy + tot_sell

                        buy_ratio = round((tot_buy / total_vol) * 100, 1) if total_vol > 0 else 50.0
                        sell_ratio = round((tot_sell / total_vol) * 100, 1) if total_vol > 0 else 50.0

                        # Institutional Whale Analysis
                        if buy_ratio >= 65.0:
                            whale_signal = "WHALE_ACCUMULATION"
                            whale_bias = "BULLISH"
                            whale_label = f"🐋 FII/DII Whale Accumulation ({buy_ratio}% Buy Vol)"
                        elif sell_ratio >= 65.0:
                            whale_signal = "WHALE_DISTRIBUTION"
                            whale_bias = "BEARISH"
                            whale_label = f"🚨 FII/DII Whale Dumping ({sell_ratio}% Sell Vol)"
                        else:
                            whale_signal = "NEUTRAL"
                            whale_bias = "BALANCED"
                            whale_label = f"⚖️ Balanced Order Book ({buy_ratio}% B / {sell_ratio}% S)"

                        big_bids = [b for b in bids if float(b.get("quantity", 0)) >= 2500]
                        big_asks = [a for a in asks if float(a.get("quantity", 0)) >= 2500]

                        return {
                            "status": True,
                            "symbol": symbol,
                            "ltp": float(item.get("ltp", 0.0)),
                            "percent_change": float(item.get("percentChange", 0.0)),
                            "net_change": float(item.get("netChange", 0.0)),
                            "trade_volume": int(item.get("tradeVolume", 0)),
                            "avg_price": float(item.get("avgPrice", 0.0)),
                            "bids": bids,
                            "asks": asks,
                            "tot_buy_quan": int(tot_buy),
                            "tot_sell_quan": int(tot_sell),
                            "buy_ratio": buy_ratio,
                            "sell_ratio": sell_ratio,
                            "whale_signal": whale_signal,
                            "whale_bias": whale_bias,
                            "whale_label": whale_label,
                            "big_buy_wall": bool(big_bids),
                            "big_sell_wall": bool(big_asks),
                            "feed_time": item.get("exchFeedTime", "")
                        }
        except Exception as e:
            print(f"[SmartAPI] Market depth error for {symbol}: {e}")
            return {"status": False, "message": str(e)}

        return {"status": False, "message": "No depth data returned"}

    def calculate_margin(self, symbol: str, price: float = 0.0) -> dict:
        """
        Calculate live 5x Intraday MIS Margin & Max Allowed Quantity.
        Eliminates 'Insufficient Funds' order rejections completely.
        """
        rms = self.get_rms()
        cash = rms.get("available_cash", 0.0)
        net = rms.get("net", cash)
        effective_funds = max(0.0, cash if cash > 0 else net)

        if price <= 0.0:
            quote = self.get_live_quote(symbol)
            if quote and quote.get("price", 0.0) > 0:
                price = float(quote["price"])
            else:
                price = 1000.0

        leverage = 5.0
        total_buying_power = round(effective_funds * leverage, 2)
        margin_per_share = round(price / leverage, 2) if price > 0 else 0.0

        max_5x_qty = int(total_buying_power // price) if price > 0 else 0

        qty_25 = max(1, int(max_5x_qty * 0.25)) if max_5x_qty >= 4 else (1 if max_5x_qty >= 1 else 0)
        qty_50 = max(1, int(max_5x_qty * 0.50)) if max_5x_qty >= 2 else (1 if max_5x_qty >= 1 else 0)
        qty_75 = max(1, int(max_5x_qty * 0.75)) if max_5x_qty >= 2 else (1 if max_5x_qty >= 1 else 0)

        return {
            "status": True,
            "symbol": symbol,
            "price": price,
            "available_cash": effective_funds,
            "leverage": leverage,
            "total_buying_power": total_buying_power,
            "margin_per_share": margin_per_share,
            "max_5x_qty": max_5x_qty,
            "tier_quantities": {
                "pct_25": qty_25,
                "pct_50": qty_50,
                "pct_75": qty_75,
                "pct_100": max_5x_qty
            },
            "sample_cost": {
                "for_1_share": margin_per_share,
                "for_max_qty": round(max_5x_qty * margin_per_share, 2)
            }
        }

    def get_holdings(self) -> dict:
        """Fetch user Demat CNC/Delivery holdings to track and protect existing investments."""
        if not self.is_authenticated:
            ok, _ = self.login()
            if not ok:
                return {"status": False, "message": "Broker not authenticated", "holdings": []}

        headers = self._get_headers()

        try:
            req = urllib.request.Request(HOLDINGS_ENDPOINT, headers=headers, method="GET")
            with urllib.request.urlopen(req, timeout=6) as response:
                res = json.loads(response.read().decode("utf-8"))
                if res.get("status") and "data" in res:
                    holdings = res["data"].get("holdings", [])
                    return {
                        "status": True,
                        "message": "Holdings fetched successfully",
                        "holdings": holdings,
                        "holding_symbols": [h.get("tradingsymbol", "").replace("-EQ", "") for h in holdings]
                    }
        except Exception as e:
            print(f"[SmartAPI] Holdings fetch error: {e}")
        return {"status": False, "message": "Failed to fetch holdings", "holdings": []}

    def get_rms(self) -> dict:
        """Fetch live account cash and available margin."""
        if not self.is_authenticated:
            ok, _ = self.login()
            if not ok:
                return {"status": False, "message": "Broker not authenticated", "net": 0.0}

        headers = self._get_headers()

        try:
            req = urllib.request.Request(RMS_ENDPOINT, headers=headers, method="GET")
            with urllib.request.urlopen(req, timeout=5) as response:
                res = json.loads(response.read().decode("utf-8"))
                if res.get("status") and "data" in res:
                    return {
                        "status": True,
                        "net": float(res["data"].get("net", 0.0)),
                        "available_cash": float(res["data"].get("availablecash", 0.0)),
                        "collateral": float(res["data"].get("collateral", 0.0))
                    }
        except Exception as e:
            print(f"[SmartAPI] RMS fetch error: {e}")
        return {"status": False, "message": "Failed to fetch RMS funds", "net": 0.0}

    def place_order(
        self,
        symbol: str,
        side: str,
        quantity: int,
        price: float = 0.0,
        stop_loss: Optional[float] = None,
        target_price: Optional[float] = None,
        sl_pct: Optional[float] = None,
        tp_pct: Optional[float] = None,
        order_type: str = "MARKET"
    ) -> dict:
        """
        Execute Institutional 3-Stage Order on Angel One SmartAPI:
          Stage 1: Submit Entry (MARKET / LIMIT)
          Stage 2: Fill Confirmation & Retrieve Actual Fill Price
          Stage 3: Place Dual OCO (Hard Stop-Loss + Target) with 0.05 tick size & buffer
        """
        from backend.broker_oco import angel_oco_manager
        return angel_oco_manager.execute_three_stage_order(
            angel_client=self,
            symbol=symbol,
            side=side,
            quantity=quantity,
            price=price,
            stop_loss=stop_loss,
            target_price=target_price,
            sl_pct=sl_pct,
            tp_pct=tp_pct,
            order_type=order_type
        )


    def cancel_order(self, order_id: str, variety: str = "NORMAL") -> dict:
        """Cancel an open order on Angel One SmartAPI."""
        if not self.is_authenticated:
            ok, msg = self.login()
            if not ok:
                return {"status": False, "message": msg}

        headers = self._get_headers()
        payload = {
            "variety": variety,
            "orderid": order_id
        }
        try:
            req = urllib.request.Request(
                ORDER_CANCEL_ENDPOINT,
                data=json.dumps(payload).encode("utf-8"),
                headers=headers,
                method="POST"
            )
            with urllib.request.urlopen(req, timeout=6) as response:
                res = json.loads(response.read().decode("utf-8"))
                return res
        except Exception as e:
            return {"status": False, "message": str(e)}

    def get_positions(self) -> dict:
        """Fetch live intraday positions directly from Angel One."""
        if not self.is_authenticated:
            ok, msg = self.login()
            if not ok:
                return {"status": False, "message": msg, "positions": []}

        headers = self._get_headers()
        try:
            req = urllib.request.Request(POSITION_ENDPOINT, headers=headers, method="GET")
            with urllib.request.urlopen(req, timeout=6) as response:
                res = json.loads(response.read().decode("utf-8"))
                if res.get("status") and "data" in res:
                    raw_positions = res["data"] or []
                    # Filter for active positions with net quantity
                    active = [p for p in raw_positions if int(p.get("netqty", 0)) != 0]
                    return {"status": True, "positions": active, "all_positions": raw_positions}
                return {"status": False, "message": res.get("message", "Failed to fetch positions"), "positions": []}
        except Exception as e:
            print(f"[SmartAPI] Get positions error: {e}")
            return {"status": False, "message": str(e), "positions": []}

    def square_off_all(self) -> dict:
        """
        Square off all active INTRADAY positions on Angel One SmartAPI immediately.
        Guaranteed to only square off MIS/INTRADAY positions and never Demat CNC holdings.
        """
        if not self.is_authenticated:
            ok, msg = self.login()
            if not ok:
                return {"status": False, "message": f"Angel One login required: {msg}", "squared_off_count": 0}

        pos_res = self.get_positions()
        if not pos_res.get("status"):
            return {"status": False, "message": f"Could not fetch positions: {pos_res.get('message')}", "squared_off_count": 0}

        positions = pos_res.get("positions", [])
        if not positions:
            return {"status": True, "message": "No active Angel One positions found to square off.", "squared_off_count": 0}

        squared_off = 0
        errors = []
        headers = self._get_headers()

        for pos in positions:
            try:
                prod = (pos.get("producttype") or "").upper()
                if prod != "INTRADAY":
                    continue  # Strict Demat Protection: NEVER touch Delivery holdings!

                net_qty = int(pos.get("netqty") or 0)
                if net_qty == 0:
                    continue

                sym = pos.get("tradingsymbol", "")
                token = str(pos.get("symboltoken", ""))
                side = "SELL" if net_qty > 0 else "BUY"
                qty = abs(net_qty)

                payload = {
                    "variety": "NORMAL",
                    "tradingsymbol": sym,
                    "symboltoken": token,
                    "transactiontype": side,
                    "exchange": pos.get("exchange", "NSE"),
                    "ordertype": "MARKET",
                    "producttype": "INTRADAY",
                    "duration": "DAY",
                    "price": "0",
                    "squareoff": "0",
                    "stoploss": "0",
                    "quantity": str(qty)
                }

                req = urllib.request.Request(
                    ORDER_PLACE_ENDPOINT,
                    data=json.dumps(payload).encode("utf-8"),
                    headers=headers,
                    method="POST"
                )
                with urllib.request.urlopen(req, timeout=6) as response:
                    res = json.loads(response.read().decode("utf-8"))
                    if res.get("status") or res.get("success"):
                        squared_off += 1
                    else:
                        errors.append(f"{sym}: {res.get('message')}")
            except Exception as e:
                errors.append(f"{pos.get('tradingsymbol')}: {e}")

        return {
            "status": True,
            "squared_off_count": squared_off,
            "message": f"Successfully squared off {squared_off} Angel One intraday positions.",
            "errors": errors
        }


    def get_order_book(self) -> dict:
        """Fetch daily order status history from Angel One."""
        if not self.is_authenticated:
            ok, _ = self.login()
            if not ok:
                return {"status": False, "orders": []}

        headers = self._get_headers()

        try:
            req = urllib.request.Request(ORDER_BOOK_ENDPOINT, headers=headers, method="GET")
            with urllib.request.urlopen(req, timeout=6) as response:
                res = json.loads(response.read().decode("utf-8"))
                if res.get("status") and "data" in res:
                    return {"status": True, "orders": res["data"]}
        except Exception as e:
            print(f"[SmartAPI] Order book error: {e}")
        return {"status": False, "orders": []}

