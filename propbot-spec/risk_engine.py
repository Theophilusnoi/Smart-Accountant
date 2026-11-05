"""
RiskEngine: pre-trade and live rule enforcement for prop-firm evaluation accounts.

All firm-specific numbers live in FirmRules. The LUCIDFLEX_50K preset uses
PLACEHOLDER values -- verify every field against the firm's current published
rules before trading. Firms change these often.

Design principles
  * Fail closed: any missing/invalid state -> no trade.
  * The engine is pure logic (no I/O). The caller feeds it fills and equity
    marks and persists `AccountState` between calls/restarts.
  * Every decision returns a `Decision` with machine-readable reasons, so the
    caller can write it to the audit log.
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field
from datetime import datetime, time, timedelta, date
from decimal import Decimal, ROUND_FLOOR
from enum import Enum
from typing import Optional
from zoneinfo import ZoneInfo

ET = ZoneInfo("America/New_York")
D = Decimal


# --------------------------------------------------------------------------- #
# Configuration
# --------------------------------------------------------------------------- #
@dataclass(frozen=True)
class Session:
    name: str
    start: time  # ET, inclusive
    end: time    # ET, exclusive


@dataclass(frozen=True)
class FirmRules:
    name: str
    starting_balance: Decimal
    profit_target: Decimal
    max_loss: Decimal                    # EOD trailing drawdown distance
    drawdown_lock_balance: Optional[Decimal]  # floor stops trailing once it reaches this (None = never locks)
    consistency_ratio: Optional[Decimal] # e.g. 0.40 -> largest day <= 40% of total profit (None = no rule)
    firm_daily_loss_limit: Optional[Decimal]  # firm-imposed; None if the firm has none
    flatten_by: time                     # ET; all positions closed before this
    trading_day_rollover: time = time(18, 0)  # ET; CME futures day starts 18:00 ET


@dataclass(frozen=True)
class BotRiskConfig:
    risk_per_trade_pct: Decimal = D("0.005")     # of current balance
    bot_daily_loss_limit: Decimal = D("500")     # self-imposed, tighter than firm
    max_losses_per_session: int = 1              # "one loss ends the session"
    max_trades_per_session: int = 1              # "one high-probability setup"
    drawdown_buffer: Decimal = D("250")          # stay this far above the floor
    consistency_safety: Decimal = D("0.90")      # use 90% of the theoretical daily cap
    flatten_lead: timedelta = timedelta(minutes=5)  # stop new entries this long before flatten_by
    sessions: tuple[Session, ...] = (
        Session("asia",      time(20, 0), time(22, 0)),
        Session("london",    time(3, 0),  time(5, 0)),
        Session("ny_open",   time(9, 30), time(11, 0)),
        Session("ny_pm",     time(13, 30), time(15, 30)),
    )


# PLACEHOLDER values -- verify against LucidFlex's current rule page.
LUCIDFLEX_50K = FirmRules(
    name="LucidFlex 50K (VERIFY)",
    starting_balance=D("50000"),
    profit_target=D("3000"),
    max_loss=D("2000"),
    drawdown_lock_balance=D("50100"),
    consistency_ratio=D("0.40"),
    firm_daily_loss_limit=None,
    flatten_by=time(16, 45),
)


# --------------------------------------------------------------------------- #
# State
# --------------------------------------------------------------------------- #
class HaltReason(str, Enum):
    TARGET_REACHED = "target_reached"
    DRAWDOWN_BUFFER = "drawdown_buffer_breached"
    ACCOUNT_FAILED = "account_failed"
    DAILY_LOSS = "daily_loss_limit"
    CONSISTENCY_CAP = "consistency_daily_cap"
    SESSION_LOSS = "session_loss_limit"
    SESSION_TRADES = "session_trade_limit"
    OUTSIDE_SESSION = "outside_session"
    NEAR_FLATTEN = "near_flatten_time"
    MANUAL = "manual_pause"


@dataclass
class AccountState:
    balance: Decimal                       # realized balance
    floor: Decimal                         # current max-loss floor
    trading_day: date
    day_start_balance: Decimal
    daily_profits: dict[date, Decimal] = field(default_factory=dict)  # closed days only
    session_trades: dict[str, int] = field(default_factory=dict)      # key: f"{day}:{session}"
    session_losses: dict[str, int] = field(default_factory=dict)
    open_risk: Decimal = D("0")            # $ at risk on open positions (to stop)
    failed: bool = False
    paused: bool = False

    @classmethod
    def new(cls, rules: FirmRules, now: datetime) -> "AccountState":
        return cls(
            balance=rules.starting_balance,
            floor=rules.starting_balance - rules.max_loss,
            trading_day=trading_day_of(now, rules),
            day_start_balance=rules.starting_balance,
        )

    @property
    def day_pnl(self) -> Decimal:
        return self.balance - self.day_start_balance


@dataclass
class Decision:
    allowed: bool
    reasons: list[HaltReason] = field(default_factory=list)
    contracts: int = 0
    detail: dict = field(default_factory=dict)


# --------------------------------------------------------------------------- #
# Helpers
# --------------------------------------------------------------------------- #
def trading_day_of(now: datetime, rules: FirmRules) -> date:
    """Futures trading day: after rollover (18:00 ET) belongs to the next date."""
    local = now.astimezone(ET)
    d = local.date()
    if local.time() >= rules.trading_day_rollover:
        d += timedelta(days=1)
    return d


def _in_window(t: time, s: Session) -> bool:
    if s.start <= s.end:
        return s.start <= t < s.end
    return t >= s.start or t < s.end  # window crosses midnight


# --------------------------------------------------------------------------- #
# Engine
# --------------------------------------------------------------------------- #
class RiskEngine:
    def __init__(self, rules: FirmRules, cfg: BotRiskConfig, state: AccountState):
        self.rules = rules
        self.cfg = cfg
        self.state = state

    # ---- time / session -------------------------------------------------- #
    def current_session(self, now: datetime) -> Optional[Session]:
        t = now.astimezone(ET).time()
        return next((s for s in self.cfg.sessions if _in_window(t, s)), None)

    def _session_key(self, now: datetime, s: Session) -> str:
        return f"{trading_day_of(now, self.rules).isoformat()}:{s.name}"

    def must_flatten(self, now: datetime) -> bool:
        """True from flatten_by until the next trading day opens."""
        t = now.astimezone(ET).time()
        return self.rules.flatten_by <= t < self.rules.trading_day_rollover

    def _near_flatten(self, now: datetime) -> bool:
        local = now.astimezone(ET)
        cutoff = datetime.combine(local.date(), self.rules.flatten_by, ET) - self.cfg.flatten_lead
        return cutoff <= local < datetime.combine(local.date(), self.rules.trading_day_rollover, ET)

    # ---- day rollover / EOD trailing drawdown ---------------------------- #
    def roll_day_if_needed(self, now: datetime) -> None:
        """Call on every tick/event. Closes out the prior day exactly once."""
        today = trading_day_of(now, self.rules)
        if today == self.state.trading_day:
            return
        self.end_of_day()
        self.state.trading_day = today
        self.state.day_start_balance = self.state.balance

    def end_of_day(self) -> None:
        """EOD trailing: floor ratchets up with the EOD balance, never down, and
        stops once it reaches the lock level."""
        s, r = self.state, self.rules
        s.daily_profits[s.trading_day] = s.day_pnl
        candidate = s.balance - r.max_loss
        if r.drawdown_lock_balance is not None:
            candidate = min(candidate, r.drawdown_lock_balance)
        s.floor = max(s.floor, candidate)

    # ---- consistency ----------------------------------------------------- #
    def total_profit(self, include_today: bool = True) -> Decimal:
        closed = sum(self.state.daily_profits.values(), D("0"))
        return closed + (self.state.day_pnl if include_today else D("0"))

    def consistency_daily_cap(self) -> Optional[Decimal]:
        """Max profit today may reach without today becoming > ratio of total.

        Today's profit d must satisfy d <= ratio * (P + d), where P is profit
        from prior days  ->  d <= ratio/(1-ratio) * P.
        Also, reaching the target with every day <= ratio*target is always
        compliant, so ratio*target is a floor on the cap. Take the larger,
        then apply a safety margin.
        """
        ratio = self.rules.consistency_ratio
        if ratio is None:
            return None
        prior = max(self.total_profit(include_today=False), D("0"))
        cap = max(ratio * self.rules.profit_target, ratio / (1 - ratio) * prior)
        return (cap * self.cfg.consistency_safety).quantize(D("0.01"))

    # ---- live checks (call on every equity mark) -------------------------- #
    def check_live(self, equity: Decimal, now: datetime) -> Decision:
        """Returns allowed=False with FLATTEN semantics if positions must close."""
        self.roll_day_if_needed(now)
        reasons: list[HaltReason] = []
        if equity <= self.state.floor:
            self.state.failed = True
            reasons.append(HaltReason.ACCOUNT_FAILED)
        elif equity <= self.state.floor + self.cfg.drawdown_buffer:
            reasons.append(HaltReason.DRAWDOWN_BUFFER)
        intraday = equity - self.state.day_start_balance
        if -intraday >= self._daily_loss_limit():
            reasons.append(HaltReason.DAILY_LOSS)
        if self.must_flatten(now):
            reasons.append(HaltReason.NEAR_FLATTEN)
        return Decision(allowed=not reasons, reasons=reasons,
                        detail={"equity": str(equity), "floor": str(self.state.floor)})

    def _daily_loss_limit(self) -> Decimal:
        limits = [self.cfg.bot_daily_loss_limit]
        if self.rules.firm_daily_loss_limit is not None:
            limits.append(self.rules.firm_daily_loss_limit)
        return min(limits)

    # ---- pre-trade ------------------------------------------------------- #
    def pre_trade(self, now: datetime, stop_ticks: int, target_ticks: int,
                  tick_value: Decimal) -> Decision:
        """Decide whether a bracket order may be sent and how many contracts.

        Checks run in order; all failing reasons are collected for the log.
        """
        self.roll_day_if_needed(now)
        s, r, c = self.state, self.rules, self.cfg
        reasons: list[HaltReason] = []

        if stop_ticks <= 0 or target_ticks <= 0 or tick_value <= 0:
            raise ValueError("stop_ticks, target_ticks and tick_value must be positive")

        if s.failed:
            reasons.append(HaltReason.ACCOUNT_FAILED)
        if s.paused:
            reasons.append(HaltReason.MANUAL)
        if self.total_profit() >= r.profit_target:
            reasons.append(HaltReason.TARGET_REACHED)

        session = self.current_session(now)
        if session is None:
            reasons.append(HaltReason.OUTSIDE_SESSION)
        else:
            key = self._session_key(now, session)
            if s.session_losses.get(key, 0) >= c.max_losses_per_session:
                reasons.append(HaltReason.SESSION_LOSS)
            if s.session_trades.get(key, 0) >= c.max_trades_per_session:
                reasons.append(HaltReason.SESSION_TRADES)
        if self._near_flatten(now):
            reasons.append(HaltReason.NEAR_FLATTEN)

        # Size: fixed % of balance, floored to whole contracts.
        risk_per_contract = D(stop_ticks) * tick_value
        budget = s.balance * c.risk_per_trade_pct
        # Never let a full stop-out breach the drawdown buffer or daily loss limit.
        room_dd = s.balance - s.open_risk - (s.floor + c.drawdown_buffer)
        room_daily = self._daily_loss_limit() + min(s.day_pnl, D("0")) - s.open_risk
        budget = min(budget, room_dd, room_daily)
        contracts = int((budget / risk_per_contract).to_integral_value(ROUND_FLOOR)) if budget > 0 else 0
        if contracts < 1:
            if room_dd < risk_per_contract:
                reasons.append(HaltReason.DRAWDOWN_BUFFER)
            if room_daily < risk_per_contract:
                reasons.append(HaltReason.DAILY_LOSS)

        # Consistency: if the target is hit, today must stay under the cap.
        cap = self.consistency_daily_cap()
        if cap is not None and contracts >= 1:
            reward_per_contract = D(target_ticks) * tick_value
            headroom = cap - s.day_pnl
            max_by_cap = int((headroom / reward_per_contract).to_integral_value(ROUND_FLOOR)) if headroom > 0 else 0
            if max_by_cap < 1:
                reasons.append(HaltReason.CONSISTENCY_CAP)
            contracts = min(contracts, max_by_cap)

        allowed = not reasons and contracts >= 1
        return Decision(
            allowed=allowed,
            reasons=reasons,
            contracts=contracts if allowed else 0,
            detail={
                "session": session.name if session else None,
                "risk_usd": str(D(contracts) * risk_per_contract) if allowed else "0",
                "floor": str(s.floor),
                "consistency_cap": str(cap) if cap is not None else None,
                "day_pnl": str(s.day_pnl),
            },
        )

    # ---- event hooks ------------------------------------------------------ #
    def on_entry(self, now: datetime, risk_usd: Decimal) -> None:
        session = self.current_session(now)
        if session is None:
            raise RuntimeError("entry outside a session should have been rejected")
        key = self._session_key(now, session)
        self.state.session_trades[key] = self.state.session_trades.get(key, 0) + 1
        self.state.open_risk += risk_usd

    def on_close(self, now: datetime, entry_time: datetime, realized_pnl: Decimal,
                 risk_usd: Decimal) -> None:
        """Book a closed trade. A loss counts against the session it was opened in."""
        self.roll_day_if_needed(now)
        self.state.balance += realized_pnl
        self.state.open_risk = max(D("0"), self.state.open_risk - risk_usd)
        if realized_pnl < 0:
            session = self.current_session(entry_time)
            if session is not None:
                key = self._session_key(entry_time, session)
                self.state.session_losses[key] = self.state.session_losses.get(key, 0) + 1
        if self.state.balance <= self.state.floor:
            self.state.failed = True
