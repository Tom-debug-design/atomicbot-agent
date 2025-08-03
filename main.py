import random, time, os, requests, json
import pandas as pd
from sklearn.ensemble import RandomForestClassifier
from datetime import datetime, timedelta

TOKENS = [
    "BTCUSDT", "ETHUSDT", "SOLUSDT", "BNBUSDT", "ADAUSDT",
    "DOGEUSDT", "MATICUSDT", "AVAXUSDT", "XRPUSDT", "TRXUSDT", "LINKUSDT"
]
STRATEGIES = ["RSI", "MEAN", "TREND", "RANDOM", "SCALP", "EMA"]
DISCORD_WEBHOOK = os.getenv("DISCORD_WEBHOOK")
START_BALANCE = 1000.0

trade_history = []
BALANCE = START_BALANCE

# ---- Chunky Parameter ----
RUN_ANALYSIS_EVERY = 3600  # sekunder mellom Rainy Forest AI (default: 1 time)
last_analysis = time.time()

def send_discord(msg):
    if not DISCORD_WEBHOOK:
        print("Discord webhook ikke satt!")
        return
    try:
        requests.post(DISCORD_WEBHOOK, json={"content": msg})
    except Exception as e:
        print(f"Discord feil: {e}")

def chunky_rainy_forest(trades):
    if len(trades) < 40:
        print("For få trades for Rainy Forest, venter...")
        return {t: random.choice(STRATEGIES) for t in TOKENS}
    df = pd.DataFrame(trades)
    df['is_win'] = df['pnl'] > 0
    df['hour'] = pd.to_datetime(df['timestamp'], unit='s').dt.hour
    df['token_id'] = pd.factorize(df['token'])[0]
    df['strategy_id'] = pd.factorize(df['strategy'])[0]
    features = ['token_id', 'strategy_id', 'hour']
    X = df[features]
    y = df['is_win']
    rf = RandomForestClassifier(n_estimators=80, max_depth=7, random_state=42)
    rf.fit(X, y)
    combos = df.groupby(['token', 'strategy']).size().reset_index().drop(0, axis=1)
    combos['token_id'] = pd.factorize(combos['token'])[0]
    combos['strategy_id'] = pd.factorize(combos['strategy'])[0]
    ai_best = {}
    for token in combos['token'].unique():
        best_score = -1
        best_strategy = None
        for _, row in combos[combos['token'] == token].iterrows():
            test_X = [[row['token_id'], row['strategy_id'], 12]]
            score = rf.predict_proba(test_X)[0][1]
            if score > best_score:
                best_score = score
                best_strategy = row['strategy']
        ai_best[token] = best_strategy
    print(f"[RAINY FOREST] Oppdatert AI-best-strategier: {ai_best}")
    return ai_best

# ---- Første AI-run (initielt tilfeldig) ----
ai_best = {t: random.choice(STRATEGIES) for t in TOKENS}

def pick_token_and_strategy():
    token = random.choice(TOKENS)
    strategy = ai_best.get(token, random.choice(STRATEGIES))
    return token, strategy

start_time = time.time()
while True:
    # ---- Kjør Rainy Forest AI (auto hver time) ----
    if time.time() - last_analysis > RUN_ANALYSIS_EVERY:
        if trade_history:
            ai_best = chunky_rainy_forest(trade_history)
            send_discord(f"[RAINY FOREST] AI-best-strategier oppdatert! 🚦 {ai_best}")
        last_analysis = time.time()
    # ---- Lag trade ----
    token, strategy = pick_token_and_strategy()
    price = random.uniform(0.5, 2.0) * 100
    qty = random.uniform(1, 5)
    direction = random.choice(["BUY", "SELL"])
    pnl = round(random.uniform(-2, 2), 2)
    trade = {
        "timestamp": time.time(),
        "token": token,
        "strategy": strategy,
        "direction": direction,
        "price": price,
        "qty": qty,
        "pnl": pnl,
    }
    trade_history.append(trade)
    BALANCE += pnl
    # ---- Rapport hver 20. trade ----
    if len(trade_history) % 20 == 0:
        msg = f"[CHUNKY-RAINY] Trade {len(trade_history)}, BAL: {round(BALANCE,2)}, {direction} {token} {qty}@{round(price,2)}, PnL: {pnl}, Edge: {strategy}"
        send_discord(msg)
    time.sleep(2)  # Juster trade-frekvens her (2 sek demo)