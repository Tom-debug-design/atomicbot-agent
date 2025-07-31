import os
import random
import time
import requests
import csv
import pickle

TOKENS = ["BTCUSDT", "ETHUSDT", "SOLUSDT", "BNBUSDT", "XRPUSDT"]
DISCORD_WEBHOOK = os.getenv("DISCORD_WEBHOOK")
START_BALANCE = 1000.0
balance = START_BALANCE
holdings = {symbol: 0.0 for symbol in TOKENS}
trade_log = []
auto_buy_pct = 0.1

AI_CSV = "ai_data_log.csv"
MODEL = "atomicbot_model.pkl"

def send_discord(msg):
    print("DISCORD:", msg)
    try:
        if DISCORD_WEBHOOK:
            requests.post(DISCORD_WEBHOOK, json={"content": msg})
    except Exception as e:
        print(f"Discord error: {e}")

def get_price(symbol):
    # Dummy: real: fetch from API
    return random.uniform(10, 50000)

def log_ai_data(row):
    write_header = not os.path.exists(AI_CSV)
    with open(AI_CSV, "a", newline="") as f:
        writer = csv.writer(f)
        if write_header:
            writer.writerow(["symbol","price","holdings","action"])
        writer.writerow(row)

def retrain_ai_model():
    if not os.path.exists(AI_CSV): return
    import pandas as pd
    from sklearn.ensemble import RandomForestClassifier
    df = pd.read_csv(AI_CSV)
    if len(df) < 30: return
    X = df[["price", "holdings"]]
    y = (df["action"] == "BUY").astype(int)
    model = RandomForestClassifier().fit(X, y)
    with open(MODEL, "wb") as f:
        pickle.dump(model, f)
    send_discord("🤖 Ny AI-modell trent!")

def ai_predict_action(price, holdings):
    try:
        with open(MODEL, "rb") as f:
            model = pickle.load(f)
        proba = model.predict_proba([[price, holdings]])[0][1]
        if proba > 0.7:
            return "BUY"
        else:
            return "HOLD"
    except Exception as e:
        return None

def get_signal(symbol, price, holdings):
    ai_signal = ai_predict_action(price, holdings)
    if ai_signal:
        return ai_signal
    # Fallback: tradisjonell strategi
    if holdings == 0 and price % 2 < 1:
        return "BUY"
    elif holdings > 0 and price % 5 < 1:
        return "SELL"
    return "HOLD"

def handle_trade(symbol, action, price):
    global balance, holdings
    amount_usd = balance * auto_buy_pct if action == "BUY" else holdings[symbol] * price
    qty = round(amount_usd / price, 6) if action == "BUY" else holdings[symbol]
    if action == "BUY" and balance >= amount_usd and qty > 0:
        balance -= amount_usd
        holdings[symbol] += qty
        send_discord(f"🔵 BUY {symbol}: {qty} at ${price:.2f}, new balance ${balance:.2f}")
        trade_log.append({"symbol": symbol, "action": "BUY", "price": price, "qty": qty, "timestamp": time.time()})
        log_ai_data([symbol, price, holdings[symbol], "BUY"])
    elif action == "SELL" and holdings[symbol] > 0:
        proceeds = qty * price
        balance += proceeds
        holdings[symbol] = 0.0
        send_discord(f"🔴 SELL {symbol}: {qty} at ${price:.2f}, balance: ${balance:.2f}")
        trade_log.append({"symbol": symbol, "action": "SELL", "price": price, "qty": qty, "timestamp": time.time()})
        log_ai_data([symbol, price, holdings[symbol], "SELL"])

def hourly_report():
    total_trades = len(trade_log)
    send_discord(f"📊 Hourly Report: Trades: {total_trades}, Balance: ${balance:.2f}")

send_discord("🟢 AtomicBot starter!")

last_report = time.time()
while True:
    for symbol in TOKENS:
        price = get_price(symbol)
        action = get_signal(symbol, price, holdings[symbol])
        if action in ("BUY", "SELL"):
            handle_trade(symbol, action, price)
    if time.time() - last_report > 60:
        hourly_report()
        retrain_ai_model()  # Tren AI hver time hvis mulig!
        last_report = time.time()
    time.sleep(10)
