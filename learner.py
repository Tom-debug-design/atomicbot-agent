
import json
import random
import os

STATS_FILE = "strategy_stats.json"
GOAL_FILE = "goal.json"
STRATEGIES = ["RSI", "EMA", "SMA", "Random"]
TOKENS = ["BTCUSDT", "ETHUSDT", "SOLUSDT", "ADAUSDT", "BNBUSDT", "XRPUSDT", "AVAXUSDT", "MATICUSDT"]

def load_stats():
    if not os.path.exists(STATS_FILE):
        return {"strategy": {}, "token": {}, "history": []}
    with open(STATS_FILE, "r") as f:
        return json.load(f)

def save_stats(stats):
    with open(STATS_FILE, "w") as f:
        json.dump(stats, f, indent=2)

def log_trade_result(token, side, price, qty, amount, pnl, pnl_percent, strategy, timestamp):
    stats = load_stats()
    sdata = stats.setdefault("strategy", {}).setdefault(strategy, {"trades": 0, "pnl": 0})
    tdata = stats.setdefault("token", {}).setdefault(token, {"trades": 0, "pnl": 0})
    sdata["trades"] += 1
    sdata["pnl"] += pnl
    tdata["trades"] += 1
    tdata["pnl"] += pnl
    stats.setdefault("history", []).append({
        "token": token, "side": side, "price": price, "qty": qty,
        "amount": amount, "pnl": pnl, "pnl_percent": pnl_percent,
        "strategy": strategy, "timestamp": timestamp
    })
    save_stats(stats)

def select_strategy(category="strategy", available=None):
    stats = load_stats()
    items = STRATEGIES if category == "strategy" else (available or TOKENS)
    data = stats.get(category, {})
    if data:
        sorted_items = sorted(data.items(), key=lambda x: x[1].get("pnl", 0), reverse=True)
        return sorted_items[0][0]
    return random.choice(items)

def get_daily_stats():
    stats = load_stats()
    trades = [h for h in stats.get("history", []) if h["timestamp"].startswith(str(get_today()))]
    pnl = sum([h["pnl"] for h in trades])
    wins = len([h for h in trades if h["pnl"] > 0])
    total = len(trades)
    pnl_percent = sum([h["pnl_percent"] for h in trades]) if trades else 0
    best_strategy = max(stats.get("strategy", {}).items(), key=lambda x: x[1].get("pnl",0), default=("None",))[0]
    winrate = round((wins / total) * 100, 1) if total else 0
    goal, streak = get_goal("value"), get_streak()
    return {
        "trades": total,
        "pnl": pnl,
        "pnl_percent": pnl_percent,
        "winrate": winrate,
        "best_strategy": best_strategy,
        "goal": goal,
        "streak": streak
    }

def get_today():
    from datetime import datetime
    return datetime.now().strftime("%Y-%m-%d")

def update_goal(pnl, next_goal=False):
    state = load_goal()
    if next_goal:
        state["streak"] += 1
        state["goal"] += state["goal_incr"]
        state["current"] = 0
        state["reached"] = False
    else:
        state["current"] += pnl or 0
        if state["current"] >= state["goal"]:
            state["reached"] = True
    save_goal(state)

def get_goal(which="value"):
    state = load_goal()
    if which == "value":
        return state.get("goal", 50)
    if which == "reached":
        return state.get("reached", False)
    return state

def reset_goal():
    save_goal({
        "goal": 50,
        "goal_incr": 25,
        "current": 0,
        "reached": False,
        "streak": 0
    })

def load_goal():
    if not os.path.exists(GOAL_FILE):
        reset_goal()
    with open(GOAL_FILE, "r") as f:
        return json.load(f)

def save_goal(state):
    with open(GOAL_FILE, "w") as f:
        json.dump(state, f)

def get_streak():
    return load_goal().get("streak", 0)
