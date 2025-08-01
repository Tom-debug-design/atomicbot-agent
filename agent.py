import os
import random
import time
import datetime
import requests

TOKENS = [
    "BTCUSDT", "ETHUSDT", "SOLUSDT", "BNBUSDT", "XRPUSDT", "ADAUSDT",
    "DOGEUSDT", "AVAXUSDT", "LINKUSDT", "TRXUSDT"
]
START_BALANCE = 900.0
DISCORD_WEBHOOK = os.environ.get("DISCORD_WEBHOOK", "https://discord.com/api/webhooks/...")
DEMO_MODE = True
STOP_LOSS_PCT = 0.07       # 7% fast stop loss
TRAIL_START_PCT = 0.03     # 3% gevinst før trailing
TRAIL_STEP_PCT = 0.02      # trailing margin
EDGE_TAP_THRESHOLD = 3     # Bytt strategi etter X tap på rad
REPORT_HOURS = [6]         # UTC 06:00 = dagsrapport

balance = START_BALANCE
holdings = {token: 0 for token in TOKENS}
entry = {token: None for token in TOKENS}
peak = {token: None for token in TOKENS}
trade_log = []
tap_counter = 0
last_hour = None
last_day = None
strategy = "RANDOM"

def send_discord(msg):
    try:
        requests.post(DISCORD_WEBHOOK, json={"content": msg})
    except Exception as e:
        print("DC error", e)

def get_price(token):
    base = {
        "BTCUSDT": 30000, "ETHUSDT": 1700, "SOLUSDT": 20, "BNBUSDT": 250, "XRPUSDT": 0.6,
        "ADAUSDT": 0.4, "DOGEUSDT": 0.07, "AVAXUSDT": 10, "LINKUSDT": 6, "TRXUSDT": 0.07
    }
    if token in base:
        return round(base[token] * random.uniform(0.97, 1.03), 2)
    return None

def select_strategy():
    global strategy, tap_counter
    # Rapid switch: bytt strategi ved flere tap på rad
    if tap_counter >= EDGE_TAP_THRESHOLD:
        old_strategy = strategy
        strategy = random.choice([s for s in ["RANDOM", "RSI", "EMA", "SCALP"] if s != strategy])
        send_discord(f"⚡️ ChunkyAI: Strategy switch: {old_strategy} → {strategy} etter {tap_counter} tap på rad!")
        tap_counter = 0
    return strategy

def calc_signal(token, strategy):
    price = get_price(token)
    if price is None:
        return None, "HOLD"
    if strategy == "RANDOM":
        return price, random.choice(["BUY", "SELL", "HOLD"])
    elif strategy == "RSI":
        rsi = random.uniform(10, 90)
        if rsi < 30: return price, "BUY"
        elif rsi > 70: return price, "SELL"
        else: return price, "HOLD"
    elif strategy == "EMA":
        ema = price * random.uniform(0.98, 1.02)
        if price < ema: return price, "BUY"
        else: return price, "SELL"
    elif strategy == "SCALP":
        if random.random() > 0.5: return price, "BUY"
        else: return price, "SELL"
    return price, "HOLD"

def now():
    return datetime.datetime.now(datetime.timezone.utc).strftime('%Y-%m-%d %H:%M:%S')

def handle_trade(token, action, price, strategy):
    global balance, tap_counter
    qty = round(balance / 10 / price, 6)
    pnl = 0
    edge_event = None

    if action == "BUY" and balance > price * qty:
        balance -= price * qty
        holdings[token] += qty
        entry[token] = price
        peak[token] = price
        send_discord(f"🟦 BUY {token}: {qty} @ ${price}, strategy: {strategy}, bal: ${round(balance,2)}")
        trade_log.append({"token": token, "action": "BUY", "price": price, "qty": qty, "strategy": strategy, "pnl": 0, "timestamp": now()})

    elif action == "SELL" and holdings[token] > 0:
        # PnL fra siste entry
        last_entry = entry[token] if entry[token] else price
        balance += price * holdings[token]
        pnl = (price - last_entry) * holdings[token]
        if pnl < 0:
            tap_counter += 1
        else:
            tap_counter = 0
        send_discord(f"🔴 SELL {token}: {holdings[token]} @ ${price}, PnL: {round(pnl,2)}, bal: ${round(balance,2)}")
        trade_log.append({"token": token, "action": "SELL", "price": price, "qty": holdings[token], "strategy": strategy, "pnl": pnl, "timestamp": now()})
        holdings[token] = 0
        entry[token] = None
        peak[token] = None
        # Reset edge events on sell
        edge_event = None

    return pnl, edge_event

def check_edge_exit(token, price):
    """ Returner ('SELL', 'trailing') eller ('SELL', 'stoploss') hvis edge utløst. """
    if holdings[token] > 0 and entry[token]:
        gain = (price - entry[token]) / entry[token]
        # Trailing stop: Peak følger kursen opp, selg på nedgang fra topp
        if gain > TRAIL_START_PCT:
            if price > peak[token]:
                peak[token] = price
            elif price < peak[token] * (1 - TRAIL_STEP_PCT):
                send_discord(f"⚡️ ChunkyAI: Trailing stop utløst – SELL {token} på ${price}!")
                return "SELL", "trailing"
        # Fast stop loss
        if gain < -STOP_LOSS_PCT:
            send_discord(f"⚡️ ChunkyAI: Stop loss utløst – SELL {token} på ${price} (PnL: {round(gain*100,2)}%)!")
            return "SELL", "stoploss"
    return "HOLD", None

def report(hourly=False, daily=False):
    realized_pnl = sum([t["pnl"] for t in trade_log if t["action"] == "SELL"])
    msg = ""
    if hourly:
        msg = f"📊 Hourly Report: Trades: {len(trade_log)}, Realized PnL: {round(realized_pnl,2)}, Balance: ${round(balance,2)}"
    elif daily:
        msg = f"📈 Daily Report: Trades: {len(trade_log)}, Realized PnL: {round(realized_pnl,2)}, Balance: ${round(balance,2)}"
    if msg:
        send_discord(msg)

def main_loop():
    global last_hour, last_day
    send_discord("🤖 ChunkyBot EDGE Edition live & trading! 🚀")
    while True:
        t = datetime.datetime.now(datetime.timezone.utc)
        hour = t.hour
        minute = t.minute

        # Heartbeat
        if minute % 1 == 0:
            send_discord(f"❤️ Heartbeat: AtomicBot is alive at {now()} UTC")

        # Trades & Edge
        for token in TOKENS:
            try:
                strat = select_strategy()
                price, signal = calc_signal(token, strat)
                # Edge exit sjekk før ny trade
                edge_action, edge_reason = check_edge_exit(token, price)
                if edge_action == "SELL":
                    handle_trade(token, "SELL", price, strat)
                if signal in ["BUY", "SELL"]:
                    handle_trade(token, signal, price, strat)
            except Exception as e:
                send_discord(f"❌ ChunkyEdge ERROR på {token}: {e}")

        # Hourly/Daily report
        if last_hour != hour:
            report(hourly=True)
            last_hour = hour
        if hour in REPORT_HOURS and last_day != t.date():
            report(daily=True)
            last_day = t.date()
        time.sleep(60)

if __name__ == "__main__":
    main_loop()
