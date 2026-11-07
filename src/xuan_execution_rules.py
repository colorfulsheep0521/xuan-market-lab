"""Execution rules requested by the user; no discretionary risk caps."""
import math
import pandas as pd
import run_xuan_lab as xuan
from execution_simulator import money


def capital_amount(value):
    value=float(value)
    if not math.isfinite(value) or value<=0:
        raise ValueError("Initial simulated capital must be finite and positive")
    result=money(value)
    if result<=0:raise ValueError("Initial capital must be at least one cent")
    return result


def hundred_share_buy(code, capacity):
    """All purchases are 100-share multiples, including user's STAR orders."""
    qty=max(0,int(capacity//100)*100)
    if code.startswith(("sh.688","sh.689")) and qty<200:
        return 0
    return qty


def reassess_t1_exit(profile, qi_row, buy_date, current_date, market_dates,
                     timing_function=None):
    """Re-evaluate the EXISTING model each session, not a forced next-day sell.

    Recompute stock_hold_days and stock_sell_time using only today's cultural
    inputs, and compare its holding horizon to actual elapsed market sessions.
    No upper waiting limit, fixed offset, extra price indicator or future lookup.
    """
    timing_function=timing_function or xuan.stock_day_timing
    elapsed=sum(buy_date<d<=current_date for d in market_dates)
    if current_date<=buy_date:
        return dict(eligible=False,date=current_date,elapsed_sessions=elapsed,
                    reason="T+1_not_sellable")
    profile=pd.Series(profile) if isinstance(profile,dict) else profile
    qi_row=pd.Series(qi_row) if isinstance(qi_row,dict) else qi_row
    timing=timing_function(profile,qi_row,str(profile["code"]))
    required=max(0,int(timing["stock_hold_days"]))
    return dict(eligible=elapsed>=required,date=current_date,
                planned_time=str(timing["stock_sell_time"]),
                elapsed_sessions=elapsed,required_sessions=required,
                reason="xuan_recomputed_hold_reached" if elapsed>=required else "waiting_for_xuan_point",
                basis=str(timing.get("stock_timing_reason","")))
