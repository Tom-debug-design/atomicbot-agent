
import time, requests, os
from strategies import get_signal

DISCORD_WEBHOOK = os.getenv('DISCORD_WEBHOOK')

def discord_message(msg):
    requests.post(DISCORD_WEBHOOK, json={"content": msg})

def heartbeat():
    discord_message("💚 AtomicBot agent is alive.")

def send_trade(action, symbol, price, qty, pnl):
    emoji = "🔵 BUY" if action == "BUY" else "🔴 SELL"
    msg = f"{emoji}: {symbol} at ${price:.2f} | Amount: ${qty:.2f} | PnL: {pnl:.2f}%"
    discord_message(msg)

def hourly_report(trades):
    total_trades = len(trades)
    total_pnl = sum([trade['pnl'] for trade in trades])
    msg = f"📊 Hourly Report:\nTotal Trades: {total_trades}\nTotal PnL: {total_pnl:.2f}%"
    discord_message(msg)

def main_loop():
    trades = []
    last_hour = time.time()
    while True:
        heartbeat()
        
        symbol, price, action = get_signal()
        if action != "HOLD":
            qty = 50
            pnl = (price * 0.05) if action == "BUY" else -(price * 0.05)
            trades.append({"symbol": symbol, "pnl": pnl})
            send_trade(action, symbol, price, qty, pnl)
        
        if time.time() - last_hour >= 3600:
            hourly_report(trades)
            trades = []
            last_hour = time.time()
        
        time.sleep(60)

if __name__ == "__main__":
    main_loop()
