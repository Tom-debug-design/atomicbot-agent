import os
import re
import sys
import time
import traceback
from datetime import datetime, timezone

import bridge  # må ligge i rotmappa
import requests

# --- v7 metadata / konfig ---
VERSION = "AtomicBot v7"
MODE = os.getenv("MODE", "demo").lower()  # demo | paper | live
TZ   = os.getenv("TZ", "Europe/Oslo")

# --- GitHub logging helpers ---
def _stamp_utc() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

def _safe(fn, *a, **kw):
    try:
        return fn(*a, **kw)
    except Exception:
        return None

def log_event_to_github(level: str, msg: str):
    _safe(bridge.append_line, "events.log", f"{_stamp_utc()} {level.upper()} {msg}")

def log_trade_to_github(side: str, symbol: str, qty: float, price: float, strat: str, balance: float):
    day  = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    path = f"trades/trades_{day}.csv"
    line = f"{_stamp_utc()},{side},{symbol},{qty:.8f},{price:.8f},{strat},{balance:.2f}"
    _safe(bridge.append_line, path, line)

def write_daily_report_to_github():
    local = datetime.now().astimezone().strftime("%Y-%m-%d %H:%M")
    day   = datetime.now().astimezone().strftime("%Y-%m-%d")
    md = [
        f"# {VERSION} – Daglig rapport",
        f"*Generert:* {local} ({TZ})",
        f"*MODE:* `{MODE}`",
        "",
        "## Sammendrag",
        "- (KPI-er kobles inn senere)",
        "",
        "## Rådata",
        "- Dagens handler ligger i `trades/` som CSV.",
    ]
    _safe(bridge.commit_file, f"reports/daily_report_{day}.md", "\n".join(md), message=f"Daily report {day}")

# --- Discord send-funksjon ---
DISCORD_WEBHOOK = os.getenv("DISCORD_WEBHOOK", "").strip()

def send_discord(msg: str):
    if not DISCORD_WEBHOOK:
        return
    try:
        requests.post(DISCORD_WEBHOOK, json={"content": msg}, timeout=10)
    except Exception:
        pass

# --- Mønstre for å fange opp meldinger ---
BUYSELL_RE = re.compile(
    r'\[(?:STD|[A-Z\- ]+)\]\s*(BUY|SELL)\s+([A-Z]+USDT):\s*([0-9.]+)\s*@\s*\$([0-9.]+).*?strategy:\s*([A-Z]+).*?bal:\s*\$([0-9.]+)',
    re.I
)
DAILY_RE   = re.compile(r'AtomicBot .*?Super Edge .*?with daily JSON report!', re.I)

# --- Pakk inn Discord-sending for logging ---
def send_discord_v7(msg: str):
    try:
        m = BUYSELL_RE.search(msg or "")
        if m:
            side, sym, qty, price, strat, bal = m.groups()
            log_trade_to_github(side.upper(), sym.upper(), float(qty), float(price), strat.upper(), float(bal))
    except Exception:
        pass

    try:
        if DAILY_RE.search(msg or ""):
            write_daily_report_to_github()
            log_event_to_github("INFO", "Daily report pushed (auto)")
    except Exception:
        pass

    prefixed = f"[{VERSION} | {MODE.upper()}] {msg}"
    send_discord(prefixed)

# --- BOOT event ---
log_event_to_github("BOOT", f"{VERSION} start MODE={MODE}")
_safe(bridge.commit_file, "bridge_test_live.txt", f"Bridge is alive - {_stamp_utc()}", message=f"Bridge test {_stamp_utc()}")

# --- Din eksisterende main_loop ---
def main_loop():
    while True:
        # Her skal du ha din strategi-loop / tick
        # Eksempel dummy trade for testing:
        send_discord_v7("[STD] BUY BTCUSDT: 0.001 @ $50000 strategy: EMA bal: $1000")
        time.sleep(5)
        send_discord_v7("[STD] SELL BTCUSDT: 0.001 @ $51000 strategy: EMA bal: $1010")
        time.sleep(10)

        # Daglig rapport trigger (test)
        send_discord_v7("AtomicBot Super Edge ... with daily JSON report!")
        time.sleep(60)

if __name__ == "__main__":
    try:
        main_loop()
    except Exception as e:
        send_discord_v7(f"🔥 Kritisk feil: {type(e).__name__}: {e}")
        log_event_to_github("ERROR", f"{type(e).__name__}: {e}")
        raise