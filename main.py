import random, time, os, requests

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

balance = START_BALANCE
peak_balance = START_BALANCE
holdings = {symbol: 0.0 for symbol in TOKENS}
trade_log = []
auto_buy_pct = 0.1
circuit_breaker_on = False
breaker_trigger = 0.7  # 70% av start-balansen (kan justeres!)

# Trailing stop storage per token
trailing_stops = {symbol: None for symbol in TOKENS}

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

def weighted_mean(pnls):
    n = len(pnls)
    if n == 0: return 0
    weights = [0.8**(n-i-1) for i in range(n)]  # Nyest veier mest
    return sum(p*w for p, w in zip(pnls, weights)) / sum(weights)

def choose_strategy():
    return random.choice(["RSI", "EMA", "RANDOM", "SCALP", "MEAN", "TREND"])

def get_rsi_signal(price, holdings):
    # Dummy RSI for nå, kan utvides med ekte RSI
    if price is None: return "HOLD"
    if price < 25 and holdings == 0: return "BUY"
    elif price > 60 and holdings > 0: return "SELL"
    return "HOLD"

def get_ema_signal(price, holdings):
    if price is None: return "HOLD"
    if int(price) % 2 == 0 and holdings == 0: return "BUY"
    elif int(price) % 5 == 0 and holdings > 0: return "SELL"
    return "HOLD"

def get_mean_signal(price, holdings):
    # Enkel mean-reversion: kjøp lavt, selg høyt
    if price is None: return "HOLD"
    if price < 40 and holdings == 0: return "BUY"
    elif price > 60 and holdings > 0: return "SELL"
    return "HOLD"

def get_random_signal(price, holdings):
    return random.choice(["BUY", "SELL", "HOLD"])

def get_scalp_signal(price, holdings):
    if price is None: return "HOLD"
    if int(price * 100) % 3 == 0 and holdings == 0: return "BUY"
    elif int(price * 100) % 7 == 0 and holdings > 0: return "SELL"
    return "HOLD"

def get_trend_signal(price, holdings):
    # Dummy trend: følg prisbevegelse
    if price is None: return "HOLD"
    if price % 4 == 0 and holdings == 0: return "BUY"
    elif price % 6 == 0 and holdings > 0: return "SELL"
    return "HOLD"

SIGNAL_MAP = {
    "RSI": get_rsi_signal,
    "EMA": get_ema_signal,
    "MEAN": get_mean_signal,
    "RANDOM": get_random_signal,
    "SCALP": get_scalp_signal,
    "TREND": get_trend_signal
}

def consensus_signal(price, holdings):
    # Multi-indikator consensus: 3/5 må være enige om BUY eller SELL
    votes = {"BUY": 0, "SELL": 0, "HOLD": 0}
    for strat in ["RSI", "EMA", "MEAN", "SCALP", "TREND"]:
        sig = SIGNAL_MAP[strat](price, holdings)
        votes[sig] += 1
    if votes["BUY"] >= 3: return "BUY"
    if votes["SELL"] >= 3: return "SELL"
    return "HOLD"

def handle_trade(symbol, action, price, strategy):
    global balance, holdings, trade_log, auto_buy_pct, trailing_stops, peak_balance
    if price is None: return
    amount_usd = balance * auto_buy_pct if action == "BUY" else holdings[symbol] * price
    qty = round(amount_usd / price, 6) if action == "BUY" else holdings[symbol]
    pnl = 0.0

    if action == "BUY" and balance >= amount_usd and qty > 0:
        balance -= amount_usd
        holdings[symbol] += qty
        # Trailing stop starter på 2% under kjøp
        trailing_stops[symbol] = {"stop": price * 0.98, "trail": 0.02, "peak": price}
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
        trailing_stops[symbol] = None
        send_discord(f"🔴 SELL {symbol}: {qty} at ${price:.2f}, PnL: {pnl:.2f}%, balance: ${balance:.2f}")
        trade_log.append({
            "symbol": symbol, "action": "SELL", "price": price,
            "qty": qty, "timestamp": time.time(), "strategy": strategy, "pnl": pnl
        })
    # Oppdater peak_balance (for circuit breaker)
    if balance > peak_balance:
        peak_balance = balance

def get_best_strategy(trade_log):
    # Edge: Bruk weighted mean siste 20 handler per strategi
    recent = [t for t in trade_log[-20:] if t["action"] == "SELL"]
    strat_stats = {}
    for t in recent:
        s = t.get("strategy", "RANDOM")
        strat_stats.setdefault(s, []).append(t.get("pnl", 0))
    if not strat_stats:
        return choose_strategy()
    best = max(strat_stats, key=lambda x: weighted_mean(strat_stats[x]) if strat_stats[x] else -999)
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
    strat_pnl = {}
    strat_wr = {}
    for strat in SIGNAL_MAP.keys():
        strat_trades = [t for t in trade_log if t["action"] == "SELL" and t["strategy"] == strat]
        pnl = sum(t.get("pnl", 0) for t in strat_trades)
        winrate = (sum(1 for t in strat_trades if t["pnl"] > 0) / len(strat_trades) * 100) if strat_trades else 0
        strat_pnl[strat] = pnl
        strat_wr[strat] = winrate
    best = max(strat_pnl, key=lambda x: strat_pnl[x])
    msg = f"📊 [CHUNKY-EDGE] Hourly report: Trades: {total_trades}, Bal: ${balance:.2f}, Realized PnL: {realized_pnl:.2f}\n"
    for strat in strat_pnl:
        msg += f"- {strat}: PnL {strat_pnl[strat]:.2f}, WR {strat_wr[strat]:.1f}%\n"
    msg += f"🔥 Best: {best}"
    send_discord(msg)

def daily_report():
    realized_pnl = sum(t.get("pnl", 0) for t in trade_log if t["action"] == "SELL")
    msg = f"📆 [CHUNKY-EDGE] Daily report: Realized PnL: {realized_pnl:.2f}, Balance: ${balance:.2f}"
    send_discord(msg)

send_discord("🟢 AtomicBot agent starter…")
last_report = time.time()
last_daily = time.time()
daily_interval = 60 * 60 * 24
last_beat = time.time()
daily_sent = False

while True:
    if circuit_breaker_on:
        send_discord("⚠️ CIRCUIT BREAKER ACTIVATED! Bot paused for review.")
        break

    for symbol in TOKENS:
        price = get_price(symbol)
        # Edge: Multi-indikator consensus
        action = consensus_signal(price, holdings[symbol])
        # Edge: Trailing stop-loss sjekk
        if holdings[symbol] > 0 and trailing_stops[symbol]:
            trail = trailing_stops[symbol]
            # Oppdater peak
            if price > trail["peak"]:
                trail["peak"] = price
                trail["stop"] = max(trail["stop"], price * (1 - trail["trail"]))
            if price <= trail["stop"]:
                handle_trade(symbol, "SELL", price, "TRAIL")
                continue  # Unngå dobbelthandel
        # Normal handler
        if action in ("BUY", "SELL"):
            # Edge: Velg beste strategi (weighted mean)
            strategy = get_best_strategy(trade_log) if len(trade_log) > 10 else choose_strategy()
            handle_trade(symbol, action, price, strategy)

    # Edge: Circuit breaker
    if balance < START_BALANCE * breaker_trigger:
        circuit_breaker_on = True
        send_discord(f"🚨 CIRCUIT BREAKER: Balance under {breaker_trigger*100:.1f}% – bot paused at ${balance:.2f}!")

    # Timesrapport, autotune, daglig rapport
    if time.time() - last_report > 60 * 60:
        hourly_report()
        auto_tune(trade_log)
        last_report = time.time()

    # Dagsrapport kl 06:00 UTC
    current_hour = int(time.strftime("%H", time.gmtime()))
    if current_hour == 6 and not daily_sent:
        daily_report()
        daily_sent = True
    if current_hour != 6:
        daily_sent = False

    time.sleep(30)