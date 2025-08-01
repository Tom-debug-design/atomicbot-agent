import os, random, time, requests
from binance.client import Client

# === TOGGLE: Demo eller ekte handler ===
USE_BINANCE_LIVE = False   # False = demo/sim, True = live på Binance

# === Binance-oppkobling (API fra Railway) ===
API_KEY = os.getenv("BINANCE_API_KEY")
API_SECRET = os.getenv("BINANCE_API_SECRET")
if USE_BINANCE_LIVE:
    client = Client(API_KEY, API_SECRET)

TOKENS = [
    "BTCUSDT", "ETHUSDT", "SOLUSDT", "BNBUSDT", "XRPUSDT",
    "ADAUSDT", "DOGEUSDT", "MATICUSDT", "AVAXUSDT", "LINKUSDT"
]
DISCORD_WEBHOOK = os.getenv("DISCORD_WEBHOOK")
START_BALANCE = 1000.0

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

def get_price(symbol):
    if USE_BINANCE_LIVE:
        try:
            ticker = client.get_symbol_ticker(symbol=symbol)
            return float(ticker["price"])
        except Exception as e:
            print(f"Binance price fetch error: {e}")
            return None
    else:
        # Demo: bruk random pris (eller erstatt med annen priskilde for demo)
        return random.uniform(0.5, 100_000)

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
    global balance, holdings, trade_log, auto_buy_pct

    if price is None: return
    amount_usd = balance * auto_buy_pct if action == "BUY" else holdings[symbol] * price
    qty = round(amount_usd / price, 6) if action == "BUY" else holdings[symbol]
    pnl = 0.0

    # === LIVE mode: Bruk Binance! ===
    if USE_BINANCE_LIVE:
        try:
            if action == "BUY" and balance >= amount_usd and qty > 0:
                order = client.create_order(
                    symbol=symbol, side=Client.SIDE_BUY,
                    type=Client.ORDER_TYPE_MARKET, quantity=qty
                )
                balance -= amount_usd
                holdings[symbol] += qty
                send_discord(f"🟢 REAL BUY {symbol}: {qty} at ${price:.2f}, order: {order['orderId']}, balance: ${balance:.2f}")
            elif action == "SELL" and holdings[symbol] > 0:
                order = client.create_order(
                    symbol=symbol, side=Client.SIDE_SELL,
                    type=Client.ORDER_TYPE_MARKET, quantity=qty
                )
                proceeds = qty * price
                last_buy = next((t for t in reversed(trade_log) if t["symbol"] == symbol and t["action"] == "BUY"), None)
                pnl = ((price - last_buy["price"]) / last_buy["price"] * 100) if last_buy else 0.0
                balance += proceeds
                holdings[symbol] = 0.0
                send_discord(f"🔴 REAL SELL {symbol}: {qty} at ${price:.2f}, PnL: {pnl:.2f}%, order: {order['orderId']}, balance: ${balance:.2f}")
        except Exception as e:
            send_discord(f"⚠️ Binance trade error: {e}")
    # === DEMO mode: bare simuler ===
    else:
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
        return choose_strategy()
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

send_discord("🟢 AtomicBot agent starter…")

last_report = time.time()

while True:
    for symbol in TOKENS:
        price = get_price(symbol)
        strategy = get_best_strategy(trade_log) if len(trade_log) > 10 else choose_strategy()
        action = get_signal(strategy, price, holdings[symbol])
        print(f"{symbol} | Pris: {price} | Strategy: {strategy} | Signal: {action}")
        if action in ("BUY", "SELL"):
            handle_trade(symbol, action, price, strategy)
    # Rapport, AI og tuning hvert 60 sek
    if time.time() - last_report > 60:
        hourly_report()
        ai_feedback()
        auto_tune(trade_log)
        last_report = time.time()
    time.sleep(30)
