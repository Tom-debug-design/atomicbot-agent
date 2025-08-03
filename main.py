import random, time, os, requests
from collections import deque
from datetime import datetime, timedelta
import numpy as np

from learner import StrategyLearner

# --- SETTINGS ---
TOKENS = [
    "BTCUSDT", "ETHUSDT", "SOLUSDT", "BNBUSDT", "ADAUSDT", "DOGEUSDT", "MATICUSDT", "AVAXUSDT", "XRPUSDT", "TRXUSDT", "LINKUSDT"
]
STRATEGIES = ["RSI", "EMA", "MEAN", "SCALP", "TREND", "RANDOM"]
DISCORD_WEBHOOK = os.getenv("DISCORD_WEBHOOK")
START_BALANCE = 1000.0

# --- EDGE LEARNER ---
learner = StrategyLearner(base_window=20, min_window=10, max_window=30)
BALANCE = START_BALANCE
trade_history = []
last_report_time = datetime.utcnow().replace(second=0, microsecond=0)
realized_pnl = 0.0

def send_discord(msg):
    if not DISCORD_WEBHOOK:
        print("Discord webhook ikke satt!")
        return
    try:
        requests.post(DISCORD_WEBHOOK, json={"content": msg})
    except Exception as e:
        print(f"Discord feil: {e}")

def pick_token_and_strategy(volatility=0.02):
    # Oppdater dynamisk window
    learner.update_window(volatility)
    combo = learner.get_weighted_edge_combo()
    if combo and combo[0] and combo[1]:
        strategy, token = combo
    else:
        strategy = random.choice(STRATEGIES)
        token = random.choice(TOKENS)
    return strategy, token

# --- Simulert tradingloop (pseudo, bytt med din ekte loop) ---
for i in range(100):
    # Dummy volatilitet, erstatt gjerne med ekte måling!
    volatility = random.uniform(0.005, 0.04)
    strategy, token = pick_token_and_strategy(volatility)
    price = random.uniform(0.5, 2.0) * 100  # dummy price
    qty = random.uniform(1, 5)
    direction = random.choice(["BUY", "SELL"])
    pnl = round(random.uniform(-2, 2), 2)  # dummy PnL

    # Logg trade til learner + history
    learner.log_trade(strategy, token, pnl)
    trade_history.append((datetime.utcnow(), strategy, token, direction, price, qty, pnl))
    BALANCE += pnl

    # Send status til Discord hver 20. trade (eller time)
    if i % 20 == 0:
        msg = f"[CHUNKY-EDGE] Trade {i}, BAL: {round(BALANCE,2)}, Last: {direction} {token} {qty}@{round(price,2)}, PnL: {pnl}, Edge: {strategy}"
        send_discord(msg)

# Eksempel på timesrapport
def hourly_report():
    last20 = trade_history[-20:]
    stats = {}
    for s in STRATEGIES:
        s_pnls = [t[6] for t in last20 if t[1] == s]
        stats[s] = round(np.mean(s_pnls), 2) if s_pnls else 0.0
    best_strategy = max(stats.items(), key=lambda x: x[1])[0]
    msg = f"\n[CHUNKY-EDGE] Hourly report:\n" + "\n".join([f"{k}: {v}" for k,v in stats.items()]) + f"\n🔥 Best: {best_strategy}"
    send_discord(msg)

# Kall denne i timesintervall eller der du ønsker
# hourly_report()