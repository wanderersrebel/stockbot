"""Intraday strategy helpers (stdlib only): EMA, RSI, EMA+RSI signals."""


def ema_series(closes, period):
    """Exponential moving average aligned to closes; None until enough data."""
    n = len(closes)
    out = [None] * n
    if n < period:
        return out
    k = 2.0 / (period + 1)
    # seed with SMA
    ema = sum(closes[:period]) / period
    out[period - 1] = ema
    for i in range(period, n):
        ema = closes[i] * k + ema * (1 - k)
        out[i] = ema
    return out


def rsi_series(closes, period=14):
    """Wilder's RSI aligned to closes; None before enough data."""
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


def signals_rsi_reversion(closes, rsi, rsi_oversold=30, rsi_exit=50,
                         allow_buy_hours=None, hours=None):
    """Mean-reversion on RSI: buy oversold bounces, sell on recovery.

    BUY  = RSI crosses UP through rsi_oversold (was below, now above)
    SELL = RSI crosses DOWN through rsi_exit (recovered) OR
           RSI >= 75 (hard stop on strong rally reversal risk)
    Position-aware: one entry per exit.
    """
    n = len(closes)
    sig = ["HOLD"] * n
    pos = False
    r_prev = None
    for i in range(n):
        r = rsi[i]
        if r is None or r_prev is None:
            r_prev = r
            continue
        ok_hour = True
        if allow_buy_hours is not None and hours is not None:
            ok_hour = (allow_buy_hours[0] <= hours[i] < allow_buy_hours[1])
        cross_up = (r_prev < rsi_oversold and r >= rsi_oversold)
        cross_dn = (r_prev >= rsi_exit and r < rsi_exit)
        if not pos:
            if cross_up and ok_hour:
                sig[i] = "BUY"
                pos = True
        else:
            if cross_dn or r >= 75:
                sig[i] = "SELL"
                pos = False
        r_prev = r
    return sig


def signals_ema_rsi(closes, ema_f, ema_s, rsi,
                    rsi_buy_max=70, rsi_sell_min=75,
                    allow_buy_hours=None, hours=None):
    """EMA crossover + RSI filter. Returns list of BUY/SELL/HOLD.

    BUY  = fast EMA crosses above slow EMA AND RSI < rsi_buy_max
    SELL = fast EMA crosses below slow EMA OR RSI >= rsi_sell_min
    Holds position state so it only acts on transitions.

    allow_buy_hours: optional (start, end) UTC hour range (24h, end exclusive).
    If provided (with a matching `hours` list of UTC hours per bar), BUY signals
    outside that window are suppressed (existing positions still get SELL).
    Used to trade only the London/NY forex overlap (e.g. (13, 17)).
    """
    n = len(closes)
    sig = ["HOLD"] * n
    f_prev = s_prev = None
    pos = False
    for i in range(n):
        f = ema_f[i]
        s = ema_s[i]
        r = rsi[i]
        if f is None or s is None or r is None:
            f_prev, s_prev = f, s
            continue
        cross_up = (f_prev is not None and s_prev is not None
                    and f_prev <= s_prev and f > s)
        cross_dn = (f_prev is not None and s_prev is not None
                    and f_prev >= s_prev and f < s)
        ok_hour = True
        if allow_buy_hours is not None and hours is not None:
            ok_hour = (allow_buy_hours[0] <= hours[i] < allow_buy_hours[1])
        if not pos:
            if cross_up and r < rsi_buy_max and ok_hour:
                sig[i] = "BUY"
                pos = True
        else:
            if cross_dn or r >= rsi_sell_min:
                sig[i] = "SELL"
                pos = False
        f_prev, s_prev = f, s
    return sig
