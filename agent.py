# =========================
# AtomicBot v7 - agent.py
# ÉN-FILS VERSJON (alt samlet)
# =========================

import os
import re
import time
from datetime import datetime, timezone

import requests
import bridge  # har commit_file() og append_line()

# --------- v7: metadata / konfig ----------
VERSION = "AtomicBot v7"
MODE = os.getenv("MODE", "demo").lower()  # demo | paper | live
TZ_LABEL = os.getenv("TZ", "Europe/Oslo")
DEMO_TRADE = os.getenv("DEMO_TRADE", "false").lower() in ("1", "true", "yes")  # valgfri test

# --------- Discord ----------
DISCORD_WEBHOOK = os.getenv("DISCORD_WEBHOOK", "").strip()

def _send_discord_raw(msg: str):
    if not DISCORD_WEBHOOK:
        return
    try:
        requests.post(DISCORD_WEBHOOK, json={"content": msg}, timeout=10)
    except Exception:
        pass

# Alle meldinger ender til slutt her via send_discord_v7()
def send_discord(msg: str):
    _send_discord_raw(msg)

# --------- Tid / stempel ----------
def _stamp_utc() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

def _now_local():
    return datetime.now().astimezone()  # viser TZ_LABEL i tekst

# --------- Safe wrapper ----------
def _safe(fn, *a, **kw):
    try:
        return fn(*a, **kw)
    except Exception:
        return None

# --------- Runtime KPI-er ----------
balance_start_of_day = None
current_balance = None
trades_today = 0
_last_report_date = None
_last_balance_seen = None  # fallback for PnL-emoji

# --------- GitHub logging ----------
def log_event_to_github(level: str, msg: str):
    _safe(bridge.append_line, "events.log", f"{_stamp_utc()} {level.upper()} {msg}")

def log_trade_to_github(side: str, symbol: str, qty: float, price: float, strat: str, balance: float):
    global trades_today, current_balance
    trades_today += 1
    current_balance = balance
    day  = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    path = f"trades/trades_{day}.csv"
    line = f"{_stamp_utc()},{side},{symbol},{qty:.8f},{price:.8f},{strat},{balance:.2f}"
    _safe(bridge.append_line, path, line)

def _fmt_money(val):
    try:
        return f"{float(val):.2f}"
    except Exception:
        return str(val)

def write_daily_report_to_github():
    day_local = _now_local().strftime("%Y-%m-%d")
    local_str = _now_local().strftime("%Y-%m-%d %H:%M")
    pnl = None
    if balance_start_of_day is not None and current_balance is not None:
        pnl = round(current_balance - balance_start_of_day, 2)

    md = [
        f"# {VERSION} – Daglig rapport",
        f"*Generert:* {local_str} ({TZ_LABEL})",
        f"*MODE:* `{MODE}`",
        "",
        "## Sammendrag",
        f"- Startbalanse: `${_fmt_money(balance_start_of_day) if balance_start_of_day is not None else '?'} `",
        f"- Sluttbalanse: `${_fmt_money(current_balance) if current_balance is not None else '?'} `",
        f"- Dagens PnL: `${_fmt_money(pnl) if pnl is not None else '?'} `",
        f"- Antall handler: `{trades_today}`",
        "",
        "## Rådata",
        "- Dagens handler ligger i `trades/` som CSV.",
    ]
    _safe(bridge.commit_file, f"reports/daily_report_{day_local}.md", "\n".join(md), message=f"Daily report {day_local}")

# --------- Mønstre ----------
BUYSELL_RE = re.compile(
    r'\[(?:STD|[A-Z\- ]+)\]\s*(BUY|SELL)\s+([A-Z]+USDT):\s*([0-9.]+)\s*@\s*\$([0-9.]+).*?strategy:\s*([A-Z]+).*?bal:\s*\$([0-9.]+)(?:.*?PnL:\s*([\-0-9.]+))?',
    re.I
)
DAILY_RE   = re.compile(r'AtomicBot .*?Super Edge .*?with daily JSON report!', re.I)

def _emoji_for_pnl(pnl_val: float) -> str:
    if pnl_val > 0:  return "🟢"
    if pnl_val < 0:  return "🔴"
    return "⚪"

# --------- v7 wrapper ----------
def send_discord_v7(msg: str):
    """
    - Parser BUY/SELL → logger til GitHub
    - SELL får PnL‑emoji (fra PnL: … om mulig, ellers balanse‑diff)
    - Trigger daglig rapport
    - Prefixer alle meldinger med [AtomicBot v7 | MODE]
    """
    global balance_start_of_day, current_balance, _last_balance_seen

    # 1) BUY/SELL parsing + logging
    try:
        m = BUYSELL_RE.search(msg or "")
        if m:
            side, sym, qty, price, strat, bal, pnl_cap = m.groups()
            qty   = float(qty); price = float(price); bal = float(bal)
            if balance_start_of_day is None:
                balance_start_of_day = bal
            log_trade_to_github(side.upper(), sym.upper(), qty, price, strat.upper(), bal)

            # PnL-emoji ved SELL
            if side.upper() == "SELL":
                pnl_val = None
                if pnl_cap is not None:
                    try: pnl_val = float(pnl_cap)
                    except: pnl_val = None
                if pnl_val is None and _last_balance_seen is not None:
                    pnl_val = bal - _last_balance_seen
                emj = _emoji_for_pnl(pnl_val if pnl_val is not None else 0.0)
                if "PnL:" in msg:
                    msg = re.sub(r'PnL:\s*([\-0-9.]+)', lambda mt: f"{emj} PnL: {mt.group(1)}", msg)
                else:
                    msg = f"{msg}   {emj}"

            _last_balance_seen = bal
    except Exception:
        pass

    # 2) Daglig rapport
    try:
        if DAILY_RE.search(msg or ""):
            write_daily_report_to_github()
            log_event_to_github("INFO", "Daily report pushed (auto)")
    except Exception:
        pass

    # 3) Prefix + send
    prefixed = f"[{VERSION} | {MODE.upper()}] {msg}"
    _send_discord_raw(prefixed)

# --------- BOOT / sanity commit ----------
log_event_to_github("BOOT", f"{VERSION} start MODE={MODE}")
_safe(bridge.commit_file, "bridge_test_live.txt", f"Bridge is alive - {_stamp_utc()}", message=f"Bridge test {_stamp_utc()}")

# --------- Schedulers ----------
_last_report_date = None
def _maybe_daily_report():
    global _last_report_date
    now_loc = _now_local()
    if now_loc.hour == 6 and now_loc.minute < 2:
        today = now_loc.date()
        if _last_report_date != today:
            write_daily_report_to_github()
            log_event_to_github("INFO", "Daily report pushed (06:00 timer)")
            _last_report_date = today

def _tick_demo_trades():
    # Kun hvis DEMO_TRADE=true (ellers stillhet)
    send_discord_v7("[STD] BUY BTCUSDT: 0.001 @ $50000 strategy: EMA bal: $1000")
    time.sleep(2)
    send_discord_v7("[STD] SELL BTCUSDT: 0.001 @ $51000 strategy: EMA bal: $1010 PnL: 10.00")

# --------- Main loop ----------
def main_loop():
    while True:
        if DEMO_TRADE:
            _tick_demo_trades()
        _maybe_daily_report()
        time.sleep(10)

if __name__ == "__main__":
    try:
        main_loop()
    except Exception as e:
        try:
            send_discord_v7(f"🔥 Kritisk feil: {type(e).__name__}: {e}")
        except Exception:
            pass
        log_event_to_github("ERROR", f"{type(e).__name__}: {e}")
        raise