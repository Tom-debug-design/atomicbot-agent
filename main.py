
import os
import time
import random
import requests
from datetime import datetime

DISCORD_WEBHOOK = os.getenv("DISCORD_WEBHOOK") or "YOUR_DISCORD_WEBHOOK_URL"
TOKEN_LIST = ["BTCUSDT", "ETHUSDT", "SOLUSDT", "ADAUSDT", "BNBUSDT", "XRPUSDT", "AVAXUSDT", "MATICUSDT"]
START_BALANCE = 1000
TRADE_SIZE_PERCENT = 5

def get_live_price(symbol):
    url = f"https://api.binance.com/api/v3/ticker/price?symbol={symbol}"
    try:
        response = requests.get(url, timeout=5)
        return float(response.json()['price'])
    except:
        return None

def send_discord_message(message):
    if DISCORD_WEBHOOK.startswith("http"):
        try:
            requests.post(DISCORD_WEBHOOK, json={"content": message})
        except Exception as e:
            print("Discord error:", e)

def make_trade(balance):
    token = random.choice(TOKEN_LIST)
    price = get_live_price(token)
    if not price:
        send_discord_message(f"🔴 Kunne ikke hente livepris for {token}.")
        return balance, 0
    trade_amount = round(balance * TRADE_SIZE_PERCENT / 100, 2)
    qty = round(trade_amount / price, 6)
    trade_type = random.choice(["BUY", "SELL"])
    result = random.uniform(-0.015, 0.015)
    pnl = round(trade_amount * result, 2)
    new_balance = balance + pnl if trade_type == "SELL" else balance
    pnl_emoji = "🟢" if pnl >= 0 else "🔴"
    send_discord_message(
        f"{pnl_emoji} {trade_type} {token} @ ${price:.2f} | Qty: {qty} | Amount: ${trade_amount} | PnL: ${pnl}"
    )
    return new_balance, pnl

def main():
    balance = START_BALANCE
    trades = 0
    send_discord_message("🤖 AtomicBot SAFE er live!")
    last_ping = time.time()
    while True:
        # Hovedloop: gjør handler, send status per minutt
        if time.time() - last_ping > 60:
            send_discord_message(f"✅ Bot status: {trades} handler | Balance: ${balance:.2f}")
            last_ping = time.time()
        balance, pnl = make_trade(balance)
        trades += 1
        time.sleep(15)

# ---- Railway/Gunicorn webserver ----
from flask import Flask
import threading

app = Flask(__name__)

@app.route("/")
def home():
    return "AtomicBot SAFE running!"

def bot_thread():
    main()

if __name__ == "__main__":
    t = threading.Thread(target=bot_thread, daemon=True)
    t.start()
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 8080)))
