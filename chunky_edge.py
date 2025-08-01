import random
import time
import datetime

TOKENS = [
    "BTCUSDT", "ETHUSDT", "SOLUSDT", "BNBUSDT", "XRPUSDT", "ADAUSDT",
    "DOGEUSDT", "AVAXUSDT", "LINKUSDT", "TRXUSDT"
]
START_BALANCE = 1000.0
CHUNKY_TRADE_SIZE = 0.03      # 3% av balanse per trade
CHUNKY_TP = 0.002             # 0.2% take profit
CHUNKY_SL = 0.002             # 0.2% stop loss
CHUNKY_SLEEP = 10             # sekunder mellom loops
MAX_DRAWDOWN = 0.6            # 60% av start-balanse = restart sim
DISCORD_WEBHOOK = https://discord.com/api/webhooks/1391855933071560735/uH6LYuqM6uHLet9KhsgCS89fQikhyuPRJmjhqmtESMhAlu3LxDfUrVggwxzSGyscEtiN

balance = START_BALANCE
chunky_trades = []
total_trades = 0

def send_discord(msg):
    # Fjern print for kun DC, legg inn requests hvis du vil ha ekte webhook
    print(msg)
    # import requests
    # try:
    #     requests.post(DISCORD_WEBHOOK, json={"content": msg})
    # except Exception as e:
    #     print("DC error", e)

def get_price(symbol):
    # Fake-priser i kjent range (juster som du vil)
    base = {
        "BTCUSDT": 30000, "ETHUSDT": 1700, "SOLUSDT": 20, "BNBUSDT": 250, "XRPUSDT": 0.6,
        "ADAUSDT": 0.4, "DOGEUSDT": 0.07, "AVAXUSDT": 10, "LINKUSDT": 6, "TRXUSDT": 0.07
    }
    return round(base[symbol] * random.uniform(0.98, 1.02), 2)

def chunky_signal(symbol):
    # Random buy/sell hver gang (full chunky mode)
    return random.choice(["BUY", "SELL"])

def chunky_trade(symbol, action, price):
    global balance, chunky_trades, total_trades
    trade_size = balance * CHUNKY_TRADE_SIZE
    result = random.uniform(-CHUNKY_SL, CHUNKY_TP)
    pnl = trade_size * result
    balance += pnl
    chunky_trades.append(pnl)
    total_trades += 1
    send_discord(f"CHUNKY: {action} {symbol} | Size: {trade_size:.2f} | PnL: {pnl:.2f} | Bal: {balance:.2f}")

    # Oppsummer chunky PnL hver 10. trade
    if total_trades % 10 == 0:
        send_discord(f"CHUNKY SUMMARY: Trades {total_trades} | Last 10 PnL: {sum(chunky_trades[-10:]):.2f} | Bal: {balance:.2f}")
    # Reset hvis drawdown
    if balance < START_BALANCE * MAX_DRAWDOWN:
        send_discord("CHUNKY: ❌ No edge detected – resetting simulation!\n")
        balance = START_BALANCE
        chunky_trades = []

def now():
    return datetime.datetime.now(datetime.timezone.utc).strftime('%Y-%m-%d %H:%M:%S')

def chunky_main():
    send_discord(f"🤖 CHUNKY EDGE v1.0 starter – {now()} – LET’S SCALP!")
    while True:
        for symbol in TOKENS:
            try:
                action = chunky_signal(symbol)
                price = get_price(symbol)
                chunky_trade(symbol, action, price)
                time.sleep(1)
            except Exception as e:
                send_discord(f"CHUNKY ERROR {symbol}: {e}")
        time.sleep(CHUNKY_SLEEP)

if __name__ == "__main__":
    chunky_main()
