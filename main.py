import random, time, os, requests
from collections import deque, defaultdict
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

# --- STOP LOSS SETTINGS ---
PER_TRADE_STOP = 0.03     # 3 % per trade
PER_STRATEGY_LOSS = 10    # $10 i tap på én time
PER_STRATEGY_LOSS_TRADES = 5  # 5 tap på rad
GLOBAL_STOP = 800
GLOBAL_PAUSE_MINUTES = 30

# --- EDGE LEARNER ---
learner = StrategyLearner(base_window=20, min_window=10, max_window=30)
BALANCE = START_BALANCE
trade_history = []
last_report_time = datetime.utcnow().replace(second=0, microsecond=0)
realized_pnl = 0.0

# --- STRATEGI-STATISTIKK FOR PAUSE ---
strategy_loss = defaultdict(float)
strategy_loss_trades = defaultdict(int)
strategy_paused_until = {}

# --- GLOBAL PAUSE ---
PAUSE_MODE = False
pause_until = None

def send_discord(msg):
    if not DISCORD_WEBHOOK:
        print("Discord webhook ikke satt!")
        return
    try:
        requests.post(DISCORD_WEBHOOK, json={"content": msg})
    except Exception as e:
        print(f"Discord-feil: {e}")

def handle_global_pause():
    global PAUSE_MODE, pause_until
    now = datetime.utcnow()
    if BALANCE < GLOBAL_STOP:
        if not PAUSE_MODE:
            PAUSE_MODE = True
            pause_until = now + timedelta(minutes=GLOBAL_PAUSE_MINUTES)
            send_discord(f"🔴 GLOBAL STOP LOSS! Bot paused for {GLOBAL_PAUSE_MINUTES} min. Balance: ${BALANCE:.2f}")
    else:
        if PAUSE_MODE and now >= pause_until:
            PAUSE_MODE = False
            send_discord(f"🟢 Bot resumed after global stop loss. Balance: ${BALANCE:.2f}")

def handle_strategy_pause(strategy):
    now = datetime.utcnow()
    if (strategy_loss[strategy] <= -PER_STRATEGY_LOSS or
        strategy_loss_trades[strategy] >= PER_STRATEGY_LOSS_TRADES):
        strategy_paused_until[strategy] = now + timedelta(hours=1)
        send_discord(f"⏸️ Strategy {strategy} paused for 1 hour (too many losses)")
        # Reset counters
        strategy_loss[strategy] = 0
        strategy_loss_trades[strategy] = 0

def is_strategy_paused(strategy):
    now = datetime.utcnow()
    until = strategy_paused_until.get(strategy)
    return until is not None and now < until

def trade(token, strategy):
    global BALANCE, realized_pnl

    if PAUSE_MODE or is_strategy_paused(strategy):
        return

    # Dummy trade logic, replace with real trading code!
    entry_price = random.uniform(0.95, 1.05)
    direction = random.choice([-1, 1])
    size = random.uniform(20, 50)
    exit_price = entry_price + direction * entry_price * random.uniform(0.001, 0.04)
    pnl = (exit_price - entry_price) * size
    BALANCE += pnl
    realized_pnl += pnl
    trade_history.append((datetime.utcnow(), token, strategy, pnl, size, entry_price, exit_price))

    # --- Per-trade stop loss ---
    if pnl < -PER_TRADE_STOP * size * entry_price:
        send_discord(f"🛑 STOP LOSS: Trade on {token} {strategy} closed at {pnl:.2f}$ (auto-exit)")
        # Optionally close/mark trade here

    # --- Per-strategy ---
    if pnl < 0:
        strategy_loss[strategy] += pnl
        strategy_loss_trades[strategy] += 1
        handle_strategy_pause(strategy)
    else:
        strategy_loss_trades[strategy] = 0

def main_loop():
    global BALANCE
    while True:
        handle_global_pause()

        if PAUSE_MODE:
            time.sleep(10)
            continue

        token = random.choice(TOKENS)
        strategy = random.choice(STRATEGIES)
        if is_strategy_paused(strategy):
            continue
        trade(token, strategy)

        # Rapporter hver time eller hva du ønsker
        time.sleep(1)

if __name__ == "__main__":
    main_loop()