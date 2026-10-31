# -*- coding: utf-8 -*-
"""Trade journal — JSONL, one record per event. State lives next to the bot."""
import json
import os
from datetime import datetime, timezone

JOURNAL_PATH = os.path.join(os.path.dirname(__file__), "state", "trades.jsonl")


def _now_iso():
    return datetime.now(timezone.utc).isoformat()


def log_open(trade_id, symbol, side, qty, entry_price, budget):
    """Record a position open event. Minimal — the close record carries the full P&L."""
    rec = {
        "timestamp": _now_iso(),
        "event": "open",
        "trade_id": trade_id,
        "symbol": symbol,
        "side": side,
        "qty": qty,
        "entry_price": entry_price,
        "budget": budget,
    }
    with open(JOURNAL_PATH, "a") as f:
        f.write(json.dumps(rec) + "\n")


def log_close(symbol, side, qty, entry_price, exit_price, pnl_usd, pnl_pct, reason):
    """Record a position close event. Self-contained: full P&L including entry/exit."""
    rec = {
        "timestamp": _now_iso(),
        "event": "close",
        "symbol": symbol,
        "side": side,
        "qty": qty,
        "entry_price": entry_price,
        "exit_price": exit_price,
        "pnl_usd": pnl_usd,
        "pnl_pct": pnl_pct,
        "reason": reason,
    }
    with open(JOURNAL_PATH, "a") as f:
        f.write(json.dumps(rec) + "\n")


def load_journal():
    """Return list of all close records (for weekly report stats)."""
    if not os.path.exists(JOURNAL_PATH):
        return []
    records = []
    with open(JOURNAL_PATH) as f:
        for line in f:
            line = line.strip()
            if line:
                records.append(json.loads(line))
    return records


def load_opens():
    """Return dict of open records keyed by trade_id."""
    if not os.path.exists(JOURNAL_PATH):
        return {}
    opens = {}
    with open(JOURNAL_PATH) as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            rec = json.loads(line)
            if rec.get("event") == "open":
                opens[rec["trade_id"]] = rec
    return opens


def journal_stats():
    """Quick stats from close records only."""
    closes = [r for r in load_journal() if r.get("event") == "close"]
    if not closes:
        return {"total_trades": 0, "total_pnl": 0.0, "win_rate": 0.0, "wins": 0, "losses": 0}
    wins = sum(1 for r in closes if r["pnl_usd"] > 0)
    losses = sum(1 for r in closes if r["pnl_usd"] <= 0)
    total_pnl = sum(r["pnl_usd"] for r in closes)
    return {
        "total_trades": len(closes),
        "total_pnl": total_pnl,
        "win_rate": wins / len(closes),
        "wins": wins,
        "losses": losses,
    }


if __name__ == "__main__":
    print("Journal module — run via top5_bot or weekly_report.")
    print(f"Journal path: {JOURNAL_PATH}")
    print(f"Existing records: {len(load_journal())}")
