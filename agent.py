import os
import random
import time
import datetime
import requests

# Demo settings
TOKENS = ["BTCUSDT", "ETHUSDT", "SOLUSDT", "BNBUSDT", "XRPUSDT", "ADAUSDT", "DOGEUSDT", "AVAXUSDT", "LINKUSDT", "TRXUSDT"]
START_BALANCE = 900.0
DEMO_MODE = True  # Sett til False for ekte handler når du vil!
DISCORD_WEBHOOK = os.environ.get("DISCORD_WEBHOOK", "https://discord.com/api/webhooks/...")
REPORT_HOURS = [6]  # Kl 06:00 UTC = dagsrapport

# State
balance = START_BALANCE
holdings = {token: 0 for token in TOKENS}
trade_log = []
pnl_log = []
last_hour = None
last_day = None

def send_discord(msg):
    try:
        requests.post(DISCORD_WEBHOOK, json={"content": msg})
    except Exception as e:
        print("DC error", e)

def get_price(token):
    # Demo: Tilfeldige priser i kjent range
    base = {
        "BTCUSDT": 30000, "ETHUSDT": 1700, "SOLUSDT": 20, "BNBUSDT": 250, "XRPUSDT": 0.6,
        "ADAUSDT": 0.4, "DOGEUSDT": 0.07, "AVAXUSDT": 10, "LINKUSDT": 6, "TRXUSDT": 0.07
    }
    if token in base:
        price = base[token] * random.uniform(0.97, 1.03)
        return round(price, 2)
    return None

def select_strategy():
    # Veldig enkel AI/ML – velg random eller RSI/EMA/Edge
    strategies = ["RANDOM", "RSI", "EMA", "SCALP"]
    if len(trade_log) > 30:
        # Eksempel: velg best av siste 30 handler
        best = max(set([t['strategy'] for t in trade_log[-30:]]), key=lambda s: sum(1 for t in trade_log[-30:] if t['strategy']==s and t['pnl']>0))
        return best
    return random.choice(strategies)

def calc_signal(token, strategy):
    # Demo: Enkel signal-logikk
    price = get_price(token)
    if price is None:
        return None, "HOLD"
    if strategy == "RANDOM":
        return price, random.choice(["BUY", "SELL", "HOLD"])
    elif strategy == "RSI":
        # Fake RSI – random, for demo
        rsi = random.uniform(10, 90)
        if rsi < 30: return price, "BUY"
        elif rsi > 70: return price, "SELL"
        else: return price, "HOLD"
    elif strategy == "EMA":
        # Fake EMA – random, for demo
        ema = price * random.uniform(0.98, 1.02)
        if price < ema: return price, "BUY"
        else: return price, "SELL"
    elif strategy == "SCALP":
        # Demo: Kjøp/sell på små svingninger
        if random.random() > 0.5: return price, "BUY"
        else: return price, "SELL"
    return price, "HOLD"

def handle_trade(token, action, price, strategy):
    global balance
    qty = round(balance / 10 / price, 6)  # Kjøp/sell for 1/10 av balanse
    old_balance = balance
    pnl = 0
    if action == "BUY" and balance > price * qty:
        balance -= price * qty
        holdings[token] += qty
        trade_log.append({"token": token, "action": "BUY", "price": price, "qty": qty, "strategy": strategy, "pnl": 0, "timestamp": now()})
        send_discord(f"🟦 BUY {token}: {qty} @ ${price}, bal: ${round(balance,2)}")
    elif action == "SELL" and holdings[token] > 0:
        balance += price * holdings[token]
        pnl = (price - trade_log[-1]["price"]) * holdings[token] if trade_log and trade_log[-1]["token"] == token else 0
        trade_log.append({"token": token, "action": "SELL", "price": price, "qty": holdings[token], "strategy": strategy, "pnl": pnl, "timestamp": now()})
        send_discord(f"🔴 SELL {token}: {holdings[token]} @ ${price}, PnL: {round(pnl,2)}, balance: ${round(balance,2)}")
        holdings[token] = 0

def report(hourly=False, daily=False):
    realized_pnl = sum([t["pnl"] for t in trade_log if t["action"] == "SELL"])
    msg = ""
    if hourly:
        msg = f"📊 Hourly Report: Trades: {len(trade_log)}, Realized PnL: {round(realized_pnl,2)}, Balance: ${round(balance,2)}"
    elif daily:
        msg = f"📈 Daily Report: Trades: {len(trade_log)}, Realized PnL: {round(realized_pnl,2)}, Balance: ${round(balance,2)}"
    if msg:
        send_discord(msg)

def now():
    return datetime.datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')

def main_loop():
    global last_hour, last_day
    send_discord("🤖 Chunky AtomicBot er live og trader demo! 🚀")
    while True:
        t = datetime.datetime.utcnow()
        hour = t.hour
        minute = t.minute
        # Heartbeat
        if minute % 1 == 0:
            send_discord(f"❤️ Heartbeat: AtomicBot is alive at {now()} UTC")
        # Trades
        for token in TOKENS:
            strategy = select_strategy()
            price, signal = calc_signal(token, strategy)
            if signal in ["BUY", "SELL"]:
                handle_trade(token, signal, price, strategy)
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
