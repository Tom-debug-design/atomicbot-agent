import requests, os, time, random, statistics

TOKENS = [
    "BTCUSDT", "ETHUSDT", "SOLUSDT", "BNBUSDT", "XRPUSDT", "ADAUSDT",
    "DOGEUSDT", "MATICUSDT", "AVAXUSDT", "LINKUSDT", "LTCUSDT", "TRXUSDT"
]
DISCORD_WEBHOOK = os.getenv("DISCORD_WEBHOOK")
START_BALANCE = 1000.0

balance = START_BALANCE
holdings = {symbol: 0.0 for symbol in TOKENS}
trade_log = []
auto_buy_pct = 0.1

price_history = {symbol: [] for symbol in TOKENS}
vol_history = {symbol: [] for symbol in TOKENS}

def send_discord(msg):
    print("DISCORD:", msg)
    try:
        requests.post(DISCORD_WEBHOOK, json={"content": msg})
    except Exception as e:
        print(f"Discord error: {e}")

# CHUNKY Binance LIVE price
def get_price(symbol):
    url = f"https://api.binance.com/api/v3/ticker/24hr?symbol={symbol}"
    try:
        data = requests.get(url, timeout=5).json()
        price = float(data["lastPrice"])
        vol = float(data["volume"])
        price_history[symbol].append(price)
        vol_history[symbol].append(vol)
        # Holder kun siste 100 priser/volumer for hastighet
        if len(price_history[symbol]) > 100: price_history[symbol] = price_history[symbol][-100:]
        if len(vol_history[symbol]) > 100: vol_history[symbol] = vol_history[symbol][-100:]
        return price, vol
    except Exception as e:
        print(f"Price fetch error for {symbol}: {e}")
        return None, None

def rolling_volatility(symbol, window=10):
    phist = price_history[symbol]
    if len(phist) < window: return 0
    returns = [abs(phist[i]-phist[i-1])/phist[i-1] for i in range(-window+1, 0)]
    return sum(returns)/len(returns) * 100

def rolling_trend(symbol, window=20):
    phist = price_history[symbol]
    if len(phist) < window: return 0
    return (phist[-1] - phist[-window])/phist[-window] * 100

def choose_strategy(symbol):
    # Bruk både trend, volatilitet, volum for smartere valg!
    trend = rolling_trend(symbol)
    vol = rolling_volatility(symbol)
    last_vol = vol_history[symbol][-1] if vol_history[symbol] else 0
    if trend > 0.5 and vol < 2:  # Opptrend, lite kaos
        return "EMA"
    elif trend < -0.5 and vol < 2:
        return "RSI"
    elif vol > 3:  # Veldig volatile, da skalpes det!
        return "SCALP"
    elif last_vol > 5000:  # Høyt volum gir mulighet for raske trades
        return "RANDOM"
    else:
        return random.choice(["RSI", "EMA", "RANDOM"])

def get_signal(symbol, strategy, price, holdings):
    if price is None: return "HOLD"
    if strategy == "SCALP":
        last = next((t for t in reversed(trade_log) if t["symbol"] == symbol and t["action"] == "BUY"), None)
        if holdings == 0 and price > 0:
            return "BUY"
        elif holdings > 0:
            entry = last["price"] if last else 0
            gain = (price - entry) / entry if entry else 0
            if gain >= 0.01 or gain <= -0.008:  # Ta små gevinster/tap
                return "SELL"
            else:
                return "HOLD"
    elif strategy == "RSI":
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

def handle_trade(symbol, action, price, strategy):
    global balance, holdings, trade_log, auto_buy_pct
    if price is None: return
    amount_usd = balance * auto_buy_pct if action == "BUY" else holdings[symbol] * price
    qty = round(amount_usd / price, 6) if action == "BUY" else holdings[symbol]
    pnl = 0.0

    if action == "BUY" and balance >= amount_usd and qty > 0:
        balance -= amount_usd
        holdings[symbol] += qty
        send_discord(f"🔵 BUY {symbol}: {qty} at ${price:.2f}, new balance ${balance:.2f}")
        trade_log.append({
            "symbol": symbol, "action": "BUY", "price": price,
            "qty": qty, "timestamp": time.time(), "strategy": strategy,
            "volatility": rolling_volatility(symbol), "trend": rolling_trend(symbol), "pnl": 0.0
        })
    elif action == "SELL" and holdings[symbol] > 0:
        proceeds = qty * price
        last_buy = next((t for t in reversed(trade_log) if t["symbol"] == symbol and t["action"] == "BUY"), None)
        pnl = ((price - last_buy["price"]) / last_buy["price"] * 100) if last_buy else 0.0
        balance += proceeds
        holdings[symbol] = 0.0
        send_discord(f"🔴 SELL {symbol}: {qty} at ${price:.2f}, PnL: {pnl:.2f}%, balance: ${balance:.2f}")
        trade_log.append({
            "symbol": symbol, "action": "SELL", "price": price,
            "qty": qty, "timestamp": time.time(), "strategy": strategy,
            "volatility": rolling_volatility(symbol), "trend": rolling_trend(symbol), "pnl": pnl
        })

def best_strategy_backtest(trade_log):
    # Mini-backtest: Hvilken strategi ga best snitt-PnL siste 50 trades?
    recent = [t for t in trade_log[-50:] if t["action"] == "SELL"]
    strat_stats = {}
    for t in recent:
        s = t.get("strategy", "RANDOM")
        strat_stats.setdefault(s, []).append(t.get("pnl", 0))
    if not strat_stats:
        return "RANDOM"
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
    best = best_strategy_backtest(trade_log)
    send_discord(f"🤖 AI: Best strategy last 50: {best}")

send_discord("🟢 AtomicBot AI BOOST starter…")

last_report = time.time()

while True:
    for symbol in TOKENS:
        price, vol = get_price(symbol)
        strategy = choose_strategy(symbol)
        action = get_signal(symbol, strategy, price, holdings[symbol])
        print(f"{symbol} | Pris: {price} | Vol: {vol} | Strategy: {strategy} | Signal: {action}")
        if action in ("BUY", "SELL"):
            handle_trade(symbol, action, price, strategy)
    if time.time() - last_report > 60:
        hourly_report()
        ai_feedback()
        auto_tune(trade_log)
        last_report = time.time()
    time.sleep(30)
