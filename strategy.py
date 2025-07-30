
import random

def rsi_strategy(price): return random.choice([True, False])
def ema_strategy(price): return random.choice([True, False])
def sma_strategy(price): return random.choice([True, False])

def get_signal(strategy, price):
    if strategy == "RSI":
        return rsi_strategy(price)
    if strategy == "EMA":
        return ema_strategy(price)
    if strategy == "SMA":
        return sma_strategy(price)
    return random.choice([True, False])
