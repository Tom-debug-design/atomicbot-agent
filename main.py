import random, time, os, requests, traceback, datetime

# === SETTINGS ===
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
DEMO = True     # Sett til False for live-handler (demo: bruker fake handler)
DAILY_REPORT_UTC = 6  # Klokkeslett for daglig rapport (UTC)
FIBONACCI_SERIES = [1, 1, 2, 3]
MAX_FIBO_IDX = len(FIBONACCI_SERIES) - 1

# === STATE ===
balance = START_BALANCE
holdings = {symbol: 0.0 for symbol in TOKENS}
trade_log = []
fibo_idx = 0
auto_buy_pct = 0.1
strategy_tap = 0
current_strategy = "RANDOM"
last_trade_won = True

# === DISCORD ===
def send_discord(msg):
    print("DISCORD:", msg)
    try:
        if DISCORD_WEBHOOK:
            requests.post(DISCORD_WEBHOOK, json={"content": msg}, timeout=4)
    except Exception as e:
        print(f"Discord error: {e}")

# === PRICE FETCH ===
def get_price(symbol):
    if not DEMO:
        # Live trading henter fra Binance API her
        pass
    coingecko_id = COINGECKO_MAP.get(symbol, "bitcoin")
    url = f"https://api.coingecko.com/api/v3/simple/price?ids={coingecko_id}&vs_currencies=usd"
    try:
        data = requests.get(url, timeout=5).json()
        return float(data[coingecko_id]["usd"])
    except Exception as e:
        print(f"Price fetch error: {e}")
        return None

# === STRATEGY LOGIC ===
def choose_strategy():
    return random.choice(["RSI", "EMA", "RANDOM", "SCALP", "MEAN", "TREND"])

def get_signal(strategy, price, holdings):
    if price is None: return "HOLD"
    if strategy == "RSI":
        if price < 25 and holdings == 0: return "BUY"
        elif price > 60 and holdings > 0: return "SELL"
        else: return "HOLD"
    elif strategy == "EMA":
        if int(price) % 2 == 0 and holdings == 0: return "BUY"
        elif int(price) % 5 == 0 and holdings > 0: return "SELL"
        else: return "HOLD"
    elif strategy == "SCALP":
        return random.choice(["BUY", "SELL", "HOLD"])
    elif strategy == "MEAN":
        if random.random() > 0.7: return "BUY"
        elif random.random() < 0.3: return "SELL"
        else: return "HOLD"
    elif strategy == "TREND":
        if random.random() > 0.6: return "BUY"
        elif random.random() < 0.4: return "SELL"
        else: return "HOLD"
    else:
        return random.choice(["BUY", "SELL", "HOLD"])

def get_best_strategy(trade_log):
    recent = [t for t in trade_log[-30:] if t["action"] == "SELL"]
    strat_stats = {}
    for t in recent:
        s = t.get("strategy", "RANDOM")
        strat_stats.setdefault(s, []).append(t.get("pnl", 0))
    if not strat_stats: return choose_strategy()
    best = max(strat_stats, key=lambda x: sum(strat_stats[x])/len(strat_stats[x]) if strat_stats[x] else -999)
    return best

# === FIBONACCI LOGIC ===
def get_fibo_size():
    return FIBONACCI_SERIES[fibo_idx]

def next_fibo(won_last):
    global fibo_idx
    if won_last:
        fibo_idx = 0
    else:
        fibo_idx = min(fibo_idx + 1, MAX_FIBO_IDX)

# === TRADE LOGIC ===
def handle_trade(symbol, action, price, strategy):
    global balance, holdings, trade_log, auto_buy_pct, last_trade_won, fibo_idx
    if price is None: return

    fibo_mult = get_fibo_size()
    amount_usd = balance * auto_buy_pct * fibo_mult if action == "BUY" else holdings[symbol] * price
    qty = round(amount_usd / price, 6) if action == "BUY" else holdings[symbol]
    pnl = 0.0

    if action == "BUY" and balance >= amount_usd and qty > 0:
        balance -= amount_usd
        holdings[symbol] += qty
        send_discord(f"🔵 BUY {symbol} ({strategy}, x{fibo_mult}): {qty} at ${price:.2f}, balance: ${balance:.2f}")
        trade_log.append({
            "symbol": symbol, "action": "BUY", "price": price,
            "qty": qty, "timestamp": time.time(), "strategy": strategy, "pnl": 0.0,
            "fibo_mult": fibo_mult
        })
        last_trade_won = False # vet ikke før evt SELL
    elif action == "SELL" and holdings[symbol] > 0:
        proceeds = qty * price
        last_buy = next((t for t in reversed(trade_log) if t["symbol"] == symbol and t["action"] == "BUY"), None)
        pnl = ((price - last_buy["price"]) / last_buy["price"] * 100) if last_buy else 0.0
        balance += proceeds
        holdings[symbol] = 0.0
        send_discord(f"🔴 SELL {symbol} ({strategy}, x{fibo_mult}): {qty} at ${price:.2f}, PnL: {pnl:.2f}%, balance: ${balance:.2f}")
        trade_log.append({
            "symbol": symbol, "action": "SELL", "price": price,
            "qty": qty, "timestamp": time.time(), "strategy": strategy, "pnl": pnl,
            "fibo_mult": fibo_mult
        })
        last_trade_won = pnl > 0
        next_fibo(last_trade_won)

# === EDGE/BLOCK DOWN SPIRAL ===
def check_edge():
    global auto_buy_pct
    # Blokkerer hvis vi taper mye siste 30 trades, går ned til defensiv størrelse
    recent = [t for t in trade_log[-30:] if t["action"] == "SELL"]
    pnl_sum = sum(t.get("pnl", 0) for t in recent)
    if recent and pnl_sum < -10 and auto_buy_pct > 0.05:
        auto_buy_pct -= 0.01
        send_discord(f"🛑 EDGE: Reduserer buy% til {auto_buy_pct*100:.1f}% pga tap")
    elif recent and pnl_sum > 10 and auto_buy_pct < 0.2:
        auto_buy_pct += 0.01
        send_discord(f"🟢 EDGE: Øker buy% til {auto_buy_pct*100:.1f}% pga gevinst")

# === STRATEGY SWITCH ===
def strategy_switch():
    global current_strategy, strategy_tap
    # Bytt strategi etter 3 tap på rad