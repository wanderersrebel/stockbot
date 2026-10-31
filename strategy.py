"""Trading strategies (stdlib only).

1. Pure SMA crossover (add_signals) - baseline.
2. RSI + SMA combo (add_signals_combo) - trend + momentum filter.
"""


def _sma(series, window, i):
    """Simple moving average of `series` ending at index i (inclusive)."""
    if i + 1 < window:
        return None
    return sum(series[i - window + 1:i + 1]) / window


def add_signals(closes, short, long):
    """Pure SMA crossover. Returns list of BUY/SELL/HOLD aligned to closes.

    BUY  = short SMA crosses above long SMA
    SELL = short SMA crosses below long SMA
    """
    n = len(closes)
    sig = ["HOLD"] * n
    s_prev = l_prev = None
    for i in range(n):
        s_now = _sma(closes, short, i)
        l_now = _sma(closes, long, i)
        if s_now is None or l_now is None:
            s_prev, l_prev = s_now, l_now
            continue
        if s_prev is not None and l_prev is not None:
            if s_prev <= l_prev and s_now > l_now:
                sig[i] = "BUY"
            elif s_prev >= l_prev and s_now < l_now:
                sig[i] = "SELL"
        s_prev, l_prev = s_now, l_now
    return sig


def latest_signal(closes, short, long):
    """Return (signal, price) for the most recent bar (pure SMA)."""
    sig = add_signals(closes, short, long)
    return sig[-1], closes[-1]


# ---------------- RSI ----------------

def rsi_series(closes, period=14):
    """Wilder's RSI. Returns list aligned to closes; None before enough data."""
    n = len(closes)
    out = [None] * n
    if n <= period:
        return out
    gains, losses = [], []
    for i in range(1, n):
        d = closes[i] - closes[i - 1]
        gains.append(max(d, 0.0))
        losses.append(max(-d, 0.0))

    def rsi_from(ag, al):
        if al == 0:
            return 100.0
        rs = ag / al
        return 100.0 - 100.0 / (1.0 + rs)

    avg_gain = sum(gains[:period]) / period
    avg_loss = sum(losses[:period]) / period
    out[period] = rsi_from(avg_gain, avg_loss)
    for j in range(period, n - 1):
        avg_gain = (avg_gain * (period - 1) + gains[j]) / period
        avg_loss = (avg_loss * (period - 1) + losses[j]) / period
        out[j + 1] = rsi_from(avg_gain, avg_loss)
    return out


def add_signals_combo_r(closes, rsi, short, long,
                        rsi_buy_min=0, rsi_buy_max=70, rsi_sell_min=75):
    """RSI + SMA combo using a PRECOMPUTED rsi list.

    BUY  = golden cross (short SMA crosses above long) AND
           rsi_buy_min <= RSI <= rsi_buy_max  (room to run, not overbought)
    SELL = death cross OR RSI >= rsi_sell_min (overbought exit)
    """
    n = len(closes)
    sig = ["HOLD"] * n
    s_prev = l_prev = None
    pos = False
    for i in range(n):
        s_now = _sma(closes, short, i)
        l_now = _sma(closes, long, i)
        r = rsi[i]
        if s_now is None or l_now is None or r is None:
            s_prev, l_prev = s_now, l_now
            continue
        golden = (s_prev is not None and l_prev is not None
                  and s_prev <= l_prev and s_now > l_now)
        death = (s_prev is not None and l_prev is not None
                 and s_prev >= l_prev and s_now < l_now)
        if not pos:
            if golden and rsi_buy_min <= r <= rsi_buy_max:
                sig[i] = "BUY"
                pos = True
        else:
            if death or r >= rsi_sell_min:
                sig[i] = "SELL"
                pos = False
        s_prev, l_prev = s_now, l_now
    return sig


def add_signals_combo(closes, short, long, rsi_period=14,
                      rsi_buy_min=0, rsi_buy_max=70, rsi_sell_min=75):
    """RSI + SMA combo; computes RSI internally (convenience wrapper)."""
    rsi = rsi_series(closes, rsi_period)
    return add_signals_combo_r(closes, rsi, short, long,
                               rsi_buy_min, rsi_buy_max, rsi_sell_min)


def latest_signal_combo(closes, short, long,
                        rsi_period=14, rsi_buy_max=70, rsi_sell_min=75):
    sig = add_signals_combo(closes, short, long, rsi_period, 0, rsi_buy_max, rsi_sell_min)
    return sig[-1], closes[-1]
