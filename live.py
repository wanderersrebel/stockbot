"""Live PAPER trader (stdlib only). Uses Alpaca paper API for real order execution.

Reuses the validated config_day.py + strategy_intraday.py. For each symbol it
computes the EMA+RSI signal and, if it differs from the current Alpaca
position state, submits a paper market order. Sends Telegram alerts.

SAFETY:
- PAPER ONLY. Uses paper-api.alpaca.markets. No real money.
- Position size = POSITION_PCT of account equity per symbol.
- Whole-share market orders (Alpaca supports fractional; we use integer qty).
- If Alpaca keys are blank, falls back to the local PaperAccount simulator.

Run:
  python live.py            live loop (one pass per SCAN_INTERVAL_SECONDS)
  python live.py --once     one pass then exit
  python live.py --rank     print live opportunity ranking + weighted allocation
  python live.py --train    re-tune PER_ASSET now

Positions are sized by opportunity strength (strongest signal gets the biggest
slice of the POSITION_PCT budget) via rank.py.
"""
import sys
import time

from config_day import (UNIVERSE, TIMEFRAME, HISTORY_RANGE, PER_ASSET,
                        EMA_FAST, EMA_SLOW, RSI_PERIOD, RSI_BUY_MAX,
                        RSI_SELL_MIN, POSITION_PCT, SCAN_INTERVAL_SECONDS,
                        MAX_DAILY_LOSS_PCT, FEE_STOCK)
from data_feed import get_history
import strategy_intraday as si
from notifier import notify

try:
    from secrets import APCA_API_KEY_ID, APCA_API_SECRET_KEY
    from alpaca import (get_account, get_positions, submit_order,
                        close_position, connected, _req)
    USE_BROKER = bool(APCA_API_KEY_ID and APCA_API_SECRET_KEY and connected())

    def market_open():
        try:
            d = _req("GET", "https://paper-api.alpaca.markets/v2/clock")
            return bool(d.get("is_open"))
        except Exception:
            return False
except Exception:
    USE_BROKER = False

    def market_open():
        return True  # local sim doesn't care about market hours

if not USE_BROKER:
    from paper_account import PaperAccount


def params_for(sym):
    if sym in PER_ASSET:
        return PER_ASSET[sym]
    return (EMA_FAST, EMA_SLOW, RSI_BUY_MAX, RSI_SELL_MIN)


def compute_signal(sym, is_forex):
    h = get_history(sym, period=HISTORY_RANGE, interval=TIMEFRAME)
    closes = h["close"]
    ef, es, rb, rs = params_for(sym)
    ema_f = si.ema_series(closes, ef)
    ema_s = si.ema_series(closes, es)
    rsi = si.rsi_series(closes, RSI_PERIOD)
    sig = si.signals_ema_rsi(closes, ema_f, ema_s, rsi, rb, rs)
    return sig[-1], closes[-1]


def run_once():
    if USE_BROKER:
        acct = get_account()
        equity = float(acct.get("equity", 0.0))
        cash = float(acct.get("cash", 0.0))
        positions = {p["symbol"]: float(p["qty"]) for p in get_positions()}
        print(f"[PAPER BROKER] equity ${equity:,.2f} | positions {positions}")
    else:
        acct = PaperAccount(10_000.0)
        positions = {s: acct.positions.get(s, 0.0) for s, _ in UNIVERSE}
        cash = acct.cash
        equity = cash
        print(f"[LOCAL SIM] cash ${cash:,.2f} | positions {positions}")

    # Hard cap: never deploy more than POSITION_PCT of equity total across the
    # whole session. Track $ already deployed by this process this run.
    budget_total = equity * POSITION_PCT          # max $ to deploy this pass
    deployed = 0.0                                # $ already booked by this run
    self_bought = set()                           # symbols we already bought this run

    # Rank opportunities and get opportunity-weighted BUY allocation
    try:
        from rank import ranked, size_weights
        rows = ranked()
        wts = size_weights(rows)          # {symbol: fraction of budget}
    except Exception as e:
        print("ranker error (falling back to flat sizing):", e)
        rows = []
        wts = {}

    for sym, is_forex in UNIVERSE:
        # Skip if we already bought this symbol this run (prevents double-buy on
        # stale/repainted positions, or a fast second pass).
        if sym in self_bought:
            continue

        try:
            sig, price = compute_signal(sym, is_forex)
            held = positions.get(sym, 0.0) > 0
            if sig == "BUY" and not held:
                share = wts.get(sym, 1.0 / max(1, len(UNIVERSE)))
                alloc = budget_total * share
                # Hard cap: don't exceed total budget.
                if deployed + alloc > budget_total:
                    alloc = max(0.0, budget_total - deployed)
                if alloc <= 0:
                    print(f"  {sym}: BUY signal but session budget exhausted")
                    continue
                qty = int(alloc // price) if price > 0 else 0
                if qty > 0 and USE_BROKER:
                    submit_order(sym, qty, "buy")
                    # Refresh actual position so this run + any next pass sees it.
                    pos = get_position(sym)
                    if pos is not None and float(pos.get("qty", 0)) > 0:
                        positions[sym] = float(pos["qty"])
                    self_bought.add(sym)
                    deployed += alloc
                    notify(f"PAPER BUY {sym} {qty}@{price:.2f} (alloc {share*100:.0f}% of budget, ${alloc:,.0f})")
                    print(f"  PAPER BUY {sym} {qty}@{price:.2f} (alloc {share*100:.0f}%, ${alloc:,.0f}, deployed ${deployed:,.0f}/{budget_total:,.0f})")
                elif qty > 0:
                    acct.buy(sym, price, alloc)
                    self_bought.add(sym)
                    deployed += alloc
                    notify(f"SIM BUY {sym} @ {price:.2f} (alloc {share*100:.0f}% of budget, ${alloc:,.0f})")
                    print(f"  SIM BUY {sym} @ {price:.2f} (alloc {share*100:.0f}%, ${alloc:,.0f}, deployed ${deployed:,.0f}/{budget_total:,.0f})")
                else:
                    print(f"  {sym}: BUY signal but qty=0 at price {price:.2f} (alloc ${alloc:,.0f})")
            elif sig == "SELL" and held:
                if USE_BROKER:
                    close_position(sym)
                    self_bought.discard(sym)
                    notify(f"PAPER SELL {sym} @ {price:.2f}")
                    print(f"  PAPER SELL {sym} @ {price:.2f}")
                else:
                    acct.sell(sym, price)
                    self_bought.discard(sym)
                    notify(f"SIM SELL {sym} @ {price:.2f}")
                    print(f"  SIM SELL {sym} @ {price:.2f}")
            else:
                print(f"  {sym}: {sig} @ {price:.2f} (held={held})")
        except Exception as e:
            print(f"  ! {sym}: {e}")


def daily_summary():
    """One clean Telegram report at end of session."""
    if USE_BROKER:
        try:
            acct = get_account()
            eq = float(acct.get("equity", 0.0))
            cash = float(acct.get("cash", 0.0))
            positions = get_positions()
            pos_str = ", ".join(f"{p['symbol']}:{p['qty']}@{p['avg_entry_price']}"
                               for p in positions) or "flat"
            msg = (f"StockBot daily summary (PAPER)\n"
                   f"Equity ${eq:,.2f} | Cash ${cash:,.2f}\n"
                   f"Positions: {pos_str}")
            notify(msg)
            print(msg)
        except Exception as e:
            print("summary error:", e)
    else:
        print("[LOCAL SIM] daily summary skipped (no broker)")


class CircuitBreaker:
    """Halts trading if PAPER equity drops > MAX_DAILY_LOSS_PCT from session open."""

    def __init__(self, start_equity, max_loss_pct):
        self.start = start_equity
        self.max_loss = max_loss_pct
        self.tripped = False

    def check(self, equity):
        if self.tripped:
            return True
        if self.start > 0 and equity < self.start * (1 - self.max_loss):
            self.tripped = True
            loss_pct = (equity / self.start - 1) * 100
            msg = (f" CIRCUIT BREAKER TRIPPED: equity ${equity:,.2f} is "
                   f"{loss_pct:.2f}% below session open ${self.start:,.2f} "
                   f"(limit -{self.max_loss*100:.1f}%). Flattening ALL positions "
                   f"and halting trading for the session.")
            notify(msg)
            print(msg)
            self._flatten()
        return self.tripped

    def _flatten(self):
        if not USE_BROKER:
            return
        for sym, _ in UNIVERSE:
            try:
                close_position(sym)
            except Exception as e:
                print(f"  flatten {sym} error: {e}")


def main():
    mode = "ALPACA PAPER" if USE_BROKER else "LOCAL SIMULATOR"
    print(f"Live trader | mode={mode} | universe={[s for s,_ in UNIVERSE]} | "
          f"{TIMEFRAME} EMA+RSI\n")

    if "--train" in sys.argv:
        import train
        train.main()
        return

    if "--rank" in sys.argv:
        import rank
        rank.main()
        return

    if "--once" in sys.argv:
        if USE_BROKER and not market_open():
            print("Market closed - skipping (no orders queued).")
            return
        run_once()
        return

    # session-start equity for the circuit breaker
    start_equity = float(get_account().get("equity", 0.0)) if USE_BROKER else 10_000.0
    breaker = CircuitBreaker(start_equity, MAX_DAILY_LOSS_PCT)
    print(f"Circuit breaker armed: halts if equity drops > {MAX_DAILY_LOSS_PCT*100:.1f}% "
          f"below ${start_equity:,.2f}\n")
    print(f"Loop every {SCAN_INTERVAL_SECONDS}s (Ctrl+C to stop)\n")
    print("Self-training: re-tunes PER_ASSET once/day via train.py\n")
    last_train_day = None
    try:
        while True:
            if USE_BROKER and not market_open():
                print(f"[closed] {time.strftime('%H:%M')} - market shut, idle")
            else:
                # check breaker first
                if USE_BROKER:
                    eq = float(get_account().get("equity", start_equity))
                    if breaker.check(eq):
                        print(f"[HALTED] breaker tripped - no new orders. "
                              f"Equity ${eq:,.2f}. Ctrl+C to stop the loop.")
                    else:
                        run_once()
                        # self-train once per day (first open pass of a new UTC day)
                        today = time.strftime("%Y-%m-%d")
                        if last_train_day != today:
                            try:
                                import train
                                print(f"[train] re-tuning PER_ASSET on {today}...")
                                train.main()
                                last_train_day = today
                            except Exception as e:
                                print("train error:", e)
            time.sleep(SCAN_INTERVAL_SECONDS)
    except KeyboardInterrupt:
        daily_summary()
        print("\nStopped.")


if __name__ == "__main__":
    main()
