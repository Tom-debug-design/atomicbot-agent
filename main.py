import random, time, os, requests
from collections import deque, defaultdict
from datetime import datetime, timedelta
from learner import StrategyLearner
import numpy as np

# --- SETTINGS ---
TOKENS = [
    "BTCUSDT", "ETHUSDT", "SOLUSDT", "BNBUSDT", "ADAUSDT",
    "DOGEUSDT", "MATICUSDT", "AVAXUSDT", "XRPUSDT", "LINKUSDT", "TRXUSDT"
]
STRATEGIES = ["RSI", "EMA", "MEAN", "SCALP", "TREND", "RANDOM"]
DISCORD_WEBHOOK = os.getenv("DISCORD_WEBHOOK")
START_BALANCE = 1000.0

# --- CHUNKY EDGE AI ---
learner = StrategyLearner(base_window=20, min_window=10, max_window=40)
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
        print("Discord error:", e)

def get_volatility(n=20):
    if len(trade_history) < n:
        return 1.0
    returns = [x['pnl'] for x in trade_history[-n:]]
    return float(np.std(returns)) if returns else 1.0

def pick_token_and_strategy():
    vol = get_volatility()
    best_strat, best_token = learner.get_weighted_best_combo(vol)
    if best_strat and best_token:
        return best_strat, best_token
    # fallback hvis ikke nok data
    return random.choice(STRATEGIES), random.choice(TOKENS)

def execute_trade(side, token, strategy, price, qty):
    global BALANCE, realized_pnl
    # Dummy PnL – bytt ut med reell beregning i live
    pnl = round(random.uniform(-2, 2), 2)
    trade = {
        'timestamp': datetime.utcnow().isoformat(),
        'side': side,
        'token': token,
        'strategy': strategy,
        'price': price,
        'qty': qty,
        'pnl': pnl,
        'bal': BALANCE
    }
    trade_history.append(trade)
    # Oppdater balance og PnL
    BALANCE += pnl
    realized_pnl += pnl
    vol = get_volatility()
    learner.log_trade(strategy, token, pnl, vol)
    # Meld til Discord
    emoji = "🟢" if pnl >= 0 else "🔴"
    send_discord(f"[STD] {side} {token}: {qty} @ ${price}, strategy: {strategy}, PnL: {emoji}{pnl}, bal: ${round(BALANCE,2)}")

def hourly_report():
    now = datetime.utcnow()
    last_hour = [x for x in trade_history if datetime.fromisoformat(x['timestamp']) >= now - timedelta(hours=1)]
    if not last_hour:
        return
    lines = [f"📊 [CHUNKY-EDGE] Hourly report: Trades: {len(last_hour)}, Bal: ${round(BALANCE,2)}, Realized PnL: {round(realized_pnl,2)}"]
    strat_stats = defaultdict(lambda: {'pnl': 0, 'count': 0, 'win': 0})
    for t in last_hour:
        s = t['strategy']
        strat_stats[s]['pnl'] += t['pnl']
        strat_stats[s]['count'] += 1
        if t['pnl'] > 0:
            strat_stats[s]['win'] += 1
    for s in STRATEGIES:
        st = strat_stats[s]
        if st['count'] == 0:
            continue
        winrate = 100 * st['win'] / st['count']
        lines.append(f"- {s}: PnL {round(st['pnl'],2)}, WR {round(winrate,1)}%")
    best_strat = max(STRATEGIES, key=lambda s: strat_stats[s]['pnl'] if strat_stats[s]['count'] else -9999)
    lines.append(f"🔥 Best: {best_strat}")
    send_discord("\n".join(lines))

def main_loop():
    global last_report_time
    while True:
        now = datetime.utcnow().replace(second=0, microsecond=0)
        # Heartbeat hvert minutt
        send_discord(f"❤️ Heartbeat: AtomicBot is alive at {now.isoformat()} UTC")
        # Hver time: rapport
        if (now - last_report_time).total_seconds() >= 3600:
            hourly_report()
            last_report_time = now

        # Trading (demo) – 2 trades per minutt for demo, juster som du vil
        for _ in range(2):
            strat, token = pick_token_and_strategy()
            price = round(random.uniform(0.05, 40000), 2)
            qty = round(random.uniform(0.001, 10), 6)
            side = random.choice(['BUY', 'SELL'])
            execute_trade(side, token, strat, price, qty)
            time.sleep(3)
        time.sleep(45)  # slik at loopen ~1 minutt totalt

if __name__ == "__main__":
    main_loop()
