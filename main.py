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
LIVE_DEMO = True

# --- STATE ---
balance = START_BALANCE
holdings = {symbol: 0.0 for symbol in TOKENS}
trade_log = []
auto_buy_pct = 0.1
paused_strategies = set()
last_loss = {}

def send_discord(msg):
    print("DISCORD:", msg)
    try:
        requests.post(DISCORD_WEBHOOK, json={"content": msg})
    except Exception as e:
        print(f"Discord error: {e}")

def get_live_price(symbol):
    coingecko_id = COINGECKO_MAP.get(symbol, "bitcoin")
    url = f"https://api.coingecko.com/api/v3/simple/price?ids={coingecko_id}&vs_currencies=usd"
    try:
        data = requests.get(url, timeout=5).json()
        return float(data[coingecko_id]["usd"])
    except Exception as e:
        print(f"Live price error: {e}")
        return None

def get_dummy_price(symbol):
    return random.uniform(10, 100)

def all_strategies():
    return ["RSI", "EMA", "RANDOM", "SCALP", "MEAN", "TREND"]

def choose_strategy(active_strategies):
    # Plukk tilfeldig av aktive, hvis tom: fallback til RANDOM
    if not active_strategies:
        return "RANDOM"
    return random.choice(active_strategies)

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
    elif strategy == "SCALP":
        # Kjapp trade – kjøp hvis pris slutter på 3 eller 7, selg hvis 8 eller 9
        if int(price) % 10 in (3, 7) and holdings == 0:
            return "BUY"
        elif int(price) % 10 in (8, 9) and holdings > 0:
            return "SELL"
        else:
            return "HOLD"
    elif strategy == "MEAN":
        # Mean reversion (late som): Kjøp hvis pris er under 40, selg hvis over 70
        if price < 40 and holdings == 0:
            return "BUY"
        elif price > 70 and holdings > 0:
            return "SELL"
        else:
            return "HOLD"
    elif strategy == "TREND":
        # Trend: kjøp hvis pris er stigende siste 3 ticks
        if price > 50 and holdings == 0:
            return "BUY"
        elif price < 50 and holdings > 0:
            return "SELL"
        else:
            return "HOLD"
    else:
        return random.choice(["BUY", "SELL", "HOLD"])

def get_best_strategies(trade_log, min_pnl=0):
    recent = [t for t in trade_log[-20:] if t["action"] == "SELL"]
    strat_stats = {}
    for t in recent:
        s = t.get("strategy", "RANDOM")
        strat_stats.setdefault(s, []).append(t.get("pnl", 0))
    winners = []
    for s, pnl_list in strat_stats.items():
        if sum(pnl_list)/len(pnl_list) > min_pnl:
            winners.append(s)
    return winners if winners else ["RANDOM"]

def handle_trade(symbol, action, price, strategy):
    global balance, holdings, trade_log, auto_buy_pct, last_loss
    if price is None: return
    amount_usd = balance * auto_buy_pct if action == "BUY" else holdings[symbol] * price
    qty = round(amount_usd / price, 6) if action == "BUY" else holdings[symbol]
    pnl = 0.0

    if action == "BUY" and balance >= amount_usd and qty > 0:
        balance -= amount_usd
        holdings[symbol] += qty
        send_discord(f"🔵 BUY {symbol}: {qty} at ${price:.2f}, new balance ${balance:.2f} [{strategy}] [{('LIVE DEMO' if LIVE_DEMO else 'DUMMY')}]")
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
        send_discord(f"🔴 SELL {symbol}: {qty} at ${price:.2f}, PnL: {pnl:.2f}%, balance: ${balance:.2f} [{strategy}] [{('LIVE DEMO' if LIVE_DEMO else 'DUMMY')}]")
        trade_log.append({
            "symbol": symbol, "action": "SELL", "price": price,
            "qty": qty, "timestamp": time.time(), "strategy": strategy, "pnl": pnl
        })
        # Track tap for strategi
        if pnl < 0:
            last_loss.setdefault(strategy, []).append(1)
        else:
            last_loss.setdefault(strategy, []).append(0)
        # Slett eldre enn 3
        if len(last_loss[strategy]) > 3:
            last_loss[strategy] = last_loss[strategy][-3:]

def hourly_report():
    total_trades = len(trade_log)
    realized_pnl = sum(t.get("pnl", 0) for t in trade_log if t["action"] == "SELL")
    strat_pnls = {}
    strat_wins = {}
    for s in all_strategies():
        sells = [t for t in trade_log if t.get("strategy")==s and t["action"]=="SELL"]
        pnl = sum(t["pnl"] for t in sells)
        wins = [t for t in sells if t["pnl"]>0]
        wr = 100*len(wins)/len(sells) if sells else 0
        strat_pnls[s] = pnl
        strat_wins[s] = wr
    msg = f"📊 [CHUNKY-EDGE] Hourly report: Trades: {total_trades}, Bal: ${balance:.2f}, Realized PnL: {realized_pnl:.2f}\n"
    for s in all_strategies():
        msg += f"- {s}: PnL {strat_pnls[s]:.2f}, WR {strat_wins[s]:.1f}%\n"
    best = max(strat_pnls, key=lambda s: strat_pnls[s])
    msg += f"🔥 Best: {best}"
    send_discord(msg)

def daily_report():
    total_trades = len(trade_log)
    realized_pnl = sum(t.get("pnl", 0) for t in trade_log if t["action"] == "SELL")
    msg = f"📅 [CHUNKY-EDGE] DAILY report: Trades: {total_trades}, Bal: ${balance:.2f}, Realized PnL: {realized_pnl:.2f} [{('LIVE DEMO' if LIVE_DEMO else 'DUMMY')}]"
    send_discord(msg)

send_discord(f"🟢 AtomicBot starter… ({'LIVE DEMO' if LIVE_DEMO else 'DUMMY'} mode!)")

last_report = time.time()
last_hour = time.gmtime().tm_hour
daily_sent = False
pause_until = {}

while True:
    # Emergency mode hvis under 60 % av startbalanse
    if balance < START_BALANCE * 0.6:
        active_strategies = ["RSI", "RANDOM"]
        send_discord("⚠️ EMERGENCY MODE: Bruker kun RSI & RANDOM (balanse lav!)")
    else:
        # Pause tapere i 1 time hvis 3 tap på rad
        now = time.time()
        for s, losses in last_loss.items():
            if sum(losses)==3 and (pause_until.get(s,0) < now):
                paused_strategies.add(s)
                pause_until[s] = now + 3600  # 1 time pause
                send_discord(f"⏸️ Setter strategi {s} på pause i 1 time (3 tap på rad)")
            if pause_until.get(s,0) < now and s in paused_strategies:
                paused_strategies.remove(s)
        # Velg vinnere
        active_strategies = [s for s in get_best_strategies(trade_log) if s not in paused_strategies]
        if not active_strategies:
            active_strategies = ["RANDOM"]
    for symbol in TOKENS:
        price = get_live_price(symbol) if LIVE_DEMO else get_dummy_price(symbol)
        strategy = choose_strategy(active_strategies)
        action = get_signal(strategy, price, holdings[symbol])
        print(f"{symbol} | Pris: {price} | Strategy: {strategy} | Signal: {action}")
        if action in ("BUY", "SELL"):
            handle_trade(symbol, action, price, strategy)

    now = time.gmtime()
    if now.tm_min == 0 and now.tm_sec < 30 and last_hour != now.tm_hour:
        hourly_report()
        last_hour = now.tm_hour
    if now.tm_hour == 7 and now.tm_min == 0 and now.tm_sec < 30 and not daily_sent:
        daily_report()
        daily_sent = True
    elif now.tm_hour != 7:
        daily_sent = False

    time.sleep(5)