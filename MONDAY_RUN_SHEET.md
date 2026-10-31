# StockBot — Monday Run Sheet (PAPER ONLY / fake money)

Alpaca PAPER account. No real money can move. PK-prefix keys = paper env.

================================================================
WHAT IT DOES
================================================================
- Auto-trades 8 US stocks (AAPL TSLA NVDA AMZN META AMD GOOGL MSFT) on Alpaca paper.
- Strategy: EMA + RSI trend (per-asset tuned, validated +4.48% on 6mo backtest).
- Scans every hour during US market hours (Mon–Fri 9:30–16:00 ET).
- Sends a Telegram alert on every fill + a daily summary at stop.
- Re-tunes its parameters once per day (self-training).
- 5% circuit breaker: if paper equity drops >5% from session open, it
  flattens ALL positions and halts for the session.

================================================================
STEP 0 — PREP (do once, before market open)
================================================================
cd C:/Users/Wande/stockbot
python --version            # should be Python 3.x
# keys already in secrets.py; Telegram already wired.

================================================================
STEP 1 — DRY RUN @ ~09:25 ET (no orders, just checks connectivity)
================================================================
python live.py --rank
  -> prints live prices + opportunity ranking for all 8 stocks.
  -> if it shows ranks with no error, you're connected.

================================================================
STEP 2 — FIRST LIVE TRIAL @ 09:30 ET (single scan, safe)
================================================================
python live.py --once
  -> scans once, places any paper BUY/SELL signals, then exits.
  -> check Alpaca dashboard (Positions tab) — paper fills appear there.
  -> check Telegram — you get a ping per fill.
Run this 2–3 times across the morning to watch real paper fills land.

================================================================
STEP 3 — LET IT RUN (only after Step 2 looks right)
================================================================
python live.py
  -> continuous loop. Hourly scans, auto paper orders, daily self-train.
  -> Ctrl+C to stop at any time (sends a daily summary on exit).

================================================================
OTHER COMMANDS
================================================================
python live.py --train    # force re-tune PER_ASSET now
python live.py --rank     # live opportunity board (no trading)
python daytrader.py --backtest   # 6mo backtest of the strategy
python train.py                   # re-tune + write config
python rank.py                    # standalone ranking

================================================================
HOW TO STOP
================================================================
Ctrl+C  (in the terminal running live.py). Instant. Sends daily summary.
To flatten everything manually: Alpaca dashboard -> Positions -> close,
or the bot does it automatically if the 5% breaker trips.

================================================================
RED FLAGS — STOP AND ASK IF YOU SEE THESE
================================================================
- Orders filling at wildly wrong prices (should be near market).
- Equity jumping by >5% in one scan (breaker should halt it anyway).
- Repeated "!" errors per symbol in the log.
- Any real-money movement (should be impossible — paper only).

================================================================
HONEST NOTES
================================================================
- +4.48% is BACKTESTED on 6mo data, not a live guarantee.
- Live paper fills differ (slippage, fill timing, daily re-training drift).
- Free Yahoo caps intraday history at ~6mo, so training window is 6mo.
- This is a tool, not financial advice. Paper-only by design.
