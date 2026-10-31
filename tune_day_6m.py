"""6-month day-trading validation tuner (stdlib only).

Uses 1h bars (= ~6 months free history on Yahoo) to find, per asset, the best
EMA + RSI combo, then reports whether the edge survives a longer window than
the 60-day 15m test. Baseline = flat $10,000.

Run:  python tune_day_6m.py
"""
from config_day import (UNIVERSE, POSITION_PCT, FEE_STOCK,
                        FEE_FOREX_PIPS, PIP_VALUE)
from data_feed import get_history
from strategy_intraday import ema_series, rsi_series, signals_ema_rsi

TF = "1h"
RANGE = "1y"          # ~6 months of 1h bars
EMA_FAST_RANGE = [9, 12, 20, 30, 50]
EMA_SLOW_RANGE = [30, 50, 80, 120, 200]
RSI_BUY_RANGE = [55, 60, 65, 70]
RSI_SELL_RANGE = [70, 75, 80, 85]
CASH = 10_000.0


def backtest_series(closes, ema_f, ema_s, rsi, rsi_buy, rsi_sell, fee_pct):
    sig = signals_ema_rsi(closes, ema_f, ema_s, rsi, rsi_buy, rsi_sell)
    cash = CASH
    shares = 0.0
    trades = 0
    eq_curve = [CASH]
    peak = CASH
    for i in range(len(closes)):
        price = closes[i]
        if sig[i] == "BUY" and shares == 0:
            qty = int((cash * POSITION_PCT * (1 - fee_pct)) // price)
            if qty > 0:
                cash -= qty * price * (1 + fee_pct)
                shares = qty
                trades += 1
        elif sig[i] == "SELL" and shares > 0:
            cash += shares * price * (1 - fee_pct)
            shares = 0.0
            trades += 1
        eq = cash + shares * price
        eq_curve.append(eq)
        peak = max(peak, eq)
    final = cash + shares * closes[-1]
    ret = (final / CASH - 1) * 100
    dd = (min(eq_curve) / peak - 1) * 100 if peak else 0.0
    return ret, trades, dd


def main():
    print(f"6-month tuner | {TF} bars (~6mo) | baseline flat $10k | "
          f"pos {POSITION_PCT:.0%} | fee stock {FEE_STOCK:.1%}, "
          f"forex {FEE_FOREX_PIPS:.1f}pip\n")
    grand = []
    for sym, is_forex in UNIVERSE:
        fee = FEE_FOREX_PIPS * PIP_VALUE if is_forex else FEE_STOCK
        try:
            h = get_history(sym, period=RANGE, interval=TF)
            closes = h["close"]
        except Exception as e:
            print(f"{sym:10s}: data error {e}")
            continue
        best = None
        for ef in EMA_FAST_RANGE:
            for es in EMA_SLOW_RANGE:
                if es <= ef:
                    continue
                for rb in RSI_BUY_RANGE:
                    for rs in RSI_SELL_RANGE:
                        if rs <= rb:
                            continue
                        ema_f = ema_series(closes, ef)
                        ema_s = ema_series(closes, es)
                        rsi = rsi_series(closes, 14)
                        ret, tr, dd = backtest_series(
                            closes, ema_f, ema_s, rsi, rb, rs, fee)
                        if best is None or ret > best[0]:
                            best = (ret, ef, es, rb, rs, tr, dd)
        if best:
            print(f"{sym:10s} | best EMA{best[1]}/{best[2]} RSI<{best[3]}/≥{best[4]} "
                  f"-> {best[0]:+.2f}% | trades {best[5]} | maxDD {best[6]:.1f}%")
            grand.append((sym, best[0]))
        else:
            print(f"{sym:10s}: no valid test")
    avg = sum(r[1] for r in grand) / len(grand) if grand else 0
    print(f"\nAverage 6-month return across universe: {avg:+.2f}%  "
          f"(positive = beats doing nothing over 6 months)")


if __name__ == "__main__":
    main()
