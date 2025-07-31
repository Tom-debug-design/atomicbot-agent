import random, time, os, requests, csv, json
import pandas as pd
from sklearn.ensemble import RandomForestClassifier
import joblib

TOKENS = [
    "BTCUSDT", "ETHUSDT", "SOLUSDT", "BNBUSDT", "XRPUSDT", "ADAUSDT",
    "DOGEUSDT", "MATICUSDT", "AVAXUSDT", "LINKUSDT", "FILUSDT", "LTCUSDT", "TRXUSDT", "ATOMUSDT", "SUIUSDT", "BCHUSDT", "ARBUSDT", "PEPEUSDT", "TUSDT", "ETCUSDT"
]
COINGECKO_MAP = {
    "BTCUSDT": "bitcoin", "ETHUSDT": "ethereum", "SOLUSDT": "solana",
    "BNBUSDT": "binancecoin", "XRPUSDT": "ripple", "ADAUSDT": "cardano",
    "DOGEUSDT": "dogecoin", "MATICUSDT": "matic-network",
    "AVAXUSDT": "avalanche-2", "LINKUSDT": "chainlink", "FILUSDT": "filecoin",
    "LTCUSDT": "litecoin", "TRXUSDT": "tron", "ATOMUSDT": "cosmos",
    "SUIUSDT": "sui", "BCHUSDT": "bitcoin-cash", "ARBUSDT": "arbitrum",
    "PEPEUSDT": "pepe", "TUSDT": "threshold", "ETCUSDT": "ethereum-classic"
}
DISCORD_WEBHOOK = os.getenv("DISCORD_WEBHOOK")
START_BALANCE = 1000.0

balance = START_BALANCE
holdings = {symbol: 0.0 for symbol in TOKENS}
trade_log = []
auto_buy_pct = 0.10

LOGFILE = "trades.jsonl"
AICSV = "ai_data_log.csv"
AIMODEL = "atomicbot_model.pkl"

def send_discord(msg):
    print("DISCORD:", msg)
    if DISCORD_WEBHOOK:
        try:
            requests.post(DISCORD_WEBHOOK, json={"content": msg})
        except Exception as e:
            print(f"Discord error: {e}")

def log_trade(entry):
    try:
        with open(LOGFILE, "a") as f:
            f.write(json.dumps(entry) + "\n")
    except Exception as e:
        print(f"File log error: {e}")

def log_ai_data(row):
    write_header = not os.path.exists(AICSV)
    with open(AICSV, "a", newline="") as f:
        writer = csv.writer(f)
        if write_header:
            writer.writerow(["timestamp","symbol","price","rsi","ema","holdings","strategy","trend","balance","action","pnl"])
        writer.writerow(row)

def get_price(symbol):
    coingecko_id = COINGECKO_MAP.get(symbol, "bitcoin")
    url = f"https://api.coingecko.com/api/v3/simple/price?ids={coingecko_id}&vs_currencies=usd"
    try:
        data = requests.get(url, timeout=5).json()
        return float(data[coingecko_id]["usd"])
    except Exception as e:
        print(f"Price fetch error: {e}")
        return None

def calc_rsi(price, prev_price):
    # Simpel RSI for test – kan byttes ut!
    return 50 + (price - prev_price) * 0.5

def calc_ema(price, prev_ema, alpha=0.2):
    return alpha * price + (1 - alpha) * prev_ema

trend_memory = {symbol: [] for symbol in TOKENS}
def get_trend(symbol, price):
    mem = trend_memory[symbol]
    mem.append(price)
    if len(mem) > 4:
        mem.pop(0)
    if len(mem) < 3:
        return 0
    if mem[-1] > mem[-2] > mem[-3]:
        return 1
    elif mem[-1] < mem[-2] < mem[-3]:
        return -1
    else:
        return 0

def retrain_ai_model():
    if not os.path.exists(AICSV): return
    df = pd.read_csv(AICSV)
    if len(df) < 100: return  # Vent til litt data!
    X = df[["price","rsi","ema","holdings","trend","balance"]]
    y = (df["pnl"] > 0).astype(int)
    clf = RandomForestClassifier(n_estimators=50)
    clf.fit(X, y)
    joblib.dump(clf, AIMODEL)
    send_discord("🤖 AI-modell trent og lagret!")
    print("AI-modell trent og lagret!")

def ai_predict_action(price, rsi, ema, holdings, trend, balance):
    import os
    if not os.path.exists(AIMODEL):
        return None
    try:
        clf = joblib.load(AIMODEL)
        X = [[price, rsi, ema, holdings, trend, balance]]
        y_pred = clf.predict(X)[0]
        y_prob = clf.predict_proba(X)[0][1]
        return y_pred, y_prob
    except Exception as e:
        print(f"AI-prediksjon feilet: {e}")
        return None

def choose_strategy():
    return random.choice(["RSI", "EMA", "RANDOM"])

def get_signal(strategy, price, holdings, trend, rsi, ema, balance):
    pred = ai_predict_action(price, rsi, ema, holdings, trend, balance)
    if pred:
        y_pred, y_prob = pred
        if y_pred == 1 and y_prob > 0.7 and holdings == 0:
            return "BUY"
        elif y_pred == 1 and y_prob > 0.7 and holdings > 0:
            return "SELL"
        else:
            return "HOLD"
    # Fallback: gammel strategi!
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
    else:
        return random.choice(["BUY", "SELL", "HOLD"])

def handle_trade(symbol, action, price, strategy, rsi, ema, trend, balance):
    global balance as g_balance, holdings, trade_log, auto_buy_pct
    if price is None: return
    amount_usd = g_balance * auto_buy_pct if action == "BUY" else holdings[symbol] * price
    qty = round(amount_usd / price, 6) if action == "BUY" else holdings[symbol]
    pnl = 0.0
    timestamp = time.time()
    if action == "BUY" and g_balance >= amount_usd and qty > 0:
        g_balance -= amount_usd
        holdings[symbol] += qty
        send_discord(f"🔵 BUY {symbol}: {qty} @ ${price:.2f}, bal: ${g_balance:.2f}")
        trade = {
            "timestamp": timestamp, "symbol": symbol, "action": "BUY", "price": price,
            "qty": qty, "strategy": strategy, "pnl": 0.0, "rsi": rsi, "ema": ema, "trend": trend, "balance": g_balance
        }
        trade_log.append(trade)
        log_trade(trade)
        log_ai_data([timestamp, symbol, price, rsi, ema, holdings[symbol], strategy, trend, g_balance, "BUY", 0.0])
    elif action == "SELL" and holdings[symbol] > 0:
        proceeds = qty * price
        last_buy = next((t for t in reversed(trade_log) if t["symbol"] == symbol and t["action"] == "BUY"), None)
        pnl = ((price - last_buy["price"]) / last_buy["price"] * 100) if last_buy else 0.0
        g_balance += proceeds
        holdings[symbol] = 0.0
        send_discord(f"🔴 SELL {symbol}: {qty} @ ${price:.2f}, PnL: {pnl:.2f}%, bal: ${g_balance:.2f}")
        trade = {
            "timestamp": timestamp, "symbol": symbol, "action": "SELL", "price": price,
            "qty": qty, "strategy": strategy, "pnl": pnl, "rsi": rsi, "ema": ema, "trend": trend, "balance": g_balance
        }
        trade_log.append(trade)
        log_trade(trade)
        log_ai_data([timestamp, symbol, price, rsi, ema, 0.0, strategy, trend, g_balance, "SELL", pnl])

def get_best_strategy(trade_log, n=30):
    recent = [t for t in trade_log[-n:] if t["action"] == "SELL"]
    strat_stats = {}
    for t in recent:
        s = t.get("strategy", "RANDOM")
        strat_stats.setdefault(s, []).append(t.get("pnl", 0))
    if not strat_stats:
        return choose_strategy()
    best = max(strat_stats, key=lambda x: sum(strat_stats[x])/len(strat_stats[x]) if strat_stats[x] else -999)
    return best

def auto_tune(trade_log):
    global auto_buy_pct
    recent = [t for t in trade_log[-10:] if t["action"] == "SELL"]
    pnl_sum = sum(t.get("pnl", 0) for t in recent)
    if recent and pnl_sum > 0 and auto_buy_pct < 0.25:
        auto_buy_pct += 0.02
        send_discord(f"🔧 AI auto-tuning: Øker buy% til {auto_buy_pct*100:.1f}")
    elif recent and pnl_sum < 0 and auto_buy_pct > 0.05:
        auto_buy_pct -= 0.02
        send_discord(f"🔧 AI auto-tuning: Senker buy% til {auto_buy_pct*100:.1f}")

def hourly_report():
    total_trades = len(trade_log)
    realized_pnl = sum(t.get("pnl", 0) for t in trade_log if t["action"] == "SELL")
    msg = f"📊 Hourly Report: Trades: {total_trades}, Realized PnL: {realized_pnl:.2f}%, Balance: ${balance:.2f}"
    send_discord(msg)

def ai_feedback():
    best = get_best_strategy(trade_log)
    send_discord(f"🤖 AI: Best strategy last 30: {best}")

send_discord("🟢 AtomicBot AI Turbo Chunky v4 starter!")
last_report = time.time()
ema_memory = {symbol: None for symbol in TOKENS}
prev_price = {symbol: None for symbol in TOKENS}
last_train = time.time()

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

        strategy = get_best_strategy(trade_log, 30) if len(trade_log) > 30 else choose_strategy()
        action = get_signal(strategy, price, holdings[symbol], trend, rsi, ema, balance)
        print(f"{symbol} | Pris: {price:.2f} | Strat: {strategy} | RSI: {rsi:.1f} | EMA: {ema:.1f} | Trend: {trend} | Signal: {action}")
        if action in ("BUY", "SELL"):
            handle_trade(symbol, action, price, strategy, rsi, ema, trend, balance)
        else:
            log_ai_data([time.time(), symbol, price, rsi, ema, holdings[symbol], strategy, trend, balance, action, 0.0])
        time.sleep(0.2)
    if time.time() - last_report > 60:
        hourly_report()
        ai_feedback()
        auto_tune(trade_log)
        last_report = time.time()
    # ML-trening hver 12. time eller hvis du vil: endre til oftere for test!
    if time.time() - last_train > 43200:
        retrain_ai_model()
        last_train = time.time()
