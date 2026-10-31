"""Opportunity ranker + opportunity-weighted sizing (stdlib only).

Scores each stock in the universe by technical "strength" so we can see where
the biggest opportunity is RIGHT NOW, and size positions by that strength
instead of flat 20% each.

Score components (each 0..1, combined):
  - trend_gap: how far fast EMA is above slow EMA (normalized)
  - rsi_momentum: RSI climbing toward but below overbought (room to run)
  - cross_proximity: how close the fast/slow EMAs are to a fresh cross

signal_state: from strategy_intraday.signals_ema_rsi (BUY/SELL/HOLD) is the
actual trigger; the score is used for RANKING and SIZING, not triggering.

Run:  python rank.py      (prints live ranked opportunities + a Telegram ping)
"""
from config_day import (UNIVERSE, TIMEFRAME, HISTORY_RANGE, PER_ASSET,
                        EMA_FAST, EMA_SLOW, RSI_PERIOD, RSI_BUY_MAX,
                        RSI_SELL_MIN, POSITION_PCT)
from data_feed import get_history
import strategy_intraday as si


def params_for(sym):
    return PER_ASSET.get(sym, (EMA_FAST, EMA_SLOW, RSI_BUY_MAX, RSI_SELL_MIN))


def score_stock(sym):
    """Return dict with price, signal, strength(0..1), components."""
    h = get_history(sym, period=HISTORY_RANGE, interval=TIMEFRAME)
    closes = h["close"]
    ef, es, rb, rs = params_for(sym)
    emaf = si.ema_series(closes, ef)
    emas = si.ema_series(closes, es)
    rsi = si.rsi_series(closes, RSI_PERIOD)
    sig = si.signals_ema_rsi(closes, emaf, emas, rsi, rb, rs)
    i = len(closes) - 1

    gap = (emaf[i] - emas[i]) / emas[i] * 100 if emas[i] else 0.0   # %
    # trend_gap: map +/-3% gap to 0..1 (cap)
    trend_gap = max(0.0, min(1.0, (gap + 1.0) / 4.0))   # -1%->0, +3%->1
    # rsi_momentum: best when RSI climbing in 40-65 zone (room to run)
    r = rsi[i] if rsi[i] is not None else 50.0
    if r <= 30:
        rsi_mom = 0.4          # oversold but no confirmation yet
    elif r < 65:
        rsi_mom = 0.5 + (r - 30) / 70.0   # 30->0.5, 65->1.0
    else:
        rsi_mom = max(0.0, 1.0 - (r - 65) / 35.0)  # overbought -> fades
    # cross_proximity: |gap| small = close to cross
    cross_prox = max(0.0, 1.0 - abs(gap) / 1.0)    # within 1% = high
    strength = 0.5 * trend_gap + 0.3 * rsi_mom + 0.2 * cross_prox
    return {
        "symbol": sym, "price": closes[-1], "signal": sig[i],
        "gap": gap, "rsi": r, "strength": strength,
        "trend_gap": trend_gap, "rsi_mom": rsi_mom, "cross_prox": cross_prox,
    }


def ranked():
    rows = [score_stock(s) for s, _ in UNIVERSE]
    # rank by strength, but live BUY signals float to top regardless
    rows.sort(key=lambda r: (0 if r["signal"] == "BUY" else 1, -r["strength"]))
    return rows


def size_weights(rows):
    """Opportunity-weighted allocation. BUY signals get weight ~ strength;
    others get near-zero. Returns {symbol: fraction_of_POSITION_PCT_budget}."""
    buy = [r for r in rows if r["signal"] == "BUY"]
    if not buy:
        return {}
    total = sum(max(r["strength"], 0.05) for r in buy)
    return {r["symbol"]: max(r["strength"], 0.05) / total for r in buy}


def main():
    rows = ranked()
    print(f"Live opportunity ranking ({TIMEFRAME}, {len(rows)} symbols)\n")
    print(f"{'SYM':6s} {'signal':>6s} {'strength':>9s} {'gap%':>7s} {'RSI':>6s}  allocation")
    for r in rows:
        print(f"{r['symbol']:6s} {r['signal']:>6s} {r['strength']:9.2f} "
              f"{r['gap']:7.2f} {r['rsi']:6.1f}")
    wts = size_weights(rows)
    if wts:
        print("\nOpportunity-weighted BUY allocation (of total budget):")
        for s, w in sorted(wts.items(), key=lambda x: -x[1]):
            print(f"  {s}: {w*100:.1f}%")
    else:
        print("\nNo live BUY signals right now - ranking shows relative strength only.")
    return rows, wts


if __name__ == "__main__":
    main()
