# parser.py
import re
from typing import Dict, Any

SYMBOL_MAP = {
    "gold": "XAUUSD", "xau": "XAUUSD",
    "eurusd":"EURUSD","gbpusd":"GBPUSD","usd/jpy":"USDJPY","usdchf":"USDCHF",
    "nas100":"NAS100","us30":"US30","us500":"US500"
}

ENTRY_RE = re.compile(r"\b(buy now|sell now|buy limit|sell limit|buy|sell)\b", re.IGNORECASE)
RANGE_RE = re.compile(r"(\d{2,6}(?:\.\d+)?)[\s–-]+(\d{2,6}(?:\.\d+)?)")
PRICE_RE = re.compile(r"@?\s*(\d{2,6}(?:\.\d+)?)")
SL_RE = re.compile(r"(?:sl[:\s]*|stop loss[:\s]*)(\d{2,6}(?:\.\d+)?)", re.IGNORECASE)
TP_RE = re.compile(r"(?:tp\d*[:\s]*)(\d{2,6}(?:\.\d+)?)", re.IGNORECASE)
CMD_RE = re.compile(r"(close half|close all|close full|partial close|breakeven|set breakeven|tighten sl|again|take profit now|tp now|hold 1/2)", re.IGNORECASE)
VIP_RE = re.compile(r"\b(vip|#vip|paid)\b", re.IGNORECASE)
VIP_SHORT_RE = re.compile(r"^\s*(?P<sym>[A-Za-z0-9\./]{2,12})\s+(?P<side>buy|sell)\s+now\s*$", re.IGNORECASE)

def normalize_symbol(word: str) -> str:
    w = word.strip().lower()
    return SYMBOL_MAP.get(w, word.upper())

def detect_short_vip(text: str):
    m = VIP_SHORT_RE.match(text.strip())
    if not m:
        return None
    sym_raw = m.group("sym").lower()
    sym = normalize_symbol(sym_raw)
    side = m.group("side").lower()
    return {
        "raw": text,
        "symbol": sym,
        "side": side,
        "entry_type": "market",
        "price": None,
        "price_range": None,
        "sl": None,
        "tps": [],
        "commands": [],
        "vip": True,
        "again": False
    }

def parse_signal(text: str) -> Dict[str, Any]:
    data = {"raw": text, "symbol": None, "side": None, "entry_type":"market", "price":None, "price_range":None, "sl":None, "tps":[], "commands":[], "vip":False, "again":False}
    if VIP_RE.search(text):
        data["vip"] = True
    for m in CMD_RE.finditer(text):
        cmd = m.group(1).lower()
        data["commands"].append(cmd)
        if "again" in cmd: data["again"] = True
    ent = ENTRY_RE.search(text)
    if ent:
        raw_entry = ent.group(1).lower()
        data["entry_type"] = "limit" if "limit" in raw_entry else "market"
        if "buy" in raw_entry: data["side"] = "buy"
        elif "sell" in raw_entry: data["side"] = "sell"
    tokens = re.split(r"[\s,;]+", text)
    for tok in tokens[:8]:
        norm = tok.strip().lower()
        if norm in SYMBOL_MAP or re.match(r"^[a-z]{3,6}\d*$", norm):
            data["symbol"] = normalize_symbol(norm); break
    rng = RANGE_RE.search(text)
    if rng:
        p1 = float(rng.group(1)); p2 = float(rng.group(2))
        data["price_range"] = (min(p1,p2), max(p1,p2)); data["price"] = (p1+p2)/2.0; data["entry_type"]="limit"
    p = PRICE_RE.search(text)
    if p and not data["price"]:
        try: data["price"] = float(p.group(1))
        except: pass
    s = SL_RE.search(text)
    if s:
        try: data["sl"] = float(s.group(1))
        except: pass
    for m in TP_RE.finditer(text):
        try: data["tps"].append(float(m.group(1)))
        except: pass
    if not data["symbol"]:
        for name in SYMBOL_MAP:
            if name in text.lower():
                data["symbol"] = normalize_symbol(name); break
    return data        "entry_type": "market",
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
