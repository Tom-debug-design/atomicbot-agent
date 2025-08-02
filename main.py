import random, time, os, requests
from collections import deque, defaultdict
from datetime import datetime, timedelta

# --- SETTINGS ---
TOKENS = [
    "BTCUSDT", "ETHUSDT", "SOLUSDT", "BNBUSDT", "XRPUSDT", "ADAUSDT",
    "DOGEUSDT", "MATICUSDT", "AVAXUSDT", "LINKUSDT"
]
STRATEGIES = ["RSI", "EMA", "MEAN", "RANDOM", "SCALP"]
DISCORD_WEBHOOK = os.getenv("DISCORD_WEBHOOK")
START_BALANCE = 1000.0

# --- EDGE/LEARNER ---
class StrategyLearner:
    def __init__(self, window_size=20):
        self.window_size = window_size
        self.history = deque(maxlen=window_size)  # (strategy, token, pnl, ts)
    def log_trade(self, strategy, token, pnl, timestamp=None):
        self.history.append((strategy, token, pnl, timestamp))
    def get_top_n_combos(self, n=5):
        stats = defaultdict(list)
        for strat, token, pnl, _ in self.history:
            stats[(strat, token)].append(pnl)
        ranked = sorted(stats.items(), key=lambda x: sum(x[1])/len(x[1]), reverse=True)
        return [combo for combo, _ in ranked[:n]]
    def get_stats(self):
        stats = defaultdict(list)
        for strat, token, pnl, _ in self.history:
            stats[(strat, token)].append(pnl)
        return {k: sum(v)/len(v) for k,v in stats.items()}

learner = StrategyLearner(window_size=20)
trade_log = []  # full historikk for rapport

# --- DISCORD ---
def send_discord(msg):
    try:
        requests.post(DISCORD_WEBHOOK, json={"content": msg})
    except Exception as e:
        print(f"Discord error: {e}")

# --- FAKE PRICE (demo, bytt ut med ekte pris-funksjon) ---
def get_price(symbol):
    return random.uniform(10, 60)

# --- MAIN LOOP ---
balance = START_BALANCE
holdings = {symbol: 0.0 for symbol in TOKENS}
last_hourly = time.time()
last_daily = datetime.utcnow().replace(hour=6, minute=0, second=0, microsecond=0).timestamp()
TRADE_FREQ_SEC = 4   # juster for aggressivitet

def hourly_report():
    now = datetime.utcnow().strftime("%Y-%m-%d %H:%M")
    trades = [t for t in trade_log if t["timestamp"] > time.time()-3600]
    wins = sum(1 for t in trades if t.get("pnl",0) > 0)
    losses = sum(1 for t in trades if t.get("pnl",0) < 0)
    realized_pnl = sum(t.get("pnl",0) for t in trades)
    total = len(trades)
    winrate = (wins/total*100) if total else 0
    stratstats = defaultdict(list)
    for t in trades:
        stratstats[(t["strategy"], t["token"])].append(t.get("pnl",0))
    if stratstats:
        best = max(stratstats, key=lambda x: sum(stratstats[x])/len(stratstats[x]))
        beststat = f"{best[0]} on {best[1]}"
    else:
        beststat = "n/a"
    msg = (
        f"📊 **Hourly report {now}**\n"
        f"Trades: {total} | Wins: {wins} | Losses: {losses} | Win-rate: {winrate:.1f}%\n"
        f"Realized PnL: {realized_pnl:.2f} | Best strat/token: {beststat}\n"
        f"Balance: ${balance:.2f}"
    )
    send_discord(msg)

def daily_report():
    now = datetime.utcnow().strftime("%Y-%m-%d")
    # Få med alle trades siste UTC-døgn
    midnight = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0).timestamp()
    trades = [t for t in trade_log if t["timestamp"] > midnight]
    wins = sum(1 for t in trades if t.get("pnl",0) > 0)
    losses = sum(1 for t in trades if t.get("pnl",0) < 0)
    realized_pnl = sum(t.get("pnl",0) for t in trades)
    total = len(trades)
    winrate = (wins/total*100) if total else 0
    stratstats = defaultdict(list)
    for t in trades:
        stratstats[(t["strategy"], t["token"])].append(t.get("pnl",0))
    if stratstats:
        best = max(stratstats, key=lambda x: sum(stratstats[x])/len(stratstats[x]))
        beststat = f"{best[0]} on {best[1]}"
    else:
        beststat = "n/a"
    msg = (
        f"📈 **Dagsrapport {now} (UTC 06:00)**\n"
        f"Trades: {total} | Wins: {wins} | Losses: {losses} | Win-rate: {winrate:.1f}%\n"
        f"Realized PnL: {realized_pnl:.2f} | Best strat/token: {beststat}\n"
        f"Balance: ${balance:.2f}\n"
        f"Strategi stats: {dict(learner.get_stats())}"
    )
    send_discord(msg)

def pick_next_combo():
    combos = learner.get_top_n_combos(n=5)
    if combos:
        return random.choice(combos)
    else:
        return (random.choice(STRATEGIES), random.choice(TOKENS))

send_discord("🟢 ChunkyBot starter v3 med edge, times- og dagsrapport...")

while True:
    # 1. Velg strategi og token
    strategy, symbol = pick_next_combo()
    price = get_price(symbol)
    holding = holdings[symbol]

    # 2. Signal (veldig enkel/demo, bytt ut med ekte signalgenerator!)
    if random.random() < 0.5:
        action = "BUY"
    else:
        action = "SELL" if holding > 0 else "HOLD"

    qty = round(balance*0.1/price, 4) if action=="BUY" else holding
    pnl = 0.0

    # 3. Gjør trade og logg
    if action == "BUY" and balance >= qty*price:
        balance -= qty*price
        holdings[symbol] += qty
        trade_log.append({"action":"BUY", "symbol":symbol, "strategy":strategy, "token":symbol,
                          "price":price, "qty":qty, "timestamp":time.time(), "pnl":0.0})
        learner.log_trade(strategy, symbol, 0.0, time.time())
        send_discord(f"[STD] BUY {symbol} {qty} @ ${price:.2f} | Strat: {strategy} | Bal: ${balance:.2f}")
    elif action == "SELL" and holding > 0:
        proceeds = holding*price
        last_buy = next((t for t in reversed(trade_log) if t["symbol"]==symbol and t["action"]=="BUY"), None)
        pnl = (price-last_buy["price"])/last_buy["price"]*100 if last_buy else 0.0
        balance += proceeds
        holdings[symbol] = 0.0
        trade_log.append({"action":"SELL", "symbol":symbol, "strategy":strategy, "token":symbol,
                          "price":price, "qty":holding, "timestamp":time.time(), "pnl":pnl})
        learner.log_trade(strategy, symbol, pnl, time.time())
        send_discord(f"[STD] SELL {symbol} {holding} @ ${price:.2f} | PnL: {pnl:.2f}% | Strat: {strategy} | Bal: ${balance:.2f}")

    # 4. Time-rapport (hver time)
    if time.time() - last_hourly > 3600:
        hourly_report()
        last_hourly = time.time()

    # 5. Dagsrapport 06:00 UTC
    now_utc = datetime.utcnow().timestamp()
    if now_utc > last_daily:
        daily_report()
        # Sett neste rapport til 06:00 i morgen
        tomorrow = datetime.utcnow() + timedelta(days=1)
        last_daily = tomorrow.replace(hour=6, minute=0, second=0, microsecond=0).timestamp()

    time.sleep(TRADE_FREQ_SEC)
