from datetime import datetime
from decimal import Decimal as D

import pytest

from risk_engine import (ET, LUCIDFLEX_50K, AccountState, BotRiskConfig,
                         HaltReason, RiskEngine)

MNQ_TICK = D("0.50")   # micro Nasdaq: $0.50/tick
NQ_TICK = D("5.00")


def at(y, m, d, hh, mm):
    return datetime(y, m, d, hh, mm, tzinfo=ET)


def engine(now=None, **cfg):
    now = now or at(2026, 11, 2, 9, 0)
    return RiskEngine(LUCIDFLEX_50K, BotRiskConfig(**cfg), AccountState.new(LUCIDFLEX_50K, now))


def test_outside_session_rejected():
    e = engine()
    d = e.pre_trade(at(2026, 11, 2, 12, 0), 40, 80, MNQ_TICK)
    assert not d.allowed and HaltReason.OUTSIDE_SESSION in d.reasons


def test_sizing_is_fixed_percent():
    e = engine()
    # 0.5% of 50k = $250; 40 ticks * $0.50 = $20/contract -> 12 contracts
    d = e.pre_trade(at(2026, 11, 2, 9, 45), 40, 80, MNQ_TICK)
    assert d.allowed and d.contracts == 12


def test_one_loss_ends_session_but_not_next_session():
    e = engine(max_trades_per_session=3)
    t = at(2026, 11, 2, 9, 45)
    e.on_entry(t, D("240"))
    e.on_close(at(2026, 11, 2, 10, 0), t, D("-240"), D("240"))
    d = e.pre_trade(at(2026, 11, 2, 10, 15), 40, 80, MNQ_TICK)
    assert not d.allowed and HaltReason.SESSION_LOSS in d.reasons
    assert e.pre_trade(at(2026, 11, 2, 13, 45), 40, 80, MNQ_TICK).allowed


def test_eod_trailing_floor_ratchets_and_locks():
    e = engine()
    assert e.state.floor == D("48000")
    e.state.balance = D("51000")
    e.roll_day_if_needed(at(2026, 11, 2, 18, 30))       # next trading day
    assert e.state.floor == D("49000")
    e.state.balance = D("50500")                         # losing day: floor must not drop
    e.roll_day_if_needed(at(2026, 11, 3, 18, 30))
    assert e.state.floor == D("49000")
    e.state.balance = D("53000")                         # would trail to 51000, locks at 50100
    e.roll_day_if_needed(at(2026, 11, 4, 18, 30))
    assert e.state.floor == D("50100")


def test_live_breach_fails_account():
    e = engine()
    d = e.check_live(D("47999"), at(2026, 11, 2, 9, 50))
    assert HaltReason.ACCOUNT_FAILED in d.reasons and e.state.failed


def test_daily_loss_limit_blocks_and_caps_size():
    e = engine(bot_daily_loss_limit=D("300"), max_trades_per_session=5)
    e.state.balance -= D("250")      # down $250 on the day
    d = e.pre_trade(at(2026, 11, 2, 9, 45), 40, 80, MNQ_TICK)
    assert d.allowed and d.contracts == 2   # only $50 room left -> 2 x $20
    e.state.balance -= D("50")
    d = e.pre_trade(at(2026, 11, 2, 9, 45), 40, 80, MNQ_TICK)
    assert not d.allowed and HaltReason.DAILY_LOSS in d.reasons


def test_consistency_cap_limits_target_size():
    e = engine()
    # cap on day one = 0.40 * 3000 * 0.9 = 1080. NQ 20-tick stop ($100/c), 60-tick target ($300/c)
    # risk budget 250 -> 2 contracts -> potential +600, under cap
    d = e.pre_trade(at(2026, 11, 2, 9, 45), 20, 60, NQ_TICK)
    assert d.allowed and d.contracts == 2
    e.state.balance += D("900")      # already +900 today -> headroom 180 < 300
    d = e.pre_trade(at(2026, 11, 2, 13, 45), 20, 60, NQ_TICK)
    assert not d.allowed and HaltReason.CONSISTENCY_CAP in d.reasons


def test_consistency_cap_grows_with_prior_profit():
    e = engine()
    e.state.daily_profits = {at(2026, 10, 1, 9, 0).date(): D("2400")}
    # 0.4/0.6 * 2400 = 1600 > 1200 -> cap 1600 * 0.9 = 1440
    assert e.consistency_daily_cap() == D("1440.00")


def test_target_reached_stops_trading():
    e = engine()
    e.state.daily_profits = {at(2026, 10, 1, 9, 0).date(): D("3000")}
    d = e.pre_trade(at(2026, 11, 2, 9, 45), 40, 80, MNQ_TICK)
    assert HaltReason.TARGET_REACHED in d.reasons


def test_flatten_time():
    e = engine()
    assert e.must_flatten(at(2026, 11, 2, 16, 45))
    assert not e.must_flatten(at(2026, 11, 2, 16, 44))
    assert not e.must_flatten(at(2026, 11, 2, 18, 0))   # new day open


def test_drawdown_buffer_blocks_near_floor():
    e = engine()
    e.state.balance = D("48300")   # floor 48000 + buffer 250 = 48250, room $50
    d = e.pre_trade(at(2026, 11, 2, 9, 45), 20, 60, NQ_TICK)   # $100/contract
    assert not d.allowed and HaltReason.DRAWDOWN_BUFFER in d.reasons


def test_invalid_inputs_raise():
    with pytest.raises(ValueError):
        engine().pre_trade(at(2026, 11, 2, 9, 45), 0, 80, MNQ_TICK)
