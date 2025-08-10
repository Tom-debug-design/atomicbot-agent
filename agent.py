import os
import random
import time
import datetime
import json

TOKENS = [
    "BTCUSDT", "ETHUSDT", "SOLUSDT", "BNBUSDT", "XRPUSDT", "ADAUSDT",
    "DOGEUSDT", "AVAXUSDT", "LINKUSDT", "TRXUSDT"
]
START_BALANCE = 1000.0
TRADE_SIZE = 0.03
TP = 0.002
SL = 0.002
STOP_LOSS_PCT = 0.07
TRAIL_START_PCT = 0.03
TRAIL_STEP_PCT = 0.02
STRATEGIES = ["RANDOM", "RSI", "EMA", "SCALP", "MEAN", "TREND"]
DISCORD_WEBHOOK = os.environ.get("DISCORD_WEBHOOK", "https://discord.com/api/webhooks/...")

balance = START_BALANCE
holdings = {token: 0 for token in TOKENS}
entry = {token: None for token in TOKENS}
peak = {token: None for token in TOKENS}
trade_log = []
strat_stats = {s: {"wins": 0, "loss": 0, "last_pnl": []} for s in STRATEGIES}
tap_counter = 0
strategy = "RANDOM"
total_trades = 0
last_daily = None

def send_discord(msg, filedata=None, filename=None):
    import requests
    payload = {"content": msg}
    files = None
    if filedata and filename:
        files = {"file": (filename, filedata)}
    try:
        if files:
            requests.post(DISCORD_WEBHOOK, data=payload, files=files)
        else:
            requests.post(DISCORD_WEBHOOK, json=payload)
    except Exception as e:
        print("DC error", e)

def get_price(token):
    base = {
        "BTCUSDT": 30000, "ETHUSDT": 1700, "SOLUSDT": 20, "BNBUSDT": 250, "XRPUSDT": 0.6,
        "ADAUSDT": 0.4, "DOGEUSDT": 0.07, "AVAXUSDT": 10, "LINKUSDT": 6, "TRXUSDT": 0.07
    }
    return round(base[token] * random.uniform(0.98, 1.02), 2)

def select_strategy():
    global strategy, tap_counter
    if total_trades >= 20:
        best = max(STRATEGIES, key=lambda s: sum(strat_stats[s]["last_pnl"][-20:]))
        if best != strategy:
            send_discord(f"🔄 [CHUNKY-EDGE][AI] Switching to best strategy: {best}")
        strategy = best
        tap_counter = 0
    if tap_counter >= 3:
        old_strategy = strategy
        strategy = random.choice([s for s in STRATEGIES if s != strategy])
        send_discord(f"🔄 [CHUNKY-EDGE][Rapid] Forced switch: {old_strategy} → {strategy} etter {tap_counter} tap!")
        tap_counter = 0
    return strategy

def calc_signal(token, strategy):
    price = get_price(token)
    if price is None:
        return None, "HOLD"
    if strategy == "RANDOM":
        return price, random.choice(["BUY", "SELL", "HOLD"])
    elif strategy == "RSI":
        rsi = random.uniform(10, 90)
        if rsi < 30: return price, "BUY"
        elif rsi > 70: return price, "SELL"
        else: return price, "HOLD"
    elif strategy == "EMA":
        ema = price * random.uniform(0.98, 1.02)
        if price < ema: return price, "BUY"
        else: return price, "SELL"
    elif strategy == "SCALP":
        if random.random() > 0.5: return price, "BUY"
        else: return price, "SELL"
    elif strategy == "MEAN":
        if random.random() < 0.05: return price, "BUY"
        elif random.random() > 0.95: return price, "SELL"
        else: return price, "HOLD"
    elif strategy == "TREND":
        last_trades = [t for t in trade_log[-5:] if t["token"] == token]
        if last_trades:
            last = last_trades[-1]
            if last["action"] == "BUY": return price, "BUY"
            else: return price, "SELL"
        return price, random.choice(["BUY", "SELL"])
    return price, "HOLD"

def now():
    return datetime.datetime.now(datetime.timezone.utc).strftime('%Y-%m-%d %H:%M:%S')

def handle_trade(token, action, price, strategy, edge=False, edge_type=""):
    global balance, tap_counter, total_trades
    qty = round(balance * TRADE_SIZE / price, 6)
    pnl = 0
    label = "[CHUNKY-EDGE]" if edge else "[STD]"
    if edge_type:
        label += f" [{edge_type}]"
    if action == "BUY" and balance > price * qty:
        balance -= price * qty
        holdings[token] += qty
        entry[token] = price
        peak[token] = price
        send_discord(f"{label} BUY {token}: {qty} @ ${price}, strategy: {strategy}, bal: ${round(balance,2)}")
        trade_log.append({"token": token, "action": "BUY", "price": price, "qty": qty, "strategy": strategy, "pnl": 0, "timestamp": now()})
    elif action == "SELL" and holdings[token] > 0:
        last_entry = entry[token] if entry[token] else price
        balance += price * holdings[token]
        pnl = (price - last_entry) * holdings[token]
        if pnl < 0:
            tap_counter += 1
            strat_stats[strategy]["loss"] += 1
        else:
            tap_counter = 0
            strat_stats[strategy]["wins"] += 1
        strat_stats[strategy]["last_pnl"].append(pnl)
        send_discord(f"{label} SELL {token}: {holdings[token]} @ ${price}, PnL: {round(pnl,2)}, bal: ${round(balance,2)}")
        trade_log.append({"token": token, "action": "SELL", "price": price, "qty": holdings[token], "strategy": strategy, "pnl": pnl, "timestamp": now()})
        holdings[token] = 0
        entry[token] = None
        peak[token] = None
    total_trades += 1

def check_edge_exit(token, price):
    if holdings[token] > 0 and entry[token]:
        gain = (price - entry[token]) / entry[token]
        if gain > TRAIL_START_PCT:
            if price > peak[token]:
                peak[token] = price
            elif price < peak[token] * (1 - TRAIL_STEP_PCT):
                send_discord(f"🔥 [CHUNKY-EDGE][Trailing] Trailing stop utløst – SELL {token} på ${price}!")
                return "SELL", True, "Trailing"
        if gain < -STOP_LOSS_PCT:
            send_discord(f"🔥 [CHUNKY-EDGE][Stoploss] Stop loss utløst – SELL {token} på ${price} (PnL: {round(gain*100,2)}%)!")
            return "SELL", True, "Stoploss"
    return "HOLD", False, ""

def hourly_report():
    realized_pnl = sum([t["pnl"] for t in trade_log if t["action"] == "SELL"])
    strat_pnl = {s: sum([t["pnl"] for t in trade_log if t["action"] == "SELL" and t["strategy"] == s]) for s in STRATEGIES}
    strat_win = {s: sum([1 for t in trade_log if t["action"] == "SELL" and t["strategy"] == s and t["pnl"] > 0]) for s in STRATEGIES}
    strat_trades = {s: sum([1 for t in trade_log if t["action"] == "SELL" and t["strategy"] == s]) for s in STRATEGIES}
    strat_wr = {s: (100*strat_win[s]/strat_trades[s] if strat_trades[s]>0 else 0) for s in STRATEGIES}
    best = max(STRATEGIES, key=lambda s: strat_pnl[s])
    msg = f"📊 [CHUNKY-EDGE] Hourly report: Trades: {len(trade_log)}, Bal: ${round(balance,2)}, Realized PnL: {round(realized_pnl,2)}\n"
    msg += "\n".join([f"- {s}: PnL {round(strat_pnl[s],2)}, WR {round(strat_wr[s],1)}%" for s in STRATEGIES])
    msg += f"\n🔥 Best: {best}"
    send_discord(msg)

def daily_json_report():
    today = datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%d")
    filename = f"chunky_trades_{today}.json"
    data = json.dumps(trade_log, indent=2)
    msg = f"📈 Daily chunky trading log for {today}.\nSee attached JSON file for all trades.\n"
    send_discord(msg, filedata=data.encode(), filename=filename)

def main_loop():
    global total_trades, last_daily
    send_discord(f"🤖 [CHUNKY-EDGE] AtomicBot Super Edge {now()} – with daily JSON report!")
    while True:
        now_dt = datetime.datetime.now(datetime.timezone.utc)
        # Main trading loop
        for token in TOKENS:
            try:
                strat = select_strategy()
                price, signal = calc_signal(token, strat)
                edge_action, is_edge, edge_type = check_edge_exit(token, price)
                if edge_action == "SELL":
                    handle_trade(token, "SELL", price, strat, edge=True, edge_type=edge_type)
                if signal in ["BUY", "SELL"]:
                    handle_trade(token, signal, price, strat, edge=False)
            except Exception as e:
                send_discord(f"❌ [CHUNKY-EDGE] ERROR {token}: {e}")

        # Hourly report
        if now_dt.minute == 0 and (not hasattr(main_loop, "last_hour") or main_loop.last_hour != now_dt.hour):
            hourly_report()
            main_loop.last_hour = now_dt.hour

        # Daily JSON report (UTC 06:00)
        if now_dt.hour == 6 and (last_daily is None or last_daily != now_dt.date()):
            daily_json_report()
            last_daily = now_dt.date()
        time.sleep(10)

# ... alt innholdet i agent.py over denne blokken ...

if __name__ == "__main__":
    # 🚀 GitHub-bridge test ved oppstart (med env-sjekk og Discord-varsel)
    try:
        import os, datetime, bridge

        missing = [k for k in ("GITHUB_TOKEN", "GITHUB_REPO") if not os.getenv(k)]
        if missing:
            send_discord(f"❌ [BRIDGE] Mangler env vars: {', '.join(missing)}")
        else:
            stamp = datetime.datetime.utcnow().isoformat() + "Z"
            ok = bridge.commit_file("bridge_test_live.txt", f"Bridge is alive - {stamp}")
            if ok:
                send_discord(f"✅ [BRIDGE] bridge_test_live.txt pushet {stamp}")
            else:
                send_discord("❌ [BRIDGE] commit_file() returnerte False (sjekk token/scope/branch).")
    except Exception as e:
        send_discord(f"🔥 [BRIDGE ERROR] {type(e).__name__}: {e}")

    # Start trading-loopen
    main_loop()
