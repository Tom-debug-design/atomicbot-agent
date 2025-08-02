# learner.py (Chunky Edge Steg 3 – Dynamisk window og vekting)

from collections import deque, defaultdict
import numpy as np

class StrategyLearner:
    def __init__(self, base_window=20, min_window=10, max_window=40):
        self.base_window = base_window
        self.min_window = min_window
        self.max_window = max_window
        self.history = deque(maxlen=self.max_window)  # holder på inntil max_window

    def log_trade(self, strategy, token, pnl, volatility=1.0):
        # volatility kan komme fra main (f.eks. stddev siste X handler)
        self.history.append((strategy, token, pnl, volatility))

    def get_dynamic_window(self, current_volatility):
        # Enkel logikk: høy volatilitet => kort window, lav volatilitet => lang window
        if current_volatility > 2.0:
            return self.min_window
        elif current_volatility < 0.8:
            return self.max_window
        else:
            # Lineær interpolering mellom min og max
            span = self.max_window - self.min_window
            adj = int(self.max_window - (current_volatility - 0.8) / (2.0 - 0.8) * span)
            return max(self.min_window, min(self.max_window, adj))

    def get_weighted_best_combo(self, volatility=1.0):
        window = self.get_dynamic_window(volatility)
        data = list(self.history)[-window:] if window <= len(self.history) else list(self.history)
        if not data:
            return None, None
        stats = defaultdict(list)
        n = len(data)
        for i, (strategy, token, pnl, _) in enumerate(data):
            # Eksponentielt vekt: nyere handler teller mer
            weight = np.exp(i / n)  # eller: weight = 0.5 + 0.5 * (i / n)
            stats[(strategy, token)].append(pnl * weight)
        # Finn combo med høyest snitt (vektet)
        best_combo = max(stats.items(), key=lambda x: np.mean(x[1]))
        best_strategy, best_token = best_combo[0]
        return best_strategy, best_token

    def get_top_n_combos(self, n=5, volatility=1.0):
        window = self.get_dynamic_window(volatility)
        data = list(self.history)[-window:] if window <= len(self.history) else list(self.history)
        if not data:
            return []
        stats = defaultdict(list)
        n_data = len(data)
        for i, (strategy, token, pnl, _) in enumerate(data):
            weight = np.exp(i / n_data)
            stats[(strategy, token)].append(pnl * weight)
        # Returner topp n etter snitt
        ranked = sorted(stats.items(), key=lambda x: np.mean(x[1]), reverse=True)
        return [(k[0], k[1], np.mean(v)) for k, v in ranked[:n]]
