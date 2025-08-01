import os, time, random, requests
from binance.client import Client
from collections import deque

BINANCE_API_KEY = os.getenv("BINANCE_API_KEY")
BINANCE_API_SECRET = os.getenv("BINANCE_API_SECRET")
DISCORD_WEBHOOK = os.getenv("DISCORD_WEBHOOK")

client = Client(BINANCE_API_KEY, BINANCE_API_SECRET)

TOKENS = [
    "BTCUSDT", "ETHUSDT", "SOLUSDT", "BNBUSDT", "XRPUSDT", "ADAUSDT",
    "DOGEUSDT", "MATICUSDT", "AVAXUSDT", "LINKUSDT", "LTCUSDT", "TRXUSDT"
]

START_BALANCE = 1000.0
balance = START_BALANCE
holdings = {symbol: 0.0 for symbol in TOKENS}
trade_log = []
auto_buy_pct = 0.1

# Pattern Memory & Price history
pattern_memory = deque(maxlen=20)
price_history = {symbol: deque(maxlen=60) for symbol in TOKENS}

def send_discord(msg):
    print("DISCORD:", msg)
    try:
        requests.post(DISCORD_WEBHOOK, json={"content": msg})
    except Exception as e:
        print(f"Discord error: {e}")

def get_price(symbol):
    try:
        ticker = client.get_symbol_ticker(symbol=symbol)
        price = float(ticker['price'])
        price_history[symbol].append(price)
        return price
    except Exception as e:
        print(f"Binance error: {e}")
        return None

def record_pattern(trades):
    if len(trades) < 3: return
    seq = '-'.join([t['action'] for t in trades[-3:]])
    outcome = sum(t['pnl'] for t in trades[-3:])
    pattern_memory.append({'seq': seq, 'pnl': outcome})

def detect_pattern_risk():
    if len(trade_log) < 3: return False
    seq_now = '-'.join([t['action'] for t in trade_log[-3:]])
    risky = sum(p['pnl'] < 0 for p in pattern_memory if p['seq'] == seq_now)
    if risky >= 2:
        send_discord(f"🚨 Pattern warning: Sekvens {seq_now} har gitt tap flere ganger!")
    return risky >= 2

def get_regime(prices):
    if len(prices) < 50:
        return "UNKNOWN"
    ma10 = sum(prices[-10:]) / 10
    ma50 = sum(prices[-50:]) / 50
    atr = sum(abs(prices[i] - prices[i-1]) for i in range(-10, -1)) / 9
    if ma10 > ma50 and atr < (0.01 * ma10):
        return "BULL"
    elif ma10 < ma50 and atr < (0.01 * ma10):
        return "BEAR"
    elif atr > (0.02 * ma10):
        return "VOLATILE"
    else:
        return "RANGE"

def choose_strategy(symbol):
    regime = get_regime(list(price_history[symbol]))
    if regime == "BULL":
        send_discord(f"📈 {symbol} regime: BULL – bruker EMA")
        return "EMA"
    elif regime == "BEAR":
        send_discord(f"📉 {symbol} regime: BEAR – bruker RSI")
        return "RSI"
    elif regime == "VOLATILE":
        send_discord(f"⚡ {symbol} regime: VOLATILE – bruker RANDOM")
        return "RANDOM"
    else:
        return random.choice(["RSI", "EMA", "RANDOM"])

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
            "qty": qty, "timestamp": time.time(), "strategy": strategy, "pnl": 0.0
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
            "qty": qty, "timestamp": time.time(), "strategy": strategy, "pnl": pnl
        })

def get_best_strategy(trade_log):
    recent = [t for t in trade_log[-30:] if t["action"] == "SELL"]
    strat_stats = {}
    for t in recent:
        s = t.get("strategy", "RANDOM")
        strat_stats.setdefault(s, []).append(t.get("pnl", 0))
    if not strat_stats:
        return choose_strategy(random.choice(TOKENS))
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

def balance_emoji(bal):
    if bal > START_BALANCE * 1.1: return "💚"
    if bal > START_BALANCE * 1.02: return "🟢"
    if bal > START_BALANCE * 0.98: return "🟡"
    if bal > START_BALANCE * 0.8: return "🔴"
    return "💀"

send_discord("🟢 AtomicBot starter... (Pattern Memory + Regime Detection ENABLED)")

last_report = time.time()
last_magic = time.time()

while True:
    for symbol in TOKENS:
        price = get_price(symbol)
        if not price: continue
        strategy = choose_strategy(symbol)
        action = get_signal(strategy, price, holdings[symbol])
        print(f"{symbol} | Pris: {price} | Strategy: {strategy} | Signal: {action}")
        if action in ("BUY", "SELL"):
            handle_trade(symbol, action, price, strategy)
            record_pattern(trade_log)
            if detect_pattern_risk():
                send_discord(f"⚠️ ChunkyAI: Oppdaget risikomønster etter trade – vurder HOLD/bytte strategi!")
    if time.time() - last_magic > 600:
        last_hour = [t for t in trade_log if t["action"] == "SELL" and t["timestamp"] > time.time() - 3600]
        if last_hour:
            best = max(last_hour, key=lambda t: t["pnl"])
            worst = min(last_hour, key=lambda t: t["pnl"])
            send_discord(f"🤖 Beste strategi siste time: {best['strategy']} {best['symbol']} ({best['pnl']:.2f}%)")
            send_discord(f"💀 Største tap siste time: {worst['strategy']} {worst['symbol']} ({worst['pnl']:.2f}%)")
        send_discord(f"{balance_emoji(balance)} Balanse nå: ${balance:.2f}")
        last_magic = time.time()
    if time.time() - last_report > 60:
        hourly_report()
        ai_feedback()
        auto_tune(trade_log)
        last_report = time.time()
    time.sleep(30)
