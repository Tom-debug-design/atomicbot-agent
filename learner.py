from collections import deque, defaultdict
import numpy as np

class StrategyLearner:
    def __init__(self, base_window=20, min_window=10, max_window=30):
        self.base_window = base_window
        self.min_window = min_window
        self.max_window = max_window
        self.window_size = base_window
        self.history = deque(maxlen=self.max_window)  # lagrer alle siste trades

    def update_window(self, volatility):
        # Dynamisk window: mindre ved høy volatilitet, større ved lav volatilitet
        if volatility > 0.03:
            self.window_size = self.min_window
        elif volatility < 0.01:
            self.window_size = self.max_window
        else:
            self.window_size = self.base_window

    def log_trade(self, strategy, token, pnl):
        self.history.append((strategy, token, pnl))

    def get_weighted_edge_combo(self):
        if len(self.history) == 0:
            return None, None

        # Bruk siste window_size trades, og vekter de ferskeste høyest
        window_trades = list(self.history)[-self.window_size:]
        n = len(window_trades)
        stats = defaultdict(list)
        weights = np.linspace(0.3, 1, n)  # Gir de siste høyest vekt
        for i, (strategy, token, pnl) in enumerate(window_trades):
            stats[(strategy, token)].append(pnl * weights[i])

        avg_pnls = {k: np.sum(v)/len(v) for k, v in stats.items()}
        if not avg_pnls:
            return None, None
        best_combo = max(avg_pnls.items(), key=lambda x: x[1])[0]
        return best_combo