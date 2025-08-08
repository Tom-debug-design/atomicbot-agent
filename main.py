# main.py — AtomicBot v6 (no Fibonacci)
# Mode: demo (live Binance klines) | dummy (syntetiske priser)
# Features:
# - Dynamic Edge Score (PnL%, winrate, #trades) per strategi
# - 4 av 5 strategier må være enige før entry
# - Stop-loss ~ -2% per trade, exit også når 4/5 signal snur imot
# - Hourly + daily (06:00 Europe/Oslo) Discord-rapporter
# - Versjonsmerking i rapport + grønn markering ved balanse > 1000
# - Ekstra logging til Discord for AI-analyse
# ---------------------------------------------------------------

import os
import time
import math
import json
import random
import threading
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

import requests
from flask import Flask, jsonify
import bridge
bridge.commit_file("bridge_test.txt", f"Bridge is alive - {__name__}")
VERSION = "AtomicBot v6"
DEFAULT_TOKENS = ["BTC", "ETH", "BNB", "XRP", "ADA", "SOL", "AVAX", "MATIC"]
BINANCE_BASE = "https://api.binance.com/api/v3"

DISCORD_WEBHOOK = os.getenv("DISCORD_WEBHOOK", "").strip()
MODE = os.getenv("MODE", "demo").lower().strip()  # "demo" | "dummy"
TOKENS = os.getenv("TOKENS")
TOKENS = [t.strip().upper() for t in TOKENS.split(",")] if TOKENS else DEFAULT_TOKENS

INITIAL_BALANCE = float(os.getenv("INITIAL_BALANCE", "1000"))
TRADE_PCT = float(os.getenv("TRADE_PCT", "0.05"))  # 5% pos størrelse
STOP_LOSS_PCT = float(os.getenv("STOP_LOSS_PCT", "0.02"))  # ~2%

TICK_SECONDS = int(os.getenv("TICK_SECONDS", "15"))  # loop-frekvens
OSLO = ZoneInfo("Europe/Oslo")

app = Flask(__name__)

def send_discord(message: str, extra_fields: dict | None = None, level: str = "info"):
    if not DISCORD_WEBHOOK:
        print("[Discord disabled]", message, extra_fields or {})
        return
    color = 0x2ecc71 if "🟢" in message else 0xe67e22 if level == "warn" else 0xe74c3c if level == "error" else 0x3498db
    embed = {
        "title": VERSION,
        "description": message,
        "color": color,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "footer": {"text": "AtomicBot • v6"},
    }
    if extra_fields:
        fields = []
        for k, v in extra_fields.items():
            fields.append({"name": str(k), "value": f"`{v}`", "inline": True})
        if fields:
            embed["fields"] = fields
    try:
        requests.post(DISCORD_WEBHOOK, json={"embeds": [embed]}, timeout=10)
    except Exception as e:
        print("Discord error:", e)

def get_klines(symbol: str, interval="1m", limit=120):
    # Returns list of closes (floats). Demo uses Binance; Dummy uses synthetic.
    if MODE == "dummy":
        # Synthetic random walk for indicator testing
        base = 100 + random.random() * 50
        series = [base]
        for _ in range(limit - 1):
            series.append(series[-1] * (1 + random.uniform(-0.003, 0.003)))
        return series
    # DEMO: fetch live klines
    pair = f"{symbol}USDT"
    try:
        resp = requests.get(f"{BINANCE_BASE}/klines", params={"symbol": pair, "interval": interval, "limit": limit}, timeout=10)
        data = resp.json()
        closes = [float(c[4]) for c in data]  # close price index
        return closes
    except Exception as e:
        print("Klines error:", e)
        return []

# --- Indicators (minimal implementations)
def sma(values, n):
    if len(values) < n: return None
    return sum(values[-n:]) / n

def ema(values, n):
    if len(values) < n: return None
    k = 2 / (n + 1)
    e = sum(values[:n]) / n
    for v in values[n:]:
        e = v * k + e * (1 - k)
    return e

def rsi(values, n=14):
    if len(values) <= n: return None
    gains = []
    losses = []
    for i in range(1, len(values)):
        diff = values[i] - values[i-1]
        gains.append(max(diff, 0))
        losses.append(abs(min(diff, 0)))
    avg_gain = sum(gains[-n:]) / n
    avg_loss = sum(losses[-n:]) / n
    if avg_loss == 0: return 100.0
    rs = avg_gain / avg_loss
    return 100 - (100 / (1 + rs))

def macd(values, fast=12, slow=26, signal=9):
    if len(values) < slow + signal: return None, None, None
    fast_ema = ema(values, fast)
    slow_ema = ema(values, slow)
    if fast_ema is None or slow_ema is None: return None, None, None
    macd_line = fast_ema - slow_ema
    # crude signal using last N calculated deltas
    # to keep dependencies light we recompute a short tail
    tail = values[-(slow+signal+2):]
    macd_series = []
    for i in range(len(tail)):
        sub = tail[:i+1]
        if len(sub) >= slow:
            macd_series.append(ema(sub, fast) - ema(sub, slow))
    if len(macd_series) < signal: return macd_line, None, None
    # signal line as SMA of last "signal" macd points (good enough here)
    sig_line = sum(macd_series[-signal:]) / signal
    hist = macd_line - sig_line
    return macd_line, sig_line, hist

def bollinger(values, n=20, k=2):
    if len(values) < n: return None, None, None
    mean = sma(values, n)
    var = sum((v - mean)**2 for v in values[-n:]) / n
    std = math.sqrt(var)
    upper = mean + k * std
    lower = mean - k * std
    return lower, mean, upper

def momentum(values, n=10):
    if len(values) < n+1: return None
    return values[-1] - values[-1-n]

# --- Strategies (5 total; return True for bullish/entry, False for bearish/exit)
def strat_rsi(values):
    r = rsi(values, 14)
    if r is None: return None
    # Entry if RSI cross up from <50 to >50 bias
    return r > 52  # slightly stricter than neutral

def strat_ema_cross(values):
    e9 = ema(values, 9); e21 = ema(values, 21)
    if e9 is None or e21 is None: return None
    return e9 > e21

def strat_macd(values):
    m, s, h = macd(values)
    if m is None or s is None: return None
    return h is not None and h > 0

def strat_bbands(values):
    lower, mid, upper = bollinger(values, 20, 2)
    if lower is None: return None
    price = values[-1]
    # bullish if price above mid but not overheated vs upper
    return price > mid and price < upper * 1.01

def strat_momentum(values):
    m = momentum(values, 10)
    if m is None: return None
    return m > 0

STRATEGIES = {
    "RSI": strat_rsi,
    "EMA": strat_ema_cross,
    "MACD": strat_macd,
    "BBANDS": strat_bbands,
    "MOMENTUM": strat_momentum,
}

class AtomicBot:
    def __init__(self):
        self.balance = INITIAL_BALANCE
        self.initial_balance = INITIAL_BALANCE
        self.positions = {}  # symbol -> {"qty": float, "entry": float}
        self.history = []    # list of trades
        # stats per strategy
        self.stats = {name: {"wins": 0, "losses": 0, "pnl": 0.0, "trades": 0} for name in STRATEGIES.keys()}
        self.last_hour_sent = None
        self.last_daily_date = None
        self.startup_ping()

    # --- Reporting
    def startup_ping(self):
        marker = "🟢" if self.balance > 1000 else "🔵"
        send_discord(f"{marker} Start: {VERSION} online • Mode: `{MODE}` • Tokens: {', '.join(TOKENS)}",
                     {"Balance": f"{self.balance:.2f}", "TradePct": f"{TRADE_PCT*100:.1f}%", "SL": f"{STOP_LOSS_PCT*100:.1f}%"})

    def hourly_report_due(self, now_oslo):
        if self.last_hour_sent is None: return True
        return (now_oslo - self.last_hour_sent) >= timedelta(hours=1)

    def daily_report_due(self, now_oslo):
        return (now_oslo.hour == 6) and (self.last_daily_date != now_oslo.date())

    def send_hourly(self):
        pnl = self.balance - self.initial_balance
        marker = "🟢" if self.balance > 1000 else "🔵"
        winrate_global = self.global_winrate()
        extra = {
            "Balance": f"{self.balance:.2f}",
            "PnL": f"{pnl:+.2f} ({(pnl/self.initial_balance)*100:+.2f}%)",
            "Winrate": f"{winrate_global:.1f}%",
            "OpenPos": ", ".join([f"{s}:{p['qty']:.6f}@{p['entry']:.2f}" for s, p in self.positions.items()]) or "None",
            "Trades": str(len(self.history)),
        }
        send_discord(f"{marker} Hourly report", extra)
        self.last_hour_sent = datetime.now(OSLO)

    def send_daily(self):
        # strategy snapshot
        snap = {k: f"w:{v['wins']} l:{v['losses']} pnl:{v['pnl']:.2f}" for k, v in self.stats.items()}
        marker = "🟢" if self.balance > 1000 else "🔵"
        extra = {
            "Balance": f"{self.balance:.2f}",
            "Winrate": f"{self.global_winrate():.1f}%",
            "ByStrategy": json.dumps(snap, ensure_ascii=False),
            "TradesToday": str(sum(1 for t in self.history if datetime.fromtimestamp(t['ts'], OSLO).date() == datetime.now(OSLO).date()))
        }
        send_discord(f"{marker} Daily report (06:00)", extra)
        self.last_daily_date = datetime.now(OSLO).date()

    def global_winrate(self):
        wins = sum(v["wins"] for v in self.stats.values())
        losses = sum(v["losses"] for v in self.stats.values())
        total = wins + losses
        return (wins / total * 100) if total else 0.0

    # --- Edge Score
    def edge_score(self, name):
        st = self.stats[name]
        trades = st["trades"]
        winrate = (st["wins"] / trades) if trades else 0.5  # prior
        pnl_pct = (st["pnl"] / self.initial_balance) if self.initial_balance else 0.0
        # weights: winrate 0.6, pnl 0.3, volume 0.1 (log scaled)
        vol = math.log10(trades + 1) / 2.0  # 0..~1
        score = 0.6 * winrate + 0.3 * (0.5 + pnl_pct) + 0.1 * vol
        return score  # ~0..1+

    def overall_edge(self):
        # mean of available strategy scores
        scores = [self.edge_score(n) for n in STRATEGIES.keys()]
        return sum(scores) / len(scores) if scores else 0.5

    # --- Trading
    def decide_signals(self, closes):
        votes = {}
        for name, fn in STRATEGIES.items():
            try:
                sig = fn(closes)
            except Exception:
                sig = None
            votes[name] = sig
        agree_true = sum(1 for v in votes.values() if v is True)
        agree_false = sum(1 for v in votes.values() if v is False)
        return votes, agree_true, agree_false

    def maybe_trade(self, symbol, closes):
        if not closes or len(closes) < 30:
            return
        price = closes[-1]
        votes, agree_true, agree_false = self.decide_signals(closes)
        # entry rule: need 4/5 bullish
        if agree_true >= 4 and symbol not in self.positions:
            # position sizing
            amount_usd = max(1.0, self.balance * TRADE_PCT)
            qty = amount_usd / price
            if qty <= 0: return
            self.positions[symbol] = {"qty": qty, "entry": price}
            self.balance -= amount_usd
            self.log_trade("BUY", symbol, price, qty, votes)
        # exit rules: SL or 4/5 bearish
        if symbol in self.positions:
            pos = self.positions[symbol]
            entry = pos["entry"]
            # stop-loss
            if price <= entry * (1 - STOP_LOSS_PCT):
                self.close_position(symbol, price, reason="SL")
                return
            # strong bearish agreement
            if agree_false >= 4:
                self.close_position(symbol, price, reason="BEAR")

    def close_position(self, symbol, price, reason="EXIT"):
        pos = self.positions.pop(symbol, None)
        if not pos: return
        proceeds = pos["qty"] * price
        cost = pos["qty"] * pos["entry"]
        pnl = proceeds - cost
        self.balance += proceeds
        # update simple global stats attribution: attribute result to ALL strategies that voted at last trade time
        last = next((t for t in reversed(self.history) if t["symbol"] == symbol and t["side"] == "BUY"), None)
        attributions = list(STRATEGIES.keys())
        if last and "votes" in last:
            attributions = [k for k, v in last["votes"].items() if isinstance(v, bool)]
        for name in attributions:
            st = self.stats[name]
            st["trades"] += 1
            if pnl >= 0:
                st["wins"] += 1
            else:
                st["losses"] += 1
            st["pnl"] += pnl
        marker = "🟢" if self.balance > 1000 else "🔵"
        self.history.append({
            "ts": time.time(),
            "symbol": symbol,
            "side": "SELL",
            "price": price,
            "qty": pos["qty"],
            "pnl": pnl,
            "reason": reason
        })
        send_discord(f"{marker} 🔴 SELL {symbol} at {price:.2f} | PnL {pnl:+.2f} | Reason: {reason}",
                     {"Balance": f"{self.balance:.2f}", "OverallEdge": f"{self.overall_edge():.3f}"})

    def log_trade(self, side, symbol, price, qty, votes=None):
        marker = "🟢" if self.balance > 1000 else "🔵"
        extra = {
            "Symbol": symbol,
            "Price": f"{price:.2f}",
            "Qty": f"{qty:.6f}",
            "Balance": f"{self.balance:.2f}",
            "OverallEdge": f"{self.overall_edge():.3f}",
            "Votes": json.dumps({k: v for k, v in (votes or {}).items()}, ensure_ascii=False),
        }
        txt = "🔵 BUY" if side == "BUY" else "🔴 SELL"
        send_discord(f"{marker} {txt} {symbol}", extra)
        self.history.append({
            "ts": time.time(),
            "symbol": symbol,
            "side": side,
            "price": price,
            "qty": qty,
            "votes": votes or {}
        })

    def run_once(self):
        for sym in TOKENS:
            closes = get_klines(sym, "1m", 120)
            self.maybe_trade(sym, closes)

    def loop(self):
        while True:
            try:
                self.run_once()
                now_oslo = datetime.now(OSLO)
                if self.hourly_report_due(now_oslo):
                    self.send_hourly()
                if self.daily_report_due(now_oslo):
                    self.send_daily()
            except Exception as e:
                send_discord(f"Error in loop: {e}", level="error")
            time.sleep(TICK_SECONDS)

bot = AtomicBot()

def _bg():
    bot.loop()

threading.Thread(target=_bg, daemon=True).start()

@app.get("/")
def root():
    pnl = bot.balance - bot.initial_balance
    return jsonify({
        "version": VERSION,
        "mode": MODE,
        "tokens": TOKENS,
        "balance": round(bot.balance, 2),
        "pnl": round(pnl, 2),
        "winrate": round(bot.global_winrate(), 2),
        "positions": bot.positions,
        "trades": len(bot.history)
    })

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.getenv("PORT", "8080")))