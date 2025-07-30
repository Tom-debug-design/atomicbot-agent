
import os
import time
import json
import random
import requests
from datetime import datetime
from learner import select_strategy, log_trade_result, get_daily_stats, update_goal, get_goal, reset_goal, get_streak

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
        requests.post(DISCORD_WEBHOOK, json={"content": message})

def choose_token():
    return select_strategy("token", TOKEN_LIST)

def make_trade(balance, strategy_name):
    token = choose_token()
    price = get_live_price(token)
    if not price:
        send_discord_message(f"🔴 Could not get live price for {token}. Skipping.")
        return balance, None, None
    trade_amount = round(balance * TRADE_SIZE_PERCENT / 100, 2)
    qty = round(trade_amount / price, 6)
    trade_type = random.choice(["BUY", "SELL"])
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    result = random.uniform(-0.025, 0.025)  # simulate random PNL ±2.5%
    pnl = round(trade_amount * result, 2)
    pnl_percent = round((pnl / trade_amount) * 100, 2)
    new_balance = balance + pnl if trade_type == "SELL" else balance
    log_trade_result(token, trade_type, price, qty, trade_amount, pnl, pnl_percent, strategy_name, timestamp)
    pnl_emoji = "🟢" if pnl >= 0 else "🔴"
    send_discord_message(
        f"{pnl_emoji} **{trade_type}** {token} @ ${price:.2f} | Qty: {qty} | Amount: ${trade_amount} | "
        f"PnL: ${pnl} ({pnl_percent}%) | Strat: {strategy_name}"
    )
    return new_balance, pnl, pnl_percent

def daily_report():
    stats = get_daily_stats()
    if not stats["trades"]:
        return
    report = (
        f"📈 **Daglig ChunkyAI rapport:**
"
        f"Totalt handler: {stats['trades']}
"
        f"Daglig gevinst: ${stats['pnl']:.2f} ({stats['pnl_percent']:.2f}%)
"
        f"Winrate: {stats['winrate']}%
"
        f"Beste strategi: {stats['best_strategy']}
"
        f"Mål: ${stats['goal']} | Streak: {stats['streak']}
"
    )
    send_discord_message(report)

def main():
    balance = START_BALANCE
    trades = 0
    reset_goal()
    send_discord_message("🤖 ChunkyAI v5 bot startet!")
    last_report_day = datetime.now().day
    while True:
        strategy = select_strategy("strategy")
        balance, pnl, pnl_percent = make_trade(balance, strategy)
        trades += 1
        update_goal(pnl)
        # Check if goal is reached and auto-increment
        if get_goal("reached"):
            send_discord_message(f"🎯 **Daglig gevinstmål nådd!** Nytt mål: ${get_goal('value')} | Streak: {get_streak()}")
            update_goal(0, next_goal=True)
        # Send daglig rapport
        now = datetime.now()
        if now.day != last_report_day:
            daily_report()
            last_report_day = now.day
        time.sleep(12)

if __name__ == "__main__":
    main()
