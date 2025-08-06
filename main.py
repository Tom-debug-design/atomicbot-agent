import os, random, time, requests, json
from datetime import datetime, timedelta

# ---- SETTINGS ----
TOKENS = [
    "BTCUSDT", "ETHUSDT", "SOLUSDT", "BNBUSDT", "XRPUSDT", "ADAUSDT",
    "DOGEUSDT", "MATICUSDT", "AVAXUSDT", "LINKUSDT"
]
COINGECKO_MAP = {
    "BTCUSDT": "bitcoin", "ETHUSDT": "ethereum", "SOLUSDT": "solana",
    "BNBUSDT": "binancecoin", "XRPUSDT": "ripple", "ADAUSDT": "cardano",
    "DOGEUSDT": "dogecoin", "MATICUSDT": "matic-network",
    "AVAXUSDT": "avalanche-2", "LINKUSDT": "chainlink"
}
DISCORD_WEBHOOK = os.getenv("DISCORD_WEBHOOK")
START_BALANCE = 1000.0
TRADE_PCT = 0.1
MIN_TRADE_PCT = 0.05
MAX_TRADE_PCT = 0.35
STRATEGIES = ["RANDOM", "RSI", "EMA", "SCALP", "MEAN", "TREND"]

# ------------- STOP-LOSS ----------------
GLOBAL_STOP = 350     # Stopp boten hvis balanse < dette (demo/test)
STOP_LOSS_PER_TRADE = -2.0  # Maks tap pr trade i %

# ----------- DYNAMIC EDGE ----------------
EDGE_CONFIRM = 3      # Hvor mange strategier må være enige for å handle
SWITCH_AFTER_LOSSES = 3  # Skift strategi etter X tap på rad

# ----------- AI/ML (random forest placeholder) --------
USE_ML = True

# ---- STATE ----
balance = START_BALANCE
holdings = {s: 0.0 for s in TOKENS}
trade_log = []
current_strategy = "RANDOM"
loss_streak = 0
trade_pct = TRADE_PCT

last_hourly = time.time()
last_daily = datetime.utcnow().date()
hourly_trade_count = 0
best_strat = "RANDOM"

def send_discord(msg):
    print("DISCORD:", msg)
    try:
        requests.post(DISCORD_WEBHOOK, json={"content": msg})
    except Exception as e:
        print("Discord error:", e)

def get_price(symbol):
    coingecko_id = COINGECKO_MAP.get(symbol, "bitcoin")
    url = f"https://api.coingecko.com/api/v3/simple/price?ids={coingecko_id}&vs_currencies=usd"
    try:
        data = requests.get(url, timeout=5).json()
        return float(data[coingecko_id]["usd"])
    except Exception as e:
        print("Price fetch error:", e)
        return None

def rsi_signal(price, holdings):
    # Dummy RSI logic, can upgrade
    if price is None: return "HOLD"
    if price < 25 and holdings == 0: return "BUY"
    if price > 60 and holdings > 0: return "SELL"
    return "HOLD"

def ema_signal(price, holdings):
    if price is None: return "HOLD"
    if int(price) % 2 == 0 and holdings == 0: return "BUY"
    if int(price) % 5 == 0 and holdings > 0: return "SELL"
    return "HOLD"

def scalp_signal(price, holdings):
    # Scalping: buy any random dip
    if price is None: return "HOLD"
    if random.random() < 0.12 and holdings == 0: return "BUY"
    if random.random() < 0.09 and holdings > 0: return "SELL"
    return "HOLD"

def mean_signal(price, holdings):
    if price is None: return "HOLD"
    avg = 45
    if price < avg - 4 and holdings == 0: return "BUY"
    if price > avg + 4 and holdings > 0: return "SELL"
    return "HOLD"

def trend_signal(price, holdings):
    if price is None: return "HOLD"
    if random.random() < 0.1 and holdings == 0: return "BUY"
    if random.random() < 0.07 and holdings > 0: return "SELL"
    return "HOLD"

def random_signal(price, holdings):
    return random.choice(["BUY", "SELL", "HOLD"])

SIGNAL_FUNCS = {
    "RANDOM": random_signal,
    "RSI": rsi_signal,
    "EMA": ema_signal,
    "SCALP": scalp_signal,
    "MEAN": mean_signal,
    "TREND": trend_signal
}

def get_signals(price, holdings):
    signals = {}
    for strat in STRATEGIES:
        signals[strat] = SIGNAL_FUNCS[strat](price, holdings)
    return signals

def handle_trade(symbol, action, price, strategy):
    global balance, holdings, trade_log, trade_pct, loss_streak
    if price is None: return
    qty = round((balance * trade_pct) / price, 6) if action == "BUY" else holdings[symbol]
    pnl = 0.0

    if action == "BUY" and balance >= qty * price and qty > 0:
        balance -= qty * price
        holdings[symbol] += qty
        msg = f"🔵 [CHUNKY-{strategy}] BUY {symbol}: {qty} @ ${price:.2f}, Bal: ${balance:.2f}"
        send_discord(msg)
        trade_log.append({
            "symbol": symbol, "action": "BUY", "price": price,
            "qty": qty, "timestamp": time.time(), "strategy": strategy, "pnl": 0.0
        })
    elif action == "SELL" and holdings[symbol] > 0:
        proceeds = qty * price
        last_buy = next((t for t in reversed(trade_log) if t["symbol"] == symbol and t["action"] == "BUY"), None)
        pnl = ((price - last_buy["price"]) / last_buy["price"] * 100) if last_buy else 0.0
        balance += proceeds
        holdings[symbol] = 0.0
        color = "🟢" if pnl > 0 else "🔴"
        msg = f"🔴 [CHUNKY-{strategy}] SELL {symbol}: {qty} @ ${price:.2f}, PnL: {color} {pnl:.2f}%, Bal: ${balance:.2f}"
        send_discord(msg)
        trade_log.append({
            "symbol": symbol, "action": "SELL", "price": price,
            "qty": qty, "timestamp": time.time(), "strategy": strategy, "pnl": pnl
        })
        # STOP LOSS trigger
        if pnl < STOP_LOSS_PER_TRADE:
            send_discord(f"🚨 [CHUNKY] STOP-LOSS hit! {symbol} PnL: {pnl:.2f}%")
            loss_streak += 1
        elif pnl < 0:
            loss_streak += 1
        else:
            loss_streak = 0

def dynamic_edge_score(signals):
    votes = {"BUY": 0, "SELL": 0}
    for strat, signal in signals.items():
        if signal == "BUY": votes["BUY"] += 1
        if signal == "SELL": votes["SELL"] += 1
    if votes["BUY"] >= EDGE_CONFIRM: return "BUY"
    if votes["SELL"] >= EDGE_CONFIRM: return "SELL"
    return "HOLD"

def best_strategy_report():
    strat_stats = {}
    for strat in STRATEGIES:
        sells = [t for t in trade_log if t["action"] == "SELL" and t["strategy"] == strat]
        pnl = sum(t["pnl"] for t in sells)
        wr = (sum(1 for t in sells if t["pnl"] > 0) / len(sells)) * 100 if sells else 0
        strat_stats[strat] = {"pnl": pnl, "wr": wr}
    best = max(strat_stats, key=lambda s: strat_stats[s]["pnl"])
    return strat_stats, best

def hourly_report():
    strat_stats, best = best_strategy_report()
    realized_pnl = sum(t.get("pnl", 0) for t in trade_log if t["action"] == "SELL")
    total_trades = len(trade_log)
    msg = f"📊 [CHUNKY-EDGE] Hourly report: Trades: {total_trades}, Bal: ${balance:.2f}, Realized PnL: {realized_pnl:.2f}"
    for strat, d in strat_stats.items():
        msg += f"\n- {strat}: PnL {d['pnl']:.2f}, WR {d['wr']:.1f}%"
    msg += f"\n🔥 Best: {best}"
    send_discord(msg)

def daily_report():
    strat_stats, best = best_strategy_report()
    realized_pnl = sum(t.get("pnl", 0) for t in trade_log if t["action"] == "SELL")
    total_trades = len(trade_log)
    msg = f"📅 [CHUNKY-EDGE] Daily report: Trades: {total_trades}, Bal: ${balance:.2f}, Realized PnL: {realized_pnl:.2f}"
    for strat, d in strat_stats.items():
        msg += f"\n- {strat}: PnL {d['pnl']:.2f}, WR {d['wr']:.1f}%"
    msg += f"\n🔥 Best: {best}"
    send_discord(msg)

def ai_learn(trades):
    # Placeholder for ML/RandomForest training
    # Kan bygges ut til å bruke trade-log som feature set
    if USE_ML:
        # Simulert "learning"
        if len(trades) > 1000:
            send_discord("🧠 [CHUNKY-EDGE] ML-model oppdatert på trades!")

def stop_bot():
    send_discord("⛔️ [CHUNKY-EDGE] Bot stopped! (Global stop-loss)")
    exit()

send_discord("🟢 [CHUNKY-EDGE] AtomicBot starter…")

# --------------- MAIN LOOP ----------------

while True:
    if balance < GLOBAL_STOP:
        stop_bot()

    for symbol in TOKENS:
        price = get_price(symbol)
        signals = get_signals(price, holdings[symbol])
        action = dynamic_edge_score(signals)

        # Optional: override for testing
        # action = random.choice(["BUY", "SELL", "HOLD"])

        if action in ("BUY", "SELL"):
            handle_trade(symbol, action, price, current_strategy)
    # Switch strategy after X losses
    if loss_streak >= SWITCH_AFTER_LOSSES:
        old_strat = current_strategy
        current_strategy = random.choice([s for s in STRATEGIES if s != old_strat])
        send_discord(f"🔁 [CHUNKY] Switch strat after losses! {old_strat} ➡️ {current_strategy}")
        loss_streak = 0
    # Hourly/daily report
    now = datetime.utcnow()
    if time.time() - last_hourly > 3600:
        hourly_report()
        ai_learn(trade_log)
        last_hourly = time.time()
    if now.date() != last_daily and now.hour >= 7:
        daily_report()
        last_daily = now.date()
    time.sleep(15)