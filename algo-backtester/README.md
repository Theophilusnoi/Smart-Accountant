# FlowDesk Backtester

A personal, single-file order-flow charting and backtesting app, inspired by the feature set of
NinjaTrader order-flow add-ons such as AlgoBox (flow-coloured bars, delta, alerts, one-click setups),
with a full strategy backtester added on top.

Open `index.html` in any modern browser. No install, no server, no account.

## Pages
- **Welcome** (`#welcome`): landing page with an animated flow-bar preview, features, how it works and a Pine import showcase.
- **Sign up** (`#signup`) and **Log in** (`#login`): validation, password strength meter, show/hide password, "keep me logged in".
  A "Try it without an account" option opens the app as a guest.
- **Welcome aboard** (`#start`): shown after sign-up, with shortcuts to sample data, live crypto, or custom rules / Pine import.
- **App** (`#app`): the backtester. Presets and last settings are stored per account.

Accounts are stored only in this browser (localStorage). Passwords are hashed on-device with PBKDF2-SHA256 and never sent
anywhere. This keeps casual eyes out of a personal app but is not server-grade security; anyone with access to the browser
profile can clear or bypass it. Real multi-device accounts would need a backend (e.g. Supabase or Firebase Auth).

## Features
- **Data**: synthetic sample data, live Binance klines (real taker buy/sell volume → measured delta), or your own CSV
  (TradingView, NinjaTrader `YYYYMMDD HHMMSS`, Yahoo, unix timestamps). Without buy volume, delta is estimated
  from where each bar closes in its range.
- **Flow-coloured bars**: candles coloured by delta strength and relative volume (strong buy / buy / balanced / sell / strong sell).
- **Delta pane**: per-bar delta histogram plus cumulative delta.
- **Setups**: order-flow momentum, absorption reversal, cumulative-delta divergence, EMA crossover,
  RSI mean reversion, Donchian breakout, VWAP reversion. All parameters editable.
- **Risk model**: ATR stop, R-multiple target, breakeven move, ATR trailing stop (optionally starting after X R profit), max bars held, % risk sizing, leverage cap,
  commission and slippage. Signals fill at the next bar's open; if stop and target are both touched in one bar, the stop is assumed.
- **Results**: equity vs buy & hold, drawdown, 25+ statistics (CAGR, Sharpe, Sortino, profit factor, expectancy, R, streaks…),
  monthly returns table, trade list with MFE/MAE, CSV export.
- **Optimizer**: two-parameter grid search with in-sample / out-of-sample split and heatmap.
- **Replay & alerts**: step through history bar by bar; live watch polls Binance every 30 s and alerts with sound,
  toast and browser notification when the setup fires on a closed bar.
- **Custom rules**: backtest your own strategy by typing formulas (Pine-Script-like, no coding needed), e.g.
  `crossUp(ema(close, p1), ema(close, p2)) and rsi(close, 14) < 70` or `close > vwap and deltaPct > 30`.
  `x[1]` means one bar ago; `p1`–`p3` are tunable numbers the optimizer can search. Includes `macd/macdSignal/macdHist(src, fast, slow, signal)` and `bbUpper/bbMiddle/bbLower(src, n, mult)`, computed the same way as TradingView. See the in-app cheat sheet.
- **Pine Script import**: paste a TradingView strategy and it is converted into custom rules. Supports inputs (first three
  become p1–p3), variables, `if / else if / else`, `strategy.entry / close / close_all`, `when=`, `plot()`, and common `ta.*` / `math.*`
  functions, plus `[macd, signal, hist] = ta.macd(...)` and `[middle, upper, lower] = ta.bb(...)`. Anything it can't convert is listed. Not supported: `strategy.exit` levels (use the Risk panel), `var`/`:=` state,
  custom functions, other multi-value functions (`ta.kc`, `ta.dmi`, `ta.supertrend`), `request.security`, arrays and loops.
- Presets and last settings are saved in your browser.

Backtest results are hypothetical and are not a guarantee of future performance.
