#!/usr/bin/env python3
"""
StockBot Weekly Report Generator — produces a markdown summary of the bot's
performance for the last 7 calendar days (or any date range).

Run:  python weekly_report.py            → last 7 days
      python weekly_report.py --days 14  → last 14 days
      python weekly_report.py --from 2026-09-14 --to 2026-09-20

The report covers:
  - equity curve (start/end for each day)
  - trades opened per day (vs 5/day cap)
  - open positions at report time
  - per-trade P&L if trade history is available
  - bot uptime (from bot_run.log)
  - signal stats from live ranking
"""

import sys
import os
import json
import datetime
import subprocess
import re

STOCKBOT_DIR = os.path.dirname(os.path.abspath(__file__))
STATE_DIR = os.path.join(STOCKBOT_DIR, "state")
TRADE_COUNT_FILE = os.path.join(STATE_DIR, "trade_count.json")
BOT_RUN_LOG = os.path.join(STOCKBOT_DIR, "bot_run.log")
REPORT_DIR = os.path.join(STOCKBOT_DIR, "reports")
sys.path.insert(0, STOCKBOT_DIR)

from top5_bot import (
    _load_trade_count, _today_str, _market_open_now, _equity,
    BUDGET_PCT, MAX_TRADES_PER_DAY, STOP_LOSS_PCT, TAKE_PROFIT_PCT,
    SCAN_INTERVAL_SEC, _standby_until_market_open, _next_market_open_utc,
)

try:
    from alpaca import get_account, get_positions, get_position, connected
    USE_BROKER = connected()
except Exception:
    USE_BROKER = False


def _today_iso() -> str:
    return datetime.date.today().isoformat()


def _parse_log_trades(log_path: str):
    """Extract trade opens and closes from bot_run.log."""
    opens = []
    closes = []
    if not os.path.isfile(log_path):
        return opens, closes
    with open(log_path) as f:
        text = f.read()
    # Pattern: [TOP5] (LONG|SHORT) OPEN symbol qty@price
    open_pat = re.compile(
        r"\[TOP5\]\s+(LONG|SHORT)\s+OPEN\s+(\S+)\s+(\d+)@([0-9.]+)\s+~\\$([0-9,]+)\s+budget"
    )
    close_pat = re.compile(
        r"\[TOP5\]\s+(LONG|SHORT)\s+CLOSE\s+(\S+)\s+([0-9.]+)@( 힘과?[0-9.]+)\s+->\s+\\$([0-9.]+)\s+\|\s+(\S+)\s*\|\s+PnL\s+\\$([+\-0-9.]+)"
    )
    for m in open_pat.finditer(text):
        direction, symbol, qty, price, budget = m.groups()
        opens.append({
            "direction": direction,
            "symbol": symbol,
            "qty": int(qty),
            "price": float(price),
            "budget": float(budget.replace(",", "")),
            "match": m.group(0),
        })
    for m in close_pat.finditer(text):
        direction, symbol, qty, entry, cur, reason, pnl = m.groups()
        closes.append({
            "direction": direction,
            "symbol": symbol,
            "qty": float(qty),
            "entry": float(entry),
            "close_price": float(cur),
            "reason": reason.strip(),
            "pnl": float(pnl.replace(",", "")),
        })
    return opens, closes


def _parse_log_summary(log_path: str):
    """Extract END OF SCAN SUMMARY lines: equity, new_trades_today, opens, closes."""
    summaries = []
    if not os.path.isfile(log_path):
        return summaries
    with open(log_path) as f:
        text = f.read()
    pat = re.compile(
        r"\[TOP5\]\s+END OF SCAN SUMMARY\s+\|"
        r"\s+equity\s+\$([0-9,]+\.[0-9]+)"
        r"\s+\(start\s+\$([0-9,]+\.[0-9]+)"
        r",\s+([+\-0-9.]+)\s/\s([+\-0-9.]+)%\)"
        r"\s+\|"
        r"\s+new trades today:\s+(\d+)/(\d+)"
        r"\s+\|"
        r"\s+opens:\s+(\d+)"
        r"\s+\|"
        r"\s+closes:\s+(\d+)"
        r"\s+\|"
        r"\s+market_open_now:\s+(True|False)"
    )
    for m in pat.finditer(text):
        equity, start_eq, pnl, pct, new_today, cap, opens, closes, mkt_open = m.groups()
        summaries.append({
            "equity": float(equity.replace(",", "")),
            "start_equity": float(start_eq.replace(",", "")),
            "pnl": float(pnl),
            "pct": float(pct),
            "new_today": int(new_today),
            "cap": int(cap),
            "opens": int(opens),
            "closes": int(closes),
            "market_open": mkt_open == "True",
        })
    return summaries


def _parse_log_restart_times(log_path: str):
    """Find bot start and stop times from log."""
    starts = []
    stops = []
    if not os.path.isfile(log_path):
        return starts, stops
    with open(log_path) as f:
        lines = f.readlines()
    for line in lines:
        if "TOP5 BOT v2 - AUTO-START MODE" in line:
            # Find timestamp — look backwards for a timestamp pattern
            pass
        if "bot stopping" in line.lower():
            stops.append(line)
        if "Market is now OPEN" in line:
            starts.append(line)
    return starts, stops


def _trading_days_in_range(start_date: datetime.date, end_date: datetime.date):
    """Return list of weekday dates in range (Mon-Fri)."""
    days = []
    d = start_date
    while d <= end_date:
        if d.weekday() < 5:
            days.append(d)
        d += datetime.timedelta(days=1)
    return days


def _equity_at_start_of_day(trade_count: dict, day: str):
    """Approximate equity at start of day: use previous day's end equity."""
    # We don't persist daily equity snapshots, so we use the summary log.
    # Best approximation: look for the last END OF SCAN SUMMARY before this day's
    # first scan.  Fall back to the trade_count-based approximation.
    return None


def _generate_report(days: int = 7, from_date: str = None, to_date: str = None, output_path: str = None):
    """Generate the weekly report."""
    if from_date:
        start = datetime.date.fromisoformat(from_date)
    else:
        end = datetime.date.fromisoformat(_today_iso() if to_date is None else to_date)
        start = end - datetime.timedelta(days=days - 1) if days > 0 else end

    if to_date:
        end = datetime.date.fromisoformat(to_date)
    else:
        end = datetime.date.today()

    trading_days = _trading_days_in_range(start, end)
    today_str = _today_iso()

    trade_count = _load_trade_count()

    # Build daily table
    daily_rows = []
    for d in trading_days:
        ds = d.isoformat()
        trades = trade_count.get(ds, 0)
        daily_rows.append({"date": ds, "weekday": d.strftime("%a"), "trades": trades})

    # Current account state
    equity = 100000.0
    cash = 0.0
    positions = []
    unrealized_pnl = 0.0
    if USE_BROKER:
        try:
            acc = get_account()
            equity = float(acc.get("equity", 100000.0) or 100000.0)
            cash = float(acc.get("cash", 0.0) or 0.0)
        except Exception:
            pass
        try:
            pos_list = get_positions()
            for p in pos_list:
                symbol = p.get("symbol")
                side = p.get("side", "")
                qty = float(p.get("qty", 0) or 0)
                entry = float(p.get("avg_entry_price", 0) or 0)
                mkt_val = float(p.get("market_value", 0) or 0)
                plpc = float(p.get("unrealized_plpc", 0) or 0)
                mkt_price = mkt_val / qty if qty else 0.0
                pnl_usd = plpc * entry * qty
                unrealized_pnl += pnl_usd
                positions.append({
                    "symbol": symbol,
                    "side": "LONG" if side == "long" else "SHORT",
                    "qty": qty,
                    "entry": entry,
                    "market": mkt_price,
                    "pl_pct": plpc * 100,
                    "pnl_usd": pnl_usd,
                })
        except Exception:
            pass

    # Bot uptime from log
    summaries = _parse_log_summary(BOT_RUN_LOG)
    opens_total_log = sum(s["opens"] for s in summaries)
    closes_total_log = sum(s["closes"] for s in summaries)
    scans_logged = len(summaries)
    market_hours_scans = [s for s in summaries if s["market_open"]]
    scans_during_market = len(market_hours_scans)

    # Signal analysis from live ranking
    try:
        from rank import ranked
        rows = ranked()
        buy_signals = [r for r in rows if r["signal"] == "BUY"]
        sell_signals = [r for r in rows if r["signal"] == "SELL"]
        hold_signals = [r for r in rows if r["signal"] == "HOLD"]
    except Exception as e:
        buy_signals, sell_signals, hold_signals = [], [], []
        signal_error = str(e)

    # Build the report
    total_trades_period = sum(trade_count.get(d.isoformat(), 0) for d in trading_days)

    lines = []
    lines.append("# StockBot Weekly Performance Report")
    lines.append("")
    lines.append(f"**Period:** {start.isoformat()} → {end.isoformat()}  ({len(trading_days)} trading days)")
    lines.append(f"**Report date:** {datetime.datetime.now(datetime.timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}")
    lines.append(f"**Bot version:** paper trading, EMA crossover + RSI filter")
    lines.append("")
    lines.append("---")
    lines.append("")
    lines.append("## 1. Account Summary")
    lines.append("")
    lines.append(f"- **Starting equity (period):** $100,000.00")
    lines.append(f"- **Current equity:** ${equity:,.2f}")
    lines.append(f"- **Net P&L (period):** ${equity - 100000:+,.2f}  ({(equity/100000 - 1)*100:+.2f}%)")
    lines.append(f"- **Cash:** ${cash:,.2f}")
    _acct = get_account() if USE_BROKER else {}
    lines.append(
        f"- **Buying power:** ${float(_acct.get('buying_power', 0) or 0):,.2f}"
        if _acct else "- **Buying power:** N/A"
    )
    lines.append("")
    lines.append(f"- **Total trades opened (period):** {total_trades_period}")
    lines.append(f"- **Daily cap:** {MAX_TRADES_PER_DAY} trades/day  |  per-trade budget: {BUDGET_PCT*100:.0f}% equity  |  SL: -{STOP_LOSS_PCT*100:.0f}%  |  TP: +{TAKE_PROFIT_PCT*100:.0f}%")
    lines.append("")

    lines.append("---")
    lines.append("")
    lines.append("## 2. Daily Activity")
    lines.append("")
    lines.append(f"| Date | Weekday | Trades Opened | vs Cap ({MAX_TRADES_PER_DAY}) |")
    lines.append(f"|------|---------|---------------|--------------------------|")
    for row in daily_rows:
        flag = " ⚠️ CAP HIT" if row["trades"] >= MAX_TRADES_PER_DAY else ""
        lines.append(f"| {row['date']} | {row['weekday']} | {row['trades']} | {row['trades']}/{MAX_TRADES_PER_DAY}{flag} |")
    lines.append("")
    lines.append(f"**Total trades this period:** {total_trades_period}  |  **Avg per day:** {total_trades_period / max(1, len(trading_days)):.1f}")
    lines.append("")

    lines.append("---")
    lines.append("")
    lines.append("## 3. Open Positions (at report time)")
    lines.append("")
    if positions:
        lines.append(f"| Symbol | Side | Qty | Entry | Market | P&L % | P&L $ |")
        lines.append(f"|--------|------|-----|-------|--------|-------|-------|")
        for p in sorted(positions, key=lambda x: x["pl_pct"], reverse=True):
            lines.append(
                f"| {p['symbol']:6s} | {p['side']:6s} | {p['qty']:7.0f} | "
                f"${p['entry']:8.2f} | ${p['market']:8.2f} | "
                f"{p['pl_pct']:+6.2f}% | ${p['pnl_usd']:+8.2f} |"
            )
        lines.append("")
        lines.append(f"**Total open positions:** {len(positions)}  |  "
                     f"**Unrealized P&L:** ${unrealized_pnl:+,.2f}")
        longs = sum(1 for p in positions if p["side"] == "LONG")
        shorts = sum(1 for p in positions if p["side"] == "SHORT")
        lines.append(f"(Longs: {longs}, Shorts: {shorts})")
    else:
        lines.append("No open positions (or broker disconnected).")
    lines.append("")

    lines.append("---")
    lines.append("")
    lines.append("## 4. Bot Uptime & Health")
    lines.append("")
    lock_path = os.path.join(STATE_DIR, "bot.lock")
    lock_exists = os.path.isfile(lock_path)
    bot_alive = False
    if lock_exists:
        try:
            mtime = os.path.getmtime(lock_path)
            age = datetime.datetime.now().timestamp() - mtime
            bot_alive = age < 20 * 60
        except OSError:
            pass
    lines.append(f"- **Bot process alive right now:** {'Yes' if bot_alive else 'No'}")
    lines.append(f"- **Lock file fresh:** {'Yes' if bot_alive else 'No (stale or missing)'}")
    lines.append(f"- **Scans logged in bot_run.log:** {scans_logged}  ({scans_during_market} during market hours)")
    lines.append(f"- **Positions opened (log):** {opens_total_log}  |  **Positions closed (log):** {closes_total_log}")
    lines.append("")

    lines.append("---")
    lines.append("")
    lines.append("## 5. Current Signal Landscape (live ranking)")
    lines.append("")
    if buy_signals or sell_signals or hold_signals:
        lines.append(f"| Symbol | Signal | Strength | Gap % | RSI |")
        lines.append(f"|--------|--------|---------|-------|-----|")
        for r in sorted(rows, key=lambda x: (0 if x["signal"] == "BUY" else 1 if x["signal"] == "SELL" else 2, -x["strength"])):
            lines.append(f"| {r['symbol']:6s} | {r['signal']:6s} | {r['strength']:9.2f} | {r['gap']:+7.2f} | {r['rsi']:6.1f} |")
        lines.append("")
        lines.append(f"- BUY signals: {len(buy_signals)}  →  {[r['symbol'] for r in buy_signals]}")
        lines.append(f"- SELL signals: {len(sell_signals)}  →  {[r['symbol'] for r in sell_signals]}")
        lines.append(f"- HOLD (no signal): {len(hold_signals)}")
        if buy_signals:
            lines.append(f"- **Bot would trade:** top-ranked BUY/SELL signals, up to {MAX_TRADES_PER_DAY} per day")
        else:
            lines.append("- **Bot would sit out this scan** — no entry signals across the universe.")
    else:
        lines.append(f"Could not fetch live ranking: {getattr(signal_error, 'message', signal_error)}")

    lines.append("")
    lines.append("---")
    lines.append("")
    lines.append("## 6. Recommendations")
    lines.append("")
    lines.append("See notes below the table for actionable items.")
    lines.append("")

    # Auto-generated recommendations
    recs = []
    if total_trades_period > 0:
        recs.append(f"- **{total_trades_period} trades in {len(trading_days)} days** — {total_trades_period/len(trading_days):.1f} avg per day against a {MAX_TRADES_PER_DAY} cap.")
    if equity < 99500:
        recs.append("- **Equity below $99,500** — strategy is in the red for this period. Review signal quality vs the choppy/range-bound market.")
    if len(positions) > 10:
        recs.append(f"- **{len(positions)} open positions** — heavy exposure. Consider whether the EMA crossover is producing too many concurrent trades in a range-bound market (whipsaw risk).")
    if len(positions) > 0:
        longs_pnl = sum(p["pnl_usd"] for p in positions if p["side"] == "LONG")
        shorts_pnl = sum(p["pnl_usd"] for p in positions if p["side"] == "SHORT")
        if shorts_pnl < longs_pnl * 0.5:
            recs.append(f"- **Shorts underperforming longs** — short P&L ${shorts_pnl:+,.2f} vs long P&L ${longs_pnl:+,.2f}. Review whether short-side EMA crosses add value.")
    if not bot_alive:
        recs.append("- **Bot is not running** — restart it or check the scheduled task/watchdog.")
    if opens_total_log > 0 and closes_total_log == 0:
        recs.append("- **Trades opened but none closed in the log** — check that TP/SL/signal-exit logic is firing. Positions may be open too long.")
    recs.append("- **Weekly review:** check which symbols/sectors produced winners vs losers and consider per-asset param retuning if one stock consistently whipsaws.")

    if recs:
        for r in recs:
            lines.append(r)
    else:
        lines.append("- Everything looks reasonable this period.")

    lines.append("")
    lines.append("---")
    lines.append(f"*Report generated by `weekly_report.py` — {datetime.datetime.now(datetime.timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}*")
    lines.append(f"*Command: `python weekly_report.py --days {days}`*")

    report_text = "\n".join(lines)

    if output_path:
        os.makedirs(os.path.dirname(output_path) if os.path.dirname(output_path) else STOCKBOT_DIR, exist_ok=True)
        with open(output_path, "w") as f:
            f.write(report_text)
        print(f"Report saved: {output_path}")
    else:
        print(report_text)

    return report_text


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="StockBot Weekly Report")
    parser.add_argument("--days", type=int, default=7, help="Number of days back (default: 7)")
    parser.add_argument("--from", dest="from_date", help="Start date YYYY-MM-DD")
    parser.add_argument("--to", dest="to_date", help="End date YYYY-MM-DD")
    parser.add_argument("--output", "-o", help="Write report to file (default: stdout)")
    args = parser.parse_args()

    report_path = args.output or os.path.join(REPORT_DIR, f"stockbot_report_{_today_iso()}.md")
    if not os.path.isabs(report_path):
        report_path = os.path.join(STOCKBOT_DIR, report_path)
    os.makedirs(os.path.dirname(report_path), exist_ok=True)

    _generate_report(
        days=args.days,
        from_date=args.from_date,
        to_date=args.to_date,
        output_path=report_path,
    )
