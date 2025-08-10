# =========================
# AtomicBot v7 - agent.py
# ÉN-FILS VERSJON (alt samlet)
# =========================

import os
import re
import sys
import time
import json
import traceback
from datetime import datetime, timezone, timedelta

import requests
import bridge  # må ligge i rotmappa (har commit_file / append_line)

# --------- v7: metadata / konfig ----------
VERSION = "AtomicBot v7"
MODE = os.getenv("MODE", "demo").lower()  # demo | paper | live
TZ_LABEL = os.getenv("TZ", "Europe/Oslo")

# DEMO: Sett DEMO_TRADE=true for å lage dummy-trades automatisk (default: false = ingen spam)
DEMO_TRADE = os.getenv("DEMO_TRADE", "false").lower() in ("1", "true", "yes")

# --------- Discord ----------
DISCORD_WEBHOOK = os.getenv("DISCORD_WEBHOOK", "").strip()

def _send_discord_raw(msg: str):
    if not DISCORD_WEBHOOK:
        return
    try:
        requests.post(DISCORD_WEBHOOK, json={"content": msg}, timeout=10)
    except Exception:
        pass

def send_discord(msg: str):
    """Alle meldinger går via denne – v7 prefix legges på i wrapper lenger ned."""
    _send_discord_raw(msg)

# --------- Tid / stempel ----------
def _stamp_utc() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

def _now_local():
    # Bruk systemens lokale tz; TZ_LABEL vises i tekst
    return datetime.now().astimezone()

# --------- Sikker IO (ikke stopp trading ved GitHub-feil) ----------
def _safe(fn, *a, **kw):
    try:
        return fn(*a, **kw)
    except Exception:
        return None

# --------- Runtime KPI-er ----------
balance_start_of_day = None
current_balance = None
trades_today = 0
_last_report_date = None  # for 06:00-daglig rapport
_last_balance_seen = None # for fallback PnL hvis ikke oppgitt i meldingen

# --------- GitHub logging helpers ----------
def log_event_to_github(level: str, msg: str):
    _safe(bridge.append_line, "events.log", f"{_stamp_utc()} {level.upper()} {msg}")

def log_trade_to_github(side: str, symbol: str, qty: float, price: float, strat: str, balance: float):
    global trades_today, current_balance
    trades_today += 1
    current_balance = balance
    day  = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    path = f"trades/trades_{day}.csv"
    header = "timestamp,side,symbol,qty,price,strategy,balance"
    # Sørg for at første append lager en fil som i praksis har header (kun om filen ikke finnes enda)
    existing = _safe(bridge.append_line, path, header) if trades_today == 1 else True  # harmless hvis finnes
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

# --------- Mønstre for å fange opp meldinger ----------
# Støtter både meldinger uten PnL og med "PnL: <tall>"
BUYSELL_RE = re.compile(
    r'\[(?:STD|[A-Z\- ]+)\]\s*(BUY|SELL)\s+([A-Z]+USDT):\s*([0-9.]+)\s*@\s*\$([0-9.]+).*?strategy:\s*([A-Z]+).*?bal:\s*\$([0-9.]+)(?:.*?PnL:\s*([\-0-9.]+))?',
    re.I
)
DAILY_RE   = re.compile(r'AtomicBot .*?Super Edge .*?with daily JSON report!', re.I)

def _emoji_for_pnl(pnl_val: float) -> str:
    if pnl_val > 0:  return "🟢"
    if pnl_val < 0:  return "🔴"
    return "⚪"

# --------- v7 wrapper rundt Discord-sending ----------
def send_discord_v7(msg: str):
    """
    - Logger BUY/SELL til GitHub (CSV)
    - Legger til PnL-emoji på SELL (henter PnL fra meldingen hvis mulig, ellers fallback fra balanse-diff)
    - Trigger daglig rapport når daily-signalet dukker opp
    - Prefixer alle meldinger med [AtomicBot v7 | MODE]
    """
    global balance_start_of_day, current_balance, _last_balance_seen

    # 1) Prøv å tolke BUY/SELL-linje og logg til GitHub
    try:
        m = BUYSELL_RE.search(msg or "")
        if m:
            side, sym, qty, price, strat, bal, pnl_captured = m.groups()
            qty   = float(qty)
            price = float(price)
            bal   = float(bal)
            if balance_start_of_day is None:
                balance_start_of_day = bal
            # Logg trade til GitHub
            log_trade_to_github(side.upper(), sym.upper(), qty, price, strat.upper(), bal)

            # 2) PnL-emoji på SELL
            if side.upper() == "SELL":
                pnl_val = None
                if pnl_captured is not None:
                    try: pnl_val = float(pnl_captured)
                    except: pnl_val = None
                if pnl_val is None and _last_balance_seen is not None:
                    # Fallback: balanse-diff til emoji (ikke perfekt, men nyttig)
                    pnl_val = bal - _last_balance_seen
                emj = _emoji_for_pnl(pnl_val if pnl_val is not None else 0.0)
                # Hvis meldingen allerede har "PnL: <...>", sett emoji foran; ellers legg til på slutten.
                if "PnL:" in msg:
                    msg = re.sub(r'PnL:\s*([\-0-9.]+)', lambda mt: f"{emj} PnL: {mt.group(1)}", msg)
                else:
                    msg = f"{msg}   {emj}"

            _last_balance_seen = bal
    except Exception:
        pass

    # 3) Daglig rapport-trigg
    try:
        if DAILY_RE.search(msg or ""):
            write_daily_report_to_github()
            log_event_to_github("INFO", "Daily report pushed (auto)")
    except Exception:
        pass

    # 4) Prefix alle meldinger med versjon/mode
    prefixed = f"[{VERSION} | {MODE.upper()}] {msg}"
    _send_discord_raw(prefixed)

# --------- BOOT / sanity commit ----------
log_event_to_github("BOOT", f"{VERSION} start MODE={MODE}")
_safe(bridge.commit_file, "bridge_test_live.txt", f"Bridge is alive - {_stamp_utc()}", message=f"Bridge test {_stamp_utc()}")

# --------- Hovedloop ----------
def _tick_demo_trades():
    """Liten demo som lager trades hvis DEMO_TRADE=true (for rask verifisering)."""
    # BUY
    send_discord_v7("[STD] BUY BTCUSDT: 0.001 @ $50000 strategy: EMA bal: $1000")
    time.sleep(2)
    # SELL med PnL i meldingen (for å teste emoji)
    send_discord_v7("[STD] SELL BTCUSDT: 0.001 @ $51000 strategy: EMA bal: $1010 PnL: 10.00")

def _maybe_daily_report():
    """Kjør daglig rapport kl 06:00 lokal tid (Europe/Oslo oppgitt i tekst)."""
    global _last_report_date
    now_loc = _now_local()
    # Trigger kl 06:00 - 06:01 og kun én gang per dag
    if now_loc.hour == 6 and now_loc.minute < 2:
        today = now_loc.date()
        if _last_report_date != today:
            write_daily_report_to_github()
            log_event_to_github("INFO", "Daily report pushed (06:00 timer)")
            _last_report_date = today

def main_loop():
    # Her legger du strategi-loop senere. Nå: lettvekts scheduler + (valgfri) demo-trades.
    while True:
        if DEMO_TRADE:
            _tick_demo_trades()
        _maybe_daily_report()
        time.sleep(10)

# --------- Entrypoint ----------
if __name__ == "__main__":
    try:
        main_loop()
    except Exception as e:
        # rapportér alvorlig feil, men la prosessen feile (Railway restarter typisk)
        try:
            send_discord_v7(f"🔥 Kritisk feil: {type(e).__name__}: {e}")
        except Exception:
            pass
        log_event_to_github("ERROR", f"{type(e).__name__}: {e}")
        raise