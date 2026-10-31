"""
top5_bot.py - Auto-trader (PAPER ONLY).

Rules (from user spec):
- Auto both ways: BUY -> open long, SELL -> open short.
- Per trade: 4% of current paper equity.
- Daily cap: max 5 NEW trades opened per day (existing positions still managed
  for TP/SL and signal-based exits after that).
- Auto-start at market open: bot waits for 9:30 AM ET, then scans every 15 min
  for best opportunities across the full ranked universe.
- Alerts: Telegram ping on every open, close (TP/SL/signal exit), and a daily
  summary at end of session.

Run:
  python top5_run.py --once   # single scan, then exit (for scheduler)
  python top5_bot.py           # auto-start: standby -> scan -> trade up to 5/day

State files (in state/):
  trade_count.json   -> {"YYYY-MM-DD": <new_trades_opened_today>}
  positions_open.json -> persisted open-position snapshot for TP/SL tracking
    (Alpaca get_position also used live; this is backup/reset resilience.)
"""

import sys
import os
import json
import time
import datetime

from config_day import (UNIVERSE, PER_ASSET, RSI_PERIOD,
                        USE_FILTERED_UNIVERSE, FILTERED_UNIVERSE,
                        POSITION_PCT as CFG_POSITION_PCT,
                        FEE_STOCK)
from data_feed import get_history
import strategy_intraday as si
from rank import score_stock
from notifier import notify
from journal import log_open, log_close

try:
    from secrets import APCA_API_KEY_ID, APCA_API_SECRET_KEY
    from alpaca import (get_account, get_positions, get_position,
                        submit_order, close_position, connected)
    USE_BROKER = bool(APCA_API_KEY_ID and APCA_API_SECRET_KEY and connected())
except Exception:
    USE_BROKER = False

STATE_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "state")
TRADE_COUNT_FILE = os.path.join(STATE_DIR, "trade_count.json")
POSITIONS_FILE = os.path.join(STATE_DIR, "positions_open.json")
LOCK_FILE = os.path.join(STATE_DIR, "bot.lock")
DAILY_BUDGET_FILE = os.path.join(STATE_DIR, "daily_budget.json")
POSITION_TIMES_FILE = os.path.join(STATE_DIR, "position_open_times.json")

# ---- User spec constants ----
BUDGET_PCT = 0.04          # 4% of equity per trade
STOP_LOSS_PCT = 0.08       # -8% of a trade's deployed value -> close (was -5%, too tight)
TAKE_PROFIT_PCT = 0.10     # +10% of a trade's deployed value -> close
TIME_STOP_HOURS = 3        # exit if trade not working within 3 hours
MAX_TRADES_PER_DAY = 5     # max 5 new trades/day
MARKET_OPEN_ET = (9, 30)   # 9:30 AM ET
MARKET_CLOSE_ET = (16, 0)  # 4:00 PM ET
SCAN_INTERVAL_SEC = 15 * 60  # 15 minutes between scans once market is open


def _today_str():
    return datetime.date.today().isoformat()


def _market_open_now():
    """Return True if now is a US equity market day+hour (ET 9:30-16:00)."""
    now = datetime.datetime.now(datetime.timezone.utc)
    weekday = now.weekday()  # Mon=0 .. Sun=6
    if weekday >= 5:
        return False
    # ET in August = UTC-4 (EDT). Convert ET hour window to UTC.
    # 9:30 ET = 13:30 UTC ; 16:00 ET = 20:00 UTC
    et_offset_min = -4 * 60
    now_minutes_utc = now.hour * 60 + now.minute
    open_minutes_utc = (MARKET_OPEN_ET[0] * 60 + MARKET_OPEN_ET[1]) - et_offset_min
    close_minutes_utc = (MARKET_CLOSE_ET[0] * 60 + MARKET_CLOSE_ET[1]) - et_offset_min
    # wrap handling not needed: 13:30..20:00 UTC is within same day in summer
    return open_minutes_utc <= now_minutes_utc < close_minutes_utc


def _next_market_open_utc():
    """Return datetime (UTC) of the next market open (9:30 ET), today if not yet closed."""
    now = datetime.datetime.now(datetime.timezone.utc)
    weekday = now.weekday()
    # Find next weekday (skip Sat/Sun)
    days_ahead = 0
    while True:
        candidate_weekday = (weekday + days_ahead) % 7
        if candidate_weekday < 5:  # Mon-Fri
            break
        days_ahead += 1
    # Build candidate date
    candidate_date = datetime.date.today() + datetime.timedelta(days=days_ahead)
    et_offset = datetime.timedelta(hours=-4)
    market_open_et = datetime.time(9, 30)
    market_open_naive = datetime.datetime.combine(candidate_date, market_open_et)
    market_open_et_time = market_open_naive.replace(tzinfo=datetime.timezone(et_offset))
    market_open_utc = market_open_et_time.astimezone(datetime.timezone.utc)
    # If today's open already passed and we're still on today, use tomorrow
    if days_ahead == 0 and now >= market_open_utc:
        # Check if today's close has passed too; if so, move to next weekday
        market_close_naive = datetime.datetime.combine(candidate_date,
                                                        datetime.time(16, 0))
        market_close_et = market_close_naive.replace(tzinfo=datetime.timezone(et_offset))
        market_close_utc = market_close_et.astimezone(datetime.timezone.utc)
        if now >= market_close_utc:
            # Move to next weekday
            days_ahead = 1
            while True:
                candidate_weekday = (weekday + days_ahead) % 7
                if candidate_weekday < 5:
                    break
                days_ahead += 1
            candidate_date = datetime.date.today() + datetime.timedelta(days=days_ahead)
            market_open_naive = datetime.datetime.combine(candidate_date, market_open_et)
            market_open_et_time = market_open_naive.replace(tzinfo=datetime.timezone(et_offset))
            market_open_utc = market_open_et_time.astimezone(datetime.timezone.utc)
    return market_open_utc


def _load_trade_count():
    if os.path.exists(TRADE_COUNT_FILE):
        with open(TRADE_COUNT_FILE) as f:
            return json.load(f)
    return {}


def _save_trade_count(d):
    os.makedirs(STATE_DIR, exist_ok=True)
    with open(TRADE_COUNT_FILE, "w") as f:
        json.dump(d, f, indent=2)


def _load_daily_budget():
    if os.path.exists(DAILY_BUDGET_FILE):
        with open(DAILY_BUDGET_FILE) as f:
            return json.load(f)
    return {}


def _save_daily_budget(d):
    os.makedirs(STATE_DIR, exist_ok=True)
    with open(DAILY_BUDGET_FILE, "w") as f:
        json.dump(d, f, indent=2)


def _load_position_times():
    """Load {symbol: open_timestamp_iso} for time-stop tracking."""
    if os.path.exists(POSITION_TIMES_FILE):
        with open(POSITION_TIMES_FILE) as f:
            return json.load(f)
    return {}


def _save_position_times(d):
    os.makedirs(STATE_DIR, exist_ok=True)
    with open(POSITION_TIMES_FILE, "w") as f:
        json.dump(d, f, indent=2)


def _positions_snapshot():
    """Persist current open positions for resilience between scans."""
    if not USE_BROKER:
        return {}
    try:
        pos_list = get_positions()
    except Exception:
        return {}
    snap = {}
    for p in pos_list:
        sym = p.get("symbol")
        if sym:
            snap[sym] = {
                "qty": float(p.get("qty", 0)),
                "side": p.get("side", ""),        # "long" or "short"
                "avg_entry_price": float(p.get("avg_entry_price", 0) or 0),
                "unrealized_plpc": float(p.get("unrealized_plpc", 0) or 0),
                "market_value": float(p.get("market_value", 0) or 0),
            }
    return snap


def _equity():
    if not USE_BROKER:
        return 100000.0
    try:
        return float(get_account().get("equity", 0) or 0)
    except Exception:
        return 100000.0


def _rank_candidates(held_symbols):
    """Score all symbols, return ranked opportunities (not already held)."""
    rows = []
    for sym, _isfx in (FILTERED_UNIVERSE if USE_FILTERED_UNIVERSE else UNIVERSE):
        if sym in held_symbols:
            continue
        try:
            r = score_stock(sym)
            rows.append(r)
        except Exception as e:
            print(f"  ! rank {sym}: {e}")
    # sort by strength desc; BUY signals float to top within equal strength
    rows.sort(key=lambda x: (0 if x["signal"] == "BUY" else 1, -x["strength"]))
    return rows  # consider every ranked candidate; daily cap governs how many are actually opened


def _signal_for(symbol):
    """Latest EMA+RSI signal for a symbol using its per-asset params."""
    ef, es, rb, rs = PER_ASSET.get(symbol, (12, 30, 65, 85))
    h = get_history(symbol, period="1y", interval="1h")
    closes = h["close"]
    emaf = si.ema_series(closes, ef)
    emas = si.ema_series(closes, es)
    rsi = si.rsi_series(closes, RSI_PERIOD)
    sigs = si.signals_ema_rsi(closes, emaf, emas, rsi, rb, rs)
    return sigs[-1]


def _open_new_positions(ranked, per_trade_budget, trade_count_today):
    """Open long/short for ranked candidates that fire. Return list of opens.
    Each fired trade gets per_trade_budget (= equity * BUDGET_PCT),
    even if multiple signals fire in the same scan.
    """
    opens = []
    firing = []
    for r in ranked:
        sig = _signal_for(r["symbol"])
        r["_signal"] = sig
        if sig in ("BUY", "SELL"):
            firing.append(r)
    if not firing:
        return opens
    for r in firing:
        sym = r["symbol"]
        sig = r["_signal"]
        if sig not in ("BUY", "SELL"):
            continue
        # Re-check cap after each open within this scan so a single
        # scan cannot blow past MAX_TRADES_PER_DAY when many signals
        # fire at once (the bug that opened 9 trades on Sep 18).
        if trade_count_today + len(opens) >= MAX_TRADES_PER_DAY:
            print(f"  -> {sym}: daily trade cap ({MAX_TRADES_PER_DAY}) reached, skip")
            continue
        price = r["price"]
        qty = int((per_trade_budget * (1 - FEE_STOCK)) // price)
        if qty <= 0:
            continue
        side = "buy" if sig == "BUY" else "sell"  # sell = short
        try:
            res = submit_order(sym, qty, side)
            if res and res.get("id"):
                direction = "LONG" if side == "buy" else "SHORT"
                msg = (f"[TOP5] {direction} OPEN {sym} {qty}@{price:.2f} "
                       f"~${per_trade_budget:,.0f} budget | RSI {r['rsi']:.1f} "
                       f"gap {r['gap']:.2f}% strength {r['strength']:.2f}")
                log_open(res["id"], sym, direction, qty, price, per_trade_budget)
                print(msg)
                notify(msg)
                opens.append({"symbol": sym, "side": side, "qty": qty,
                              "entry_price": price, "budget": per_trade_budget})
                # Record open time for time-stop tracking
                pos_times = _load_position_times()
                pos_times[sym] = datetime.datetime.now(datetime.timezone.utc).isoformat()
                _save_position_times(pos_times)
        except Exception as e:
            print(f"  ! open {sym}: {e}")
    return opens


def _manage_open_positions(open_snapshot, new_today_count):
    """Check every open position for TP/SL, time-stop, or signal-based exit. Close as needed."""
    closes = []
    held = set(open_snapshot.keys())
    pos_times = _load_position_times()
    now = datetime.datetime.now(datetime.timezone.utc)
    for sym in list(held):
        try:
            p = get_position(sym)
        except Exception:
            continue
        if not p:
            continue
        side = p.get("side", "")         # "long" or "short"
        plpc = float(p.get("unrealized_plpc", 0) or 0)  # signed fraction
        qty = float(p.get("qty", 0) or 0)
        entry = float(p.get("avg_entry_price", 0) or 0)
        cur_price = float(p.get("market_value", 0) or 0) / qty if qty else 0.0
        if qty == 0:
            continue

        closed = False
        reason = None
        # TP / SL based on unrealized_plpc (works for long and short on Alpaca paper)
        if plpc >= TAKE_PROFIT_PCT:
            reason = f"TP +{TAKE_PROFIT_PCT*100:.0f}%"
            closed = True
        elif plpc <= -STOP_LOSS_PCT:
            reason = f"SL -{STOP_LOSS_PCT*100:.0f}%"
            closed = True

        # Time-stop: exit if trade not working within TIME_STOP_HOURS
        if not closed and sym in pos_times:
            try:
                open_time = datetime.datetime.fromisoformat(pos_times[sym])
                hold_hours = (now - open_time).total_seconds() / 3600
                if hold_hours >= TIME_STOP_HOURS:
                    reason = f"time stop ({TIME_STOP_HOURS}h)"
                    closed = True
            except Exception:
                pass

        # Signal-based reversal exit (do not count as a new trade)
        # Only exit on signal reversal if position is already losing (plpc < 0)
        # This prevents death cross from closing winners
        if not closed:
            sig = _signal_for(sym)
            if side == "long" and sig == "SELL" and plpc < 0:
                reason = "signal SELL (death cross) on losing long -> exit"
                closed = True
            elif side == "short" and sig == "BUY" and plpc < 0:
                reason = "signal BUY (golden cross) on losing short -> cover"
                closed = True

        if closed:
            try:
                close_position(sym)
                direction = "LONG" if side == "long" else "SHORT"
                pnl = plpc * (entry * qty)
                msg = (f"[TOP5] {direction} CLOSE {sym} {qty:.0f}@{entry:.2f} -> "
                       f"${cur_price:.2f} | {reason} | PnL ${pnl:+,.2f} "
                       f"({plpc*100:+.1f}%)")
                print(msg)
                notify(msg)
                log_close(sym, direction, qty, entry, cur_price, pnl, plpc * 100, reason)
                closes.append((sym, side, qty, entry, cur_price, plpc, reason))
                # Clean up position time tracking
                if sym in pos_times:
                    del pos_times[sym]
                    _save_position_times(pos_times)
            except Exception as e:
                print(f"  ! close {sym}: {e}")
    return closes


def _daily_summary(equity_start, equity_now, new_today_count, opens_today,
                   closes_today):
    pnl = equity_now - equity_start
    pct = (pnl / equity_start * 100) if equity_start else 0.0
    msg = (f"[TOP5] END OF SCAN SUMMARY | equity ${equity_now:,.2f} "
           f"(start ${equity_start:,.2f}, {pnl:+,.2f} / {pct:+.2f}%) | "
           f"new trades today: {new_today_count}/{MAX_TRADES_PER_DAY} | "
           f"opens: {len(opens_today)} | closes: {len(closes_today)} | "
           f"market_open_now: {_market_open_now()}")
    print(msg)
    notify(msg)


def run_once():
    """One scan pass. Called by top5_run.py --once (scheduler tick)."""
    if not _market_open_now():
        msg = ("[TOP5] outside US market hours (ET 9:30-16:00, Mon-Fri) - skipped")
        print(msg)
        return

    equity = _equity()
    trade_count = _load_trade_count()
    today = _today_str()
    new_today = trade_count.get(today, 0)
    opens_today = []
    closes_today = []

    # snapshot open positions before acting
    open_snap = _positions_snapshot()
    held = set(open_snap.keys())

    # 1) manage existing positions (TP/SL / signal exits)
    closes_today = _manage_open_positions(open_snap, new_today)

    # refresh held set after closes
    held = set(_positions_snapshot().keys())

    # 2) pick best opportunities not already held
    per_trade_budget = equity * BUDGET_PCT      # 4% of equity per trade
    ranked = _rank_candidates(held)

    if not ranked:
        _daily_summary(equity, equity, new_today, [], closes_today)
        return

    # 3) open new positions (long/short) for ranked firing signals
    opens_today = _open_new_positions(ranked, per_trade_budget, new_today)

    # count new openings against today's cap
    new_open_count = len(opens_today)
    new_today += new_open_count
    trade_count[today] = new_today
    _save_trade_count(trade_count)

    # 4) summary
    equity_after = _equity()
    _daily_summary(equity, equity_after, new_today, opens_today, closes_today)
    
    # Return whether any trades were opened this scan
    return len(opens_today) > 0



def _lock_pid_file():
    """Single-instance guard using a PID file in state/.

    If a running bot already owns bot.lock, exit immediately (the scheduler
    tick that woke this process should not start a second copy).

    The guard is timestamp-based rather than PID-aliveness-based: the lock is
    considered stale if it was written more than 30 minutes ago, which covers
    the common failure mode (crash / kill without cleanup) without relying on
    OS-specific process-existence checks.
    """
    # Ensure state dir exists
    os.makedirs(STATE_DIR, exist_ok=True)

    pid = os.getpid()
    now = datetime.datetime.now(datetime.timezone.utc)
    STALE_SECONDS = 30 * 60  # lock older than this = holder is dead

    if os.path.exists(LOCK_FILE):
        try:
            mtime = datetime.datetime.fromtimestamp(
                os.path.getmtime(LOCK_FILE), tz=datetime.timezone.utc
            )
        except OSError:
            mtime = None

        if mtime is not None and (now - mtime).total_seconds() < STALE_SECONDS:
            # Lock is fresh — another copy is alive
            print("[TOP5] Another bot instance appears to be running "
                  f"(lock file mtime {mtime:%H:%M:%S} UTC, "
                  f"{int((now - mtime).total_seconds())}s ago). Exiting.")
            notify("[TOP5] Another bot instance appears to be running - exiting.")
            sys.exit(0)

        # Lock is stale (or unreadable) — take it over
        try:
            os.remove(LOCK_FILE)
        except OSError:
            pass

    with open(LOCK_FILE, "w") as fh:
        fh.write(f"{pid} {now.isoformat()}\n")


def main():
    if "--once" in sys.argv:
        run_once()
        return

    # Single-instance lock (prevents double-run when scheduler fires while
    # the standby loop is already alive). PID-file based so it works on Win+Linux.
    _lock_pid_file()
    try:

        print("=" * 60)
        print("TOP5 BOT v2 - AUTO-START MODE")
        print("=" * 60)
        print(f"PAPER trading | per-trade budget: {BUDGET_PCT*100:.0f}% of equity")
        print(f"Max trades/day: {MAX_TRADES_PER_DAY} | SL: -{STOP_LOSS_PCT*100:.0f}% | "
              f"TP: +{TAKE_PROFIT_PCT*100:.0f}% | Time stop: {TIME_STOP_HOURS}h")
        print(f"Market hours: ET {MARKET_OPEN_ET[0]:02d}:{MARKET_OPEN_ET[1]:02d} - "
              f"{MARKET_CLOSE_ET[0]:02d}:{MARKET_CLOSE_ET[1]:02d} (Mon-Fri)")
        print(f"Behavior: auto-analyze when market opens, up to {MAX_TRADES_PER_DAY} trades/day")
        print(f"Scan interval: every {SCAN_INTERVAL_SEC // 60} min when market is open")
        print("=" * 60)

        # Phase 1: Only scan during market hours - exit if closed
        if not _market_open_now():
            print("[TOP5] Market is closed - bot exiting. Will restart at next market open.")
            notify("[TOP5] Market is closed - bot exiting.")
            return
        else:
            print("[TOP5] Market is open. Starting scan cycle.")

        # Phase 2: Scan loop - run repeatedly until the daily trade cap
        # is reached, the market closes, or the process is interrupted
        today = _today_str()
        trade_count = _load_trade_count()
        trades_today = trade_count.get(today, 0)

        if trades_today >= MAX_TRADES_PER_DAY:
            print(f"[TOP5] Daily trade cap ({MAX_TRADES_PER_DAY}) already reached today - nothing to do.")
            notify(f"[TOP5] Daily trade cap ({MAX_TRADES_PER_DAY}) already reached - bot idle.")
            return

        print(f"[TOP5] Scanning for opportunities...")

        while True:
            # Check if market is still open
            if not _market_open_now():
                print("[TOP5] Market closed before any trade was made today.")
                notify("[TOP5] Market closed before any trade was made today - bot stopping.")
                break

            # Run one scan
            run_once()

            # Refresh trade count
            trade_count = _load_trade_count()
            trades_today = trade_count.get(today, 0)

            # Check daily cap (one scan pass can open multiple trades;
            # so we only stop when the daily cap is actually reached)
            if trades_today >= MAX_TRADES_PER_DAY:
                print(f"[TOP5] Daily trade cap ({MAX_TRADES_PER_DAY}) reached - stopping.")
                notify(f"[TOP5] Daily trade cap ({MAX_TRADES_PER_DAY}) reached - bot stopping.")
                break

            # Wait before next scan
            print(f"[TOP5] No trade yet. Sleeping {SCAN_INTERVAL_SEC // 60} min until next scan...")
            # Sleep in 1-min increments to respect market close
            slept = 0
            while slept < SCAN_INTERVAL_SEC:
                if not _market_open_now():
                    print("[TOP5] Market closed during sleep - stopping.")
                    notify("[TOP5] Market closed during sleep - bot stopping.")
                    return
                time.sleep(60)
                slept += 60
    finally:
        try:
            os.remove(LOCK_FILE)
        except OSError:
            pass


if __name__ == "__main__":
    main()
