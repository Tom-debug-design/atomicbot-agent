import random, time, os, requests

# --- SETTINGS ---
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
LIVE_DEMO = True   # <--- BYTT TIL FALSE FOR DUMMY, TRUE FOR LIVE DEMO

# --- STATE ---
balance = START_BALANCE
holdings = {symbol: 0.0 for symbol in TOKENS}
trade_log = []
auto_buy_pct = 0.1

def send_discord(msg):
    print("DISCORD:", msg)
    try:
        requests.post(DISCORD_WEBHOOK, json={"content": msg})
    except Exception as e:
        print(f"Discord error: {e}")

def get_live_price(symbol):
    # Bytt til din ekte live-feed hvis du har!
    coingecko_id = COINGECKO_MAP.get(symbol, "bitcoin")
    url = f"https://api.coingecko.com/api/v3/simple/price?ids={coingecko_id}&vs_currencies=usd"
    try:
        data = requests.get(url, timeout=5).json()
        return float(data[coingecko_id]["usd"])
    except Exception as e:
        print(f"Live price error: {e}")
        return None

def get_dummy_price(symbol):
    # Dummy-funksjon, simulerer pris (kan evt. bruke gamle get_price her)
    return random.uniform(10, 100)

def choose_strategy():
    return random.choice(["RSI", "EMA", "RANDOM", "SCALP", "MEAN", "TREND"])

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

def handle_trade(symbol, action, price, strategy):
    global balance, holdings, trade_log, auto_buy_pct
    if price is None: return
    amount_usd = balance * auto_buy_pct if action == "BUY" else holdings[symbol] * price
    qty = round(amount_usd / price, 6) if action == "BUY" else holdings[symbol]
    pnl = 0.0

    if action == "BUY" and balance >= amount_usd and qty > 0:
        balance -= amount_usd
        holdings[symbol] += qty
        send_discord(f"🔵 BUY {symbol}: {qty} at ${price:.2f}, new balance ${balance:.2f} [{('LIVE DEMO' if LIVE_DEMO else 'DUMMY')}]")
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
        send_discord(f"🔴 SELL {symbol}: {qty} at ${price:.2f}, PnL: {pnl:.2f}%, balance: ${balance:.2f} [{('LIVE DEMO' if LIVE_DEMO else 'DUMMY')}]")
        trade_log.append({
            "symbol": symbol, "action": "SELL", "price": price,
            "qty": qty, "timestamp": time.time(), "strategy": strategy, "pnl": pnl
        })

def get_best_strategy(trade_log):
    recent = [t for t in trade_log[-20:] if t["action"] == "SELL"]
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
    recent = [t for t in trade_log[-5:] if t["action"] == "SELL"]
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
    msg = f"📊 [CHUNKY-EDGE] Hourly report: Trades: {total_trades}, Bal: ${balance:.2f}, Realized PnL: {realized_pnl:.2f} [{('LIVE DEMO' if LIVE_DEMO else 'DUMMY')}]"
    send_discord(msg)

def daily_report():
    total_trades = len(trade_log)
    realized_pnl = sum(t.get("pnl", 0) for t in trade_log if t["action"] == "SELL")
    msg = f"📅 [CHUNKY-EDGE] DAILY report: Trades: {total_trades}, Bal: ${balance:.2f}, Realized PnL: {realized_pnl:.2f} [{('LIVE DEMO' if LIVE_DEMO else 'DUMMY')}]"
    send_discord(msg)

def ai_feedback():
    best = get_best_strategy(trade_log)
    send_discord(f"🤖 AI: Best strategy last 20: {best}")

send_discord(f"🟢 AtomicBot starter… ({'LIVE DEMO' if LIVE_DEMO else 'DUMMY'} mode!)")

last_report = time.time()
last_hour = time.gmtime().tm_hour
daily_sent = False

while True:
    for symbol in TOKENS:
        price = get_live_price(symbol) if LIVE_DEMO else get_dummy_price(symbol)
        strategy = get_best_strategy(trade_log) if len(trade_log) > 10 else choose_strategy()
        action = get_signal(strategy, price, holdings[symbol])
        print(f"{symbol} | Pris: {price} | Strategy: {strategy} | Signal: {action}")
        if action in ("BUY", "SELL"):
            handle_trade(symbol, action, price, strategy)

    now = time.gmtime()
    # Timesrapport: Send eksakt én gang i timen
    if now.tm_min == 0 and now.tm_sec < 30 and last_hour != now.tm_hour:
        hourly_report()
        ai_feedback()
        auto_tune(trade_log)
        last_hour = now.tm_hour

    # Dagsrapport kl 07:00 UTC
    if now.tm_hour == 7 and now.tm_min == 0 and now.tm_sec < 30 and not daily_sent:
        daily_report()
        daily_sent = True
    elif now.tm_hour != 7:
        daily_sent = False

    time.sleep(5)  # Hyppig sjekk for å treffe "window" for times/dagsrapport