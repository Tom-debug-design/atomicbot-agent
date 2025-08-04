import random, time, os, requests
from collections import deque
from datetime import datetime, timedelta
import numpy as np
from learner import StrategyLearner

# --- SETTINGS ---
TOKENS = [
    "BTCUSDT", "ETHUSDT", "SOLUSDT", "BNBUSDT", "ADAUSDT", "DOGEUSDT",
    "MATICUSDT", "AVAXUSDT", "XRPUSDT", "TRXUSDT", "LINKUSDT"
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

# --- STRATEGY TRACKERS ---
recent_pnls = deque(maxlen=4)
strategy_wr = {s: deque(maxlen=10) for s in STRATEGIES}
banned_strategies = set()
current_strategy = "MEAN"

def send_discord(msg):
    if not DISCORD_WEBHOOK:
        print("Discord webhook ikke satt!")
        return
    try:
        requests.post(DISCORD_WEBHOOK, json={"content": msg})
    except Exception as e:
        print(f"Discord-feil: {e}")

def switch_strategy():
    global current_strategy
    available = [s for s in STRATEGIES if s not in banned_strategies]
    # Velg tilfeldig blant de gjenværende, ikke den samme
    new_strat = random.choice([s for s in available if s != current_strategy])
    send_discord(f"🔄 Bytter strategi fra {current_strategy} til {new_strat}!")
    current_strategy = new_strat

def best_strategy():
    # Finn strategi med best WR siste 10 trades
    wrs = {s: sum(strategy_wr[s])/len(strategy_wr[s]) if strategy_wr[s] else 0 for s in STRATEGIES}
    return max(wrs, key=wrs.get)

def simulate_trade():
    global BALANCE, realized_pnl, current_strategy
    # --- Dummy trade ---
    token = random.choice(TOKENS)
    price = random.uniform(0.95, 1.05) * 20  # Fake price
    qty = random.uniform(0.9, 1.1) * 1
    direction = random.choice(["BUY", "SELL"])
    # --- Lag PnL: Gi random, men la vinn/tap-oddsen avhenge litt av strategi
    strat_bonus = {"RSI": 0.52, "EMA": 0.48, "MEAN": 0.55, "SCALP": 0.51, "TREND": 0.49, "RANDOM": 0.35}
    win = random.random() < strat_bonus.get(current_strategy, 0.5)
    pnl = round(random.uniform(0.2, 2.5) * (1 if win else -1), 2)
    BALANCE += pnl
    realized_pnl += pnl
    trade_history.append({
        "time": datetime.utcnow().isoformat(),
        "strategy": current_strategy,
        "token": token,
        "qty": qty,
        "price": price,
        "direction": direction,
        "pnl": pnl,
        "bal": BALANCE
    })
    # Oppdater winrate-tracker
    strategy_wr[current_strategy].append(pnl > 0)
    # Glidende tap
    recent_pnls.append(pnl)
    losses = sum(1 for x in recent_pnls if x < 0)
    wins = sum(1 for x in recent_pnls if x > 0)

    # --- Hot streak: Bli på strategi hvis 3+ pluss på rad
    if wins >= 3 and len(recent_pnls) == 4:
        pass
    # --- Bytt strategi ved 3 av 4 tap
    elif losses >= 3 and len(recent_pnls) == 4:
        send_discord(f"⚠️ {losses} tap på rad – bytter strategi!")
        switch_strategy()
        recent_pnls.clear()
    # --- Ban RANDOM hvis WR < 25% siste 10 trades
    if current_strategy == "RANDOM":
        wr = sum(strategy_wr["RANDOM"]) / len(strategy_wr["RANDOM"]) if len(strategy_wr["RANDOM"]) else 0
        if len(strategy_wr["RANDOM"]) == 10 and wr < 0.25:
            send_discord("🚫 RANDOM banet for lav winrate!")
            banned_strategies.add("RANDOM")
            switch_strategy()
    # --- Emergency: 4 tap på rad, gå til best strategi
    if len(recent_pnls) == 4 and losses == 4:
        best = best_strategy()
        send_discord(f"🆘 Nødsituasjon: bytter til best WR strategi: {best}")
        current_strategy = best
        recent_pnls.clear()

def hourly_report():
    # Lag timesrapport
    wrs = {s: sum(strategy_wr[s])/len(strategy_wr[s]) if strategy_wr[s] else 0 for s in STRATEGIES}
    pnls = {s: sum(x["pnl"] for x in trade_history if x["strategy"] == s) for s in STRATEGIES}
    msg = (
        f"📊 [CHUNKY-EDGE] Hourly report: Trades: {len(trade_history)}, Bal: ${BALANCE:.2f}, Realized PnL: {realized_pnl:.2f}\n" +
        "".join([f"- {s}: PnL {pnls[s]:.2f}, WR {wrs[s]*100:.1f}%\n" for s in STRATEGIES]) +
        f"🔥 Best: {best_strategy()}"
    )
    send_discord(msg)

# --- MAIN LOOP ---
next_report = datetime.utcnow() + timedelta(hours=1)
while True:
    simulate_trade()
    time.sleep(1)  # Juster for test/demo
    if datetime.utcnow() >= next_report:
        hourly_report()
        next_report += timedelta(hours=1)