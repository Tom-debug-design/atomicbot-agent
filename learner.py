# learner.py (Full chunky edge AI - strategi og token)

from collections import deque, defaultdict

class StrategyLearner:
    def __init__(self, window_size=20):
        self.window_size = window_size
        self.history = deque(maxlen=window_size)  # [(strategy, token, pnl, timestamp)]
    
    def log_trade(self, strategy, token, pnl, timestamp=None):
        # Logg hver handel
        self.history.append((strategy, token, pnl, timestamp))
    
    def get_best_combo(self):
        # Finn strategi-token med høyest snitt-PnL siste window
        stats = defaultdict(list)
        for strat, token, pnl, _ in self.history:
            stats[(strat, token)].append(pnl)
        if not stats:
            return None, None
        best_combo = max(stats.items(), key=lambda x: sum(x[1])/len(x[1]))
        best_strategy, best_token = best_combo[0]
        return best_strategy, best_token

    def get_top_n_combos(self, n=5):
        # Returner de n beste strategi-token-kombinasjonene
        stats = defaultdict(list)
        for strat, token, pnl, _ in self.history:
            stats[(strat, token)].append(pnl)
        ranked = sorted(stats.items(), key=lambda x: sum(x[1])/len(x[1]), reverse=True)
        return [combo for combo, _ in ranked[:n]]

    def get_stats(self):
        # For rapport: alle komboer og deres snitt
        stats = defaultdict(list)
        for strat, token, pnl, _ in self.history:
            stats[(strat, token)].append(pnl)
        return {k: sum(v)/len(v) for k, v in stats.items()}

    def get_last_n_trades(self, n=20):
        return list(self.history)[-n:]

# Eksempel på bruk:
# learner = StrategyLearner(window_size=20)
# learner.log_trade("EMA", "BTCUSDT", 1.3)
# print(learner.get_best_combo())
# print(learner.get_top_n_combos(n=5))
