"""Strategy tuner (stdlib only): grid-search SMA windows on real 1y data.

Tests every (short, long) combo with a realistic trading fee and reports
which beat buy-and-hold. Pure Python, no numpy/pandas.

Run:  python tune.py
"""
from config import WATCHLIST, POSITION_PCT
from data_feed import get_history
from strategy import add_signals

FEE = 0.001          # 0.1% per trade (round-trip ~0.2%) - realistic for retail
SHORT_RANGE = range(5, 21, 1)      # 5..20 day short averages
LONG_RANGE = range(22, 61, 2)      # 22..60 day long averages
CASH = 10_000.0


def backtest_series(closes, short, long, fee=FEE):
    """Return (return_pct, n_trades, max_drawdown_pct) for one combo."""
    sig = add_signals(closes, short, long)
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
    drawdown = (min(equity_curve) / peak - 1) * 100 if peak else 0.0
    return ret, trades, drawdown


def buy_hold(closes):
    return (closes[-1] / closes[0] - 1) * 100


def main():
    print(f"Tuner | fee {FEE:.1%} | pos {POSITION_PCT:.0%} | "
          f"short {SHORT_RANGE.start}-{SHORT_RANGE.stop-1} | "
          f"long {LONG_RANGE.start}-{LONG_RANGE.stop-1}\n")
    overall = []
    for sym in WATCHLIST:
        try:
            h = get_history(sym, period="1y", interval="1d")
            closes = h["close"]
        except Exception as e:
            print(f"{sym}: data error {e}")
            continue
        bh = buy_hold(closes)
        best = None
        for s in SHORT_RANGE:
            for l in LONG_RANGE:
                if l <= s:
                    continue
                ret, trades, dd = backtest_series(closes, s, l)
                if best is None or ret > best[0]:
                    best = (ret, s, l, trades, dd)
        beat = best[0] - bh
        print(f"{sym:5s} | buy&hold {bh:+.2f}%  | "
              f"best SMA {best[1]}/{best[2]} -> {best[0]:+.2f}% "
              f"(beat BH by {beat:+.2f}%) | trades {best[3]} | maxDD {best[4]:.1f}%")
        overall.append((sym, best[0], best[1], best[2], beat, best[3], best[4], bh))

    print("\n=== Ranked by edge over buy-and-hold ===")
    overall.sort(key=lambda r: r[5], reverse=True)
    print(f"{'SYM':5s} {'BEST':>8s} {'vsB&H':>8s} {'win':>12s} {'trades':>6s} {'maxDD':>7s}")
    for sym, ret, s, l, beat, tr, dd, bh in overall:
        print(f"{sym:5s} {ret:+7.2f}% {beat:+7.2f}% {f'{s}/{l}':>12s} {tr:>6} {dd:>6.1f}%")

    avg_beat = sum(r[5] for r in overall) / len(overall) if overall else 0
    print(f"\nAverage edge vs buy-and-hold across watchlist: {avg_beat:+.2f}%")
    print("Positive edge = strategy adds value. Negative = just buy and hold.")


if __name__ == "__main__":
    main()
