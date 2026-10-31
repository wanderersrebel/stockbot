"""Head-to-head: trend (EMA+RSI) vs mean-reversion (RSI bounce) on forex.

Uses real 6mo 1h bars for the FX pairs. Compares both strategies with
realistic forex fees so we see which actually works on this data.

Run:  python fx_compare.py
"""
from config_day import (FEE_FOREX_PIPS, PIP_VALUE, POSITION_PCT, INITIAL_CASH)
from data_feed import get_history
import strategy_intraday as si

FX_PAIRS = [("EURUSD=X", True), ("GBPUSD=X", True)]
TF = "1h"
RANGE = "1y"          # ~6mo of 1h bars
CASH = 10_000.0
FEE = FEE_FOREX_PIPS * PIP_VALUE

# trend (EMA+RSI) params per pair (from tune_day_6m winners)
TREND_PARAMS = {
    "EURUSD=X": (12, 50, 60, 85),
    "GBPUSD=X": (30, 50, 60, 85),
}
# mean-reversion (RSI bounce) params
REV_PARAMS = {
    "EURUSD=X": (30, 50),   # oversold 30, exit 50
    "GBPUSD=X": (30, 50),
}


def backtest(closes, sig, fee_pct):
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


def _utc_hours(ts):
    from datetime import datetime, timezone
    return [datetime.fromtimestamp(t, tz=timezone.utc).hour for t in ts]


def main():
    print(f"FX strategy comparison | {TF} ~6mo | fee {FEE_FOREX_PIPS}pip | "
          f"pos {POSITION_PCT:.0%}\n")
    print(f"{'PAIR':10s} | {'TREND':>9s} | {'REVERSAL':>9s} | winner")
    for sym, _ in FX_PAIRS:
        h = get_history(sym, period=RANGE, interval=TF)
        closes = h["close"]
        dates = h["dates"]
        hours = _utc_hours(dates)
        rsi = si.rsi_series(closes, 14)
        # trend
        ef, es, rb, rs = TREND_PARAMS[sym]
        ema_f = si.ema_series(closes, ef)
        ema_s = si.ema_series(closes, es)
        sig_t = si.signals_ema_rsi(closes, ema_f, ema_s, rsi, rb, rs,
                                   allow_buy_hours=(13, 17), hours=hours)
        rt, tt, ddt = backtest(closes, sig_t, FEE)
        # reversion
        ov, ex = REV_PARAMS[sym]
        sig_r = si.signals_rsi_reversion(closes, rsi, ov, ex,
                                         allow_buy_hours=(13, 17), hours=hours)
        rr, tr, ddr = backtest(closes, sig_r, FEE)
        win = "TREND" if rt > rr else "REVERSAL"
        print(f"{sym:10s} | {rt:+8.2f}% | {rr:+8.2f}% | {win} "
              f"(trades {tt}/{tr})")


if __name__ == "__main__":
    main()
