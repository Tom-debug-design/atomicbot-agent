from collections import deque, defaultdict

class StrategyLearner:
    def __init__(self, window_size=20):
        self.window_size = window_size
        self.history = deque(maxlen=window_size)

    def log_trade(self, strategy, token, pnl):
        self.history.append((strategy, token, pnl))

    def get_weighted_combo(self):
        stats = defaultdict(list)
        weights = []
        n = len(self.history)
        # Vekt: siste handler teller mer
        for i, (strat, token, pnl) in enumerate(self.history):
            weight = 1 + i / n  # Siste trade får høyest vekt
            stats[(strat, token)].append(pnl * weight)
        if not stats:
            return None, None
        best_combo = max(stats.items(), key=lambda x: sum(x[1]) / len(x[1]))
        best_strategy, best_token = best_combo[0]
        return best_strategy, best_token
