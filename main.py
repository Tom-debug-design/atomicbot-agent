import random, time, os, requests
from collections import deque
from datetime import datetime
import numpy as np
from learner import ChunkyEdgeLearner

TOKENS = [
    "BTCUSDT", "ETHUSDT", "SOLUSDT", "BNBUSDT", "ADAUSDT",
    "DOGEUSDT", "MATICUSDT", "AVAXUSDT", "XRPUSDT", "TRXUSDT", "LINKUSDT"
]
STRATEGIES = ["RSI", "MEAN", "TREND", "RANDOM"]
DISCORD_WEBHOOK = os.getenv("DISCORD_WEBHOOK")
START_BALANCE = 1000.0

learner = ChunkyEdgeLearner(ban_threshold=-5, ban_window=20, boost_window=20)
BALANCE = START_BALANCE
trade_history = []
last_report_time = datetime.utcnow().replace(second=0, microsecond=0)

def send_discord(msg):
    if not DISCORD_WEBHOOK:
        print("Discord webhook ikke satt!")
        return
    try:
        requests.post(DISCORD_WEBHOOK, json={"content": msg})
    except Exception as e:
        print(f"Discord feil: {e}")

def pick_combo():
    # Prioriter whitelist, ellers random av de som ikke er bannet
    combo = learner.get_suggested_combo()
    if combo:
        strategy, token = combo
    else:
        # fallback: random combo uten ban
        valid = [(s, t) for s in STRATEGIES for t in TOKENS if (s, t) not in learner.banlist]
        if not valid:
            strategy, token = random.choice(STRATEGIES), random.choice(TOKENS)
        else:
            strategy, token = random.choice(valid)
    return strategy, token

for i in range(1, 1001):  # Dummy loop (bytt til din egen live-loop!)
    strategy, token = pick_combo()
    price = random.uniform(0.5, 2.0) * 100
    qty = random.uniform(1, 5)
    direction = random.choice(["BUY", "SELL"])
    pnl = round(random.uniform(-2, 2), 2)  # dummy PnL
    learner.log_trade(strategy, token, pnl)
    trade_history.append((datetime.utcnow(), strategy, token, direction, price, qty, pnl))
    BALANCE += pnl

    if i % 20 == 0:
        lists = learner.get_lists()
        msg = f"[CHUNKY-V4] Trade {i}, BAL: {round(BALANCE,2)}, {direction} {token} {qty}@{round(price,2)}, PnL: {pnl}, Edge: {strategy}\n"
        msg += f"Whitelist: {lists['whitelist']}\nBanlist: {lists['banlist']}"
        send_discord(msg)

# Eksempel på timesrapport (tilpass for live-loop)
def hourly_report():
    last20 = trade_history[-20:]
    stats = {}
    for s in STRATEGIES:
        s_pnls = [t[6] for t in last20 if t[1] == s]
        stats[s] = round(np.mean(s_pnls), 2) if s_pnls else 0.0
    best_strategy = max(stats.items(), key=lambda x: x[1])[0]
    lists = learner.get_lists()
    msg = f"\n[CHUNKY-V4] Hourly report:\n" + "\n".join([f"{k}: {v}" for k,v in stats.items()]) + f"\n🔥 Best: {best_strategy}\nWhitelist: {lists['whitelist']}\nBanlist: {lists['banlist']}"
    send_discord(msg)

# hourly_report()  # kall denne i loop/live