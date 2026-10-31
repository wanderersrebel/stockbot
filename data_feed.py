"""Data feed: real price history from Yahoo Finance via stdlib only (no numpy/pandas).

Returns a dict: {"dates": [...], "close": [...]} of floats/labels.
"""
import urllib.request
import json

_HEADERS = {"User-Agent": "Mozilla/5.0 (StockBot)"}


def get_history(symbol: str, period: str = "6mo", interval: str = "1d") -> dict:
    """Return {'dates': [...], 'close': [...]} for the symbol."""
    url = (f"https://query1.finance.yahoo.com/v8/finance/chart/{symbol}"
           f"?range={period}&interval={interval}")
    req = urllib.request.Request(url, headers=_HEADERS)
    with urllib.request.urlopen(req, timeout=20) as r:
        data = json.loads(r.read().decode())
    res = data["chart"]["result"][0]
    ts = res["timestamp"]
    closes = res["indicators"]["quote"][0]["close"]
    out_dates, out_close = [], []
    for t, c in zip(ts, closes):
        if c is None:
            continue
        out_dates.append(t)
        out_close.append(float(c))
    if not out_close:
        raise ValueError(f"No data returned for {symbol}")
    return {"dates": out_dates, "close": out_close}


def get_price(symbol: str) -> float:
    h = get_history(symbol, period="5d", interval="1d")
    return h["close"][-1]
