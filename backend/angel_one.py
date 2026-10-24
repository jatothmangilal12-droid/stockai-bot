"""
Angel One SmartAPI Integration Adapter for Indian Markets (NSE / BSE).
Supports official SmartAPI authentication with TOTP, live market quotes, and 15m historical candles.
"""
import base64
import hashlib
import hmac
import json
import os
import struct
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

# Common NSE Instrument Tokens for Top Indian Stocks
NSE_TOKENS = {
    "RELIANCE.NS": "2885",
    "HDFCBANK.NS": "1333",
    "TCS.NS": "11536",
    "ICICIBANK.NS": "4963",
    "INFY.NS": "1594",
    "SBIN.NS": "3045",
    "BHARTIARTL.NS": "10604",
    "ITC.NS": "1660",
    "LT.NS": "11483",
    "AXISBANK.NS": "5900",
    "KOTAKBANK.NS": "1922",
    "TMCV.NS": "3456",
    "TMPV.NS": "3457",
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


class AngelOneClient:
    """Manages SmartAPI session and live NSE data retrieval."""

    def __init__(self, api_key: str = "", client_code: str = "", password: str = "", totp_secret: str = ""):
        self.api_key = api_key or os.getenv("ANGELONE_API_KEY", "")
        self.client_code = client_code or os.getenv("ANGELONE_CLIENT_CODE", "")
        self.password = password or os.getenv("ANGELONE_PASSWORD", "")
        self.totp_secret = totp_secret or os.getenv("ANGELONE_TOTP_SECRET", "")
        self.jwt_token: Optional[str] = None
        self.feed_token: Optional[str] = None
        self.refresh_token: Optional[str] = None
        self.is_authenticated = False

    def is_configured(self) -> bool:
        """Check if all required credentials are present."""
        return bool(self.api_key and self.client_code and self.password and self.totp_secret)

    def login(self) -> bool:
        """Authenticate with Angel One SmartAPI using Client Code, PIN, and TOTP."""
        if not self.is_configured():
            return False

        totp_code = generate_totp(self.totp_secret)
        if not totp_code:
            return False

        payload = {
            "clientcode": self.client_code,
            "password": self.password,
            "totp": totp_code
        }

        headers = {
            "Content-Type": "application/json",
            "Accept": "application/json",
            "X-UserType": "USER",
            "X-SourceID": "WEB",
            "X-ClientLocalIP": "127.0.0.1",
            "X-ClientPublicIP": "106.193.147.1",
            "X-MACAddress": "02:00:00:00:00:00",
            "X-PrivateKey": self.api_key
        }

        try:
            req = urllib.request.Request(
                LOGIN_ENDPOINT,
                data=json.dumps(payload).encode("utf-8"),
                headers=headers,
                method="POST"
            )
            with urllib.request.urlopen(req, timeout=8) as response:
                res = json.loads(response.read().decode("utf-8"))
                if res.get("status") and "data" in res:
                    data = res["data"]
                    self.jwt_token = data.get("jwtToken")
                    self.feed_token = data.get("feedToken")
                    self.refresh_token = data.get("refreshToken")
                    self.is_authenticated = True
                    print(f"[SmartAPI] Successfully logged in to Angel One for client {self.client_code}!")
                    return True
                else:
                    print(f"[SmartAPI] Login rejected: {res.get('message')}")
                    return False
        except Exception as e:
            print(f"[SmartAPI] Login network error: {e}")
            return False

    def get_live_quote(self, symbol: str) -> Optional[dict]:
        """Fetch real-time snapshot quote from SmartAPI for given stock."""
        token = NSE_TOKENS.get(symbol)
        if not token:
            return None

        if not self.is_authenticated and not self.login():
            return None

        headers = {
            "Content-Type": "application/json",
            "Accept": "application/json",
            "X-UserType": "USER",
            "X-SourceID": "WEB",
            "X-PrivateKey": self.api_key,
            "Authorization": f"Bearer {self.jwt_token}"
        }

        payload = {
            "mode": "LTP",
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
                        return {"price": ltp, "symbol": symbol, "source": "AngelOne"}
        except Exception as e:
            print(f"[SmartAPI] Quote fetch error for {symbol}: {e}")
        return None
