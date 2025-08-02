# learner.py (Full chunky edge AI – strategi+token, vektede topp 5)

from collections import deque, defaultdict

class StrategyLearner:
    def __init__(self, window_size=20):
        self.window_size = window_size
        self.history = deque(maxlen=window_size)
    
    def log_trade(self, strategy, token, pnl, timestamp=None):
        # Logger hver trade som (strategi, token, pnl, timestamp)
        self.history.append((strategy, token, pnl, timestamp))
    
    def get_best_combo(self):
        # Returnerer strategi-token med høyest snitt-pnl (siste N handler)
        stats = defaultdict(list)
        for strat, token, pnl, _ in self.history:
            stats[(strat, token)].append(pnl)
        if not stats:
            return None, None
        best_combo = max(stats.items(), key=lambda x: sum(x[1]) / len(x[1]))
        best_strategy, best_token = best_combo[0]
        return best_strategy, best_token

    def get_top_n_combos(self, n=5):
        # Returnerer de N beste strategi-token komboene (uten vekting)
        stats = defaultdict(list)
        for strat, token, pnl, _ in self.history:
            stats[(strat, token)].append(pnl)
        if not stats:
            return []
        scores = {k: sum(v) / len(v) for k, v in stats.items()}
        best = sorted(scores.items(), key=lambda x: x[1], reverse=True)[:n]
        # Returnerer liste av tuples: ((strategi, token), snitt-pnl)
        return best

    def get_weighted_top_n_combos(self, n=5, recent_weight=3, recent_n=5):
        # Returnerer de N beste strategi-token komboene, vekter siste recent_n ekstra
        stats = defaultdict(list)
        hist = list(self.history)
        for i, (strat, token, pnl, _) in enumerate(hist):
            weight = recent_weight if i >= len(hist) - recent_n else 1
            stats[(strat, token)] += [pnl] * weight
        if not stats:
            return []
        scores = {k: sum(v) / len(v) for k, v in stats.items()}
        best = sorted(scores.items(), key=lambda x: x[1], reverse=True)[:n]
        return best
