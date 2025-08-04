import random, time, os, requests
from collections import defaultdict, deque
from datetime import datetime

# SETTINGS
TOKENS = [
    "BTCUSDT", "ETHUSDT", "SOLUSDT", "BNBUSDT", "ADAUSDT",
    "DOGEUSDT", "MATICUSDT", "AVAXUSDT", "XRPUSDT", "TRXUSDT", "LINKUSDT"
]
STRATEGIES = ["RANDOM", "RSI", "EMA", "SCALP", "MEAN", "TREND"]
DISCORD_WEBHOOK = os.getenv("DISCORD_WEBHOOK")
START_BALANCE = 1000.0
TRADE_SIZE_PCT = 0.10  # 10 % av balanse normalt
LOW_BALANCE_TRADE_SIZE = 0.06  # 6 % hvis under $600
STOP_LOSS_PCT = -0.02   # -2 % tap per trade
TAKE_PROFIT_PCT = 0.025  # +2.5 % gevinst per trade
STRATEGY_SWITCH_LOSSES = 3

# EDGE/REPORTS
LADDER_STEP = 200
LADDER_MARGIN = 0.8
REPORT_HOUR_UTC = 7
HOURLY_REPORT = True

# STATE
BALANCE = START_BALANCE
ATH_BALANCE = START_BALANCE
LADDER_STOP = int(START_BALANCE * LADDER_MARGIN)
trade_history = []
strategy_stats = defaultdict(lambda: {"pnl": 0.0, "trades": 0, "wins": 0, "last_pnl": deque(maxlen=20), "consec_losses": 0})
last_edge = None
strategy_switch_log = []
last_daily_report = None
best_strategy_now = None

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
        LADDER_STOP = int(ATH_BALANCE * LADDER_MARGIN)
        send_discord(f"🔒 Ladder stop-loss flyttet til ${LADDER_STOP} (ATH: ${ATH_BALANCE})")

def log_trade(strategy, pnl):
    stats = strategy_stats[strategy]
    stats["pnl"] += pnl
    stats["trades"] += 1
    if pnl > 0:
        stats["wins"] += 1
        stats["consec_losses"] = 0
    else:
        stats["consec_losses"] += 1
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
        return
    if now.hour == REPORT_HOUR_UTC:
        msg = f"📅 [CHUNKY-EDGE] Daily report ({now.strftime('%Y-%m-%d')}): Trades: {len(trade_history)}, Bal: ${BALANCE:.2f}"
        for strat in STRATEGIES:
            s = strategy_stats[strat]
            wr = 100 * s["wins"] / s["trades"] if s["trades"] > 0 else 0
            msg += f"\n- {strat}: PnL {s['pnl']:.2f}, WR {wr:.1f}%"
        send_discord(msg)
        last_daily_report = now

def main_loop():
    global BALANCE, last_edge, best_strategy_now
    report_timer = time.time()
    strategy = select_strategy()
    loss_streak = 0

    while True:
        update_ladder_stop()
        # Dynamic trade size
        size_pct = TRADE_SIZE_PCT if BALANCE >= 600 else LOW_BALANCE_TRADE_SIZE

        # Edge-bytte hvis 3 tap på rad
        if strategy_stats[strategy]["consec_losses"] >= STRATEGY_SWITCH_LOSSES:
            prev = strategy
            strategy = select_strategy()
            if strategy != prev:
                send_discord(f"🔁 Bytter strategi pga. {STRATEGY_SWITCH_LOSSES} tap: {prev} → {strategy} (Bal: ${BALANCE:.2f})")
            strategy_stats[prev]["consec_losses"] = 0

        # Dummy trade – bytt ut med ekte signaler/kode
        token = random.choice(TOKENS)
        size = round(BALANCE * size_pct, 2)
        entry = random.uniform(0.95, 1.05)
        # Simuler PnL
        direction = 1 if random.random() < 0.5 else -1
        price_move = random.uniform(STOP_LOSS_PCT, TAKE_PROFIT_PCT)
        pnl_pct = price_move if direction > 0 else -price_move
        pnl = size * pnl_pct

        # Apply take profit/stop loss
        if pnl_pct < STOP_LOSS_PCT:
            pnl = size * STOP_LOSS_PCT
        elif pnl_pct > TAKE_PROFIT_PCT:
            pnl = size * TAKE_PROFIT_PCT

        BALANCE += pnl
        trade_history.append((datetime.utcnow(), token, strategy, pnl, size, entry, entry + pnl_pct))
        log_trade(strategy, pnl)

        # Hourly/daily rapporter
        if HOURLY_REPORT and (time.time() - report_timer > 3600):
            report_hourly()
            report_timer = time.time()
        report_daily()
        time.sleep(1)

if __name__ == "__main__":
    send_discord("🟢 Chunky Edge Bot starter (with all chunky tweaks)!")
    main_loop()