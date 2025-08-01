import requests, os, time, random, statistics

# === CONFIG (endres enkelt på toppen) ===
TOKENS = [
    "BTCUSDT", "ETHUSDT", "SOLUSDT", "BNBUSDT", "XRPUSDT", "ADAUSDT",
    "DOGEUSDT", "MATICUSDT", "AVAXUSDT", "LINKUSDT", "LTCUSDT", "TRXUSDT"
]
DISCORD_WEBHOOK = os.getenv("DISCORD_WEBHOOK")
START_BALANCE = 1000.0
USE_SCALPING = True           # True=kjapp scalp, False=vanlig AI
RISKCONTROL = False           # True=auto-pause ved stort tap
REPORT_FREQ = 3600            # Sekunder mellom Discord rapport (3600 = 1 time)
DAILY_REPORT_UTC = 6          # UTC-tid for dagsrapport
DEMO_MODE = True              # False = aktiver ekte handler (bygger inn støtte, krever Binance API)

# === STATE ===
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

def get_price(symbol):
    url = f"https://api.binance.com/api/v3/ticker/24hr?symbol={symbol}"
    try:
        data = requests.get(url, timeout=5).json()
        price = float(data["lastPrice"])
        vol = float(data["volume"])
        # Sikkerhetsvask for null/negative
        if price <= 0: return None, None
        price_history[symbol].append(price)
        vol_history[symbol].append(vol)
        if len(price_history[symbol]) > 100: price_history[symbol] = price_history[symbol][-100:]
        if len(vol_history[symbol]) > 100: vol_history[symbol] = vol_history[symbol][-100:]
        return price, vol
    except Exception as e:
        print(f"Price fetch error for {symbol}: {e}")
        return None, None

def rolling_volatility(symbol, window=10):
    phist = price_history[symbol]
    if len(phist) < window: return 0
    returns = [abs(phist[i]-phist[i-1])/phist[i-1] for i in range(-window+1, 0) if phist[i-1] != 0]
    return sum(returns)/len(returns) * 100 if returns else 0

def rolling_trend(symbol, window=20):
    phist = price_history[symbol]
    if len(phist) < window: return 0
    return (phist[-1] - phist[-window])/phist[-window] * 100 if phist[-window] != 0 else 0

def choose_strategy(symbol):
    trend = rolling_trend(symbol)
    vol = rolling_volatility(symbol)
    last_vol = vol_history[symbol][-1] if vol_history[symbol] else 0
    if USE_SCALPING and vol > 3:
        return "SCALP"
    if trend > 0.5 and vol < 2:
        return "EMA"
    elif trend < -0.5 and vol < 2:
        return "RSI"
    elif vol > 3:
        return "SCALP"
    elif last_vol > 5000:
        return "RANDOM"
    else:
        return random.choice(["RSI", "EMA", "RANDOM"])

def get_signal(symbol, strategy, price, holdings):
    if price is None or price == 0: return "HOLD"
    if strategy == "SCALP":
        last = next((t for t in reversed(trade_log) if t["symbol"] == symbol and t["action"] == "BUY"), None)
        if holdings == 0 and price > 0:
            return "BUY"
        elif holdings > 0 and last:
            entry = last["price"]
            gain = (price - entry) / entry if entry else 0
            if gain >= 0.01 or gain <= -0.008:
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
    if price is None or price == 0: return
    amount_usd = balance * auto_buy_pct if action == "BUY" else holdings[symbol] * price
    qty = round(amount_usd / price, 6) if action == "BUY" else holdings[symbol]
    pnl = 0.0

    if DEMO_MODE:
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

def daily_report():
    total_trades = len(trade_log)
    realized_pnl = sum(t.get("pnl", 0) for t in trade_log if t["action"] == "SELL")
    msg = f"🗓️ Dagsrapport: Trades: {total_trades}, Realized PnL: {realized_pnl:.2f}%, End balance: ${balance:.2f}"
    send_discord(msg)

send_discord("🟢 AtomicBot SUPERCHUNKY starter…")

last_report = time.time()
last_daily = time.time()
start_day = time.gmtime().tm_mday

while True:
    for symbol in TOKENS:
        price, vol = get_price(symbol)
        if price is None: continue
        strategy = choose_strategy(symbol)
        action = get_signal(symbol, strategy, price, holdings[symbol])
        print(f"{symbol} | Pris: {price} | Vol: {vol} | Strategy: {strategy} | Signal: {action}")
        if action in ("BUY", "SELL"):
            handle_trade(symbol, action, price, strategy)
    # Riskcontrol
    if RISKCONTROL and balance < START_BALANCE * 0.7:
        send_discord("🛑 PAUSE: Balanse under 70%, trading stoppet!")
        break
    # Rapport per REPORT_FREQ sekunder
    if time.time() - last_report > REPORT_FREQ:
        hourly_report()
        ai_feedback()
        auto_tune(trade_log)
        last_report = time.time()
    # Dagsrapport kl 06:00 UTC
    utc_now = time.gmtime()
    if utc_now.tm_hour == DAILY_REPORT_UTC and utc_now.tm_mday != start_day:
        daily_report()
        start_day = utc_now.tm_mday
    time.sleep(30)
