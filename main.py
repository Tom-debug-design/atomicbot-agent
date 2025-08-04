import random, time, os, requests
from collections import deque
from datetime import datetime, timedelta
import numpy as np

from learner import StrategyLearner

# --- SETTINGS ---
TOKENS = [
    "BTCUSDT", "ETHUSDT", "SOLUSDT", "BNBUSDT",
    "ADAUSDT", "DOGEUSDT", "MATICUSDT", "AVAXUSDT",
    "XRPUSDT", "TRXUSDT", "LINKUSDT"
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

# --- SLIDING LOSS WINDOW ---
recent_pnls = deque(maxlen=5)  # Holder de siste 5 PnL for tap-sjekk

def send_discord(msg):
    if not DISCORD_WEBHOOK:
        print("Discord webhook ikke satt!")
        return
    try:
        requests.post(DISCORD_WEBHOOK, json={"content": msg})
    except Exception as e:
        print(f"Discord-feil: {e}")

def switch_strategy():
    # Dummy-funksjon, bytt til en ny tilfeldig strategi
    global current_strategy
    available = [s for s in STRATEGIES if s != current_strategy]
    current_strategy = random.choice(available)
    send_discord(f"🟡 [CHUNKY-EDGE] Switched strategy to: {current_strategy}")

# --- START MED EN TILFELDIG STRATEGI ---
current_strategy = random.choice(STRATEGIES)

def simulate_trade():
    global BALANCE, realized_pnl

    # Dummy trading-logic (bytt ut med ekte signaler)
    token = random.choice(TOKENS)
    price = random.uniform(0.95, 1.05) * 100
    amount = random.uniform(1, 10)
    direction = random.choice(["BUY", "SELL"])
    pnl = round(random.uniform(-5, 5), 2)  # Simulert PnL

    # Logg trade til learner og history
    learner.log_trade(current_strategy, token, pnl, price)
    trade_history.append((datetime.utcnow(), direction, token, price, amount, current_strategy, pnl))
    realized_pnl += pnl
    BALANCE += pnl

    # --- SLIDING WINDOW CHECK ---
    recent_pnls.append(pnl)
    if len(recent_pnls) == 5:
        num_losses = sum(1 for x in recent_pnls if x < 0)
        if num_losses >= 4:
            switch_strategy()
            print("🟡 [CHUNKY-EDGE] Bytter strategi etter 4 av 5 tap!")
            recent_pnls.clear()

    # --- EVENTUELT STOP LOSS, ETC ---
    if BALANCE < 800:
        send_discord(f"🔴 Stop-loss triggered! Balance: ${BALANCE:.2f}. Pauser trading.")
        print("🔴 Stop-loss utløst!")
        time.sleep(60)  # Pause for demo (fjern eller erstatt i prod)

    # --- Discord-rapport (enkel demo) ---
    if random.random() < 0.05:
        send_discord(f"[STD] {direction} {token}: {amount:.4f} @ ${price:.2f}, strategy: {current_strategy}, bal: ${BALANCE:.2f}")

def main_loop():
    while True:
        simulate_trade()
        time.sleep(1)  # Justér for ønsket hastighet

if __name__ == "__main__":
    print("🚀 ChunkyBot starter...")
    main_loop()