# manager.py - core decision engine & state persistence
import json
import time
import threading
from typing import Dict, Any
from fxapi_client import FXAPI
from config import LOG_CSV, STATE_JSON, NEAR_MISS_PIPS, VIP_PROFIT_TRAIL_PIPS, TP1_THRESHOLD_PERCENT, MAX_CONCURRENT_PER_SYMBOL

fx = FXAPI()
_lock = threading.Lock()

# persisted runtime state
_state = {
    "processed_messages": set(),   # message ids
    "open_trades": {},            # key: ticket or symbol+side -> trade metadata
    "trade_history": []           # list of closed trades
}

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

# risk calculation
def calculate_lot(balance: float, last_result: str) -> float:
    # last_result: "win" or "loss" or None
    if balance <= 15:
        return 0.01
    elif 16 <= balance <= 49:
        if last_result == "loss":
            percent = 40
        else:
            percent = 50
    else:
        percent = 50
    # convert percent of balance to lots via risk per pip formula
    # For simplicity: treat 1 lot risk conversion placeholder (user should tune for account contract size)
    # We'll return percent% of balance / 100 as lots (user can adjust)
    lots = max(0.01, round((balance * percent / 100) / 100, 2))
    return lots

def open_trade_from_signal(msg_id: str, signal: Dict[str, Any], last_result: str = "win"):
    """
    Core decision function: applies 75% TP1 rule, VIP handling, near-miss for limits, opens order.
    """
    # Idempotency
    if msg_id in _state["processed_messages"]:
        return None
    _state["processed_messages"].add(msg_id)

    sym = signal["symbol"]
    side = signal["side"] or ("buy" if "buy" in signal["raw"].lower() else "sell")
    entry_type = signal["entry_type"]
    sl = signal.get("sl")
    tps = signal.get("tps", [])
    price = signal.get("price")
    price_range = signal.get("price_range")
    vip = signal.get("vip", False)
    again = signal.get("again", False)

    # If symbol already has many open trades, limit
    count_same = sum(1 for v in _state["open_trades"].values() if v.get("symbol")==sym)
    if count_same >= MAX_CONCURRENT_PER_SYMBOL and not again:
        print("Blocked: too many concurrent trades for", sym)
        save_state()
        return None

    # get account balance
    acct = fx.get_account()
    balance = float(acct.get("balance", 0.0)) if isinstance(acct, dict) else acct.get("balance", 0.0)

    # lot sizing
    lot = calculate_lot(balance, last_result)

    # 75% TP1 rule: if there is an open trade of same symbol+dir with TP1 not yet 75% reached, block new trade
    # We compute for open trades
    tp1_block = False
    for k,v in _state["open_trades"].items():
        if v.get("symbol")==sym and v.get("side")==side and v.get("tp1"):
            tp1 = v["tp1"]
            entry_price = v["entry_price"]
            # compute target profit in pips approximate: (tp1 - entry) in points for direction
            # Use price units: we need to fetch current profit via FXAPI for that position
            progress = 0.0
            # approximate: ask fx.get_profit with ticket
            ticket = v.get("ticket")
            if ticket:
                profit = fx.get_profit(ticket=ticket)
                # use stored tp1_profit (in $) if available or approximate using difference
                target_profit = v.get("tp1_profit", None)
                if target_profit:
                    progress = (profit / target_profit) * 100 if target_profit != 0 else 0
                else:
                    progress = 100  # if unknown assume allowed
            if progress < TP1_THRESHOLD_PERCENT:
                tp1_block = True
                break
    if tp1_block and not again:
        print("Blocked by 75% TP1 rule for", sym, side)
        save_state()
        return None

    # If limit order with range, place limit or do near-miss market if within NEAR_MISS_PIPS
    result = None
    client_id = f"{msg_id}-{int(time.time()*1000)}"
    if entry_type == "limit" and price_range:
        low, high = price_range
        # decide limit price depending on side
        limit_price = low if side == "buy" else high
        # check current quote
        q = fx.get_quote(sym)
        if not q:
            print("No quote for", sym)
            return None
        current = (q.get("ask") + q.get("bid")) / 2.0 if q.get("ask") and q.get("bid") else q.get("ask") or q.get("bid")
        # If price within NEAR_MISS_PIPS of OTHER END -> market execute at current
        if side == "buy":
            # if price did not reach low but touched within NEAR_MISS_PIPS of high? rule was "2 pips close to other end"
            # Implementation: if current <= high and current - low <= NEAR_MISS_PIPS -> execute market
            if abs(current - low) <= NEAR_MISS_PIPS or (current <= high and (current - low) <= NEAR_MISS_PIPS):
                result = fx.place_market(sym, side, lot, sl=sl, tp= tps[0] if tps else None, client_id=client_id)
            else:
                result = fx.place_limit(sym, side, lot, price=limit_price, sl=sl, tp=(tps[0] if tps else None), client_id=client_id)
        else:
            if abs(current - high) <= NEAR_MISS_PIPS or (current >= low and (high - current) <= NEAR_MISS_PIPS):
                result = fx.place_market(sym, side, lot, sl=sl, tp= (tps[0] if tps else None), client_id=client_id)
            else:
                result = fx.place_limit(sym, side, lot, price=limit_price, sl=sl, tp=(tps[0] if tps else None), client_id=client_id)
    else:
        # Market entry
        result = fx.place_market(sym, side, lot, sl=sl, tp=(tps[0] if tps else None), client_id=client_id)

    # On success, record open trade
    if result and isinstance(result, dict):
        ticket = result.get("ticket") or result.get("order") or result.get("id") or client_id
        entry_price = float(result.get("price", 0.0)) if result.get("price") else price
        tp1 = tps[0] if tps else None
        # compute tp1_profit estimate (rough) for blocking logic: in $ — best-effort: leave None if cannot compute
        tp1_profit = None
        _state["open_trades"][ticket] = {
            "ticket": ticket,
            "symbol": sym,
            "side": side,
            "entry_price": entry_price,
            "volume": lot,
            "sl": sl,
            "tp1": tp1,
            "tp_list": tps,
            "vip": vip,
            "msg_id": msg_id,
            "client_id": client_id,
            "opened_at": time.time(),
            "peak_profit": 0.0,
            "tp1_profit": tp1_profit
        }
        log_trade_row({
            "time": time.strftime("%Y-%m-%d %H:%M:%S"),
            "action": "open",
            "symbol": sym,
            "side": side,
            "volume": lot,
            "price": entry_price,
            "sl": sl,
            "tp": tp1,
            "ticket": ticket,
            "notes": f"source_msg={msg_id} vip={vip}"
        })
        save_state()
        return ticket
    else:
        print("Order failed or unexpected response:", result)
        return None

# follow-up handlers
def apply_command_to_trade(msg_id: str, signal: Dict[str, Any], command_text: str):
    """
    Try to map to the most-likely open trade and apply command: close half, close all, breakeven, tighten sl
    """
    # mapping logic: if reply_to present or symbol+dir match, use it
    target = None
    sym = signal.get("symbol")
    side = signal.get("side")
    # prefer exact ticket mention if present in text
    for t, info in _state["open_trades"].items():
        if sym and info.get("symbol")==sym:
            target = info
            break
    if not target:
        # fallback: take most recent open trade
        if _state["open_trades"]:
            target = list(_state["open_trades"].values())[-1]

    if not target:
        print("No open trade found for command:", command_text)
        return False

    ticket = target["ticket"]
    cmd = command_text.lower()
    if "close half" in cmd or "partial" in cmd or "close 50" in cmd:
        fx.close_order(ticket, volume=target["volume"] * 0.5)
        log_trade_row({"time": time.strftime("%Y-%m-%d %H:%M:%S"), "action":"partial_close","symbol":target["symbol"], "side":target["side"], "volume": target["volume"]*0.5, "price":"", "sl":target["sl"], "tp":target.get("tp1"), "ticket":ticket, "notes":"partial via cmd"})
    elif "close all" in cmd or "take profit now" in cmd or "tp now" in cmd:
        fx.close_order(ticket)
        # move to history
        h = _state["open_trades"].pop(ticket, None)
        if h:
            h["closed_at"] = time.time()
            _state["trade_history"].append(h)
        log_trade_row({"time": time.strftime("%Y-%m-%d %H:%M:%S"), "action":"close","symbol":target["symbol"], "side":target["side"], "volume": target["volume"], "price":"", "sl":target["sl"], "tp":target.get("tp1"), "ticket":ticket, "notes":"close via cmd"})
    elif "breakeven" in cmd or "set breakeven" in cmd or "secure entry" in cmd:
        # move SL to entry price (approx)
        entry_price = target.get("entry_price")
        if entry_price:
            fx.modify_order(ticket, sl=entry_price, tp=target.get("tp1"))
            log_trade_row({"time": time.strftime("%Y-%m-%d %H:%M:%S"), "action":"breakeven","symbol":target["symbol"], "side":target["side"], "volume": target["volume"], "price":"", "sl":entry_price, "tp":target.get("tp1"), "ticket":ticket, "notes":"breakeven via cmd"})
    elif "tighten sl" in cmd or "tighten" in cmd:
        # attempt to move SL closer to current price by MAX_SLIPPAGE (approx)
        cur = fx.get_quote(target["symbol"])
        if cur:
            curp = (cur.get("ask") + cur.get("bid"))/2.0 if cur.get("ask") and cur.get("bid") else cur.get("ask") or cur.get("bid")
            # tighten towards price
            if target["side"] == "buy":
                new_sl = curp - 0.5  # example tighten 0.5 points; you can compute from pip size
            else:
                new_sl = curp + 0.5
            fx.modify_order(ticket, sl=new_sl)
            log_trade_row({"time": time.strftime("%Y-%m-%d %H:%M:%S"), "action":"tighten_sl","symbol":target["symbol"], "side":target["side"], "volume": target["volume"], "price":"", "sl":new_sl, "tp":target.get("tp1"), "ticket":ticket, "notes":"tighten via cmd"})
    save_state()
    return True

# watchdog-job called periodically by telegram_listener
def watchdog_tick():
    """
    Run internal checks:
      - Confirm pending orders / retry failed
      - Update peak profit for VIP trades and apply trailing protection
      - If VIP trade without SL and silent, watch for profit drop >=VIP_PROFIT_TRAIL_PIPS and close
    """
    # iterate open trades
    for ticket, info in list(_state["open_trades"].items()):
        try:
            # fetch latest profit
            profit = fx.get_profit(ticket=ticket) or fx.get_profit(symbol=info.get("symbol"))
            if profit is None:
                profit = 0.0
            # update peak
            if profit > info.get("peak_profit", 0):
                info["peak_profit"] = profit
            # VIP protection: if no recent follow-up and profit dropped >= VIP_PROFIT_TRAIL_PIPS -> close
            if info.get("vip"):
                peak = info.get("peak_profit", 0)
                if peak - profit >= VIP_PROFIT_TRAIL_PIPS:
                    fx.close_order(ticket)
                    log_trade_row({"time": time.strftime("%Y-%m-%d %H:%M:%S"), "action":"vip_close","symbol":info["symbol"], "side":info["side"], "volume":info["volume"], "price":"","sl":info.get("sl"), "tp":info.get("tp1"), "ticket":ticket, "notes":"vip trailing hit"})
                    # archive
                    h = _state["open_trades"].pop(ticket, None)
                    if h:
                        h["closed_at"] = time.time()
                        _state["trade_history"].append(h)
            # auto partial close rules etc can be implemented here as needed
        except Exception as e:
            print("Watchdog error for", ticket, e)
    save_state()
