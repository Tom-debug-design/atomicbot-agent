import random, time, os, requests, json

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
holdings = {symbol: 0.0 for symbol in TOKENS}
trade_log = []
edge_scores = {}  # Holder suksessrate per strategi-kombinasjon
auto_buy_pct = 0.1

def send_discord(msg):
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

# Eksempelstrategier (lag flere/mer avanserte om ønskelig)
def rsi_signal(price): return "BUY" if int(price)%10==3 else "SELL" if int(price)%10==7 else "HOLD"
def ema_signal(price): return "BUY" if int(price)%2==0 else "SELL" if int(price)%5==0 else "HOLD"
def mean_signal(price): return random.choice(["BUY", "SELL", "HOLD"])
def scalp_signal(price): return "BUY" if price and price%13<2 else "SELL" if price and price%7==0 else "HOLD"
def trend_signal(price): return "BUY" if int(price)%3==0 else "SELL" if int(price)%4==0 else "HOLD"

strategies = [rsi_signal, ema_signal, mean_signal, scalp_signal, trend_signal]

def get_signals(price):
    # Henter signal fra alle strategier, returnerer ["BUY", "SELL", ...]
    return [strategy(price) for strategy in strategies]

def consensus_action(signals):
    # Handler bare hvis minst 4 er enige
    buy_votes = signals.count("BUY")
    sell_votes = signals.count("SELL")
    if buy_votes >= 4: return "BUY"
    if sell_votes >= 4: return "SELL"
    return "HOLD"

def edge_key(signals):
    # Bruker signalene som key for edge-statistikk (eks: "BUY-BUY-HOLD-SELL-BUY")
    return "-".join(signals)

def update_edge_scores(signals, pnl):
    k = edge_key(signals)
    if k not in edge_scores: edge_scores[k] = []
    edge_scores[k].append(pnl)
    # Kun siste 30 resultater for denne kombinasjonen
    if len(edge_scores[k]) > 30:
        edge_scores[k] = edge_scores[k][-30:]

def best_edge_combo():
    # Returner den signal-kombinasjonen som har best gjennomsnittlig edge
    best = None
    best_score = -999
    for k, lst in edge_scores.items():
        if len(lst) < 6: continue  # Minstekrav for at ML skal bruke
        avg = sum(lst)/len(lst)
        if avg > best_score:
            best = k
            best_score = avg
    return best, best_score

def handle_trade(symbol, action, price, strategy_combo, signals):
    global balance, holdings, trade_log, auto_buy_pct
    if price is None: return
    amount_usd = balance * auto_buy_pct if action == "BUY" else holdings[symbol] * price
    qty = round(amount_usd / price, 6) if action == "BUY" else holdings[symbol]
    pnl = 0.0

    if action == "BUY" and balance >= amount_usd and qty > 0:
        balance -= amount_usd
        holdings[symbol] += qty
        send_discord(f"🔵 BUY {symbol}: {qty} at ${price:.2f}, balance: ${balance:.2f} [{strategy_combo}]")
        trade_log.append({
            "symbol": symbol, "action": "BUY", "price": price,
            "qty": qty, "timestamp": time.time(),
            "signals": signals, "edge_combo": strategy_combo, "pnl": 0.0
        })
    elif action == "SELL" and holdings[symbol] > 0:
        proceeds = qty * price
        last_buy = next((t for t in reversed(trade_log) if t["symbol"] == symbol and t["action"] == "BUY"), None)
        pnl = ((price - last_buy["price"]) / last_buy["price"] * 100) if last_buy else 0.0
        balance += proceeds
        holdings[symbol] = 0.0
        send_discord(f"🔴 SELL {symbol}: {qty} at ${price:.2f}, PnL: {pnl:.2f}%, balance: ${balance:.2f} [{strategy_combo}]")
        trade_log.append({
            "symbol": symbol, "action": "SELL", "price": price,
            "qty": qty, "timestamp": time.time(),
            "signals": signals, "edge_combo": strategy_combo, "pnl": pnl
        })
        update_edge_scores(signals, pnl)

def should_switch_strategy():
    # Smartere byttelogikk:
    recent = trade_log[-10:]
    if len(recent) < 3: return False
    last_trades = trade_log[-3:]
    # Bytt om 3 tap på rad
    if all(t.get("pnl", 0) < 0 for t in last_trades): return True
    # Bytt om PnL siste 10 trades er dårlig
    if sum(t.get("pnl", 0) for t in recent) < -2.0: return True
    # Bytt hvis balansen har falt >6% siste 25 trades
    if len(trade_log) > 25:
        bal_then = START_BALANCE + sum(t["pnl"]/100*START_BALANCE for t in trade_log[-25:])
        if balance < bal_then * 0.94: return True
    return False

def hourly_report():
    total_trades = len(trade_log)
    realized_pnl = sum(t.get("pnl", 0) for t in trade_log if t["action"] == "SELL")
    msg = f"📊 [CHUNKY-EDGE] Hourly: Trades: {total_trades}, Bal: ${balance:.2f}, PnL: {realized_pnl:.2f}"
    best_combo, best_score = best_edge_combo()
    if best_combo:
        msg += f"\n🔥 Best combo: {best_combo} ({best_score:.2f}%)"
    send_discord(msg)

send_discord("🟢 Chunky main v. edge/consensus starter!")

last_report = time.time()

while True:
    for symbol in TOKENS:
        price = get_price(symbol)
        signals = get_signals(price)
        action = consensus_action(signals)
        if action in ("BUY", "SELL"):
            handle_trade(symbol, action, price, edge_key(signals), signals)
        if should_switch_strategy():
            send_discord("🔄 Bytter strategi pga tap/dårlig edge!")
            # Her kan du evt. bytte til ny kombinasjon eller endre strategi-mix.
    if time.time() - last_report > 60:
        hourly_report()
        last_report = time.time()
    time.sleep(30)