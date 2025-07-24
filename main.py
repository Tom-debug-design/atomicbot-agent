import time
import random
import datetime
import requests

WEBHOOK_URL = "https://discord.com/api/webhooks/..."  # ← Sett inn din Discord URL

def send_discord_message(message):
    try:
        requests.post(WEBHOOK_URL, json={"content": message})
    except Exception as e:
        print("Discord error:", e)

def simulate_strategy():
    action = random.choice(["BUY", "SELL"])
    price = round(random.uniform(100, 200), 2)
    pnl = round(random.uniform(-10, 10), 2)
    return action, price, pnl

def run_bot():
    while True:
        action, price, pnl = simulate_strategy()
        timestamp = datetime.datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")
        icon = "🔵" if action == "BUY" else "🔴"
        pnl_icon = "🟢" if pnl >= 0 else "🔴"
        msg = f"{icon} {action} @ ${price} | PnL: {pnl_icon} {pnl} USD | {timestamp} UTC"
        send_discord_message(msg)
        time.sleep(60)