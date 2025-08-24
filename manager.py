# manager.py
import json, time, threading
from typing import Dict, Any
from fxapi_client import FXAPI
from config import LOG_CSV, STATE_JSON, NEAR_MISS_PIPS, VIP_PROFIT_TRAIL_PIPS, TP1_THRESHOLD_PERCENT, MAX_CONCURRENT_PER_SYMBOL

fx = FXAPI()
_lock = threading.Lock()

_state = {"processed_messages": set(), "open_trades": {}, "trade_history": []}

def save_state():
    with _lock:
        try:
            s = _state.copy()
            s["processed_messages"] = list(s["processed_messages"])
            with open(STATE_JSON, "w") as f:
                json.dump(s, f, default=str, indent=2)
        except Exception as e:
            print("State save error:", e)

def load_state():
    try:
        with open(STATE_JSON, "r") as f:
            s = json.load(f)
            s["processed_messages"] = set(s.get("processed_messages", []))
            _state.update(s)
    except FileNotFoundError:
        pass

load_state()

def log_trade_row(row: Dict[str, Any]):
    import csv, os
    header = ["time","action","symbol","side","volume","price","sl","tp","ticket","notes"]
    exists = os.path.exists(LOG_CSV)
    with open(LOG_CSV, "a", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=header)
        if not exists:
            writer.writeheader()
        writer.writerow(row)

def calculate_lot(balance: float, last_result: str) -> float:
    if balance <= 15:
        return 0.01
    elif 16 <= balance <= 49:
        percent = 40 if last_result == "loss" else 50
    else:
        percent = 50
    lots = max(0.01, round((balance * percent / 100) / 100, 2))
    return lots

def open_trade_from_signal(msg_id: str, signal: Dict[str, Any], last_result: str = "win"):
    if msg_id in _state["processed_messages"]:
        return None
    _state["processed_messages"].add(msg_id)

    sym = signal["symbol"]; side = signal["side"]
    entry_type = signal.get("entry_type", "market")
    sl = signal.get("sl"); tps = signal.get("tps", [])
    price = signal.get("price"); price_range = signal.get("price_range")
    vip = signal.get("vip", False); again = signal.get("again", False)

    count_same = sum(1 for v in _state["open_trades"].values() if v.get("symbol")==sym)
    if count_same >= MAX_CONCURRENT_PER_SYMBOL and not again:
        print("Blocked: too many concurrent for", sym); save_state(); return None

    acct = fx.get_account()
    balance = float(acct.get("balance", 0.0)) if isinstance(acct, dict) else 0.0
    lot = calculate_lot(balance, last_result)

    tp1_block = False
    for v in _state["open_trades"].values():
        if v.get("symbol")==sym and v.get("side")==side and v.get("tp1"):
            ticket = v.get("ticket")
            profit = fx.get_profit(ticket=ticket) or 0.0
            tp1_profit = v.get("tp1_profit")
            if tp1_profit:
                progress = (profit / tp1_profit) * 100 if tp1_profit != 0 else 100
                if progress < TP1_THRESHOLD_PERCENT:
                    tp1_block = True; break
    if tp1_block and not again:
        print("Blocked by 75% TP1 rule for", sym); save_state(); return None

    client_id = f"{msg_id}-{int(time.time()*1000)}"
    result = None
    if entry_type == "limit" and price_range:
        low, high = price_range
        limit_price = low if side=="buy" else high
        q = fx.get_quote(sym)
        if q and "bid" in q and "ask" in q:
            current = (q["bid"] + q["ask"]) / 2.0
        else:
            current = price or limit_price
        if side == "buy":
            if abs(current - low) <= NEAR_MISS_PIPS or (current <= high and (current-low) <= NEAR_MISS_PIPS):
                result = fx.place_market(sym, side, lot, sl=sl, tp=(tps[0] if tps else None), client_id=client_id)
            else:
                result = fx.place_limit(sym, side, lot, price=limit_price, sl=sl, tp=(tps[0] if tps else None), client_id=client_id)
        else:
            if abs(current - high) <= NEAR_MISS_PIPS or (current >= low and (high-current) <= NEAR_MISS_PIPS):
                result = fx.place_market(sym, side, lot, sl=sl, tp=(tps[0] if tps else None), client_id=client_id)
            else:
                result = fx.place_limit(sym, side, lot, price=limit_price, sl=sl, tp=(tps[0] if tps else None), client_id=client_id)
    else:
        result = fx.place_market(sym, side, lot, sl=sl, tp=(tps[0] if tps else None), client_id=client_id)

    if result and isinstance(result, dict):
        ticket = result.get("ticket") or result.get("id") or client_id
        entry_price = float(result.get("price", 0.0)) if result.get("price") else price
        tp1 = tps[0] if tps else None
        tp1_profit = None
        if tp1 and entry_price:
            try:
                delta = abs(tp1 - entry_price)
                tp1_profit = delta * lot * 100
            except:
                tp1_profit = None

        _state["open_trades"][ticket] = {
            "ticket": ticket, "symbol": sym, "side": side, "entry_price": entry_price,
            "volume": lot, "sl": sl, "tp1": tp1, "tp_list": tps, "vip": vip, "msg_id": msg_id,
            "client_id": client_id, "opened_at": time.time(), "peak_profit": 0.0, "tp1_profit": tp1_profit
        }
        log_trade_row({"time": time.strftime("%Y-%m-%d %H:%M:%S"), "action":"open","symbol":sym,"side":side,"volume":lot,"price":entry_price,"sl":sl,"tp":tp1,"ticket":ticket,"notes":f"vip={vip}"})
        save_state()
        return ticket
    else:
        print("Order failed:", result)
        return None

def apply_command_to_trade(msg_id: str, signal: Dict[str, Any], command_text: str):
    target = None
    sym = signal.get("symbol")
    for t,info in _state["open_trades"].items():
        if sym and info.get("symbol")==sym:
            target = info; break
    if not target:
        if _state["open_trades"]:
            target = list(_state["open_trades"].values())[-1]
    if not target:
        print("No open trade for command", command_text); return False

    ticket = target["ticket"]; cmd = command_text.lower()
    if "close half" in cmd or "partial" in cmd or "50" in cmd:
        fx.close_order(ticket, volume=target["volume"]*0.5)
        log_trade_row({"time": time.strftime("%Y-%m-%d %H:%M:%S"), "action":"partial_close","symbol":target["symbol"], "side":target["side"], "volume": target["volume"]*0.5, "price":"", "sl":target["sl"], "tp":target.get("tp1"), "ticket":ticket, "notes":"cmd"})
    elif "close all" in cmd or "take profit now" in cmd or "tp now" in cmd:
        fx.close_order(ticket)
        h = _state["open_trades"].pop(ticket, None)
        if h:
            h["closed_at"] = time.time(); _state["trade_history"].append(h)
        log_trade_row({"time": time.strftime("%Y-%m-%d %H:%M:%S"), "action":"close","symbol":target["symbol"], "side":target["side"], "volume": target["volume"], "price":"", "sl":target["sl"], "tp":target.get("tp1"), "ticket":ticket, "notes":"cmd"})
    elif "breakeven" in cmd or "secure entry" in cmd:
        entry_price = target.get("entry_price")
        if entry_price:
            fx.modify_order(ticket, sl=entry_price, tp=target.get("tp1"))
            log_trade_row({"time": time.strftime("%Y-%m-%d %H:%M:%S"), "action":"breakeven","symbol":target["symbol"], "side":target["side"], "volume": target["volume"], "price":"", "sl":entry_price, "tp":target.get("tp1"), "ticket":ticket, "notes":"cmd"})
    elif "tighten" in cmd:
        curq = fx.get_quote(target["symbol"])
        if curq and "bid" in curq and "ask" in curq:
            curp = (curq["bid"] + curq["ask"])/2.0
            if target["side"]=="buy":
                new_sl = round(curp - 0.5, 5)
            else:
                new_sl = round(curp + 0.5, 5)
            fx.modify_order(ticket, sl=new_sl)
            log_trade_row({"time": time.strftime("%Y-%m-%d %H:%M:%S"), "action":"tighten_sl","symbol":target["symbol"], "side":target["side"], "volume": target["volume"], "price":"", "sl":new_sl, "tp":target.get("tp1"), "ticket":ticket, "notes":"cmd"})
    save_state(); return True

def watchdog_tick():
    for ticket, info in list(_state["open_trades"].items()):
        try:
            profit = fx.get_profit(ticket=ticket) or fx.get_profit(symbol=info.get("symbol")) or 0.0
            if profit > info.get("peak_profit", 0.0):
                info["peak_profit"] = profit
            if info.get("vip"):
                peak = info.get("peak_profit", 0.0)
                if peak - profit >= VIP_PROFIT_TRAIL_PIPS:
                    fx.close_order(ticket)
                    log_trade_row({"time": time.strftime("%Y-%m-%d %H:%M:%S"), "action":"vip_close","symbol":info["symbol"], "side":info["side"], "volume":info["volume"], "price":"","sl":info.get("sl"), "tp":info.get("tp1"), "ticket":ticket, "notes":"vip_trail_hit"})
                    h = _state["open_trades"].pop(ticket, None)
                    if h:
                        h["closed_at"] = time.time(); _state["trade_history"].append(h)
        except Exception as e:
            print("Watchdog error for", ticket, e)
    save_state()
