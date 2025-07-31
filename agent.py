import random, time, os, requests

# --- SETTINGS ---
TOKENS = ["BTCUSDT", "ETHUSDT", "SOLUSDT"]
DISCORD_WEBHOOK = os.getenv("DISCORD_WEBHOOK")
START_BALANCE = 1000.0

# --- STATE ---
balance = START_BALANCE
holdings = {symbol: 0.0 for symbol in TOKENS}
trade_log = []

def send_discord(msg):
    try:
        requests.post(DISCORD_WEBHOOK, json={"content": msg})
    except Exception as e:
        print(f"Discord error: {e}")

def get_price(symbol):
    # Demo: random price, bytt med real API-kall hvis du vil
    return round(random.uniform(100, 50000), 2)

def choose_strategy():
    # Dummy – kan byttes med AI/learning senere!
    return random.choice(["RSI", "EMA", "RANDOM"])

def get_signal(strategy, price, holdings):
    if strategy == "RSI":
        if price < 2000 and holdings == 0:
            return "BUY"
        elif price > 4000 and holdings > 0:
            return "SELL"
        else:
            return "HOLD"
    elif strategy == "EMA":
        if price % 2 < 1 and holdings == 0:
            return "BUY"
        elif price % 5 > 3 and holdings > 0:
            return "SELL"
        else:
            return "HOLD"
    else:
        return random.choice(["BUY", "SELL", "HOLD"])

def handle_trade(symbol, action, price):
    global balance, holdings, trade_log
    amount_usd = balance * 0.1 if action == "BUY" else holdings[symbol] * price
    qty = round(amount_usd / price, 6) if action == "BUY" else holdings[symbol]
    pnl = 0.0

    if action == "BUY" and balance >= amount_usd:
        balance -= amount_usd
        holdings[symbol] += qty
        send_discord(f"🔵 BUY {symbol}: {qty} at ${price}, new balance ${balance:.2f}")
        trade_log.append({"symbol": symbol, "action": "BUY", "price": price, "qty": qty, "timestamp": time.time()})
    elif action == "SELL" and holdings[symbol] > 0:
        proceeds = qty * price
        last_buy = next((t for t in reversed(trade_log) if t["symbol"] == symbol and t["action"] == "BUY"), None)
        pnl = ((price - last_buy["price"]) / last_buy["price"] * 100) if last_buy else 0.0
        balance += proceeds
        holdings[symbol] = 0.0
        send_discord(f"🔴 SELL {symbol}: {qty} at ${price}, PnL: {pnl:.2f}%, balance: ${balance:.2f}")
        trade_log.append({"symbol": symbol, "action": "SELL", "price": price, "qty": qty, "timestamp": time.time(), "pnl": pnl})

def hourly_report():
    total_trades = len(trade_log)
    realized_pnl = sum(t.get("pnl", 0) for t in trade_log if t["action"] == "SELL")
    msg = f"📊 Hourly Report: Trades: {total_trades}, Realized PnL: {realized_pnl:.2f}%, Balance: ${balance:.2f}"
    send_discord(msg)

def ai_learning():
    # Dummy: teller strategi-wins. Kan bygges ut!
    stats = {"RSI":0, "EMA":0, "RANDOM":0}
    for t in trade_log:
        if t["action"] == "SELL" and t.get("pnl", 0) > 0:
            strategy = t.get("strategy", "RANDOM")
            stats[strategy] += 1
    best = max(stats, key=stats.get)
    send_discord(f"🤖 AI-Feedback: Best strategy so far: {best} ({stats[best]} wins)")

# --- MAIN LOOP ---
last_report = time.time()
while True:
    for symbol in TOKENS:
        price = get_price(symbol)
        strategy = choose_strategy()
        action = get_signal(strategy, price, holdings[symbol])
        if action in ("BUY", "SELL"):
            handle_trade(symbol, action, price)
    # Hourly (eller bruk kortere intervall for test)
    if time.time() - last_report > 3600:  # Endre til 60 for test!
        hourly_report()
        ai_learning()
        last_report = time.time()
    time.sleep(30)  # Kjør hvert 30 sek, juster som du vil
