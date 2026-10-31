"""
top5_run.py - scheduler-friendly runner for top5_bot.py.

Fires a single scan (--once) so a scheduler (e.g. Windows Task Scheduler) can
tick it every 15 minutes during US market hours. PAPER ONLY.
"""

import sys
import os

STOCKBOT_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, STOCKBOT_DIR)

from top5_bot import run_once

if __name__ == "__main__":
    run_once()
