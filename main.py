import os
import random
import time
import datetime

TOKENS = [
    "BTCUSDT", "ETHUSDT", "SOLUSDT", "BNBUSDT", "XRPUSDT", "ADAUSDT",
    "DOGEUSDT", "AVAXUSDT", "LINKUSDT", "TRXUSDT"
]
START_BALANCE = 1000.0
TRADE_SIZE = 0.03         # 3%
TP = 0.002                # 0.2%
SL = 0.002                # 0.2%
STOP_LOSS_PCT = 0.07
TRAIL_START_PCT = 0.03
TRAIL_STEP_PCT = 0.02
STRATEGIES = ["RANDOM", "RSI", "EMA", "SCALP"]
DISCORD_WEBHOOK = os.environ.get("DISCORD_WEBHOOK", "https://discord.com/api/webhooks/...")

balance = START_BALANCE
holdings = {token: 0 for token in TOKENS}
entry = {token: None for token in TOKENS}
peak = {token: None for token in TOKENS}
trade_log = []
tap_counter = 0
strategy = "RANDOM"
total_trades = 0

def send_discord(msg):
    # import requests
    print(msg)
    # try:
    #     requests.post(DISCORD_WEBHOOK, json={"content": msg})
    # except Exception as e:
    #     print("DC error", e)

def get_price(token):
    base = {
        "BTCUSDT": 30000, "ETHUSDT": 1700, "SOLUSDT": 20, "BNBUSDT": 250, "XRPUSDT": 0.6,
        "ADAUSDT": 0.4, "DOGEUSDT": 0.07, "AVAXUSDT": 10, "LINKUSDT": 6, "TRXUSDT": 0.07
    }
    return round(base[token] * random.uniform(0.98, 1.02), 2)

def select_strategy():
    global strategy, tap_counter
    # Rapid switch: bytt strategi etter 3 tap på rad
    if tap_counter >= 3:
        old_strategy = strategy
        strategy = random.choice([s for s in STRATEGIES if s != strategy])
        send_discord(f"🔄 [CHUNKY-EDGE] Strategy switch: {old_strategy} → {strategy} etter {tap_counter} tap på rad!")
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

def handle_trade(token, action, price, strategy, edge=False, edge_type=""):
    global balance, tap_counter, total_trades
    qty = round(balance * TRADE_SIZE / price, 6)
    pnl = 0

    label = "[CHUNKY-EDGE]" if edge else "[STD]"
    if edge_type:
        label += f" [{edge_type}]"

    if action == "BUY" and balance > price * qty:
        balance -= price * qty
        holdings[token] += qty
        entry[token] = price
        peak[token] = price
        send_discord(f"{label} BUY {token}: {qty} @ ${price}, strategy: {strategy}, bal: ${round(balance,2)}")
        trade_log.append({"token": token, "action": "BUY", "price": price, "qty": qty, "strategy": strategy, "pnl": 0, "timestamp": now()})

    elif action == "SELL" and holdings[token] > 0:
        last_entry = entry[token] if entry[token] else price
        balance += price * holdings[token]
        pnl = (price - last_entry) * holdings[token]
        if pnl < 0:
            tap_counter += 1
        else:
            tap_counter = 0
        send_discord(f"{label} SELL {token}: {holdings[token]} @ ${price}, PnL: {round(pnl,2)}, bal: ${round(balance,2)}")
        trade_log.append({"token": token, "action": "SELL", "price": price, "qty": holdings[token], "strategy": strategy, "pnl": pnl, "timestamp": now()})
        holdings[token] = 0
        entry[token] = None
        peak[token] = None
    total_trades += 1

def check_edge_exit(token, price):
    if holdings[token] > 0 and entry[token]:
        gain = (price - entry[token]) / entry[token]
        # Trailing stop
        if gain > TRAIL_START_PCT:
            if price > peak[token]:
                peak[token] = price
            elif price < peak[token] * (1 - TRAIL_STEP_PCT):
                send_discord(f"🔥 [CHUNKY-EDGE][Trailing] Trailing stop utløst – SELL {token} på ${price}!")
                return "SELL", True, "Trailing"
        # Stop loss
        if gain < -STOP_LOSS_PCT:
            send_discord(f"🔥 [CHUNKY-EDGE][Stoploss] Stop loss utløst – SELL {token} på ${price} (PnL: {round(gain*100,2)}%)!")
            return "SELL", True, "Stoploss"
    return "HOLD", False, ""

def main_loop():
    send_discord(f"🤖 [CHUNKY-EDGE] AtomicBot Edge live {now()} – klar for action!")
    global total_trades
    while True:
        for token in TOKENS:
            try:
                strat = select_strategy()
                price, signal = calc_signal(token, strat)
                # EDGE-exit
                edge_action, is_edge, edge_type = check_edge_exit(token, price)
                if edge_action == "SELL":
                    handle_trade(token, "SELL", price, strat, edge=True, edge_type=edge_type)
                if signal in ["BUY", "SELL"]:
                    handle_trade(token, signal, price, strat, edge=False)
            except Exception as e:
                send_discord(f"❌ [CHUNKY-EDGE] ERROR {token}: {e}")
        if total_trades % 10 == 0:
            send_discord(f"📊 [CHUNKY-EDGE] Trades: {total_trades}, Bal: ${round(balance,2)}")
        time.sleep(10)

if __name__ == "__main__":
    main_loop()
