#!/usr/bin/env python3
"""
StockBot Backtesting Harness — runs the existing EMA+RSI strategy
(strategy_intraday.py) over historical data for every symbol in the
universe (config_day.py), then reports win rate, profit factor, drawdowns,
and per-symbol P&L so you can see which stocks the strategy actually works on.

Run:
  python backtest_harness.py                     # 2y, 1h, all symbols
  python backtest_harness.py --period 6mo        # shorter history
  python backtest_harness.py --symbols AAPL TSLA  # specific symbols
  python backtest_harness.py -o results.json     # save full trade list
"""
import sys
import os
import json
import datetime
import argparse

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from config_day import (UNIVERSE, PER_ASSET, EMA_FAST, EMA_SLOW,
                        RSI_PERIOD, RSI_BUY_MAX, RSI_SELL_MIN)
from data_feed import get_history
import strategy_intraday as si


def _max_drawdown(closes):
    """Peak-to-trough drawdown over the full series (fractional)."""
    peak = closes[0]
    max_dd = 0.0
    for p in closes:
        if p > peak:
            peak = p
        dd = (peak - p) / peak if peak else 0.0
        if dd > max_dd:
            max_dd = dd
    return max_dd


def backtest_symbol(sym, period="2y", interval="1h"):
    """Run EMA+RSI on one symbol's history, return stats + closed trades."""
    ef, es, rb, rs = PER_ASSET.get(
        sym, (EMA_FAST, EMA_SLOW, RSI_BUY_MAX, RSI_SELL_MIN)
    )
    h = get_history(sym, period=period, interval=interval)
    closes = h["close"]
    if len(closes) < max(ef, es, RSI_PERIOD) + 5:
        return {"symbol": sym, "error": "too few bars"}

    emaf = si.ema_series(closes, ef)
    emas = si.ema_series(closes, es)
    rsi = si.rsi_series(closes, RSI_PERIOD)
    signals = si.signals_ema_rsi(closes, emaf, emas, rsi, rb, rs)

    # Walk bar-by-bar with a single-position state machine (mirrors the live bot:
    # enter on BUY, exit on SELL, no pyramiding).
    trades = []
    pos = None  # None or {"entry_idx": i, "entry_price": float}

    for i, price in enumerate(closes):
        sig = signals[i]
        if pos is None and sig == "BUY":
            pos = {"entry_idx": i, "entry_price": price, "side": "LONG"}
        elif pos is not None and sig == "SELL":
            entry = pos["entry_price"]
            pnl_pct = (price - entry) / entry if entry else 0.0
            pnl_usd = pnl_pct * entry
            trades.append({
                "symbol": sym,
                "side": "LONG",
                "entry_idx": pos["entry_idx"],
                "exit_idx": i,
                "entry_price": entry,
                "exit_price": price,
                "pnl_pct": pnl_pct,
                "pnl_usd": pnl_usd,
                "bars_held": i - pos["entry_idx"],
            })
            pos = None

    # Keep open positions open at the end (don't force-close).
    while_pos = []
    if pos is not None:
        last = closes[-1]
        entry = pos["entry_price"]
        pnl_pct = (last - entry) / entry if entry else 0.0
        while_pos.append({
            "symbol": sym,
            "side": "LONG",
            "entry_idx": pos["entry_idx"],
            "entry_price": entry,
            "current_price": last,
            "pnl_pct": pnl_pct,
            "pnl_usd": pnl_pct * entry,
            "bars_held": len(closes) - 1 - pos["entry_idx"],
        })

    closed = [t for t in trades if not t.get("open_at_end")]
    winners = [t for t in closed if t["pnl_usd"] > 0]
    losers = [t for t in closed if t["pnl_usd"] < 0]

    win_total = sum(t["pnl_usd"] for t in winners)
    loss_total = sum(t["pnl_usd"] for t in losers)
    pf = win_total / abs(loss_total) if loss_total else float("inf")

    return {
        "symbol": sym,
        "period": period,
        "interval": interval,
        "bars": len(closes),
        "ema_fast": ef,
        "ema_slow": es,
        "rsi_buy_max": rb,
        "rsi_sell_min": rs,
        "num_buy_signals": int(signals.count("BUY")),
        "num_sell_signals": int(signals.count("SELL")),
        "num_trades": len(closed),
        "win_rate": len(winners) / len(closed) if closed else 0.0,
        "total_pnl": sum(t["pnl_usd"] for t in closed),
        "avg_win": (win_total / len(winners)) if winners else 0.0,
        "avg_loss": (loss_total / len(losers)) if losers else 0.0,
        "profit_factor": pf if pf != float("inf") else None,
        "max_drawdown": _max_drawdown(closes),
        "final_price": closes[-1],
        "start_price": closes[0],
        "buy_hold_pnl_pct": (closes[-1] - closes[0]) / closes[0] if closes[0] else 0.0,
        "closed_trades": closed,
        "open_positions": while_pos,
    }


def backtest_universe(period="2y", interval="1h", symbols=None, output=None):
    """Backtest every symbol (or a given list) and print a summary table."""
    targets = symbols or [s for s, _ in UNIVERSE]
    results = []
    errors = []

    print(f"Backtesting {len(targets)} symbols | {period} {interval} | "
          f"strategy: EMA({EMA_FAST}/{EMA_SLOW}) + RSI({RSI_PERIOD}, "
          f"buy<{RSI_BUY_MAX}, sell>={RSI_SELL_MIN})")
    print("-" * 78)

    for sym in targets:
        try:
            r = backtest_symbol(sym, period, interval)
        except Exception as e:
            errors.append((sym, str(e)))
            print(f"  ! {sym}: {e}")
            continue
        if "error" in r:
            errors.append((sym, r["error"]))
            print(f"  - {sym}: {r['error']}")
            continue
        results.append(r)

    # Sort by total P&L desc
    results.sort(key=lambda x: x["total_pnl"], reverse=True)

    # Print table
    print(f"\n{'SYM':6s} {'bars':>5s} {'trades':>6s} {'win%':>6s} "
          f"{'P&L $':>10s} {'avgW':>7s} {'avgL':>7s} {'PF':>6s} "
          f"{'maxDD':>7s} {'BH%':>6s}")
    print("-" * 78)
    for r in results:
        pf_s = f"{r['profit_factor']:.2f}" if r["profit_factor"] is not None else "inf"
        bh = r["buy_hold_pnl_pct"] * 100
        print(f"{r['symbol']:6s} {r['bars']:5d} {r['num_trades']:6d} "
              f"{r['win_rate']*100:5.1f}% ${r['total_pnl']:9,.2f} "
              f"${r['avg_win']:6.2f} ${r['avg_loss']:6.2f} "
              f"{pf_s:>6s} {r['max_drawdown']*100:5.1f}% {bh:5.1f}%")

    total_trades = sum(r["num_trades"] for r in results)
    total_pnl = sum(r["total_pnl"] for r in results)
    total_closed_wins = sum(
        1 for r in results for t in r["closed_trades"] if t["pnl_usd"] > 0
    )
    total_closed_losses = sum(
        1 for r in results for t in r["closed_trades"] if t["pnl_usd"] < 0
    )
    all_wins = sum(t["pnl_usd"] for r in results for t in r["closed_trades"] if t["pnl_usd"] > 0)
    all_losses = sum(t["pnl_usd"] for r in results for t in r["closed_trades"] if t["pnl_usd"] < 0)
    total_pf = all_wins / abs(all_losses) if all_losses else None
    bh_total_pnl = sum(
        (r["final_price"] - r["start_price"]) / r["start_price"] * r["start_price"]
        for r in results if r["start_price"]
    )

    print(f"\n{'=' * 78}")
    print(f"Universe summary:")
    print(f"  Symbols tested:        {len(results)}")
    print(f"  Symbols with errors:   {len(errors)}")
    print(f"  Total trades (closed): {total_trades}")
    print(f"  Win rate:              {total_closed_wins / max(1, total_trades) * 100:.1f}%")
    print(f"  Total P&L (closed):    ${total_pnl:,.2f}")
    print(f"  vs Buy & Hold:         ${total_pnl - bh_total_pnl:+,.2f} "
          f"(BH would have returned ${bh_total_pnl:+,.2f})")
    if total_pf is not None:
        print(f"  Profit factor:         {total_pf:.2f}")
    print(f"  Best symbol:           {results[0]['symbol']}  "
          f"({results[0]['num_trades']} trades, ${results[0]['total_pnl']:,.2f})")
    print(f"  Worst symbol:          {results[-1]['symbol']}  "
          f"({results[-1]['num_trades']} trades, ${results[-1]['total_pnl']:,.2f})")

    if errors:
        print(f"\nSymbols skipped ({len(errors)}):")
        for sym, why in errors[:20]:
            print(f"  - {sym}: {why}")
        if len(errors) > 20:
            print(f"  ... and {len(errors) - 20} more")

    if output:
        out = {
            "generated_at": datetime.datetime.now(datetime.timezone.utc).isoformat(),
            "period": period,
            "interval": interval,
            "universe_source": "config_day.UNIVERSE",
            "per_symbol_params": {s: PER_ASSET.get(s, (EMA_FAST, EMA_SLOW, RSI_BUY_MAX, RSI_SELL_MIN))
                                  for s in [s for s, _ in UNIVERSE]},
            "summary": {
                "symbols_tested": len(results),
                "symbols_with_errors": len(errors),
                "total_trades_closed": total_trades,
                "win_rate": total_closed_wins / max(1, total_trades),
                "total_pnl_closed": total_pnl,
                "profit_factor": total_pf,
                "best_symbol": results[0]["symbol"],
                "best_symbol_pnl": results[0]["total_pnl"],
                "worst_symbol": results[-1]["symbol"],
                "worst_symbol_pnl": results[-1]["total_pnl"],
            },
            "per_symbol": [{k: v for k, v in r.items() if k != "closed_trades"}
                           for r in results],
            "closed_trades": [t for r in results for t in r["closed_trades"]],
            "errors": [{"symbol": s, "reason": w} for s, w in errors],
        }
        os.makedirs(os.path.dirname(output) or ". ", exist_ok=True)
        with open(output, "w") as f:
            json.dump(out, f, indent=2)
        print(f"\nFull results (per-symbol stats + all trades) saved: {output}")

    return results


def main():
    ap = argparse.ArgumentParser(description="StockBot EMA+RSI Backtest Harness")
    ap.add_argument("--period", default="2y",
                    help="History period for Yahoo (default: 2y)")
    ap.add_argument("--interval", default="1h",
                    help="Bar interval (default: 1h)")
    ap.add_argument("--symbols", nargs="+",
                    help="Specific symbols to test (default: whole universe)")
    ap.add_argument("--output", "-o", metavar="FILE",
                    help="Save full results (per-symbol stats + trade list) to JSON")
    args = ap.parse_args()

    if args.symbols:
        results = []
        for sym in args.symbols:
            r = backtest_symbol(sym, args.period, args.interval)
            if "error" not in r:
                results.append(r)
        results.sort(key=lambda x: x["total_pnl"], reverse=True)
        for r in results:
            pf = f"{r['profit_factor']:.2f}" if r["profit_factor"] is not None else "inf"
            print(f"{r['symbol']:6s} trades={r['num_trades']:3d}  "
                  f"win={r['win_rate']*100:4.1f}%  P&L=${r['total_pnl']:,.2f}  "
                  f"pf={pf}  maxDD={r['max_drawdown']*100:4.1f}%  "
                  f"BH={r['buy_hold_pnl_pct']*100:+.1f}%")
    else:
        backtest_universe(args.period, args.interval, output=args.output)


if __name__ == "__main__":
    main()
