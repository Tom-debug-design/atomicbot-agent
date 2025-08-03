from collections import deque, defaultdict
import numpy as np

class ChunkyEdgeLearner:
    def __init__(self, ban_threshold=-5, ban_window=20, boost_window=20):
        self.ban_window = ban_window
        self.boost_window = boost_window
        self.ban_threshold = ban_threshold
        self.history = deque(maxlen=max(self.ban_window, self.boost_window))
        self.banlist = set()
        self.whitelist = set()

    def log_trade(self, strategy, token, pnl):
        self.history.append((strategy, token, pnl))
        self.update_lists()

    def update_lists(self):
        # Telle PnL siste X trades for alle combos
        stats = defaultdict(list)
        for strat, token, pnl in self.history:
            stats[(strat, token)].append(pnl)
        # Oppdater banlist
        for (strat, token), pnl_list in stats.items():
            if len(pnl_list) >= self.ban_window and sum(pnl_list[-self.ban_window:]) < self.ban_threshold:
                self.banlist.add((strat, token))
            else:
                self.banlist.discard((strat, token))
        # Oppdater whitelist (boosted edge: de beste)
        avg_pnls = {k: np.mean(v[-self.boost_window:]) for k,v in stats.items() if len(v) >= self.boost_window}
        if avg_pnls:
            best = sorted(avg_pnls, key=avg_pnls.get, reverse=True)[:3]
            self.whitelist = set(best)

    def get_suggested_combo(self):
        # Velg først fra whitelist, ellers random av de ikke bannede
        pool = list(self.whitelist) or [k for k in {(strat, token) for strat, token, _ in self.history} if k not in self.banlist]
        if pool:
            return pool[np.random.randint(len(pool))]
        return None

    def get_lists(self):
        return {
            "banlist": list(self.banlist),
            "whitelist": list(self.whitelist)
        }