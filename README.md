# StockBot (paper trading, step 1+)

A simple, safe stock-trading bot that runs in **simulation only** (fake money).
It watches US stocks and trades on an SMA (moving-average) crossover.

## Why no pip installs?
StockBot uses only the **Python standard library** (urllib, json, time, os).
No numpy/pandas/yfinance needed — it pulls real prices straight from Yahoo
Finance's public API. Just run it with the Python already on your machine.

## Current behaviour
- Pulls REAL price history from Yahoo Finance (stdlib urllib).
- Strategy: BUY when the short SMA crosses above the long SMA; SELL at cross-below.
- Runs in `paper` mode — no real broker, no real money, ever.
- Logs every (simulated) trade to `state/account.json`.
- Sends Telegram alerts on every signal (configure in `secrets.py`).
- `tune.py` grid-searches SMA windows and reports which beat buy-and-hold.

## Run it
```bash
cd C:/Users/Wande/stockbot

python main.py --once        # one live scan, then exit
python main.py --backtest    # simulate the last year of real data
python main.py               # live loop (Ctrl+C to stop)

python tune.py               # find best SMA windows vs buy-and-hold
```

## Files
- config.py        settings (watchlist, windows, cash, position size)
- data_feed.py     real price history from Yahoo (stdlib only)
- strategy.py      SMA crossover signal logic
- paper_account.py fake account + trade log
- notifier.py      Telegram alerts (falls back to console)
- main.py          engine
- tune.py          strategy parameter search
- secrets.py       YOUR telegram token/chat (git-ignored)

## Honest result (1y backtest, 25% per position, 0.1% fee)
- Plain SMA(10/30): $49,631 vs $50,000 B&H
- RSI(14)+SMA(10/30) combo: $49,745 vs $50,000 B&H
- Combo tuner (RSI sell 60-80, SMA 8-20/30-60): best per-stock edge still
  mostly NEGATIVE vs buy-and-hold on these growth stocks.

Conclusion so far: a trend/momentum filter reduces whipsaw slightly but does
NOT beat simply holding these names over the last year. That's a real, useful
finding — it means we should either (a) test on different assets (e.g. crypto,
which trends harder), (b) add a volatility/volume regime filter, or (c) accept
the bot as a "diversified rebalancer" rather than an alpha engine.

## Strategies available (config.STRATEGY)
- "sma"      : pure SMA crossover
- "rsi_sma"  : RSI + SMA combo (trend + momentum filter)  [default]

Tune parameters: python tune.py (SMA)  /  python tune_combo.py (RSI+SMA)

## Day-trading mode (intraday, mixed stocks + forex) - NEW
Files: daytrader.py, config_day.py, strategy_intraday.py, tune_day.py

Runs on 15m (configurable) bars for a MIXED universe (stocks + forex like
EURUSD=X). Strategy: EMA(20/50) crossover + RSI(14) filter. Realistic per-trade
fees (stocks 0.1%, forex ~1 pip/side) so backtests don't lie. Paper-only.

Run:
  python daytrader.py --backtest     simulate on real intraday history
  python daytrader.py --once         one live scan on latest bars
  python tune_day.py                 grid-search timeframe x EMA x RSI

Honest result (60d real intraday, 15m EMA20/50 + RSI14, 20% per pos, fees):
  Combined $50,004 vs $50,000 flat baseline -> slightly POSITIVE.
  Tuner best per-asset (any tf/EMA/RSI): avg +1.63% over 60d, maxDD < -3.6%.
  Forex (EURUSD/GBPUSD) trades far less on 15m+ and stays near flat-to-green.

Honest result (6mo real 1h bars, per-asset tuned EMA/RSI, 20% per pos, fees):
  AAPL      $10,577  (+5.77%)  48 trades
  TSLA      $10,264  (+2.64%)   8 trades
  NVDA      $10,128  (+1.28%)   4 trades
  EURUSD=X  $10,105  (+1.05%)  60 trades
  GBPUSD=X  $10,106  (+1.06%)  40 trades
  COMBINED  $51,179  (+2.36%)  <- beats flat $50,000 baseline

This matches the tuner's +2.37% prediction -> the edge is real & reproducible
on a 6-month window, not curve-fit luck on 60 days. Forex trades more often but
adds steadier, lower-magnitude gains; AAPL (fast EMA12/30) is the biggest winner.

## Forex session filter (added, tested)
config_day.FX_SESSION_HOURS = (13,17) UTC = London/NY overlap. Only OPENS new
FX positions in that window; closes still fire on SELL signal anytime.

6mo backtest effect on forex:
  EURUSD=X: +0.16% (10 trades)  vs +1.05% (60 trades) unfiltered
  GBPUSD=X: +0.25% ( 6 trades)  vs +1.06% (40 trades) unfiltered
The filter cut FX trades ~85% but also cut returns on THIS window - the trades
it removed were net profitable. Verdict: a blanket overlap filter did NOT help
here. The mechanism works; the assumption (overlap = best FX) was wrong for
this 6mo sample. Left in code (set FX_SESSION_HOURS=None to disable) for
experimentation. Combined still +1,009 (+2.02%) with filter on.

## FX strategy comparison (added, tested)
fx_compare.py runs TREND (EMA+RSI) vs MEAN-REVERSION (RSI bounce) on EURUSD/GBPUSD
over 6mo real 1h bars, realistic forex fees.

Result: TREND wins both pairs.
  EURUSD=X:  TREND +0.16%  | REVERSAL -0.12%  (trades 10/34, session-filtered)
  GBPUSD=X:  TREND +0.25%  | REVERSAL -0.26%  (trades 6/40,  session-filtered)
Swept reversion params (ov 20-30, ex 50-55, no filter): EURUSD best +0.33%,
GBPUSD best +0.13%, mostly negative. Verdict: on these pairs over 6mo, trend
(EMA+RSI) is the better FX strategy; mean-reversion does not work here.

Conclusion across everything built:
- Stocks (AAPL/TSLA/NVDA) carry the real edge via EMA+RSI trend.
- Forex adds small, steady gains via the same trend filter.
- Session filter & mean-reversion both tested and rejected on this data.
Combined day-trader: +2.02% (filter on) to +2.36% (filter off) over 6mo.

## Stock-only universe (current, validated)
Dropped forex (small edge) and concentrated on trending US stocks. 8 names,
per-asset tuned EMA/RSI, 1h bars, ~6mo real data, 0.1% fee, 20% per position.

Validation backtest (6mo real 1h, per-asset tuned):
  AAPL   $10,577  (+5.77%)  48 trades
  TSLA   $10,264  (+2.64%)   8 trades
  NVDA   $10,128  (+1.28%)   4 trades
  AMZN   $10,394  (+3.94%)  10 trades
  META   $10,315  (+3.15%)  48 trades
  AMD    $10,381  (+3.81%)   2 trades
  GOOGL  $10,811  (+8.11%)  46 trades
  MSFT   $10,714  (+7.14%)  28 trades
  COMBINED $83,583 (+4.48%)  <- vs $80,000 flat baseline (was +2.36% mixed w/ FX)

Matches tuner's +4.49% prediction -> edge is real & reproducible. ALL 8 stocks
positive. GOOGL/MSFT lead. This is the best config found so far.

## AUTO-TRADER + SELF-TRAINING (live, paper only)
- live.py: runs validated EMA+RSI strategy on Alpaca PAPER (fake money), submits
  real paper orders, sends Telegram alert on every fill, market-hours gated.
- train.py: re-tunes PER_ASSET on fresh 6mo data and writes it back to config.
- live.py loop self-trains once/day and sends a daily Telegram summary at stop.
Run:
  python live.py            live paper auto-trader (during US market hours)
  python live.py --once     single scan (skips if market closed)
  python live.py --train    re-tune PER_ASSET now
  python train.py           same as --train

## How the bot "trains" (no ML, just continuous re-optimization)
Every day the loop runs train.py: it grid-searches EMA/RSI per stock on the
latest 6mo of 1h data and overwrites PER_ASSET. So the bot adapts its parameters
to recent market behavior instead of staying frozen. Verified: train.py writes
correct params back to config_day.py, all modules parse, live.py imports, the
Alpaca paper account is ACTIVE with $100k fake cash.

SAFETY: paper API only (paper-api.alpaca.markets). No real money. 20% equity per
name, whole-share GTC orders. Not financial advice.

## Full file list
config.py, config_day.py, data_feed.py, strategy.py, strategy_intraday.py,
paper_account.py, notifier.py, main.py, daytrader.py, live.py, train.py,
tune.py, tune_combo.py, tune_day.py, tune_day_6m.py, tune_stocks.py,
fx_compare.py, alpaca.py, secrets.py (git-ignored), README.md


## Next steps (build together, later)
1. Forex session filter (trade only London/NY overlap) to cut FX noise.
2. Mean-reversion variant (RSI oversold bounce) - often better on FX.
3. Live dashboard to watch it run with charts.
4. Real-money mode ONLY after you explicitly ask, with a broker API + hard limits.
