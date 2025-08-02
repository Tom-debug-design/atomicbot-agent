import random, time, os, requests
from collections import deque, defaultdict
from datetime import datetime, timedelta
from learner import StrategyLearner

# --- SETTINGS ---
TOKENS = [
    "BTCUSDT", "ETHUSDT", "SOLUSDT", "BNBUSDT", "XRPUSDT",
    "ADAUSDT", "DOGEUSDT", "MATICUSDT", "AVAXUSDT", "TRXUSDT"
]
STRATEGIES = ["RSI", "EMA", "MEAN", "SCALP", "RANDOM", "TREND"]
DISCORD_WEBHOOK = os.getenv("DISCORD_WEBHOOK")
START_BALANCE = 1000.0

# --- CHUNKY EDGE AI ---
learner = StrategyLearner(window_size=20)
BALANCE = START_BALANCE
trade_history = []
last_report_time = datetime.utcnow().replace(second=0, microsecond=0)
realized_pnl = 0.0

def send_discord(msg):
    if not DISCORD_WEBHOOK:
        print("Discord webhook ikke satt!")
        return
    requests.post(DISCORD_WEBHOOK, json={"content": msg})

def pick_token_and_strategy():
    # Bruk chunky edge: velg beste strategi+token fra de siste 20 handler
    strat, token = learner.get_best_combo()
    if not strat or not token:
        strat = random.choice(STRATEGIES)
        token = random.choice(TOKENS)
    return strat, token

def execute_trade(token, strategy, bal):
    # Simulert handler: tilfeldig retning og PnL
    side = random.choice(["BUY", "SELL"])
    price = round(random.uniform(0.97, 1.03) * 100, 2)  # dummy price
    qty = round(random.uniform(10, 100), 4)
    # Lag litt edge for beste strategi
    pnl = random.gauss(0.2 if strategy == "SCALP" else 0, 0.5)
    new_bal = bal + pnl
    timestamp = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")
    return {
        "timestamp": timestamp,
        "token": token,
        "strategy": strategy,
        "side": side,
        "price": price,
        "qty": qty,
        "pnl": pnl,
        "balance": new_bal
    }

def hourly_report():
    # PnL og winrate per strategi
    recent_trades = trade_history[-200:]
    strat_pnl = defaultdict(list)
    for trade in recent_trades:
        strat_pnl[trade["strategy"]].append(trade["pnl"])
    msg = "📊 [CHUNKY-EDGE] Hourly report:\n"
    msg += f"Trades: {len(recent_trades)}, Bal: ${BALANCE:.2f}, Realized PnL: {realized_pnl:.2f}\n"
    best_strat, best_token = learner.get_best_combo()
    best_line = f"🔥 Best: {best_strat or 'N/A'} / {best_token or 'N/A'}\n"
    for strat in STRATEGIES:
        pnl_list = strat_pnl[strat]
        if pnl_list:
            win_rate = 100 * sum(1 for p in pnl_list if p > 0) / len(pnl_list)
            pnl_sum = sum(pnl_list)
            msg += f"- {strat}: PnL {pnl_sum:.2f}, WR {win_rate:.1f}%\n"
    msg += best_line
    send_discord(msg)

# --- MAIN LOOP ---
print("Starter ChunkyAI AtomicBot ...")
send_discord("❤️ Heartbeat: AtomicBot is alive at " + datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S UTC"))

while True:
    now = datetime.utcnow()
    # Hvert minutt, simuler trade
    strategy, token = pick_token_and_strategy()
    trade = execute_trade(token, strategy, BALANCE)
    BALANCE = trade["balance"]
    trade_history.append(trade)
    learner.log_trade(trade["strategy"], trade["token"], trade["pnl"], trade["timestamp"])
    realized_pnl += trade["pnl"]

    # Discord trade-logg
    trade_msg = (f"[STD] {trade['side']} {trade['token']}: {trade['qty']} @ ${trade['price']}, "
                 f"strategy: {trade['strategy']}, bal: ${BALANCE:.2f}")
    send_discord(trade_msg)

    # Timesrapport hver hele time
    if now.minute == 0 and now > last_report_time:
        hourly_report()
        last_report_time = now.replace(second=0, microsecond=0)
        realized_pnl = 0.0

    # Heartbeat hver 30 sek
    if now.second % 30 == 0:
        send_discord("❤️ Heartbeat: AtomicBot is alive at " + now.strftime("%Y-%m-%d %H:%M:%S UTC"))

    time.sleep(10)  # Høy frekvens, kan settes opp/ned
