
import random

def get_signal():
    symbols = ['BTCUSDT', 'ETHUSDT', 'SOLUSDT']
    symbol = random.choice(symbols)
    price = random.uniform(100, 50000)
    action = random.choice(["BUY", "SELL", "HOLD"])
    return symbol, price, action
