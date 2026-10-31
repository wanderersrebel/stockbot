"""Day-trading mode (stdlib only): intraday EMA(9/21) + RSI(14) trend strategy.

- Pulls 5m (configurable) bars for a MIXED universe: stocks + forex (EURUSD=X).
- EMA crossover (fast crosses above slow) = trend signal.
- RSI filter: only buy when not overbought (RSI < RSI_BUY_MAX); exit on
  overbought (RSI >= RSI_SELL) or opposite cross.
- Realistic costs: stocks ~0.1% round-trip, forex ~1 pip per side (set per asset).
- Paper-only: no broker, no real money.

Run:
  python daytrader.py --backtest     simulate on real intraday history
  python daytrader.py --once         one live scan on latest 5m bars
"""

import sys
import time
from datetime import datetime, timezone

from config_day import (UNIVERSE, TIMEFRAME, HISTORY_RANGE, EMA_FAST, EMA_SLOW,
                        RSI_PERIOD, RSI_BUY_MAX, RSI_SELL_MIN, PER_ASSET,
                        FX_SESSION_HOURS,
                        INITIAL_CASH, POSITION_PCT, SCAN_INTERVAL_SECONDS,
                        FEE_STOCK, FEE_FOREX_PIPS, PIP_VALUE)
from data_feed import get_history
import strategy_intraday as si
from paper_account import PaperAccount
from notifier import notify


def _utc_hours(timestamps):
    """Return list of UTC hour-of-day (0-23) for a list of epoch seconds."""
    out = []
    for t in timestamps:
        out.append(datetime.fromtimestamp(t, tz=timezone.utc).hour)
    return out


def params_for(sym):
    if sym in PER_ASSET:
        ef, es, rb, rs = PER_ASSET[sym]
    else:
        ef, es, rb, rs = EMA_FAST, EMA_SLOW, RSI_BUY_MAX, RSI_SELL_MIN
    return ef, es, rb, rs


def scan_symbol(sym, is_forex):
    h = get_history(sym, period=HISTORY_RANGE, interval=TIMEFRAME)
    closes = h["close"]
    dates = h["dates"]
    ef, es, rb, rs = params_for(sym)
    ema_f = si.ema_series(closes, ef)
    ema_s = si.ema_series(closes, es)
    rsi = si.rsi_series(closes, RSI_PERIOD)
    hours = _utc_hours(dates) if (is_forex and FX_SESSION_HOURS) else None
    sig = si.signals_ema_rsi(closes, ema_f, ema_s, rsi, rb, rs,
                             allow_buy_hours=FX_SESSION_HOURS if is_forex else None,
                             hours=hours)
    return closes, dates, sig


def scan_once(acct):
    prices = {}
    rows = []
    for sym, is_forex in UNIVERSE:
        try:
            closes, dates, sig = scan_symbol(sym, is_forex)
            price = closes[-1]
            prices[sym] = price
            rows.append((sym, sig[-1], price, is_forex))
        except Exception as e:
            print(f"  ! {sym}: {e}")

    for sym, sig, price, is_forex in rows:
        if sig == "BUY" and acct.positions.get(sym, 0.0) == 0.0:
            fee = FEE_FOREX_PIPS * PIP_VALUE if is_forex else FEE_STOCK
            trade = acct.buy(sym, price, acct.cash * POSITION_PCT, fee_pct=fee)
            if trade:
                msg = f"PAPER BUY {sym} {trade['qty']}@{trade['price']} = ${trade['value']}"
                print(msg); notify(msg)
        elif sig == "SELL" and acct.positions.get(sym, 0.0) > 0.0:
            fee = FEE_FOREX_PIPS * PIP_VALUE if is_forex else FEE_STOCK
            trade = acct.sell(sym, price, fee_pct=fee)
            if trade:
                msg = f"PAPER SELL {sym} {trade['qty']}@{trade['price']} PnL=${trade['pnl']}"
                print(msg); notify(msg)
        else:
            print(f"  {sym}: {sig} @ {price:.5f}" if is_forex else f"  {sym}: {sig} @ {price:.2f}")

    print("  " + acct.summary(prices))


def backtest():
    print(f"Daytrader backtest | universe={[s for s,_ in UNIVERSE]} | "
          f"{TIMEFRAME} | per-asset EMA/RSI (from tune_day_6m.py)\n")
    totals = 0.0
    for sym, is_forex in UNIVERSE:
        try:
            h = get_history(sym, period=HISTORY_RANGE, interval=TIMEFRAME)
            closes = h["close"]
            dates = h["dates"]
            ef, es, rb, rs = params_for(sym)
            ema_f = si.ema_series(closes, ef)
            ema_s = si.ema_series(closes, es)
            rsi = si.rsi_series(closes, RSI_PERIOD)
            hours = _utc_hours(dates) if (is_forex and FX_SESSION_HOURS) else None
            sig = si.signals_ema_rsi(closes, ema_f, ema_s, rsi, rb, rs,
                                     allow_buy_hours=FX_SESSION_HOURS if is_forex else None,
                                     hours=hours)
            fee = FEE_FOREX_PIPS * PIP_VALUE if is_forex else FEE_STOCK
            acct = PaperAccount(INITIAL_CASH, state_file=f"state/day_{sym}.json")
            acct.trades = []
            for i in range(len(closes)):
                price = closes[i]
                ts = str(dates[i])
                if sig[i] == "BUY" and acct.positions.get(sym, 0.0) == 0.0:
                    acct.buy(sym, price, acct.cash * POSITION_PCT, fee_pct=fee, ts=ts)
                elif sig[i] == "SELL" and acct.positions.get(sym, 0.0) > 0.0:
                    acct.sell(sym, price, fee_pct=fee, ts=ts)
            last = closes[-1]
            if acct.positions.get(sym, 0.0) > 0.0:
                acct.sell(sym, last, fee_pct=fee, ts=str(dates[-1]))
            print(f"{sym:10s}: {acct.summary({sym: last})}")
            totals += acct.equity({sym: last})
        except Exception as e:
            print(f"{sym:10s}: error {e}")
    print(f"\nCombined final equity: ${totals:,.2f}  (started ${INITIAL_CASH*len(UNIVERSE):,.0f})")


def main():
    if "--backtest" in sys.argv:
        backtest()
        return
    acct = PaperAccount(INITIAL_CASH)
    fxnote = f" | FX session {FX_SESSION_HOURS} UTC" if FX_SESSION_HOURS else ""
    print(f"DayTrader | {TIMEFRAME} | universe={[s for s,_ in UNIVERSE]} | "
          f"EMA {EMA_FAST}/{EMA_SLOW} + RSI {RSI_PERIOD}{fxnote}\n")
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
