# --- Strategy/Edge Emergency Upgrade ---
consecutive_losses = 0
last_strategy = None
cooldown = 0
switches_on_row = 0

def should_switch_strategy(trade_history, current_strategy, learner, cooldown, switches_on_row):
    global consecutive_losses, last_strategy

    # 1. Tell tap på rad i nåværende strategi
    recent_trades = [t for t in reversed(trade_history) if t["strategy"] == current_strategy]
    losses = 0
    for t in recent_trades:
        if t["pnl"] < 0:
            losses += 1
        else:
            break
    consecutive_losses = losses

    # 2. Force switch hvis strategi PnL < 0 siste 50 trades
    recent_50 = [t for t in trade_history if t["strategy"] == current_strategy][-50:]
    if recent_50 and sum(t["pnl"] for t in recent_50) < 0:
        send_discord(f"🔁 [EDGE] Forcing strategy switch: {current_strategy} PnL < 0 last 50 trades")
        return True

    # 3. Bytt strategi hvis 2 tap på rad
    if consecutive_losses >= 2:
        send_discord(f"🔁 [EDGE] Switching strategy: {current_strategy} has {consecutive_losses} losses in a row")
        return True

    # 4. Cooldown for byttespam
    if switches_on_row >= 2:
        cooldown = 5  # trades pause
        send_discord("⏸️ [EDGE] Cooldown triggered, pausing strategy switch for 5 trades")
        return False

    return False

# ...i trading-loopen (eksisterende loop):
if cooldown > 0:
    cooldown -= 1
else:
    if should_switch_strategy(trade_history, current_strategy, learner, cooldown, switches_on_row):
        switches_on_row += 1
        # Bytt til beste strategi (fra learner eller top-PnL)
        best_strategy = learner.get_best_strategy()
        send_discord(f"🔄 [EDGE] Changing to {best_strategy}")
        current_strategy = best_strategy
        last_strategy = best_strategy
    else:
        switches_on_row = 0

# Husk å resette switches_on_row når cooldown er ferdig!