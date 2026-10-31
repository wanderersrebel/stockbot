"""Alpaca PAPER-TRADING client (stdlib only, no external deps).

Connects to Alpaca's PAPER environment. NO real money is ever at risk - the
paper API uses fake cash. Your keys live in secrets.py (git-ignored).

Endpoints used (v2):
  GET  /v2/account
  GET  /v2/positions
  GET  /v2/positions/{symbol}
  POST /v2/orders        (market, buy/sell, qty)
  DELETE /v2/positions/{symbol}  (flat a position)

Set APCA_API_KEY_ID and APCA_API_SECRET_KEY in secrets.py.
"""
import urllib.request
import urllib.parse
import json

PAPER_BASE = "https://paper-api.alpaca.markets"
DATA_BASE = "https://data.alpaca.markets"

_HEADERS_KEYS = ("APCA_API_KEY_ID", "APCA_API_SECRET_KEY")


def _headers():
    from secrets import APCA_API_KEY_ID, APCA_API_SECRET_KEY
    return {
        "APCA-API-KEY-ID": APCA_API_KEY_ID,
        "APCA-API-SECRET-KEY": APCA_API_SECRET_KEY,
        "Content-Type": "application/json",
    }


def _req(method, url, body=None):
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(url, data=data, headers=_headers(), method=method)
    with urllib.request.urlopen(req, timeout=20) as r:
        txt = r.read().decode()
        return json.loads(txt) if txt else {}


def get_account():
    return _req("GET", f"{PAPER_BASE}/v2/account")


def get_positions():
    return _req("GET", f"{PAPER_BASE}/v2/positions")


def get_position(symbol):
    try:
        return _req("GET", f"{PAPER_BASE}/v2/positions/{symbol}")
    except urllib.error.HTTPError as e:
        if e.code == 404:
            return None
        raise


def submit_order(symbol, qty, side):
    """side = 'buy' or 'sell'. Market order, good-for-day, paper."""
    body = {
        "symbol": symbol,
        "qty": str(int(qty)),
        "side": side,
        "type": "market",
        "time_in_force": "gtc",
    }
    return _req("POST", f"{PAPER_BASE}/v2/orders", body)


def close_position(symbol):
    try:
        return _req("DELETE", f"{PAPER_BASE}/v2/positions/{symbol}")
    except urllib.error.HTTPError as e:
        if e.code == 404:
            return None
        raise


def connected():
    try:
        get_account()
        return True
    except Exception:
        return False
