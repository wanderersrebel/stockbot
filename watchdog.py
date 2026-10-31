#!/usr/bin/env python3
"""StockBot watchdog - keeps top5_bot.py alive during market hours.
Runs as a Windows Scheduled Task every 5 minutes (or as a persistent loop).
If the bot is not running (no lock file / stale lock / dead PID), it restarts it.
Enhanced with per-iteration logging and exception catching to diagnose crashes.
"""

import os
import sys
import time
import subprocess
import datetime
import traceback

STOCKBOT_DIR = r"C:\Users\Wande\stockbot"
BOT_SCRIPT = os.path.join(STOCKBOT_DIR, "top5_bot.py")
LOCK_FILE = os.path.join(STOCKBOT_DIR, "state", "bot.lock")
PYTHON = r"C:\Users\Wande\AppData\Local\hermes\hermes-agent\venv\Scripts\python.exe"
LOG_FILE = os.path.join(STOCKBOT_DIR, "watchdog.log")
STATE_FILE = os.path.join(STOCKBOT_DIR, "state", "watchdog_state.json")

MARKET_OPEN_ET = (9, 30)
MARKET_CLOSE_ET = (16, 0)


def _market_hours_active() -> bool:
    """Return True if now is a US equity market weekday 9:30-16:00 ET."""
    now = datetime.datetime.now(datetime.timezone.utc)
    if now.weekday() >= 5:
        return False
    et_offset = datetime.timedelta(hours=-4)
    et = now.astimezone(datetime.timezone(et_offset))
    return datetime.time(MARKET_OPEN_ET[0], MARKET_OPEN_ET[1]) <= et.time() < datetime.time(MARKET_CLOSE_ET[0], MARKET_CLOSE_ET[1])


def _lock_is_alive() -> bool:
    """Check the bot.lock file - is there a live bot instance?"""
    if not os.path.isfile(LOCK_FILE):
        return False
    try:
        mtime = os.path.getmtime(LOCK_FILE)
        age = time.time() - mtime
        # Lock older than 20 minutes = stale = bot is dead
        if age > 20 * 60:
            return False
        # Read PID and check if it's alive
        with open(LOCK_FILE) as f:
            first_line = f.readline().strip()
        if not first_line:
            return False
        parts = first_line.split()
        if parts:
            try:
                pid = int(parts[0])
                # Check process exists via tasklist on Windows (more reliable than os.kill)
                try:
                    import subprocess as _sp
                    result = _sp.run(
                        ["tasklist", "/FI", f"PID eq {pid}", "/NH"],
                        capture_output=True, text=True, timeout=5
                    )
                    return str(pid) in result.stdout
                except Exception:
                    # Fallback: try os.kill
                    try:
                        os.kill(pid, 0)
                        return True
                    except (OSError, ProcessLookupError):
                        return False
            except (ValueError, IndexError):
                return False
    except (OSError, IOError):
        return False
    return False


def _log(msg: str):
    """Write a timestamped log line to both stdout and the log file."""
    ts = datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
    line = f"[{ts}] {msg}"
    try:
        print(line, flush=True)
    except Exception as e:
        pass  # can't log the logging failure
    try:
        os.makedirs(os.path.dirname(LOG_FILE), exist_ok=True)
        with open(LOG_FILE, "a") as f:
            f.write(line + "\n")
    except Exception as e:
        try:
            print(f"WATCHDOG: _log write failed: {e}", flush=True)
        except:
            pass


def _save_state(action: str, detail: str = ""):
    """Persist watchdog state for debugging."""
    state = {
        "last_action": action,
        "last_detail": detail,
        "last_run": datetime.datetime.now(datetime.timezone.utc).isoformat()
    }
    try:
        os.makedirs(os.path.dirname(STATE_FILE), exist_ok=True)
        with open(STATE_FILE, "w") as f:
            import json
            json.dump(state, f, indent=2)
    except Exception as e:
        _log(f"_save_state failed: {e}")


def _start_bot():
    """Launch top5_bot.py as a background process."""
    _log("WATCHDOG: starting bot...")
    try:
        proc = subprocess.Popen(
            [PYTHON, BOT_SCRIPT],
            cwd=STOCKBOT_DIR,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            creationflags=subprocess.CREATE_NO_WINDOW,
        )
        _log(f"WATCHDOG: bot launched, PID {proc.pid}")
        _save_state("started", f"pid={proc.pid}")
        return True
    except Exception as e:
        _log(f"WATCHDOG: FAILED to start bot: {e}")
        _save_state("start_failed", str(e))
        return False


def _wait_market_open():
    """Sleep until next market open (9:30 ET) - used between sessions."""
    _log("WATCHDOG: market closed, waiting for next open...")
    now = datetime.datetime.now(datetime.timezone.utc)
    while not _market_hours_active():
        for delta in range(7):
            candidate = now + datetime.timedelta(days=delta)
            if candidate.weekday() < 5:
                et_offset = datetime.timedelta(hours=-4)
                et_time = datetime.time(MARKET_OPEN_ET[0], MARKET_OPEN_ET[1])
                market_open = datetime.datetime.combine(
                    candidate.date(), et_time
                ).replace(tzinfo=datetime.timezone(et_offset))
                if market_open > now:
                    wait = (market_open - now).total_seconds()
                    if wait <= 0:
                        break
                    hours = wait / 3600
                    _log(f"WATCHDOG: next market open in {hours:.1f} hours")
                    # Sleep in 60s increments so we can check for market open
                    sleep_remaining = wait
                    sleep_iterations = 0
                    while sleep_remaining > 0 and not _market_hours_active():
                        sleep_chunk = min(60, sleep_remaining)
                        _log(f"WATCHDOG: sleeping {sleep_chunk}s (iteration {sleep_iterations})")
                        time.sleep(sleep_chunk)
                        sleep_remaining -= sleep_chunk
                        sleep_iterations += 1
                        now = datetime.datetime.now(datetime.timezone.utc)
                        if _market_hours_active():
                            break
                    break
        break
    _log("WATCHDOG: market is now open")


def main_loop():
    """Main watchdog loop with per-iteration logging and exception handling."""
    _log("WATCHDOG: starting (PID {})".format(os.getpid()))
    _save_state("watchdog_started", f"pid={os.getpid()}")
    _log("WATCHDOG: entering main loop")

    iteration = 0
    while True:
        iteration += 1
        try:
            now = datetime.datetime.now(datetime.timezone.utc)
            market_open = _market_hours_active()
            _log(f"WATCHDOG: loop #{iteration} tick - market_open={market_open}")

            if market_open:
                # During market hours: check every 5 minutes
                lock_alive = _lock_is_alive()
                _log(f"WATCHDOG: lock alive={lock_alive}")
                if lock_alive:
                    _log("WATCHDOG: bot is alive, nothing to do")
                else:
                    _log("WATCHDOG: bot is NOT running - restarting")
                    _start_bot()
                _log("WATCHDOG: sleeping 300s")
                time.sleep(300)
            else:
                # Outside market hours: wait for market open, then start
                _log("WATCHDOG: outside market hours, calling _wait_market_open")
                _wait_market_open()
                _log("WATCHDOG: _wait_market_open returned")
                lock_alive = _lock_is_alive()
                _log(f"WATCHDOG: lock alive after wait={lock_alive}")
                if not lock_alive:
                    _log("WATCHDOG: starting bot after market open")
                    _start_bot()
                _log("WATCHDOG: sleeping 300s after market open")
                time.sleep(300)
        except Exception as e:
            _log(f"WATCHDOG: EXCEPTION in loop #{iteration}: {e}")
            _log(f"WATCHDOG: traceback: {traceback.format_exc()}")
            _save_state("exception", str(e))
            time.sleep(60)


def scheduled_tick():
    """Single tick - meant to be called by a scheduler every 5 minutes."""
    market_open = _market_hours_active()
    _log(f"TICK: market_open={market_open}, bot_alive={_lock_is_alive()}")

    if not market_open:
        _save_state("tick_outside_hours", "bot_not_started_waiting_for_market")
        return

    if not _lock_is_alive():
        _log("TICK: bot not alive - starting")
        _start_bot()
    else:
        _log("TICK: bot alive - OK")


if __name__ == "__main__":
    _log("WATCHDOG: module loaded, __name__={}".format(__name__))
    if "--once" in sys.argv or "-t" in sys.argv:
        _log("WATCHDOG: running scheduled_tick")
        scheduled_tick()
    else:
        _log("WATCHDOG: running main_loop")
        main_loop()
