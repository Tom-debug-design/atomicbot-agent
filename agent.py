import random, time, os, requests, datetime

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
MAX_HOLD_MINUTES = 20  # Tvangsselg etter 20 minutter uansett

balance = START_BALANCE
holdings = {symbol: 0.0 for symbol in TOKENS}
last_trade_time = {symbol: None for symbol in TOKENS}
trade_log = []
auto_buy_pct = 0.1

def send_discord(msg):
    print("DISCORD:", msg)
    try:
        if DISCORD_WEBHOOK:
            requests.post(DISCORD_WEBHOOK, json={"content": msg})
    except Exception as e:
        print(f"Discord error: {e}")

def get_price(symbol):
    # 1. Prøv CoinGecko
    coingecko_id = COINGECKO_MAP.get(symbol, "bitcoin")
    url = f"https://api.coingecko.com/api/v3/simple/price?ids={coingecko_id}&vs_currencies=usd"
    try:
        data = requests.get(url, timeout=5).json()
        price = float(data[coingecko_id]["usd"])
        return price
    except Exception:
        pass
    # 2. Prøv Binance direkte (fallback)
    binance_url = f"https://api.binance.com/api/v3/ticker/price?symbol={symbol}"
    try:
        data = requests.get(binance_url, timeout=5).json()
        price = float(data['price'])
        return price
    except Exception:
        send_discord(f"⚠️ Price fetch error for {symbol}: No data from any API")
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

def handle_trade(symbol, action, price, strategy):
    global balance, holdings, trade_log, auto_buy_pct, last_trade_time
    if price is None: return
    now = time.time()
    amount_usd = balance * auto_buy_pct if action == "BUY" else holdings[symbol] * price
    qty = round(amount_usd / price, 6) if action == "BUY" else holdings[symbol]
    pnl = 0.0

    if action == "BUY" and balance >= amount_usd and qty > 0:
        balance -= amount_usd
        holdings[symbol] += qty
        last_trade_time[symbol] = now
        send_discord(f"🔵 BUY {symbol}: {qty} at ${price:.2f}, new balance ${balance:.2f}")
        trade_log.append({
            "symbol": symbol, "action": "BUY", "price": price,
            "qty": qty, "timestamp": now, "strategy": strategy, "pnl": 0.0
        })
    elif action == "SELL" and holdings[symbol] > 0:
        proceeds = qty * price
        last_buy = next((t for t in reversed(trade_log) if t["symbol"] == symbol and t["action"] == "BUY"), None)
        pnl = ((price - last_buy["price"]) / last_buy["price"] * 100) if last_buy else 0.0
        balance += proceeds
        holdings[symbol] = 0.0
        last_trade_time[symbol] = now
        send_discord(f"🔴 SELL {symbol}: {qty} at ${price:.2f}, PnL: {pnl:.2f}%, balance: ${balance:.2f}")
        trade_log.append({
            "symbol": symbol, "action": "SELL", "price": price,
            "qty": qty, "timestamp": now, "strategy": strategy, "pnl": pnl
        })

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
    msg = f"📊 Hourly Report: Trades: {total_trades}, Realized PnL: {realized_pnl:.2f}%, Balance: ${balance:.2f}"
    send_discord(msg)

def ai_feedback():
    best = get_best_strategy(trade_log)
    send_discord(f"🤖 AI: Best strategy last 30: {best}")

def force_sell(symbol, price):
    global holdings, balance, trade_log, last_trade_time
    if holdings[symbol] > 0 and price:
        qty = holdings[symbol]
        proceeds = qty * price
        last_buy = next((t for t in reversed(trade_log) if t["symbol"] == symbol and t["action"] == "BUY"), None)
        pnl = ((price - last_buy["price"]) / last_buy["price"] * 100) if last_buy else 0.0
        balance += proceeds
        holdings[symbol] = 0.0
        last_trade_time[symbol] = time.time()
        send_discord(f"⏱️ FORCE SELL {symbol}: {qty} at ${price:.2f}, PnL: {pnl:.2f}%, balance: ${balance:.2f}")
        trade_log.append({
            "symbol": symbol, "action": "FORCE_SELL", "price": price,
            "qty": qty, "timestamp": time.time(), "strategy": "FORCE", "pnl": pnl
        })

send_discord("🟢 AtomicBot Unstoppable Edition starter…")

last_report = time.time()
hold_failures = 0

while True:
    hold_this_round = 0
    for symbol in TOKENS:
        price = get_price(symbol)
        strategy = get_best_strategy(trade_log) if len(trade_log) > 10 else choose_strategy()
        action = get_signal(strategy, price, holdings[symbol])
        now = time.time()

        # Sjekk for for lenge holdt posisjon (force-sell)
        if holdings[symbol] > 0 and last_trade_time[symbol]:
            age_min = (now - last_trade_time[symbol]) / 60
            if age_min > MAX_HOLD_MINUTES:
                force_sell(symbol, price)
                continue

        if price is None:
            hold_this_round += 1
            continue

        if action in ("BUY", "SELL"):
            handle_trade(symbol, action, price, strategy)
        else:
            hold_this_round += 1

    # Hvis ALLE tokens fikk HOLD eller None – tving én random BUY/SELL
    if hold_this_round >= len(TOKENS):
        rand_symbol = random.choice(TOKENS)
        price = get_price(rand_symbol)
        if price:
            rand_action = random.choice(["BUY", "SELL"])
            send_discord(f"⚡ FORCE TRADE: {rand_action} on {rand_symbol} (all tokens on HOLD)")
            handle_trade(rand_symbol, rand_action, price, "FORCE")

    if time.time() - last_report > 60:
        hourly_report()
        ai_feedback()
        auto_tune(trade_log)
        last_report = time.time()

    time.sleep(30)
