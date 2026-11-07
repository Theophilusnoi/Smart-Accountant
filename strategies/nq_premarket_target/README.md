# NQ Market-Open Pre-Market Target Strategy (Pine Script v6)

`nq_premarket_target_strategy.pine` is a TradingView strategy that implements the
"Market Open Pre-Market Target" spec (v1.0), adapted from QQQ to **NQ / MNQ futures**.

## Setup
1. Open `NQ1!` (or `MNQ1!`) on a **1-minute** chart. Futures charts include extended hours by default.
2. Pine Editor → paste the file → *Add to chart*.
3. Before each session, add that day's high-impact news dates in **No-trade filters** and any hand-drawn green lines in **Manual levels**.

## What changed for NQ (compared with the QQQ spec)
| Spec item (QQQ) | NQ implementation |
|---|---|
| Shares = risk / (entry − stop) | Contracts = floor(equity × 1% / (stop pts × `syminfo.pointvalue`)), so $20/pt on NQ and $2/pt on MNQ |
| 2% notional cap | Replaced by a **Max contracts** input. One NQ contract is about $400k notional, so a 2% cap would never allow a trade |
| Buffer = max(0.02%, 1 tick) | Same rule with a 0.25-pt NQ tick, rounded to the tick |
| $0.50/$1 round numbers | 100-pt steps by default (50 optional), within ±0.5% of price |
| Pre-market 04:00–09:30 | Default 04:00–09:30 ET. Set it to `1800-0930` to use the full Globex overnight. Overnight high/low are added as extra key levels |
| Prior close (16:00) | Close of the last RTH bar (09:30–16:00 ET) |
| Commission/slippage | $2.50/contract per side, 2 ticks of slippage. Limit orders only fill if price trades 1 tick through them |

If 1% risk buys less than 1 NQ contract, the trade is **skipped** by default. Use MNQ on smaller accounts.

## Rules encoded
- **Bias (B.4)** is set at the open from the last pre-market price, the PM range midpoint, the gap direction and 09:15→09:30 momentum. The extended LONG/SHORT case is included.
- **Day filters (G.1/B.5):** PM range under 0.25%, news dates, no valid or conflicting bias, mid-gap chop with no key level within 0.15%, and no key level within 0.3% of the open on the bias side.
- **Entries (C.1–C.3):** a touch of a key level (within 0.05%), then confirmation within 3 bars. Confirmation is a reversal candle, a higher low / lower high, or a volume uptick of at least 1.5× the 5-bar average. You enter on the confirmation close or on a break of its high/low. Stop goes beyond the pullback extreme plus the buffer. The trade is skipped if the stop is over 0.25% or R:R to TP1 is under 1.5. The extended case uses a strong first candle (body ≥ 60%, volume ≥ 2×).
- **Management (E):** at least 50% comes off at TP1 (PMH/PML) and the stop moves to breakeven. TP2 (next key level) is used only if the TP1 breakout candle is strong. Otherwise the runner trails the 1-min low/high or 0.15%, whichever is tighter.
- **Trade count (D.4):** max 2 trades. A 2nd trade is only taken after a losing 1st trade.
- **Time exit (F):** limits are cancelled at 09:39:30, a market exit fires at 09:39:45, and a forced exit happens at 09:40:00. On a 1-minute chart these collapse into the close of the 09:39 bar (= 09:40:00). Use a 15s/30s chart for exact timing.
- Each trade is written to Pine Logs (K.9). `alert()` events fire for the bias, entries, TP1 and exits.

## Not automatable in Pine
Halts and bid/ask spread blowouts (G.1.5–6) can't be detected from chart data, so the trader must enforce them. Scheduled news must be entered by hand.

## Rule set
**Rule set = NQ-tuned** (default) switches on all three options below at once: max stop of at least 0.40%, the swing stop anchor, and half-risk trading on conflict days. **Strict spec** follows the QQQ document exactly.

## Optional switches (used by "Strict spec")
- **Stop anchor:** the spec puts the stop beyond the low/high since 09:30. The alternative is the swing at the touched level, which gives a tighter stop when the open spiked first.
- **Gap vs momentum conflict:** the spec says NO TRADE. The alternative is the G.3 exception: trade at half risk with the bias taken from momentum and PM-range position.
- **Max stop distance:** the spec's 0.25% was tuned for QQQ. Try 0.35–0.40% on NQ.

## Diagnostics
Each day is labelled at the open (filtered days) or at 09:40 with the result. The table counts filtered days, skipped setups (contract size, stop, R:R), days with no confirmation and days where price never reached a level, across all loaded history.

## Deviation from spec
- **Confirmation candle must close in trade direction** is ON by default. It is an extra safety filter, so a red candle can't "confirm" a long through the volume clause alone. Turn it off for the literal spec.
