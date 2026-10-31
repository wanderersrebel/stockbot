"""Paper (simulated) account. Uses stdlib only. Whole shares. No real broker."""
import json
import os
from datetime import datetime


class PaperAccount:
    def __init__(self, initial_cash, state_file="state/account.json"):
        self.initial_cash = float(initial_cash)
        self.cash = self.initial_cash
        self.positions = {}    # symbol -> qty
        self.avg_cost = {}     # symbol -> avg cost
        self.trades = []       # list of trade dicts
        self.state_file = state_file
        self._load()

    def _load(self):
        if os.path.exists(self.state_file):
            with open(self.state_file) as f:
                d = json.load(f)
                self.cash = d.get("cash", self.initial_cash)
                self.positions = d.get("positions", {})
                self.avg_cost = d.get("avg_cost", {})
                self.trades = d.get("trades", [])

    def save(self):
        os.makedirs(os.path.dirname(self.state_file), exist_ok=True)
        with open(self.state_file, "w") as f:
            json.dump({
                "cash": self.cash,
                "positions": self.positions,
                "avg_cost": self.avg_cost,
                "trades": self.trades,
            }, f, indent=2)

    def buy(self, symbol, price, cash_to_use, fee_pct=0.0, ts=None):
        qty = int((cash_to_use * (1 - fee_pct)) // price)
        if qty <= 0:
            return None
        cost = qty * price
        if cost > self.cash:
            qty = int((self.cash * (1 - fee_pct)) // price)
            cost = qty * price
        if qty <= 0:
            return None
        prev_qty = self.positions.get(symbol, 0.0)
        prev_cost = self.avg_cost.get(symbol, 0.0)
        fee = cost * fee_pct
        new_qty = prev_qty + qty
        self.avg_cost[symbol] = (prev_cost * prev_qty + cost + fee) / new_qty if new_qty else 0.0
        self.positions[symbol] = new_qty
        self.cash -= (cost + fee)
        return self._record("BUY", symbol, qty, price, cost, ts=ts)

    def sell(self, symbol, price, fee_pct=0.0, ts=None):
        qty = self.positions.get(symbol, 0.0)
        if qty <= 0:
            return None
        proceeds = qty * price * (1 - fee_pct)
        cost_basis = self.avg_cost.get(symbol, 0.0) * qty
        pnl = proceeds - cost_basis
        self.cash += proceeds
        self.positions[symbol] = 0.0
        self.avg_cost[symbol] = 0.0
        return self._record("SELL", symbol, qty, price, proceeds, pnl=pnl, ts=ts)

    def _record(self, side, symbol, qty, price, value, pnl=None, ts=None):
        if isinstance(ts, str):
            tstr = ts
        elif isinstance(ts, int):
            from datetime import datetime as _dt
            tstr = _dt.utcfromtimestamp(ts).isoformat(timespec="seconds")
        else:
            tstr = (ts if ts is not None else datetime.now()).isoformat(timespec="seconds")
        trade = {
            "time": tstr,
            "side": side, "symbol": symbol, "qty": qty,
            "price": round(price, 2), "value": round(value, 2),
            "pnl": round(pnl, 2) if pnl is not None else None,
            "cash_after": round(self.cash, 2),
        }
        self.trades.append(trade)
        self.save()
        return trade

    def equity(self, prices):
        held = sum(self.positions.get(s, 0.0) * prices.get(s, 0.0) for s in self.positions)
        return self.cash + held

    def summary(self, prices):
        eq = self.equity(prices)
        pnl = eq - self.initial_cash
        pct = (pnl / self.initial_cash) * 100 if self.initial_cash else 0.0
        return (f"Equity ${eq:,.2f} | Cash ${self.cash:,.2f} | "
                f"PnL ${pnl:,.2f} ({pct:+.2f}%) | Trades {len(self.trades)}")
