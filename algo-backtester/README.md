# FlowDesk Backtester

A personal, single-file order-flow charting and backtesting app, inspired by the feature set of
NinjaTrader order-flow add-ons such as AlgoBox (flow-coloured bars, delta, alerts, one-click setups),
with a full strategy backtester added on top.

Open `index.html` in any modern browser. No install, no server, no account.

## Features
- **Data**: synthetic sample data, live Binance klines (real taker buy/sell volume → measured delta), or your own CSV
  (TradingView, NinjaTrader `YYYYMMDD HHMMSS`, Yahoo, unix timestamps). Without buy volume, delta is estimated
  from where each bar closes in its range.
- **Flow-coloured bars**: candles coloured by delta strength and relative volume (strong buy / buy / balanced / sell / strong sell).
- **Delta pane**: per-bar delta histogram plus cumulative delta.
- **Setups**: order-flow momentum, absorption reversal, cumulative-delta divergence, EMA crossover,
  RSI mean reversion, Donchian breakout, VWAP reversion. All parameters editable.
- **Risk model**: ATR stop, R-multiple target, breakeven move, max bars held, % risk sizing, leverage cap,
  commission and slippage. Signals fill at the next bar's open; if stop and target are both touched in one bar, the stop is assumed.
- **Results**: equity vs buy & hold, drawdown, 25+ statistics (CAGR, Sharpe, Sortino, profit factor, expectancy, R, streaks…),
  monthly returns table, trade list with MFE/MAE, CSV export.
- **Optimizer**: two-parameter grid search with in-sample / out-of-sample split and heatmap.
- **Replay & alerts**: step through history bar by bar; live watch polls Binance every 30 s and alerts with sound,
  toast and browser notification when the setup fires on a closed bar.
- **Custom rules**: backtest your own strategy by typing formulas (Pine-Script-like, no coding needed), e.g.
  `crossUp(ema(close, p1), ema(close, p2)) and rsi(close, 14) < 70` or `close > vwap and deltaPct > 30`.
  `x[1]` means one bar ago; `p1`–`p3` are tunable numbers the optimizer can search. See the in-app cheat sheet.
- Presets and last settings are saved in your browser.

Backtest results are hypothetical and are not a guarantee of future performance.
