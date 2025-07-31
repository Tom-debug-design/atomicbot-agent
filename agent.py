import random, time, os, requests, csv
import pandas as pd
from sklearn.ensemble import RandomForestClassifier
import joblib

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

balance = START_BALANCE
holdings = {symbol: 0.0 for symbol in TOKENS}
trade_log = []
auto_buy_pct = 0.10

def calc_rsi(price, prev_price):
    return 50 + (price - prev_price) * 0.5

def calc_ema(price, prev_ema, alpha=0.2):
    return alpha * price + (1 - alpha) * prev_ema

def send_discord(msg):
    try:
        requests.post(DISCORD_WEBHOOK, json={"content": msg})
    except Exception as e:
        print(f"Discord error: {e}")

def get_price(symbol):
    coingecko_id = COINGECKO_MAP.get(symbol, "bitcoin")
    url = f"https://api.coingecko.com/api/v3/simple/price?ids={coingecko_id}&vs_currencies=usd"
    try:
        data = requests.get(url, timeout=3).json()
        return float(data[coingecko_id]["usd"])
    except Exception as e:
        print(f"Price fetch error: {e}")
        return None

def choose_strategy():
    return random.choice(["RSI", "EMA", "MOMENTUM", "RANDOM"])

trend_memory = {symbol: [] for symbol in TOKENS}

def get_trend(symbol, price):
    mem = trend_memory[symbol]
    mem.append(price)
    if len(mem) > 4:
        mem.pop(0)
    if len(mem) < 3:
        return 0
    trend = 0
    if mem[-1] > mem[-2] > mem[-3]:
        trend = 1
    elif mem[-1] < mem[-2] < mem[-3]:
        trend = -1
    return trend

def log_signal(symbol, price, rsi, ema, holdings, strategy, trend, action, pnl=0):
    with open("ai_data_log.csv", "a", newline="") as f:
        writer = csv.writer(f)
        writer.writerow([time.time(), symbol, price, rsi, ema, holdings, strategy, trend, action, pnl])

def ai_predict_action(price, rsi, ema, holdings, trend):
    import os
    if not os.path.exists("atomicbot_model.pkl"):
        return None
    try:
        clf = joblib.load("atomicbot_model.pkl")
        X = [[price, rsi, ema, holdings, trend]]
        y_pred = clf.predict(X)[0]
        y_prob = clf.predict_proba(X)[0][1]  # sannsynlighet for “profitable”
        return y_pred, y_prob
    except Exception as e:
        print(f"AI-prediksjon feilet: {e}")
        return None

def get_signal(strategy, price, holdings, trend, rsi, ema):
    # Prøv AI-beslutning først!
    pred = ai_predict_action(price, rsi, ema, holdings, trend)
    if pred:
        y_pred, y_prob = pred
        # Mer konservativ: Kun handle hvis AI er veldig sikker
        if y_pred == 1 and y_prob > 0.7 and holdings == 0:
            return "BUY"
        elif y_pred == 1 and y_prob > 0.7 and holdings > 0:
            return "SELL"
        else:
            return "HOLD"
    # Fallback: gammel strategi
    if price is None: return "HOLD"
    if strategy == "RSI":
        if rsi < 40 and holdings == 0:
            return "BUY"
        elif rsi > 60 and holdings > 0:
            return "SELL"
        else:
            return "HOLD"
    elif strategy == "EMA":
        if price > ema and holdings == 0:
            return "BUY"
        elif price < ema and holdings > 0:
            return "SELL"
        else:
            return "HOLD"
    elif strategy == "MOMENTUM":
        if trend == 1 and holdings == 0:
            return "BUY"
        elif trend == -1 and holdings > 0:
            return "SELL"
        else:
            return "HOLD"
    else:
        return random.choice(["BUY", "SELL", "HOLD"])

def handle_trade(symbol, action, price, strategy, rsi, ema, trend):
    global balance, holdings, trade_log, auto_buy_pct
    if price is None: return
    amount_usd = balance * auto_buy_pct if action == "BUY" else holdings[symbol] * price
    qty = round(amount_usd / price, 6) if action == "BUY" else holdings[symbol]
    pnl = 0.0

    if action == "BUY" and balance >= amount_usd and qty > 0:
        balance -= amount_usd
        holdings[symbol] += qty
        send_discord(f"🔵 BUY {symbol}: {qty} @ ${price:.2f}, bal: ${balance:.2f}")
        trade_log.append({"symbol": symbol, "action": "BUY", "price": price,
                          "qty": qty, "timestamp": time.time(), "strategy": strategy, "pnl": 0.0})
        log_signal(symbol, price, rsi, ema, holdings[symbol], strategy, trend, "BUY", 0.0)
    elif action == "SELL" and holdings[symbol] > 0:
        proceeds = qty * price
        last_buy = next((t for t in reversed(trade_log) if t["symbol"] == symbol and t["action"] == "BUY"), None)
        pnl = ((price - last_buy["price"]) / last_buy["price"] * 100) if last_buy else 0.0
        balance += proceeds
        holdings[symbol] = 0.0
        send_discord(f"🔴 SELL {symbol}: {qty} @ ${price:.2f}, PnL: {pnl:.2f}%, bal: ${balance:.2f}")
        trade_log.append({"symbol": symbol, "action": "SELL", "price": price,
                          "qty": qty, "timestamp": time.time(), "strategy": strategy, "pnl": pnl})
        log_signal(symbol, price, rsi, ema, 0.0, strategy, trend, "SELL", pnl)

def get_best_strategy(trade_log):
    recent = [t for t in trade_log[-30:] if t["action"] == "SELL"]
    strat_stats = {}
    for t in recent:
        s = t.get("strategy", "RANDOM")
        strat_stats.setdefault(s, []).append(t.get("pnl", 0))
    if not strat_stats: return choose_strategy()
    best = max(strat_stats, key=lambda x: sum(strat_stats[x])/len(strat_stats[x]) if strat_stats[x] else -999)
    return best

def auto_tune(trade_log):
    global auto_buy_pct
    recent = [t for t in trade_log[-10:] if t["action"] == "SELL"]
    pnl_sum = sum(t.get("pnl", 0) for t in recent)
    if recent and pnl_sum > 0 and auto_buy_pct < 0.3:
        auto_buy_pct += 0.02
        send_discord(f"🔧 AI auto-tuning: Øker buy% til {auto_buy_pct*100:.1f}")
    elif recent and pnl_sum < 0 and auto_buy_pct > 0.05:
        auto_buy_pct -= 0.01
        send_discord(f"🔧 AI auto-tuning: Senker buy% til {auto_buy_pct*100:.1f}")

def hourly_report():
    total_trades = len(trade_log)
    realized_pnl = sum(t.get("pnl", 0) for t in trade_log if t["action"] == "SELL")
    msg = f"📊 Hourly Report: Trades: {total_trades}, Realized PnL: {realized_pnl:.2f}%, Balance: ${balance:.2f}"
    send_discord(msg)

def ai_feedback():
    best = get_best_strategy(trade_log)
    send_discord(f"🤖 AI: Best strategy last 30: {best}")

# --- ML-trening (selvkjørende) ---
last_train = time.time()
def retrain_ai_model():
    try:
        df = pd.read_csv("ai_data_log.csv", header=None,
            names=["timestamp", "symbol", "price", "rsi", "ema", "holdings", "strategy", "trend", "action", "pnl"])
        df = df[df["action"].isin(["SELL", "BUY"])]
        df["target"] = (df["pnl"] > 0).astype(int)
        X = df[["price", "rsi", "ema", "holdings", "trend"]]
        y = df["target"]
        clf = RandomForestClassifier(n_estimators=50)
        clf.fit(X, y)
        joblib.dump(clf, "atomicbot_model.pkl")
        send_discord("🤖 AI-modell trent og lagret (self-learn)!")
        print("AI-modell automatisk trent og lagret!")
    except Exception as e:
        print(f"AI-trening feilet: {e}")

send_discord("🟢 AtomicBot AI-Live Decision Mode starter…")
last_report = time.time()
ema_memory = {symbol: None for symbol in TOKENS}
prev_price = {symbol: None for symbol in TOKENS}

while True:
    for symbol in TOKENS:
        price = get_price(symbol)
        if price is None: continue
        prev_p = prev_price[symbol] if prev_price[symbol] else price
        rsi = calc_rsi(price, prev_p)
        ema = calc_ema(price, ema_memory[symbol] if ema_memory[symbol] else price)
        trend = get_trend(symbol, price)
        prev_price[symbol] = price
        ema_memory[symbol] = ema

        strategy = get_best_strategy(trade_log) if len(trade_log) > 30 else choose_strategy()
        action = get_signal(strategy, price, holdings[symbol], trend, rsi, ema)
        print(f"{symbol} | Pris: {price} | Strat: {strategy} | RSI: {rsi:.1f} | EMA: {ema:.1f} | Trend: {trend} | Signal: {action}")
        if action in ("BUY", "SELL"):
            handle_trade(symbol, action, price, strategy, rsi, ema, trend)
        else:
            log_signal(symbol, price, rsi, ema, holdings[symbol], strategy, trend, action, 0.0)
        time.sleep(0.2)
    if time.time() - last_report > 60:
        hourly_report()
        ai_feedback()
        auto_tune(trade_log)
        last_report = time.time()
    if time.time() - last_train > 43200:
        retrain_ai_model()
        last_train = time.time()
