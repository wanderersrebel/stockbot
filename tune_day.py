"""Day-trading tuner (stdlib only): grid-search intraday params on real data.

Searches TIMEFRAME x EMA(fast/slow) x RSI(buy/sell) for each symbol and
reports the best combo. Baseline = do nothing = $10,000 (flat). A positive
return means the strategy added value over sitting out.

Run:  python tune_day.py
"""
from config_day import (UNIVERSE, INITIAL_CASH, POSITION_PCT,
                        FEE_STOCK, FEE_FOREX_PIPS, PIP_VALUE)
from data_feed import get_history
from strategy_intraday import ema_series, rsi_series, signals_ema_rsi

TIMEFRAMES = ["5m", "15m", "30m", "1h"]
EMA_FAST_RANGE = [9, 12, 20, 30]
EMA_SLOW_RANGE = [30, 50, 80, 120]
RSI_BUY_RANGE = [55, 60, 65, 70]
RSI_SELL_RANGE = [70, 75, 80]
HISTORY = {"5m": "60d", "15m": "60d", "30m": "60d", "1h": "60d"}
CASH = 10_000.0


def backtest_series(closes, ema_f, ema_s, rsi, rsi_buy, rsi_sell,
                    fee_pct):
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
                cost = qty * price * (1 + fee_pct)
                cash -= cost
                shares = qty
                trades += 1
        elif sig[i] == "SELL" and shares > 0:
            proceeds = shares * price * (1 - fee_pct)
            cash += proceeds
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
    print(f"Day-trading tuner | baseline = flat $10,000 | "
          f"pos {POSITION_PCT:.0%} | fee stock {FEE_STOCK:.1%}, "
          f"forex {FEE_FOREX_PIPS:.1f}pip\n")
    grand = []
    for sym, is_forex in UNIVERSE:
        fee = FEE_FOREX_PIPS * PIP_VALUE if is_forex else FEE_STOCK
        best = None
        for tf in TIMEFRAMES:
            try:
                h = get_history(sym, period=HISTORY[tf], interval=tf)
                closes = h["close"]
            except Exception as e:
                print(f"  ! {sym} {tf}: {e}")
                continue
            if len(closes) < 130:
                continue
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
                                best = (ret, tf, ef, es, rb, rs, tr, dd)
        if best:
            print(f"{sym:10s} | best {best[1]:>3s} EMA{best[2]}/{best[3]} "
                  f"RSI<{best[4]}/≥{best[5]} -> {best[0]:+.2f}% "
                  f"| trades {best[6]} | maxDD {best[7]:.1f}%")
            grand.append((sym, best[0], best))
        else:
            print(f"{sym:10s} | no valid test")
    avg = sum(r[1] for r in grand) / len(grand) if grand else 0
    print(f"\nAverage return across universe: {avg:+.2f}%  "
          f"(positive = beats doing nothing)")


if __name__ == "__main__":
    main()
