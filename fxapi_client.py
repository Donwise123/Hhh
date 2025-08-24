# fxapi_client.py
# Lightweight FXAPI wrapper: retry + idempotency + helpers.

import requests, time, uuid
from typing import Optional
from config import FXAPI_TOKEN, MAX_RETRIES

BASE = "https://fxapi.io"  # adapt if your provider uses different base

def _retry_post(path, payload, timeout=3):
    url = f"{BASE}{path}?token={FXAPI_TOKEN}"
    backoff = 0.05
    for attempt in range(MAX_RETRIES):
        try:
            r = requests.post(url, json=payload, timeout=timeout)
            r.raise_for_status()
            return r.json()
        except Exception:
            time.sleep(backoff)
            backoff = min(backoff*2, 1.0)
    raise RuntimeError(f"POST {path} failed after {MAX_RETRIES} retries")

def _retry_get(path, params=None, timeout=3):
    url = f"{BASE}{path}?token={FXAPI_TOKEN}"
    backoff = 0.05
    for attempt in range(MAX_RETRIES):
        try:
            r = requests.get(url, params=params, timeout=timeout)
            r.raise_for_status()
            return r.json()
        except Exception:
            time.sleep(backoff)
            backoff = min(backoff*2, 1.0)
    raise RuntimeError(f"GET {path} failed after {MAX_RETRIES} retries")

class FXAPI:
    def __init__(self):
        self.token = FXAPI_TOKEN

    def get_account(self):
        return _retry_get("/account")

    def get_quote(self, symbol: str):
        return _retry_get("/quotes", params={"symbols": symbol})

    def place_market(self, symbol: str, side: str, volume: float, sl: Optional[float]=None, tp: Optional[float]=None, client_id: Optional[str]=None):
        if client_id is None:
            client_id = str(uuid.uuid4())
        payload = {"symbol": symbol, "side": side, "volume": float(volume), "sl": sl, "tp": tp, "client_id": client_id}
        return _retry_post("/order", payload)

    def place_limit(self, symbol: str, side: str, volume: float, price: float, sl: Optional[float]=None, tp: Optional[float]=None, client_id: Optional[str]=None):
        if client_id is None:
            client_id = str(uuid.uuid4())
        payload = {"symbol": symbol, "side": side, "volume": float(volume), "price": float(price), "type":"limit", "sl":sl, "tp":tp, "client_id":client_id}
        return _retry_post("/order", payload)

    def modify_order(self, ticket: str, sl: Optional[float]=None, tp: Optional[float]=None):
        payload = {"ticket": ticket, "sl": sl, "tp": tp}
        return _retry_post("/modify", payload)

    def close_order(self, ticket: str, volume: Optional[float]=None):
        payload = {"ticket": ticket, "volume": volume}
        return _retry_post("/close", payload)

    def get_positions(self):
        return _retry_get("/positions")

    def get_position(self, ticket=None, symbol=None):
        res = self.get_positions()
        for p in res.get("positions", []):
            if ticket and str(p.get("ticket")) == str(ticket):
                return p
            if symbol and p.get("symbol") == symbol:
                return p
        return None

    def get_profit(self, ticket=None, symbol=None):
        p = self.get_position(ticket=ticket, symbol=symbol)
        if not p:
            return 0.0
        return float(p.get("profit", 0.0))        except Exception:
            time.sleep(backoff)
            backoff = min(backoff * 2, 1.0)
    raise RuntimeError(f"GET {path} failed after {MAX_RETRIES} retries")

class FXAPI:
    def __init__(self):
        self.token = FXAPI_TOKEN

    def get_account(self):
        return _retry_get("/account")

    def get_quote(self, symbol: str):
        # returns { "bid":..., "ask":..., "timestamp":... }
        return _retry_get("/quotes", params={"symbols": symbol})

    def place_market(self, symbol: str, side: str, volume: float, sl: Optional[float]=None, tp: Optional[float]=None, client_id: Optional[str]=None):
        """
        side: "buy" or "sell"
        returns dict with ticket/id and execution price
        """
        if client_id is None:
            client_id = str(uuid.uuid4())
        payload = {
            "symbol": symbol,
            "side": side,
            "volume": float(volume),
            "sl": sl,
            "tp": tp,
            "client_id": client_id
        }
        return _retry_post("/order", payload)

    def place_limit(self, symbol: str, side: str, volume: float, price: float, sl: Optional[float]=None, tp: Optional[float]=None, client_id: Optional[str]=None):
        if client_id is None:
            client_id = str(uuid.uuid4())
        payload = {
            "symbol": symbol,
            "side": side,
            "volume": float(volume),
            "price": float(price),
            "type": "limit",
            "sl": sl,
            "tp": tp,
            "client_id": client_id
        }
        return _retry_post("/order", payload)

    def modify_order(self, ticket: str, sl: Optional[float]=None, tp: Optional[float]=None):
        payload = {"ticket": ticket, "sl": sl, "tp": tp}
        return _retry_post("/modify", payload)

    def close_order(self, ticket: str, volume: Optional[float]=None):
        payload = {"ticket": ticket, "volume": volume}
        return _retry_post("/close", payload)

    def get_positions(self):
        return _retry_get("/positions")

    def get_position(self, ticket=None, symbol=None):
        ps = self.get_positions()
        if "positions" not in ps:
            return []
        for p in ps["positions"]:
            if ticket and str(p.get("ticket")) == str(ticket):
                return p
            if symbol and p.get("symbol") == symbol:
                return p
        return None

    def get_profit(self, ticket=None, symbol=None):
        p = self.get_position(ticket=ticket, symbol=symbol)
        if not p:
            return 0.0
        return float(p.get("profit", 0.0))
