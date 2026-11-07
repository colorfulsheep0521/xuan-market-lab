"""Daily-bar paper broker. Signals at previous close, fills next open.

No live broker integration. All prices must be UNADJUSTED. Corporate actions
require explicit events; unknown ex-right gaps stop the run instead of silently
creating a profit/loss. Calendars and security data are supplied by the caller.
"""
from dataclasses import asdict, dataclass
from decimal import Decimal, ROUND_HALF_UP
import math

import pandas as pd


def money(value):
    return float(Decimal(str(value)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP))


@dataclass(frozen=True)
class Config:
    initial_cash: float = 100000.0
    commission_rate: float = 0.0003
    minimum_commission: float = 5.0
    transfer_rate: float = 0.00001
    sell_stamp_rate: float = 0.0005
    slippage: float = 0.001
    max_previous_volume_fraction: float = 0.01
    max_positions: int = 0

    def __post_init__(self):
        if self.initial_cash <= 0 or self.max_positions < 0:
            raise ValueError("Invalid capital/position limit")
        if any(x < 0 for x in (self.commission_rate, self.minimum_commission,
                              self.transfer_rate, self.sell_stamp_rate, self.slippage)):
            raise ValueError("Negative execution cost")
        if not 0 < self.max_previous_volume_fraction <= 1:
            raise ValueError("Invalid participation limit")


@dataclass(frozen=True)
class ExecutionPolicy:
    """Explicit experiment axes; defaults reproduce the saved v1 account."""
    signal_timing: str = "previous_close"
    holding_mode: str = "individual"
    candidate_fallback: bool = True
    forbid_same_day_reentry: bool = True
    reference_price: str = "open"
    ranking_mode: str = "code_tiebreak"

    def __post_init__(self):
        if self.signal_timing not in {"previous_close", "calendar_preopen"}:
            raise ValueError("Unknown signal timing")
        if self.holding_mode not in {"individual", "legacy_review"}:
            raise ValueError("Unknown holding policy")
        if self.reference_price not in {"open", "close"}:
            raise ValueError("Unknown reference price")
        if self.ranking_mode not in {"code_tiebreak","legacy_sort"}:
            raise ValueError("Unknown ranking mode")


def fees(gross, side, cfg):
    commission = money(max(cfg.minimum_commission, gross * cfg.commission_rate))
    transfer = money(gross * cfg.transfer_rate)
    stamp = money(gross * cfg.sell_stamp_rate) if side == "SELL" else 0.0
    return commission, transfer, stamp


def limit_rate(code, is_st=False, date=None):
    if code.startswith(("sz.300", "sz.301", "sh.688", "sh.689")):
        return .20
    # Main-board risk-warning limit changed with the 2026-07-06 rules.
    return .05 if is_st and (date is None or date < "2026-07-06") else .10


def buy_quantity(code, capacity):
    if code.startswith(("sh.688", "sh.689")):
        return int(capacity) if capacity >= 200 else 0
    return int(capacity // 100) * 100


def dividend_tax(claims, buy_date, current_date):
    days = (pd.Timestamp(current_date)-pd.Timestamp(buy_date)).days
    rate = .20 if days <= 30 else .10 if days <= 365 else 0.
    return money(sum(claims)*rate)


def simulate(bars, candidates, qi, cfg=Config(), start=None, end=None,
             corporate_actions=None, policy=None):
    """Return auditable equity, trades, orders, holdings and serializable state.

    Each fill is a single lot, with independent expiry; no rank-driven liquidation.
    Blocked/partial sells persist. Buy orders expire at that day's close. A known
    cash/stock action must specify its ex-date, cash pay-date and availability date.
    Same-day sale proceeds are available for buying, but no withdrawal is modeled.
    """
    policy=policy or ExecutionPolicy()
    required = {"date", "code", "open", "high", "low", "close", "preclose",
                "volume", "tradestatus", "isST"}
    if not required.issubset(bars):
        raise ValueError(f"Missing raw-bar fields: {required-set(bars)}")
    bars = bars.copy()
    bars["date"] = pd.to_datetime(bars.date).dt.strftime("%Y-%m-%d")
    if bars.duplicated(["date", "code"]).any():
        raise ValueError("Duplicate daily security rows")
    for col in required - {"date", "code"}:
        bars[col] = pd.to_numeric(bars[col], errors="coerce")
    candidates = candidates.copy()
    candidates["date"] = pd.to_datetime(candidates.date).dt.strftime("%Y-%m-%d")
    if candidates.duplicated(["date", "code"]).any():
        raise ValueError("Duplicate candidates")
    qi = qi.copy()
    qi["date"] = pd.to_datetime(qi.date).dt.strftime("%Y-%m-%d")
    if qi.date.duplicated().any():
        raise ValueError("Duplicate calendar signals")
    dates = sorted(bars.date.unique())
    dates = [d for d in dates if not end or d <= end]
    byday = {d: g.set_index("code").to_dict("index") for d, g in bars.groupby("date")}
    signals = {d: (g.sort_values("xuan_score",ascending=False) if policy.ranking_mode=="legacy_sort"
                  else g.sort_values(["xuan_score", "code"], ascending=[False, True]))
               for d, g in candidates.groupby("date")}
    qmap = qi.set_index("date").to_dict("index")
    if not dates:
        raise ValueError("No market sessions")
    event_list=corporate_actions or []
    events = {(str(e["date"]), str(e["code"])): e for e in event_list}
    if len(events)!=len(event_list):
        raise ValueError("Duplicate corporate action events")
    for e in event_list:
        if float(e.get("cash_per_share",0))<0 or float(e.get("bonus_per_share",0))<0:
            raise ValueError("Negative corporate action entitlement")
        if float(e.get("cash_per_share",0)) and (not e.get("pay_date") or e["pay_date"]<e["date"]):
            raise ValueError("Invalid corporate dividend payment date")
        if float(e.get("bonus_per_share",0)) and (not e.get("available_date") or e["available_date"]<e["date"]):
            raise ValueError("Invalid bonus availability date")
    cash = money(cfg.initial_cash)
    positions, last_bars, last_marks, receivables = {}, {}, {}, []
    equity, trades, orders, history, action_log = [], [], [], [], []
    peak = cfg.initial_cash
    next_review=0

    def order(date, code, side, status, reason, signal_date=None):
        orders.append(dict(date=date, code=code, side=side, status=status,
                           reason=reason, signal_date=signal_date))

    def quote(code, side, today):
        bar, previous = today.get(code), last_bars.get(code)
        if not bar or bar["tradestatus"] != 1 or not bar["volume"] > 0:
            return None, 0, "suspended_or_missing"
        if not previous or not previous["volume"] > 0:
            return None, 0, "no_previous_volume"
        if not all(math.isfinite(bar[k]) and bar[k] > 0
                   for k in ("open", "high", "low", "close", "preclose")):
            return None, 0, "invalid_bar"
        # Strict policy: no fill at a limit-open, regardless of later unlocking.
        rate = limit_rate(code, bar["isST"] == 1, current_date)
        up, down = money(bar["preclose"]*(1+rate)), money(bar["preclose"]*(1-rate))
        reference=bar[policy.reference_price]
        if side == "BUY" and reference >= up-.005:
            return None, 0, "limit_up_open"
        if side == "SELL" and reference <= down+.005:
            return None, 0, "limit_down_open"
        px = money(reference*(1+cfg.slippage if side == "BUY" else 1-cfg.slippage))
        # Do not use today's high/low to grant a favorable fill at the open.
        if not down <= px <= up:
            return None, 0, "slippage_outside_price_limit"
        if not bar["low"] <= px <= bar["high"]:
            return None, 0, "slippage_outside_observed_range"
        return px, int(previous["volume"]*cfg.max_previous_volume_fraction), ""

    for idx, date in enumerate(dates):
        current_date = date
        today = byday.get(date, {})
        if start and date < start:
            last_bars.update(today)
            last_marks.update({c: b["close"] for c, b in today.items() if b["close"] > 0})
            continue
        prior = date if policy.signal_timing=="calendar_preopen" else dates[idx-1] if idx else None
        signal, rows = qmap.get(prior, {}), signals.get(prior)
        target=max(0,int(signal.get("recommended_count",0)))
        if cfg.max_positions:
            target=min(target,cfg.max_positions)
        review_due=idx>=next_review and target>0 and rows is not None and len(rows)>=target
        target_codes=set(rows.head(target).code) if rows is not None else set()
        for code, pos in positions.items():
            bar, previous = today.get(code), last_bars.get(code)
            event = events.get((date, code))
            gap = bool(bar and previous and bar["preclose"] > 0 and
                       abs(bar["preclose"]-previous["close"]) > .005)
            if gap and not event:
                raise ValueError(f"Unresolved corporate action/reference gap: {date} {code}")
            if event:
                expected = (previous["close"]-float(event.get("cash_per_share",0)))/(1+float(event.get("bonus_per_share",0)))
                if not bar or abs(expected-bar["preclose"])>.015:
                    raise ValueError(f"Corporate action does not reconcile reference price: {date} {code}")
                # Require actual payment/availability dates, not ex-date cash fiction.
                if float(event.get("cash_per_share", 0)):
                    amount = money(pos["shares"]*event["cash_per_share"])
                    receivables.append(dict(date=event["pay_date"],
                                            amount=amount, code=code))
                    action_log.append(dict(date=date,code=code,type="DIVIDEND_ENTITLEMENT",
                                           amount=amount, cash_change=0., shares_change=0))
                    if event.get("cash_is_gross", False):
                        pos.setdefault("dividend_claims", []).append(amount)
                if float(event.get("bonus_per_share", 0)):
                    if pos.get("locked_shares", 0):
                        raise ValueError("Overlapping stock distribution locks require manual review")
                    exact = pos["shares"]*float(event["bonus_per_share"])
                    if abs(exact-round(exact))>1e-6:
                        raise ValueError("Fractional corporate action allocation requires broker confirmation")
                    added = int(round(exact))
                    taxable = money(pos["shares"]*float(event.get("taxable_bonus_per_share",0)))
                    if taxable:
                        pos.setdefault("dividend_claims", []).append(taxable)
                    pos["shares"] += added
                    pos["locked_shares"] = added
                    pos["bonus_available_date"] = event["available_date"]
                    action_log.append(dict(date=date,code=code,type="BONUS_ENTITLEMENT",
                                           amount=0.,cash_change=0.,shares_change=added))
                if bar:
                    last_marks[code] = bar["preclose"]
            if pos.get("locked_shares", 0) and pos["bonus_available_date"] <= date:
                pos["locked_shares"] = 0
        for r in list(receivables):
            if r["date"] <= date:
                cash = money(cash+r["amount"])
                action_log.append(dict(date=date,code=r["code"],type="DIVIDEND_PAID",
                                       amount=r["amount"],cash_change=r["amount"],shares_change=0))
                receivables.remove(r)
        sold = set()
        for code, pos in list(positions.items()):
            if policy.holding_mode=="legacy_review":
                if review_due and code not in target_codes:
                    pos["exit_pending"]=True
                if not pos.get("exit_pending",False):
                    continue
            elif idx < pos["due_index"]:
                continue
            if date <= pos["buy_date"]:
                order(date, code, "SELL", "BLOCKED", "T+1")
                continue
            px, cap, reason = quote(code, "SELL", today)
            if reason:
                order(date, code, "SELL", "PENDING", reason)
                continue
            qty = min(pos["shares"]-pos.get("locked_shares", 0), cap)
            if qty < pos["shares"]:
                qty = buy_quantity(code, qty)
            if qty <= 0:
                order(date, code, "SELL", "PENDING", "liquidity_capacity")
                continue
            gross = money(qty*px)
            commission, transfer, stamp = fees(gross, "SELL", cfg)
            ratio = qty/pos["shares"]
            tax = money(dividend_tax(pos.get("dividend_claims", []), pos["buy_date"], date)*ratio)
            net = money(gross-commission-transfer-stamp-tax)
            if net < 0:
                order(date, code, "SELL", "PENDING", "proceeds_below_fees")
                continue
            basis = money(pos["cost_basis"]*qty/pos["shares"])
            pos["dividend_claims"] = [x*(1-ratio) for x in pos.get("dividend_claims", [])]
            cash = money(cash+net)
            pos["shares"] -= qty
            pos["cost_basis"] = money(pos["cost_basis"]-basis)
            trades.append(dict(date=date, code=code, side="SELL", shares=qty, price=px,
                               gross=gross, commission=commission, transfer_fee=transfer,
                               stamp_tax=stamp, dividend_tax=tax, cash_after=cash, realized_pnl=money(net-basis),
                               reason="individual_expiry", signal_date=pos["signal_date"]))
            sold.add(code)
            order(date, code, "SELL", "FILLED" if not pos["shares"] else "PARTIAL",
                  "individual_expiry")
            if not pos["shares"]:
                del positions[code]
        signal, rows = qmap.get(prior, {}), signals.get(prior)
        target = max(0, int(signal.get("recommended_count", 0)))
        if cfg.max_positions:
            target = min(target, cfg.max_positions)
        allowed = bool(signal.get("buy_allowed_soft", False)) and signal.get("new_position_gate") in {"开", "半开"}
        # Opening allocations use only prior closes and actual sell proceeds.
        opening_equity = cash+sum(p["shares"]*last_marks[c] for c,p in positions.items())
        budget = money(opening_equity/target) if target else 0.
        if allowed and target and rows is not None and (policy.holding_mode!="legacy_review" or review_due):
            buy_rows=rows if policy.candidate_fallback else rows.head(target)
            for row in buy_rows.to_dict("records"):
                if len(positions) >= target:
                    break
                code = row["code"]
                if code in positions or (policy.forbid_same_day_reentry and code in sold):
                    continue
                px, cap, reason = quote(code, "BUY", today)
                if today.get(code, {}).get("isST") == 1:
                    reason = "ST_buy_excluded"
                if reason:
                    order(date, code, "BUY", "EXPIRED", reason, prior)
                    continue
                allocation = min(budget, cash)
                qty = buy_quantity(code, min(cap, math.floor(allocation/px)))
                while qty:
                    gross = money(qty*px)
                    commission, transfer, stamp = fees(gross, "BUY", cfg)
                    total = money(gross+commission+transfer)
                    if total <= allocation:
                        break
                    qty = buy_quantity(code, qty-1)
                if not qty:
                    order(date, code, "BUY", "EXPIRED", "insufficient_cash_or_lot", prior)
                    continue
                cash = money(cash-total)
                hold = max(1, int(row["stock_hold_days"]))
                positions[code] = dict(shares=qty, cost_basis=total, buy_date=date,
                                       signal_date=prior, due_index=idx+hold,
                                       planned_hold_days=hold,
                                       planned_sell_date=dates[idx+hold] if idx+hold<len(dates) else None,
                                       mystic_buy_time=row.get("stock_buy_time"),
                                       mystic_sell_time=row.get("stock_sell_time"))
                trades.append(dict(date=date, code=code, side="BUY", shares=qty, price=px,
                                   gross=gross, commission=commission, transfer_fee=transfer,
                                   stamp_tax=0., dividend_tax=0., cash_after=cash, realized_pnl=0.,
                                   reason="prior_close_candidate", signal_date=prior))
                order(date, code, "BUY", "FILLED", "prior_close_candidate", prior)
        if policy.holding_mode=="legacy_review" and review_due and positions:
            next_review=idx+max(1,int(round(float(rows.head(target).stock_hold_days.median()))))
        last_marks.update({c:b["close"] for c,b in today.items() if b["close"] > 0})
        market_value = money(sum(p["shares"]*last_marks[c] for c,p in positions.items()))
        receivable = money(sum(r["amount"] for r in receivables))
        tax_liability = money(sum(dividend_tax(p.get("dividend_claims", []),p["buy_date"],date)
                                  for p in positions.values()))
        total = money(cash+market_value+receivable-tax_liability)
        peak = max(peak, total)
        equity.append(dict(date=date, cash=cash, market_value=market_value,
                           receivable=receivable, dividend_tax_liability=tax_liability, equity=total,
                           total_return=total/cfg.initial_cash-1, drawdown=total/peak-1,
                           holding_count=len(positions)))
        for code, p in positions.items():
            history.append(dict(date=date, code=code, **p,
                                remaining_hold_sessions=max(0,p["due_index"]-idx),
                                sellable_shares=p["shares"]-p.get("locked_shares",0) if p["buy_date"]<date else 0,
                                mark_price=last_marks[code], stale_mark=code not in today or today[code]["tradestatus"] != 1,
                                market_value=money(p["shares"]*last_marks[code]),
                                unrealized_pnl=money(p["shares"]*last_marks[code]-p["cost_basis"])))
        assert cash >= 0 and all(p["shares"]>0 and isinstance(p["shares"],int) for p in positions.values())
        last_bars.update(today)
    return {"equity": pd.DataFrame(equity), "trades": pd.DataFrame(trades, columns=[
                "date","code","side","shares","price","gross","commission","transfer_fee",
                "stamp_tax","dividend_tax","cash_after","realized_pnl","reason","signal_date"]),
            "orders": pd.DataFrame(orders,columns=["date","code","side","status","reason","signal_date"]),
            "corporate_actions": pd.DataFrame(action_log,columns=["date","code","type","amount","cash_change","shares_change"]),
            "holdings": pd.DataFrame(history),
            "state": dict(config=asdict(cfg), policy=asdict(policy), last_processed_date=dates[-1],
                          cash=cash, positions=positions, receivables=receivables)}
