import random, time, os, requests
from collections import defaultdict, deque
from datetime import datetime, timedelta

# SETTINGS
TOKENS = [
    "BTCUSDT", "ETHUSDT", "SOLUSDT", "BNBUSDT", "ADAUSDT",
    "DOGEUSDT", "MATICUSDT", "AVAXUSDT", "XRPUSDT", "TRXUSDT", "LINKUSDT"
]
STRATEGIES = ["RANDOM", "RSI", "EMA", "SCALP", "MEAN", "TREND"]
DISCORD_WEBHOOK = os.getenv("DISCORD_WEBHOOK")
START_BALANCE = 1000.0

# EDGE/STOP-LOSS/REPORT
LADDER_STEP = 200             # Øk ladder-stop hvert 200 USD
LADDER_MARGIN = 0.8           # Stop-loss på 80% av ATH
REPORT_HOUR_UTC = 7           # Daglig rapport kl. 07:00 UTC
HOURLY_REPORT = True

# STATE
BALANCE = START_BALANCE
ATH_BALANCE = START_BALANCE
LADDER_STOP = int(START_BALANCE * LADDER_MARGIN)
trade_history = []
strategy_stats = defaultdict(lambda: {"pnl": 0.0, "trades": 0, "wins": 0, "last_pnl": deque(maxlen=20)})
last_edge = None
strategy_switch_log = []
last_daily_report = None

def send_discord(msg):
    if DISCORD_WEBHOOK:
        try:
            requests.post(DISCORD_WEBHOOK, json={"content": msg})
        except Exception as e:
            print("Discord error:", e)
    else:
        print("Discord log:", msg)

def select_strategy():
    # Velg beste strategi basert på PnL siste 20 trades (eller fallback RANDOM)
    best, best_pnl = "RANDOM", -999
    for strat, stats in strategy_stats.items():
        if len(stats["last_pnl"]) >= 10:
            avg = sum(stats["last_pnl"]) / len(stats["last_pnl"])
            if avg > best_pnl:
                best, best_pnl = strat, avg
    return best

def update_ladder_stop():
    global ATH_BALANCE, LADDER_STOP
    if BALANCE > ATH_BALANCE:
        ATH_BALANCE = BALANCE
        # Ladder flytter seg opp for hver ATH (med margin)
        LADDER_STOP = int(ATH_BALANCE * LADDER_MARGIN)
        send_discord(f"🔒 Ladder stop-loss flyttet til ${LADDER_STOP} (ATH: ${ATH_BALANCE})")

def log_trade(strategy, pnl):
    stats = strategy_stats[strategy]
    stats["pnl"] += pnl
    stats["trades"] += 1
    if pnl > 0:
        stats["wins"] += 1
    stats["last_pnl"].append(pnl)

def report_hourly():
    msg = f"📊 [CHUNKY-EDGE] Hourly report: Trades: {len(trade_history)}, Bal: ${BALANCE:.2f}"
    best_strat = select_strategy()
    for strat in STRATEGIES:
        s = strategy_stats[strat]
        wr = 100 * s["wins"] / s["trades"] if s["trades"] > 0 else 0
        avg = sum(s["last_pnl"]) / len(s["last_pnl"]) if s["last_pnl"] else 0
        msg += f"\n- {strat}: PnL {s['pnl']:.2f}, WR {wr:.1f}%"
    msg += f"\n🔥 Best: {best_strat}"
    send_discord(msg)

def report_daily():
    global last_daily_report
    now = datetime.utcnow()
    if last_daily_report and now.date() == last_daily_report.date():
        return  # Allerede rapportert i dag
    if now.hour == REPORT_HOUR_UTC:
        msg = f"📅 [CHUNKY-EDGE] Daily report ({now.strftime('%Y-%m-%d')}): Trades: {len(trade_history)}, Bal: ${BALANCE:.2f}"
        for strat in STRATEGIES:
            s = strategy_stats[strat]
            wr = 100 * s["wins"] / s["trades"] if s["trades"] > 0 else 0
            msg += f"\n- {strat}: PnL {s['pnl']:.2f}, WR {wr:.1f}%"
        send_discord(msg)
        last_daily_report = now

def main_loop():
    global BALANCE, last_edge
    report_timer = time.time()
    while True:
        # Check ladder stop
        update_ladder_stop()
        if BALANCE < LADDER_STOP:
            send_discord(f"🛑 STOP-LOSS: Balance under ${LADDER_STOP}! Boten PAUSE 30 min. (Bal: ${BALANCE:.2f})")
            time.sleep(1800)  # 30 min pause
            continue

        # Strategi-valg med smartere edge-bytte
        best_strategy = select_strategy()
        if best_strategy != last_edge:
            strategy_switch_log.append((datetime.utcnow(), last_edge, best_strategy, BALANCE))
            send_discord(f"🔁 Bytter edge: {last_edge} → {best_strategy} (Bal: ${BALANCE:.2f})")
            last_edge = best_strategy

        # Dummy trade – bytt ut med ekte signaler/kode
        token = random.choice(TOKENS)
        size = random.uniform(20, 50)
        entry = random.uniform(0.95, 1.05)
        # Simuler PnL
        direction = 1 if random.random() < 0.5 else -1
        exitp = entry + direction * entry * random.uniform(0.001, 0.04)
        pnl = (exitp - entry) * size

        BALANCE += pnl
        trade_history.append((datetime.utcnow(), token, best_strategy, pnl, size, entry, exitp))
        log_trade(best_strategy, pnl)

        # Hourly/daily rapporter
        if HOURLY_REPORT and (time.time() - report_timer > 3600):
            report_hourly()
            report_timer = time.time()
        report_daily()
        time.sleep(1)

if __name__ == "__main__":
    send_discord("🟢 Chunky Edge Bot starter!")
    main_loop()