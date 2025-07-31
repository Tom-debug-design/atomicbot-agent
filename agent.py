import random, time, os, requests, csv

MODE = "backtest"    # Chunky styrer selv - starter i backtest
TOKENS = [
    "BTCUSDT", "ETHUSDT", "SOLUSDT", "BNBUSDT", "XRPUSDT"
]
COINGECKO_MAP = {
    "BTCUSDT": "bitcoin", "ETHUSDT": "ethereum", "SOLUSDT": "solana",
    "BNBUSDT": "binancecoin", "XRPUSDT": "ripple"
}
DISCORD_WEBHOOK = os.getenv("DISCORD_WEBHOOK")
START_BALANCE = 1000.0
balance = START_BALANCE
holdings = {symbol: 0.0 for symbol in TOKENS}
trade_log = []
auto_buy_pct = 0.1
MAX_HOLD_MINUTES = 20
last_trade_time = {symbol: None for symbol in TOKENS}

def send_discord(msg):
    print("DISCORD:", msg)
    try:
        if DISCORD_WEBHOOK and MODE == "live":
            requests.post(DISCORD_WEBHOOK, json={"content": msg})
    except Exception as e:
        print(f"Discord error: {e}")

def make_dummy_backtest(tokens=None, n=2000):
    if tokens is None:
        tokens = ["BTCUSDT", "ETHUSDT"]
    with open("backtest_data.csv", "w", newline='') as f:
        writer = csv.writer(f)
        writer.writerow(["timestamp", "symbol", "price"])
        ts = int(time.time()) - n*60
        for i in range(n):
            for sym in tokens:
                price = round(20000 + random.gauss(0,1)*3000 + random.gauss(0,1)*500*i/n, 2)
                writer.writerow([ts, sym, price])
            ts += 60
    print(f"Laget backtest_data.csv med {n*len(tokens)} rader for backtest!")

def get_price(symbol, backtest_row=None):
    if MODE == "backtest":
        return backtest_row["price"] if backtest_row is not None else None
    coingecko_id = COINGECKO_MAP.get(symbol, "bitcoin")
    url = f"https://api.coingecko.com/api/v3/simple/price?ids={coingecko_id}&vs_currencies=usd"
    try:
        data = requests.get(url, timeout=5).json()
        price = float(data[coingecko_id]["usd"])
        return price
    except Exception:
        send_discord(f"⚠️ Price fetch error for {symbol}")
        return None

def choose_strategy():
    return random.choice(["RSI", "EMA", "RANDOM"])

def get_signal(strategy, price, holdings):
    if price is None: return "HOLD"
    if strategy == "RSI":
        if price < 25 and holdings == 0:
            return "BUY"
        elif price > 60 and holdings > 0:
            return "SELL"
        else:
            return "HOLD"
    elif strategy == "EMA":
        if int(price) % 2 == 0 and holdings == 0:
            return "BUY"
        elif int(price) % 5 == 0 and holdings > 0:
            return "SELL"
        else:
            return "HOLD"
    else:
        return random.choice(["BUY", "SELL", "HOLD"])

def handle_trade(symbol, action, price, strategy, ts):
    global balance, holdings, trade_log, auto_buy_pct, last_trade_time
    if price is None: return
    amount_usd = balance * auto_buy_pct if action == "BUY" else holdings[symbol] * price
    qty = round(amount_usd / price, 6) if action == "BUY" else holdings[symbol]
    pnl = 0.0

    if action == "BUY" and balance >= amount_usd and qty > 0:
        balance -= amount_usd
        holdings[symbol] += qty
        last_trade_time[symbol] = ts
        send_discord(f"🔵 BUY {symbol}: {qty} at ${price:.2f}, new balance ${balance:.2f}")
        trade_log.append({
            "timestamp": ts, "symbol": symbol, "action": "BUY", "price": price,
            "qty": qty, "strategy": strategy, "pnl": 0.0, "balance": balance
        })
    elif action == "SELL" and holdings[symbol] > 0:
        proceeds = qty * price
        last_buy = next((t for t in reversed(trade_log) if t["symbol"] == symbol and t["action"] == "BUY"), None)
        pnl = ((price - last_buy["price"]) / last_buy["price"] * 100) if last_buy else 0.0
        balance += proceeds
        holdings[symbol] = 0.0
        last_trade_time[symbol] = ts
        send_discord(f"🔴 SELL {symbol}: {qty} at ${price:.2f}, PnL: {pnl:.2f}%, balance: ${balance:.2f}")
        trade_log.append({
            "timestamp": ts, "symbol": symbol, "action": "SELL", "price": price,
            "qty": qty, "strategy": strategy, "pnl": pnl, "balance": balance
        })

def force_sell(symbol, price, ts):
    global holdings, balance, trade_log, last_trade_time
    if holdings[symbol] > 0 and price:
        qty = holdings[symbol]
        proceeds = qty * price
        last_buy = next((t for t in reversed(trade_log) if t["symbol"] == symbol and t["action"] == "BUY"), None)
        pnl = ((price - last_buy["price"]) / last_buy["price"] * 100) if last_buy else 0.0
        balance += proceeds
        holdings[symbol] = 0.0
        last_trade_time[symbol] = ts
        send_discord(f"⏱️ FORCE SELL {symbol}: {qty} at ${price:.2f}, PnL: {pnl:.2f}%, balance: ${balance:.2f}")
        trade_log.append({
            "timestamp": ts, "symbol": symbol, "action": "FORCE_SELL", "price": price,
            "qty": qty, "strategy": "FORCE", "pnl": pnl, "balance": balance
        })

def save_log():
    with open("chunky_trades_log.csv", "w", newline='') as f:
        writer = csv.DictWriter(f, fieldnames=["timestamp","symbol","action","price","qty","strategy","pnl","balance"])
        writer.writeheader()
        writer.writerows(trade_log)

# ----------- MAIN CHUNKY BOT LOOP -----------

if MODE == "backtest":
    try:
        with open("backtest_data.csv") as f: pass
    except Exception:
        make_dummy_backtest(tokens=TOKENS, n=1000)
    import pandas as pd
    df = pd.read_csv("backtest_data.csv")
    df = df[df.symbol.isin(TOKENS)].sort_values("timestamp")
    data_stream = df.to_dict("records")
else:
    data_stream = [None] * 999999

print(f"🟢 ChunkyBot starter i {MODE.upper()} MODUS!")

step = 0
while True:
    if MODE == "backtest":
        if step >= len(data_stream):
            print("Backtest ferdig! Switche chunky til LIVE trading! 🚀")
            save_log()
            MODE = "live"
            step = 0
            continue
        row = data_stream[step]
        ts, symbol, price = row["timestamp"], row["symbol"], row["price"]
        strategy = choose_strategy()
        action = get_signal(strategy, price, holdings[symbol])
        if holdings[symbol] > 0 and last_trade_time[symbol]:
            age_min = (ts - last_trade_time[symbol]) / 60
            if age_min > MAX_HOLD_MINUTES:
                force_sell(symbol, price, ts)
                step += 1
                continue
        if action in ("BUY", "SELL"):
            handle_trade(symbol, action, price, strategy, ts)
        step += 1
        if step % 1000 == 0:
            print(f"Backtest steg: {step}/{len(data_stream)}")
    else:
        for symbol in TOKENS:
            price = get_price(symbol)
            ts = time.time()
            strategy = choose_strategy()
            action = get_signal(strategy, price, holdings[symbol])
            if holdings[symbol] > 0 and last_trade_time[symbol]:
                age_min = (ts - last_trade_time[symbol]) / 60
                if age_min > MAX_HOLD_MINUTES:
                    force_sell(symbol, price, ts)
                    continue
            if action in ("BUY", "SELL"):
                handle_trade(symbol, action, price, strategy, ts)
        time.sleep(30)
