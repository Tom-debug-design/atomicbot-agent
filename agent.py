
import random, time, os, requests, json

# --- SETTINGS ---
TOKENS = [
    "BTCUSDT", "ETHUSDT", "SOLUSDT", "BNBUSDT", "XRPUSDT", "ADAUSDT",
    "DOGEUSDT", "MATICUSDT", "AVAXUSDT", "LINKUSDT",
    "LTCUSDT", "TRXUSDT", "BCHUSDT", "FILUSDT", "OPUSDT", "STXUSDT"
]
COINGECKO_MAP = {
    "BTCUSDT": "bitcoin", "ETHUSDT": "ethereum", "SOLUSDT": "solana",
    "BNBUSDT": "binancecoin", "XRPUSDT": "ripple", "ADAUSDT": "cardano",
    "DOGEUSDT": "dogecoin", "MATICUSDT": "matic-network",
    "AVAXUSDT": "avalanche-2", "LINKUSDT": "chainlink",
    "LTCUSDT": "litecoin", "TRXUSDT": "tron", "BCHUSDT": "bitcoin-cash",
    "FILUSDT": "filecoin", "OPUSDT": "optimism", "STXUSDT": "stacks"
}
DISCORD_WEBHOOK = os.getenv("DISCORD_WEBHOOK")
START_BALANCE = 1000.0

# --- STATE ---
balance = START_BALANCE
holdings = {symbol: 0.0 for symbol in TOKENS}
trade_log = []
ai_learning_log = []
auto_buy_pct = 0.10   # Start på 10%, auto-tunes

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
    return random.choice(["RSI", "EMA", "RANDOM"])

def get_signal(strategy, price, holdings):
    if price is None: return "HOLD"
    # Gjør signalene enklere for test/demo (mer aggressive triggers)
    if strategy == "RSI":
        if price % 17 < 5 and holdings == 0:  # Mer aggressive triggere
            return "BUY"
        elif price % 13 > 10 and holdings > 0:
            return "SELL"
        else:
            return "HOLD"
    elif strategy == "EMA":
        if int(price*100) % 3 == 0 and holdings == 0:
            return "BUY"
        elif int(price*100) % 7 == 0 and holdings > 0:
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
        msg = f"🔵 BUY {symbol}: {qty} @ ${price:.2f}, bal: ${balance:.2f}"
        send_discord(msg)
        trade_log.append({"symbol": symbol, "action": "BUY", "price": price,
                          "qty": qty, "timestamp": time.time(), "strategy": strategy, "pnl": 0.0})
        ai_learning_log.append({"symbol": symbol, "strategy": strategy, "signal": "BUY", "price": price, "ts": time.time()})
    elif action == "SELL" and holdings[symbol] > 0:
        proceeds = qty * price
        last_buy = next((t for t in reversed(trade_log) if t["symbol"] == symbol and t["action"] == "BUY"), None)
        pnl = ((price - last_buy["price"]) / last_buy["price"] * 100) if last_buy else 0.0
        balance += proceeds
        holdings[symbol] = 0.0
        msg = f"🔴 SELL {symbol}: {qty} @ ${price:.2f}, PnL: {pnl:.2f}%, bal: ${balance:.2f}"
        send_discord(msg)
        trade_log.append({"symbol": symbol, "action": "SELL", "price": price,
                          "qty": qty, "timestamp": time.time(), "strategy": strategy, "pnl": pnl})
        ai_learning_log.append({"symbol": symbol, "strategy": strategy, "signal": "SELL", "price": price, "ts": time.time(), "pnl": pnl})

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

def save_ai_log():
    # Du kan hente ut dette via GitHub bridge senere
    try:
        with open("ai_learning_log.json", "w") as f:
            json.dump(ai_learning_log, f, indent=2)
    except Exception as e:
        print(f"Save AI log error: {e}")

# --- MAIN LOOP ---
send_discord("🟢 AtomicBot Aggressive v3 starter…")
last_report = time.time()

while True:
    for symbol in TOKENS:
        price = get_price(symbol)
        # Nå: bruker beste strategi basert på siste 30 handler
        strategy = get_best_strategy(trade_log) if len(trade_log) > 30 else choose_strategy()
        action = get_signal(strategy, price, holdings[symbol])
        print(f"{symbol} | Pris: {price} | Strat: {strategy} | Signal: {action}")
        if action in ("BUY", "SELL"):
            handle_trade(symbol, action, price, strategy)
        time.sleep(0.2)  # Slik at API ikke blir spammet
    if time.time() - last_report > 60:
        hourly_report()
        ai_feedback()
        auto_tune(trade_log)
        save_ai_log()
        last_report = time.time()
