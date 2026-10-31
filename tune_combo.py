"""Combo tuner (stdlib only): grid-search RSI + SMA on real 1y data.

For each ticker, searches SMA windows AND RSI sell thresholds, reports which
combos beat buy-and-hold. Pure Python.

Run:  python tune_combo.py
"""
from config import WATCHLIST, POSITION_PCT
from data_feed import get_history
from strategy import add_signals_combo_r, rsi_series

FEE = 0.001
SHORT_RANGE = range(8, 21, 2)
LONG_RANGE = range(30, 61, 5)
RSI_SELL_RANGE = [60, 65, 70, 75, 80]
RSI_BUY_MAX_DEF = 70
RSI_PERIOD = 14
CASH = 10_000.0


def backtest_series(closes, rsi, short, long, rsi_sell, fee=FEE):
    sig = add_signals_combo_r(closes, rsi, short, long, 0, RSI_BUY_MAX_DEF, rsi_sell)
    cash = CASH
    shares = 0.0
    trades = 0
    equity_curve = []
    peak = CASH
    for i in range(len(closes)):
        price = closes[i]
        if sig[i] == "BUY" and shares == 0:
            qty = (cash * POSITION_PCT * (1 - fee)) / price
            if qty > 0:
                cash -= qty * price
                shares = qty
                trades += 1
        elif sig[i] == "SELL" and shares > 0:
            proceeds = shares * price * (1 - fee)
            cash += proceeds
            shares = 0.0
            trades += 1
        equity = cash + shares * price
        equity_curve.append(equity)
        peak = max(peak, equity)
    final_eq = cash + shares * closes[-1]
    ret = (final_eq / CASH - 1) * 100
    dd = (min(equity_curve) / peak - 1) * 100 if peak else 0.0
    return ret, trades, dd


def buy_hold(closes):
    return (closes[-1] / closes[0] - 1) * 100


def main():
    print(f"Combo tuner | fee {FEE:.1%} | pos {POSITION_PCT:.0%} | RSI p{RSI_PERIOD}\n")
    overall = []
    for sym in WATCHLIST:
        try:
            h = get_history(sym, period="1y", interval="1d")
            closes = h["close"]
            rsi = rsi_series(closes, RSI_PERIOD)
        except Exception as e:
            print(f"{sym}: data error {e}")
            continue
        bh = buy_hold(closes)
        best = None
        for s in SHORT_RANGE:
            for l in LONG_RANGE:
                if l <= s:
                    continue
                for rs in RSI_SELL_RANGE:
                    ret, trades, dd = backtest_series(closes, rsi, s, l, rs)
                    if best is None or ret > best[0]:
                        best = (ret, s, l, rs, trades, dd)
        beat = best[0] - bh
        print(f"{sym:5s} | buy&hold {bh:+.2f}% | best SMA {best[1]}/{best[2]} "
              f"RSIsell{best[3]} -> {best[0]:+.2f}% (edge {beat:+.2f}%) "
              f"| trades {best[4]} | maxDD {best[5]:.1f}%")
        overall.append((sym, best[0], beat, best[1], best[2], best[3], best[4]))

    avg_beat = sum(r[2] for r in overall) / len(overall) if overall else 0
    print(f"\nAverage edge vs buy-and-hold: {avg_beat:+.2f}%")
    print("Positive edge = combo adds value over just holding.")


if __name__ == "__main__":
    main()
