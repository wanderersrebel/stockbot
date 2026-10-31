"""StockBot configuration. Edit the values below to change behaviour."""

# ---- What to trade (US stock tickers) ----
WATCHLIST = ["AAPL", "MSFT", "TSLA", "NVDA", "AMZN"]

# ---- Mode ----
# "paper"  = simulated trades, FAKE money, nothing is ever bought/sold for real.
# (real-money mode is NOT implemented yet — and won't be until you say so.)
MODE = "paper"

# ---- Strategy ----
# STRATEGY options: "sma" (pure crossover) or "rsi_sma" (RSI + SMA combo).
STRATEGY = "rsi_sma"

# SMA (moving-average) crossover windows
# BUY when short crosses above long; SELL when it crosses below.
SHORT_WINDOW = 10   # days
LONG_WINDOW = 30    # days

# RSI + SMA combo settings (used when STRATEGY = "rsi_sma")
RSI_PERIOD = 14
RSI_BUY_MIN = 0     # only buy when RSI >= this (0 = no lower filter)
RSI_BUY_MAX = 70    # ...and RSI <= this (avoid buying when overbought)
RSI_SELL_MIN = 75   # sell when RSI >= this (overbought exit) or on death cross

# ---- Paper account ----
INITIAL_CASH = 10_000.0   # starting fake money (USD)
POSITION_PCT = 0.25       # use 25% of cash per buy

# ---- Live loop ----
SCAN_INTERVAL_SECONDS = 60  # how often to re-check signals when looping

# ---- Notifications (wire up later; leave blank for now) ----
TELEGRAM_TOKEN = ""
TELEGRAM_CHAT_ID = ""
EMAIL_TO = ""
