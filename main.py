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

# --- STRATEGIER ---
STRATEGIES = ["RSI", "EMA", "TREND", "FUB"]  # du kan legge til flere her!
CONSENSUS_THRESHOLD = 3   # Minimum antall stemmer (av 4) for å handle

# --- STATE ---
balance = START_BALANCE
holdings = {symbol: 0.0 for symbol in TOKENS}
trade_log = []
auto_buy_pct = 0.1   # 10% – auto-tunes!

# --- UTILITY ---
def send_discord(msg):
    print("DISCORD:", msg)
    try:
        requests.post(DISCORD_WEBHOOK, json={"content": msg})
    except Exception as e:
        print(f"Discord error: {e}")

def get_price(symbol):
    coingecko_id = COINGECKO_MAP.get(symbol, "bitcoin")
    url = f"https://api.coingecko.com/api/v3/simple/price?ids={coingecko_id}&vs_currencies=usd"
    try:
        data = requests.get(url, timeout=5).json()
        return float(data[coingecko_id]["usd"])
    except Exception as e:
        print(f"Price fetch error: {e}")
        return None

def rolling_high_low(symbol, window=30):
    prices = [t["price"] for t in trade_log[-window:] if t["symbol"] == symbol]
    if not prices: prices = [get_price(symbol) or 0]
    return max(prices), min(prices)

# --- STRATEGIER ---
def get_signal(strategy, price, holdings, symbol):
    if price is None: return "HOLD"
    # RSI (simulert)
    if strategy == "RSI":
        if price % 100 < 30 and holdings == 0:
            return "BUY"
        elif price % 100 > 70 and holdings > 0:
            return "SELL"
        else:
            return "HOLD"
    # EMA (simulert)
    elif strategy == "EMA":
        if int(price) % 2 == 0 and holdings == 0:
            return "BUY"
        elif int(price) % 5 == 0 and holdings > 0:
            return "SELL"
        else:
            return "HOLD"
    # TREND (simulert)
    elif strategy == "TREND":
        if price > (START_BALANCE * 0.98) and holdings == 0:
            return "BUY"
        elif price < (START_BALANCE * 0.96) and holdings > 0:
            return "SELL"
        else:
            return "HOLD"
    # FUBANACCI (chunky-style fib)
    elif strategy == "FUB":
        last_high, last_low = rolling_high_low(symbol)
        fib_618 = last_high - (last_high - last_low) * 0.618
        if price <= fib_618 * 1.01 and holdings == 0:
            return "BUY"
        elif price >= fib_618 * 1.04 and holdings > 0:
            return "SELL"
        else:
            return "HOLD"
    # RANDOM (fallback)
    else:
        return random.choice(["BUY", "SELL", "HOLD"])

def consensus_action(price, holdings, symbol):
    votes = {"BUY": 0, "SELL": 0}
    signals = {}
    for strat in STRATEGIES:
        signal = get_signal(strat, price, holdings, symbol)
        signals[strat] = signal
        if signal in votes:
            votes[signal] += 1
    if votes["BUY"] >= CONSENSUS_THRESHOLD:
        send_discord(f"🔵 BUY {symbol} [Consensus: {', '.join([k for k,v in signals.items() if v == 'BUY'])}]")
        return "BUY"
    elif votes["SELL"] >= CONSENSUS_THRESHOLD:
        send_discord(f"🔴 SELL {symbol} [Consensus: {', '.join([k for k,v in signals.items() if v == 'SELL'])}]")
        return "SELL"
    else:
        return "HOLD"

def handle_trade(symbol, action, price):
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
            "qty": qty, "timestamp": time.time(), "pnl": 0.0
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
            "qty": qty, "timestamp": time.time(), "pnl": pnl
        })

def hourly_report():
    total_trades = len(trade_log)
    realized_pnl = sum(t.get("pnl", 0) for t in trade_log if t["action"] == "SELL")
    msg = f"📊 [CHUNKY-CONSENSUS] Hourly report: Trades: {total_trades}, Bal: ${balance:.2f}, Realized PnL: {realized_pnl:.2f}"
    send_discord(msg)

# --- MAIN LOOP ---
send_discord("🟢 Chunky Consensus bot starter!")
last_report = time.time()

while True:
    for symbol in TOKENS:
        price = get_price(symbol)
        action = consensus_action(price, holdings[symbol], symbol)
        if action in ("BUY", "SELL"):
            handle_trade(symbol, action, price)
    # Rapport én gang i timen
    if time.time() - last_report > 3600:
        hourly_report()
        last_report = time.time()
    time.sleep(30)