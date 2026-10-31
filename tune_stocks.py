"""Stock-universe tuner (stdlib only): find best EMA/RSI per stock on 6mo 1h.

Reuses the trend strategy. Baseline = flat $10k. Reports best combo per symbol
so we can bake PER_ASSET for the stock-only universe.

Run:  python tune_stocks.py
"""
from config_day import (UNIVERSE, POSITION_PCT, FEE_STOCK)
from data_feed import get_history
import strategy_intraday as si

TF = "1h"
RANGE = "1y"
EMA_FAST_RANGE = [9, 12, 20, 30, 50]
EMA_SLOW_RANGE = [30, 50, 80, 120, 200]
RSI_BUY_RANGE = [55, 60, 65, 70]
RSI_SELL_RANGE = [70, 75, 80, 85]
CASH = 10_000.0


def backtest_series(closes, ema_f, ema_s, rsi, rsi_buy, rsi_sell, fee_pct):
    sig = si.signals_ema_rsi(closes, ema_f, ema_s, rsi, rsi_buy, rsi_sell)
    cash = CASH
    shares = 0.0
    trades = 0
    eq = [CASH]
    peak = CASH
    for i in range(len(closes)):
        p = closes[i]
        if sig[i] == "BUY" and shares == 0:
            q = int((cash * POSITION_PCT * (1 - fee_pct)) // p)
            if q > 0:
                cash -= q * p * (1 + fee_pct)
                shares = q
                trades += 1
        elif sig[i] == "SELL" and shares > 0:
            cash += shares * p * (1 - fee_pct)
            shares = 0.0
            trades += 1
        e = cash + shares * p
        eq.append(e)
        peak = max(peak, e)
    final = cash + shares * closes[-1]
    ret = (final / CASH - 1) * 100
    dd = (min(eq) / peak - 1) * 100 if peak else 0.0
    return ret, trades, dd


def main():
    print(f"Stock tuner | {TF} ~6mo | baseline flat $10k | pos {POSITION_PCT:.0%} | "
          f"fee stock {FEE_STOCK:.1%}\n")
    results = []
    for sym, is_forex in UNIVERSE:
        if is_forex:
            continue
        try:
            h = get_history(sym, period=RANGE, interval=TF)
            closes = h["close"]
        except Exception as e:
            print(f"{sym:6s}: data error {e}")
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
                        ema_f = si.ema_series(closes, ef)
                        ema_s = si.ema_series(closes, es)
                        rsi = si.rsi_series(closes, 14)
                        ret, tr, dd = backtest_series(
                            closes, ema_f, ema_s, rsi, rb, rs, FEE_STOCK)
                        if best is None or ret > best[0]:
                            best = (ret, ef, es, rb, rs, tr, dd)
        if best:
            print(f"{sym:6s} | EMA{best[1]}/{best[2]} RSI<{best[3]}/≥{best[4]} "
                  f"-> {best[0]:+.2f}% | trades {best[5]} | maxDD {best[6]:.1f}%")
            results.append((sym, best))
        else:
            print(f"{sym:6s}: no valid test")
    if results:
        avg = sum(r[1][0] for r in results) / len(results)
        print(f"\nAverage 6mo return (stock universe): {avg:+.2f}%  "
              f"(positive = beats doing nothing)")


if __name__ == "__main__":
    main()
