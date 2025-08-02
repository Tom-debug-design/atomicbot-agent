# strategy_learner.py (full chunky AI)

from collections import deque

class StrategyLearner:
    def __init__(self, window_size=20):
        self.window_size = window_size
        self.history = deque(maxlen=window_size)  # (strategy, PnL)
        self.stats = {}

    def log_trade(self, strategy, pnl):
        self.history.append((strategy, pnl))
        self.stats = {}
        for strat, trade_pnl in self.history:
            self.stats.setdefault(strat, []).append(trade_pnl)

    def get_best_strategy(self):
        if not self.stats:
            return None
        strat_avgs = {s: sum(p)/len(p) for s, p in self.stats.items()}
        return max(strat_avgs, key=strat_avgs.get)

    def get_current_stats(self):
        return {s: round(sum(p)/len(p), 3) for s, p in self.stats.items()}


# ---- EKSEMPEL PÅ BRUK (legg i main.py, eller der du styrer handler) ----

# Import
from strategy_learner import StrategyLearner

# Opprett learner én gang ved oppstart
learner = StrategyLearner(window_size=20)

# --- I loopen, når trade skjer:
# Si at du har variablene 'strategy' og 'pnl' etter hver handel:

learner.log_trade(strategy, pnl)   # Logger strategien og PnL

# For neste trade – henter beste strategi ut fra siste 20 handler:
best_strat = learner.get_best_strategy()
if best_strat:
    strategy = best_strat
else:
    strategy = "RANDOM"    # Fallback første runde

# Hvis du vil logge til Discord (eller lokalt), bruk:
stats = learner.get_current_stats()
print(f"[CHUNKY-AI][EdgeStats] Last 20 trades: {stats} | Beste nå: {best_strat}")

# --- ferdig ---
