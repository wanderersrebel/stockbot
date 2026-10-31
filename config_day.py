"""Day-trading config. Mixed universe: stocks + forex. 5-minute bars.

Forex symbols on Yahoo end in =X (e.g. EURUSD=X). Prices are quoted rates.
PIP_VALUE is the $ per 1 pip move on a 1-unit (1 lot) position used only to
express forex fees; position sizing is still done in account $ via POSITION_PCT.
"""

# (symbol, is_forex) - stock-only universe (FX edge was small; stocks carry it)
UNIVERSE = [
    # Technology
    ("AAPL", False), ("MSFT", False), ("GOOGL", False), ("GOOG", False),
    ("META", False), ("NVDA", False), ("AMD", False), ("INTC", False),
    ("CRM", False), ("ORCL", False), ("IBM", False), ("NOW", False),
    ("PANW", False), ("SNOW", False), ("DDOG", False), ("ZS", False),
    ("CRWD", False), ("FTNT", False), ("NET", False), ("SPLK", False),
    ("MDB", False), ("OKTA", False), ("CYBR", False), ("FFIV", False),
    ("CDNS", False), ("SNPS", False), ("ANSS", False), ("ACN", False),
    ("HPQ", False), ("WDAY", False), ("ZM", False), ("RBLX", False),
    ("UBER", False), ("HOOD", False), ("PLTR", False), ("COIN", False),
    ("ADBE", False), ("QCOM", False), ("TXN", False), ("AVGO", False),
    ("KLAC", False), ("LRCX", False),
    # Communication Services / Media
    ("DIS", False), ("WBD", False), ("NFLX", False), ("CMCSA", False),
    ("T", False), ("VZ", False), ("TMUS", False), ("CHTR", False),
    ("LYV", False), ("SPOT", False), ("SE", False), ("PARA", False),
    ("BABA", False),
    # Consumer Discretionary
    ("AMZN", False), ("TSLA", False), ("HD", False), ("LOW", False),
    ("MCD", False), ("SBUX", False), ("NKE", False), ("TGT", False),
    ("WMT", False), ("COST", False), ("BKNG", False), ("ABNB", False),
    ("GM", False), ("F", False), ("DKNG", False), ("ROST", False),
    ("AZO", False), ("ORLY", False), ("TSCO", False), ("GPS", False),
    ("LEVI", False), ("DLTR", False),
    # Consumer Staples
    ("PG", False), ("KO", False), ("PEP", False), ("KMB", False),
    ("CL", False), ("UL", False), ("MO", False), ("PM", False),
    ("NVS", False), ("MKC", False), ("SJM", False), ("HSY", False),
    # Energy
    ("XOM", False), ("CVX", False), ("COP", False), ("EOG", False),
    ("SLB", False), ("OXY", False), ("MPC", False), ("VLO", False),
    ("PSX", False), ("HES", False), ("DVN", False), ("COG", False),
    ("MRO", False), ("HAL", False), ("BKR", False),
    # Financials
    ("JPM", False), ("BAC", False), ("WFC", False), ("GS", False),
    ("MS", False), ("C", False), ("V", False), ("MA", False),
    ("AXP", False), ("BLK", False), ("SCHW", False), ("SPGI", False),
    ("MCO", False), ("USB", False), ("PNC", False), ("TFC", False),
    ("COF", False), ("DFS", False), ("AIG", False), ("MET", False),
    ("PRU", False), ("BEN", False), ("RE", False), ("AFL", False),
    ("KEY", False), ("FITB", False), ("HBAN", False), ("ZION", False),
    # Health Care
    ("JNJ", False), ("UNH", False), ("LLY", False), ("PFE", False),
    ("ABBV", False), ("MRK", False), ("TMO", False), ("ABT", False),
    ("DHR", False), ("SYK", False), ("BSX", False), ("MDT", False),
    ("ZTS", False), ("BIIB", False), ("AMGN", False), ("GILD", False),
    ("MRNA", False), ("BNTX", False), ("ISRG", False), ("DXCM", False),
    ("WAT", False), ("CI", False), ("ELV", False), ("MCK", False),
    ("BDX", False),
    # Industrials
    ("CAT", False), ("DE", False), ("HON", False), ("GE", False),
    ("MMM", False), ("BA", False), ("RTX", False), ("LMT", False),
    ("NOC", False), ("GD", False), ("FDX", False), ("UPS", False),
    ("DAL", False), ("UAL", False), ("ROK", False), ("CSX", False),
    ("NSC", False), ("UNP", False), ("WM", False), ("RSG", False),
    ("ECL", False), ("ITW", False), ("EMR", False), ("IR", False),
    ("AXON", False),
    # Materials
    ("LIN", False), ("APD", False), ("ECL", False), ("DD", False),
    ("ALB", False), ("FCX", False), ("NEM", False), ("GOLD", False),
    ("SCCO", False),
    # Real Estate
    ("PLD", False), ("AMT", False), ("EQIX", False), ("DLR", False),
    ("O", False), ("VICI", False), ("EQR", False), ("SPG", False),
    ("MAA", False), ("WELL", False),
    # Utilities
    ("NEE", False), ("DUK", False), ("SO", False), ("D", False),
    ("AEP", False), ("EXC", False), ("SRE", False), ("EIX", False),
    ("PEG", False), ("XEL", False),
    # ETFs (market / sector exposure)
    ("SPY", False), ("QQQ", False), ("IWM", False), ("DIA", False),
    ("XLK", False), ("XLF", False), ("XLE", False), ("VTV", False),
    ("IEFA", False), ("EEM", False),
]

# FILTERED_UNIVERSE: symbols with PF>1.0, WR≥30%, ≥5 trades in 2yr backtest.
# Replaces UNIVERSE above when FILTERED_UNIVERSE = True (set below).
# 87 symbols from the current UNIVERSE pass Tier 1; the rest are dropped.
FILTERED_UNIVERSE = [
    "AAPL", "ABBV", "ABNB", "AFL", "ALB", "AMZN", "BA", "BAC", "BEN", "BKR",
    "C", "CAT", "COF", "COP", "CRWD", "CSX", "CVX", "DDOG", "DIA", "DLTR",
    "DVN", "DXCM", "ECL", "EEM", "EOG", "FCX", "FITB", "GE", "GOLD", "GOOG",
    "GOOGL", "GS", "HAL", "HBAN", "HOOD", "HPQ", "HSY", "IBM", "IEFA", "IWM",
    "JNJ", "JPM", "KLAC", "KO", "LEVI", "LLY", "LMT", "LRCX", "MO", "MRK",
    "MRNA", "MSFT", "NEM", "NET", "NFLX", "NOC", "NOW", "NVS", "O", "OKTA",
    "ORCL", "OXY", "PANW", "PLTR", "PSX", "QQQ", "RBLX", "ROST", "RTX", "SCCO",
    "SLB", "SPG", "SPY", "TFC", "UAL", "UNH", "USB", "VLO", "VTV", "WELL",
    "WFC", "WM", "XLE", "XLK", "XOM", "ZM",
]

# Set True to use only the filtered (winning) symbols.
# Set False to use the full 221-symbol universe.
USE_FILTERED_UNIVERSE = True

TIMEFRAME = "1h"         # Yahoo intraday interval (validated: 1h gives ~6mo history)
HISTORY_RANGE = "1y"     # ~6 months of 1h bars (free tier cap)

# EMA trend crossover (validated 6-month winners from tune_day_6m.py)
EMA_FAST = 12
EMA_SLOW = 30

# RSI filter (validated 6-month winners)
RSI_PERIOD = 14
RSI_BUY_MAX = 70    # only buy when RSI < this (not overbought)
RSI_SELL_MIN = 85   # sell when RSI >= this (overbought) or opposite cross

# Per-asset tuned params (from tune_stocks.py, 1h ~6mo real data).
# Format: symbol -> (ema_fast, ema_slow, rsi_buy_max, rsi_sell_min).
PER_ASSET = {
    "AAPL":      (12, 30, 70, 85),
    "TSLA":      (30, 120, 70, 75),
    "NVDA":      (20, 200, 70, 70),
    "AMZN":      (20, 80, 70, 85),
    "META":      (9, 30, 70, 85),
    "AMD":      (50, 80, 70, 85),
    "GOOGL":     (9, 30, 70, 85),
    "MSFT":      (20, 30, 70, 85),
}

# Paper account
INITIAL_CASH = 100_000.0
POSITION_PCT = 0.04      # 4% of equity per trade

# SAFETY: circuit breaker. If PAPER equity drops more than this % from the
# session-start value, the bot auto-flattens ALL positions and halts trading
# for the rest of the session. Paper money only, but trains good risk habits.
MAX_DAILY_LOSS_PCT = 0.05   # 5% max loss before halt

# Risk management
STOP_LOSS_PCT = 0.08       # -8% stop loss per trade
TAKE_PROFIT_PCT = 0.10     # +10% take profit per trade
TIME_STOP_HOURS = 3        # exit if trade not working within 3 hours

# Realistic costs (so backtests don't lie)
FEE_STOCK = 0.001        # 0.1% round-trip-ish per trade (broker + spread)
FEE_FOREX_PIPS = 1.0    # 1 pip per side ~ 2 pip round-trip
PIP_VALUE = 0.0001      # 1 pip in quote terms (for EURUSD etc.)

# Forex session filter: only OPEN new positions during London/NY overlap
# (13:00-17:00 UTC) - the most liquid FX window. Existing positions still close
# on their SELL signal regardless of hour. Set None to disable.
FX_SESSION_HOURS = (13, 17)

# Live loop
SCAN_INTERVAL_SECONDS = 3600  # 1 hour = one bar
