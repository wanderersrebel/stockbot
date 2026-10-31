"""Self-training: re-tune per-asset EMA/RSI params on fresh 6mo data and
update config_day.PER_ASSET. This is how the bot 'learns' - it re-optimizes its
parameters against the latest market history so the strategy stays current.

Run:  python train.py        (re-tune + write config_day.PER_ASSET)
"""
import json
from config_day import UNIVERSE, POSITION_PCT, FEE_STOCK, TIMEFRAME, HISTORY_RANGE
from data_feed import get_history
import strategy_intraday as si

EMA_FAST_RANGE = [9, 12, 20, 30, 50]
EMA_SLOW_RANGE = [30, 50, 80, 120, 200]
RSI_BUY_RANGE = [55, 60, 65, 70]
RSI_SELL_RANGE = [70, 75, 80, 85]
CASH = 10_000.0


def backtest_series(closes, ema_f, ema_s, rsi, rsi_buy, rsi_sell, fee_pct):
    sig = si.signals_ema_rsi(closes, ema_f, ema_s, rsi, rsi_buy, rsi_sell)
    cash = CASH
    sh = 0.0
    eq = [CASH]
    peak = CASH
    for i in range(len(closes)):
        p = closes[i]
        if sig[i] == "BUY" and sh == 0:
            q = int((cash * POSITION_PCT * (1 - fee_pct)) // p)
            if q > 0:
                cash -= q * p * (1 + fee_pct)
                sh = q
        elif sig[i] == "SELL" and sh > 0:
            cash += sh * p * (1 - fee_pct)
            sh = 0.0
        e = cash + sh * p
        eq.append(e)
        peak = max(peak, e)
    final = cash + sh * closes[-1]
    ret = (final / CASH - 1) * 100
    dd = (min(eq) / peak - 1) * 100 if peak else 0.0
    return ret, dd


def tune_symbol(sym):
    h = get_history(sym, period=HISTORY_RANGE, interval=TIMEFRAME)
    closes = h["close"]
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
                    ret, dd = backtest_series(closes, ema_f, ema_s, rsi, rb, rs, FEE_STOCK)
                    if best is None or ret > best[0]:
                        best = (ret, ef, es, rb, rs, dd)
    return best


def main():
    print(f"Training on {TIMEFRAME} ~6mo data for {[s for s,_ in UNIVERSE]}\n")
    new_params = {}
    report = []
    for sym, is_forex in UNIVERSE:
        if is_forex:
            continue
        try:
            best = tune_symbol(sym)
            if best:
                new_params[sym] = (best[1], best[2], best[3], best[4])
                print(f"{sym:6s} -> EMA{best[1]}/{best[2]} RSI<{best[3]}/>={best[4]} "
                      f"= {best[0]:+.2f}% (maxDD {best[5]:.1f}%)")
                report.append((sym, best))
        except Exception as e:
            print(f"{sym:6s}: error {e}")

    # Write to config_day.py PER_ASSET block
    _write_config(new_params)
    avg = sum(r[1][0] for r in report) / len(report) if report else 0
    print(f"\nAverage tuned return: {avg:+.2f}%")
    print("Wrote new PER_ASSET to config_day.py.")
    return new_params, avg


def _write_config(params):
    path = "config_day.py"
    with open(path) as f:
        lines = f.readlines()
    # find PER_ASSET dict and replace its body
    out = []
    i = 0
    in_block = False
    replaced = False
    while i < len(lines):
        line = lines[i]
        if line.strip().startswith("PER_ASSET = {"):
            in_block = True
            out.append(line)
            for sym, (ef, es, rb, rs) in params.items():
                out.append(f'    "{sym}":      ({ef}, {es}, {rb}, {rs}),\n')
            # skip until closing }
            while i < len(lines) and "}" not in lines[i]:
                i += 1
            out.append("}\n")
            replaced = True
            i += 1
            continue
        out.append(line)
        i += 1
    if not replaced:
        # append at end if not found
        out.append("\nPER_ASSET = {\n")
        for sym, (ef, es, rb, rs) in params.items():
            out.append(f'    "{sym}":      ({ef}, {es}, {rb}, {rs}),\n')
        out.append("}\n")
    with open(path, "w") as f:
        f.writelines(out)


if __name__ == "__main__":
    main()
