"""StockBot entry point (stdlib only).

Modes:
  python main.py            -> live loop: scan every SCAN_INTERVAL_SECONDS
  python main.py --once     -> single scan, then exit
  python main.py --backtest -> simulate the strategy on real past data
"""
import sys
import time

from config import (WATCHLIST, MODE, STRATEGY, SHORT_WINDOW, LONG_WINDOW,
                    RSI_PERIOD, RSI_BUY_MIN, RSI_BUY_MAX, RSI_SELL_MIN,
                    INITIAL_CASH, POSITION_PCT, SCAN_INTERVAL_SECONDS)
from data_feed import get_history, get_price
from strategy import (add_signals, add_signals_combo_r, latest_signal,
                     latest_signal_combo, rsi_series)
from paper_account import PaperAccount
from notifier import notify


def scan_once(acct):
    prices = {}
    rows = []
    for sym in WATCHLIST:
        try:
            h = get_history(sym, period="6mo", interval="1d")
            closes = h["close"]
            if STRATEGY == "rsi_sma":
                sig, price = latest_signal_combo(
                    closes, SHORT_WINDOW, LONG_WINDOW,
                    RSI_PERIOD, RSI_BUY_MAX, RSI_SELL_MIN)
            else:
                sig, price = latest_signal(closes, SHORT_WINDOW, LONG_WINDOW)
            prices[sym] = price
            rows.append((sym, sig, price))
        except Exception as e:
            print(f"  ! {sym}: {e}")

    for sym, sig, price in rows:
        if MODE != "paper":
            continue
        if sig == "BUY" and acct.positions.get(sym, 0.0) == 0.0:
            trade = acct.buy(sym, price, acct.cash * POSITION_PCT)
            if trade:
                msg = f"PAPER BUY {sym} {trade['qty']}@{trade['price']} = ${trade['value']}"
                print(msg)
                notify(msg)
        elif sig == "SELL" and acct.positions.get(sym, 0.0) > 0.0:
            trade = acct.sell(sym, price)
            if trade:
                msg = f"PAPER SELL {sym} {trade['qty']}@{trade['price']} PnL=${trade['pnl']}"
                print(msg)
                notify(msg)
        else:
            print(f"  {sym}: {sig} @ {price:.2f}")

    print("  " + acct.summary(prices))


def backtest():
    print(f"Backtest | {WATCHLIST} | strategy={STRATEGY} | "
          f"SMA {SHORT_WINDOW}/{LONG_WINDOW}" +
          (f" | RSI {RSI_PERIOD} buy[{RSI_BUY_MIN},{RSI_BUY_MAX}] sell>={RSI_SELL_MIN}"
           if STRATEGY == "rsi_sma" else "") +
          f" | pos {POSITION_PCT:.0%} | starting ${INITIAL_CASH:,.0f}\n")
    totals_eq = 0.0
    for sym in WATCHLIST:
        try:
            h = get_history(sym, period="1y", interval="1d")
            closes = h["close"]
            rsi = rsi_series(closes, RSI_PERIOD) if STRATEGY == "rsi_sma" else None
            if STRATEGY == "rsi_sma":
                sig = add_signals_combo_r(closes, rsi, SHORT_WINDOW, LONG_WINDOW,
                                         RSI_BUY_MIN, RSI_BUY_MAX, RSI_SELL_MIN)
            else:
                sig = add_signals(closes, SHORT_WINDOW, LONG_WINDOW)
            acct = PaperAccount(INITIAL_CASH, state_file=f"state/backtest_{sym}.json")
            acct.trades = []
            for i in range(len(closes)):
                price = closes[i]
                ts = str(h["dates"][i])
                if sig[i] == "BUY" and acct.positions.get(sym, 0.0) == 0.0:
                    acct.buy(sym, price, acct.cash * POSITION_PCT, ts=ts)
                elif sig[i] == "SELL" and acct.positions.get(sym, 0.0) > 0.0:
                    acct.sell(sym, price, ts=ts)
            last = closes[-1]
            if acct.positions.get(sym, 0.0) > 0.0:
                acct.sell(sym, last, ts=str(h["dates"][-1]))
            print(f"{sym:5s}: {acct.summary({sym: last})}")
            totals_eq += acct.equity({sym: last})
        except Exception as e:
            print(f"{sym:5s}: error {e}")
    print(f"\nCombined final equity (sum of per-symbol accounts): ${totals_eq:,.2f}")
    print(f"vs buy-and-hold each ${INITIAL_CASH:,.0f}:                "
          f"${(INITIAL_CASH * len(WATCHLIST)):,.2f}")


def main():
    if "--backtest" in sys.argv:
        backtest()
        return

    acct = PaperAccount(INITIAL_CASH)
    print(f"StockBot | mode={MODE} | strategy={STRATEGY} | watchlist={WATCHLIST}")
    print(f"Strategy: SMA crossover {SHORT_WINDOW}/{LONG_WINDOW}" +
          (f" + RSI({RSI_PERIOD}) buy[{RSI_BUY_MIN},{RSI_BUY_MAX}] sell>={RSI_SELL_MIN}"
           if STRATEGY == "rsi_sma" else "") + "\n")

    if "--once" in sys.argv:
        scan_once(acct)
        return

    print(f"Live loop every {SCAN_INTERVAL_SECONDS}s (Ctrl+C to stop)\n")
    try:
        while True:
            scan_once(acct)
            time.sleep(SCAN_INTERVAL_SECONDS)
    except KeyboardInterrupt:
        print("\nStopped.")


if __name__ == "__main__":
    main()
