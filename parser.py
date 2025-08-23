# parser.py - robust signal parser (regex + heuristics). Expand patterns as you see signal variants.

import re
from typing import Dict, Any, Optional

# common symbol map (user-friendly -> MT symbol)
SYMBOL_MAP = {
    "gold": "XAUUSD",
    "xau": "XAUUSD",
    "usd/jpy": "USDJPY",
    "nas100": "NAS100",
    "us30": "US30",
    "eurusd": "EURUSD"
}

ENTRY_RE = re.compile(r"\b(buy now|sell now|buy limit|sell limit|buy|sell)\b", re.IGNORECASE)
RANGE_RE = re.compile(r"(\d{2,5}(?:\.\d+)?)[\s–-]+(\d{2,5}(?:\.\d+)?)")
PRICE_RE = re.compile(r"@?\s*(\d{2,5}(?:\.\d+)?)")
SL_RE = re.compile(r"(?:sl[:\s]*|stop loss[:\s]*)(\d{2,5}(?:\.\d+)?)", re.IGNORECASE)
TP_RE = re.compile(r"(?:tp\d*[:\s]*)(\d{2,5}(?:\.\d+)?)", re.IGNORECASE)
CMD_RE = re.compile(r"(close half|close all|close full|partial close|breakeven|set breakeven|tighten sl|again|take profit now|tp now|hold 1/2)", re.IGNORECASE)
VIP_RE = re.compile(r"\b(vip|#vip|paid)\b", re.IGNORECASE)

def normalize_symbol(word: str) -> str:
    w = word.strip().lower()
    return SYMBOL_MAP.get(w, word.upper())

def parse_signal(text: str) -> Dict[str, Any]:
    """Return dict with standardized keys:
       symbol, side ('buy'/'sell'), entry_type ('market'/'limit'), price, price_range, sl, tps(list),
       commands(list), vip(bool), reply_to (optional)
    """
    data = {
        "raw": text,
        "symbol": None,
        "side": None,
        "entry_type": "market",
        "price": None,
        "price_range": None,
        "sl": None,
        "tps": [],
        "commands": [],
        "vip": False,
        "again": False
    }
    t = text.lower()

    # vip flag
    if VIP_RE.search(text):
        data["vip"] = True

    # commands
    for m in CMD_RE.finditer(text):
        cmd = m.group(1).lower()
        data["commands"].append(cmd)
        if "again" in cmd:
            data["again"] = True

    # entry
    ent = ENTRY_RE.search(text)
    if ent:
        raw_entry = ent.group(1).lower()
        if "limit" in raw_entry:
            data["entry_type"] = "limit"
        if "buy" in raw_entry:
            data["side"] = "buy"
        elif "sell" in raw_entry:
            data["side"] = "sell"

    # symbol heuristics: first known word matching symbol_map or uppercase tokens
    tokens = re.split(r"[\s,;]+", text)
    for tok in tokens[:6]:
        norm = tok.strip().lower()
        if norm in SYMBOL_MAP or re.match(r"^[a-z]{3,5}\d*$", norm):
            data["symbol"] = normalize_symbol(norm)
            break

    # price range
    rng = RANGE_RE.search(text)
    if rng:
        p1 = float(rng.group(1))
        p2 = float(rng.group(2))
        data["price_range"] = (min(p1, p2), max(p1, p2))
        data["price"] = (p1 + p2) / 2.0
        data["entry_type"] = "limit"

    # single price
    p = PRICE_RE.search(text)
    if p and not data["price"]:
        try:
            data["price"] = float(p.group(1))
        except:
            pass

    # SL
    s = SL_RE.search(text)
    if s:
        try:
            data["sl"] = float(s.group(1))
        except:
            pass

    # TPs (multiple)
    for m in TP_RE.finditer(text):
        try:
            data["tps"].append(float(m.group(1)))
        except:
            pass

    # fallback: if symbol still None look for common words
    if not data["symbol"]:
        # check for known words in message
        for name in SYMBOL_MAP:
            if name in text.lower():
                data["symbol"] = normalize_symbol(name)
                break

    return data
