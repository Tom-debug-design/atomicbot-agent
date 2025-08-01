import requests, os, time, random, statistics, math
from datetime import datetime

# === CONFIG ===
TOKENS = [
    "BTCUSDT", "ETHUSDT", "SOLUSDT", "BNBUSDT", "XRPUSDT", "ADAUSDT",
    "DOGEUSDT", "MATICUSDT", "AVAXUSDT", "LINKUSDT"
]
DISCORD_WEBHOOK = os.getenv("DISCORD_WEBHOOK")
START_BALANCE = 1000.0
MAX_POSITIONS = 3
STOP_LOSS_PCT = 0.06      # 6% tap per trade
TAKE_PROFIT_PCT = 0.10    # 10% gevinst
POSITION_SIZE_PCT = 0.10  # 10% av balansen per trade
REPORT_FREQ = 3600        # 1 time mellom hver rapport
DAILY_REPORT_UTC = 6      # 06:00 UTC
DEMO_MODE = True

# === STATE ===
balance = START_BALANCE
holdings = {symbol: 0.0 for symbol in TOKENS}
entry_price = {symbol: 0.0 for symbol in TOKENS}
trade_log = []
price_history = {symbol: [] for symbol in TOKENS}
logfile = "atomicbot_trades.csv"

def send_discord(msg):
    print("DISCORD:", msg)
    try:
        requests.post(DISCORD_WEBHOOK, json={"content": msg})
    except Exception as e:
        print(f"Discord error: {e}")

def log_trade(row):
    try:
        with open(logfile, "a") as f:
            f.write(",".join(str(row[k]) for k in row) + "\n")
    except Exception as e:
        print(f"Logging error: {e}")

def get_price(symbol, lookback=50):
    url = f"https://api.binance.com/api/v3/klines?symbol={symbol}&interval=1m&limit={lookback}"
    try:
        data = requests.get(url, timeout=5).json()
        prices = [float(candle[4]) for candle in data]  # close price
        price_history[symbol] = prices[-100:]
        return prices[-1], prices
    except Exception as e:
        print(f"Price fetch error for {symbol}: {e}")
        return None, []

def calc_rsi(prices, period=14):
    if len(prices) < period + 1:
        return 50
    deltas = [prices[i] - prices[i - 1] for i in range(1, len(prices))]
    gains = [d for d in deltas if d > 0]
    losses = [-d for d in deltas if d < 0]
    avg_gain = sum(gains[-period:]) / period if len(gains) >= period else 1
    avg_loss = sum(losses[-period:]) / period if len(losses) >= period else 1
    rs = avg_gain / avg_loss if avg_loss != 0 else 100
    rsi = 100 - (100 / (1 + rs))
    return round(rsi, 2)

def calc_ema(prices, period=14):
    if len(prices) < period:
        return sum(prices)/len(prices)
    ema = prices[0]
    k = 2 / (period + 1)
    for price in prices:
        ema = price * k + ema * (1 - k)
    return ema

def calc_volatility(prices, window=14):
    if len(prices) < window: return 0
    returns = [math.log(prices[i]/prices[i-1]) for i in range(1, len(prices))]
    return statistics.stdev(returns[-window:]) * 100 if len(returns) >= window else 0

def choose_signal(symbol, prices):
    rsi = calc_rsi(prices)
    ema = calc_ema(prices, 14)
    price_now = prices[-1]
    vol = calc_volatility(prices)
    bullish = price_now > ema and rsi < 35 and vol < 2
    bearish = price_now < ema and rsi > 65 and vol < 2
    if bullish:
        return "BUY", {"rsi": rsi, "ema": ema, "vol": vol}
    elif bearish:
        return "SELL", {"rsi": rsi, "ema": ema, "vol": vol}
    else:
        return "HOLD", {"rsi": rsi, "ema": ema, "vol": vol}

def handle_trade(symbol, action, price, meta):
    global balance, holdings, entry_price, trade_log
    now = datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')
    qty = round((balance * POSITION_SIZE_PCT) / price, 6)
    pnl = 0.0
    if action == "BUY" and holdings[symbol] == 0 and len([h for h in holdings.values() if h > 0]) < MAX_POSITIONS:
        if DEMO_MODE:
            balance -= qty * price
            holdings[symbol] = qty
            entry_price[symbol] = price
            send_discord(f"🔵 BUY {symbol}: {qty} @ ${price:.2f}, RSI={meta['rsi']} EMA={int(meta['ema'])} Bal=${balance:.2f}")
            row = {
                "dt": now, "symbol": symbol, "action": "BUY", "price": price, "qty": qty,
                "rsi": meta["rsi"], "ema": meta["ema"], "vol": meta["vol"], "balance": balance, "pnl": ""
            }
            log_trade(row)
    elif action == "SELL" and holdings[symbol] > 0:
        if DEMO_MODE:
            pnl = ((price - entry_price[symbol]) / entry_price[symbol]) * 100
            proceeds = holdings[symbol] * price
            balance += proceeds
            send_discord(f"🔴 SELL {symbol}: {holdings[symbol]} @ ${price:.2f}, PnL: {pnl:.2f}%, RSI={meta['rsi']} EMA={int(meta['ema'])} Bal=${balance:.2f}")
            row = {
                "dt": now, "symbol": symbol, "action": "SELL", "price": price, "qty": holdings[symbol],
                "rsi": meta["rsi"], "ema": meta["ema"], "vol": meta["vol"], "balance": balance, "pnl": pnl
            }
            log_trade(row)
            trade_log.append({
                "symbol": symbol, "action": "SELL", "price": price,
                "qty": holdings[symbol], "timestamp": time.time(), "strategy": "SmartSignals", "pnl": pnl
            })
            holdings[symbol] = 0.0
            entry_price[symbol] = 0.0

def check_risk_exit(symbol, price):
    if holdings[symbol] == 0 or entry_price[symbol] == 0: return "HOLD"
    gain = (price - entry_price[symbol]) / entry_price[symbol]
    if gain <= -STOP_LOSS_PCT:
        return "SELL"
    if gain >= TAKE_PROFIT_PCT:
        return "SELL"
    return "HOLD"

def daily_report():
    realized = sum(t['pnl'] for t in trade_log if t["action"] == "SELL")
    wins = [t for t in trade_log if t['pnl'] > 0]
    losses = [t for t in trade_log if t['pnl'] < 0]
    winrate = (len(wins)/len(trade_log))*100 if trade_log else 0
    msg = (f"🗓️ Dagsrapport: Handler: {len(trade_log)}, Realisert PnL: {realized:.2f}%, "
           f"Winrate: {winrate:.1f}%, Bal: ${balance:.2f}")
    send_discord(msg)

send_discord("🟢 AtomicBot v11 – CHUNKY Robust starter…")
last_report = time.time()
last_daily = time.gmtime().tm_mday

while True:
    try:
        for symbol in TOKENS:
            price, prices = get_price(symbol)
            if not price or len(prices) < 20:
                continue
            action, meta = choose_signal(symbol, prices)
            risk_exit = check_risk_exit(symbol, price)
            if holdings[symbol] > 0 and risk_exit == "SELL":
                action = "SELL"
            handle_trade(symbol, action, price, meta)
        if time.time() - last_report > REPORT_FREQ:
            daily_report()
            last_report = time.time()
        if time.gmtime().tm_hour == DAILY_REPORT_UTC and time.gmtime().tm_mday != last_daily:
            daily_report()
            last_daily = time.gmtime().tm_mday
        time.sleep(30)
    except Exception as e:
        send_discord(f"⚠️ FailSafe: {type(e).__name__}: {e}")
        time.sleep(5)
