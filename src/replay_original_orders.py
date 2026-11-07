"""Execution-only experiment: replay archived strategy intents at their own times.

This does not regenerate strategy decisions after missed executions. It measures
what execution alone changes while freezing the old stock/date/target-count plan.
Five-minute bar opens AFTER the planned minute approximate fills, never preceding
bar opens. No one-day delay, rank fallback, same-day reentry ban or 1% cap.
"""
import argparse
import fcntl
import json
import signal
from pathlib import Path

import baostock as bs
import pandas as pd
from execution_simulator import Config, fees, money, buy_quantity, limit_rate, dividend_tax
from xuan_execution_rules import capital_amount, hundred_share_buy, reassess_t1_exit


def minute_quote(minute,plan):
    if minute.empty:return None
    if set(minute.code)!={plan["code"]} or set(minute.date)!={plan["date"]}:
        raise ValueError("Wrong intraday security/session")
    minute=minute.copy()
    if not pd.to_numeric(minute.adjustflag).eq(3).all():raise ValueError("Adjusted intraday data")
    for key in ("open","high","low","close","volume"):
        minute[key]=pd.to_numeric(minute[key],errors="coerce")
    minute["bar_start"]=pd.to_datetime(minute.time.astype(str).str[:14],format="%Y%m%d%H%M%S")-pd.Timedelta(minutes=5)
    target=pd.Timestamp(plan["date"]+" "+plan["planned_time"])
    eligible=minute[(minute.bar_start>=target)&(minute.volume>0)].sort_values("bar_start")
    if eligible.empty:return None
    row=eligible.iloc[0]
    if not pd.notna(row.open) or row.open<=0:return None
    return dict(price=money(row.open),volume=int(row.volume),time=row.bar_start.strftime("%H:%M"))


def replay(args):
    initial_cash=capital_amount(getattr(args,"initial_cash",100000.))
    root=Path(".")
    old=root/"data/strategy"
    cache=root/"data/market"
    signal_root=Path(args.signals_dir) if args.signals_dir else old
    out=Path(args.output_dir) if args.output_dir else root/"outputs/research"
    out.mkdir(exist_ok=True,parents=True)
    minute_dir=Path(args.minute_dir) if args.minute_dir else out/"minute_raw";minute_dir.mkdir(exist_ok=True,parents=True)
    oldtrades=pd.read_csv(old/"xuan_trades.csv",float_precision="round_trip")
    candidates=pd.read_csv(signal_root/"daily_candidates.csv",float_precision="round_trip")
    qi=pd.read_csv(signal_root/"daily_qi_profile.csv").set_index("date")
    profiles=pd.read_csv(old/"stock_xuan_profile.csv")
    profile_map=profiles.set_index("code",drop=False).to_dict("index")
    names=profiles.set_index("code").code_name.to_dict()
    plans=[];entry_times={}
    for index,r in enumerate(oldtrades.to_dict("records")):
        if r["action"]=="BUY":
            entry_times[r["code"]]=str(r["sell_time"])
            time=str(r["buy_time"])
        else:
            time=entry_times[r["code"]]
        plans.append(dict(plan_id=index,date=r["date"],code=r["code"],side=r["action"],
                          planned_time=time,target_count=int(qi.loc[r["date"],"recommended_count"])))
    pd.DataFrame(plans).to_csv(out/"original_intents.csv",index=False)
    cfg=Config(initial_cash=initial_cash,max_previous_volume_fraction=1.,slippage=0.)
    actions=[]
    for path in [cache/"actions.json",root/"data/market/extra_actions.json"]:
        if path.exists():
            for event in json.loads(path.read_text()):
                if not any(e["date"]==event["date"] and e["code"]==event["code"] for e in actions):actions.append(event)
    action_map={(e["date"],e["code"]):e for e in actions}
    codes=set(profiles.code) if args.dynamic_legacy else set(oldtrades.code)
    bars=pd.concat([pd.read_csv(cache/"raw_unadjusted"/(c+".csv")) for c in codes],ignore_index=True)
    daymap={d:g.set_index("code").to_dict("index") for d,g in bars.groupby("date")}
    all_dates=sorted(bars.date.unique())
    all_dates=[d for d in all_dates if d<=args.end_date]
    dates=[d for d in all_dates if args.start_date<=d<=args.end_date]
    if not dates or dates[-1]!=args.end_date:raise ValueError("Requested final market session is missing")
    marks={};previous={};cash=initial_cash;book={};pending=[];receivables=[]
    trades=[];orders=[];equity=[];holdings=[];events=[];peak=initial_cash;t1_checks=[]
    Path("data/raw").mkdir(parents=True,exist_ok=True)
    lock=Path("data/raw/.daily_download.lock").open("a")
    fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
    def timeout(*unused):raise TimeoutError("Intraday provider timeout")
    signal.signal(signal.SIGALRM,timeout)
    logged=False
    next_review=0;generated=[]
    def resolve_action(date,code):
        nonlocal logged
        if not logged:
            assert bs.login().error_code=="0";logged=True
        signal.alarm(20)
        r=bs.query_dividend_data(code,year=date[:4],yearType="operate")
        if r.error_code!="0":raise ValueError(r.error_msg)
        rows=[]
        while r.next():rows.append(r.get_row_data())
        signal.alarm(0)
        if r.error_code!="0":raise ValueError(r.error_msg)
        frame=pd.DataFrame(rows,columns=r.fields)
        frame.to_csv(out/(code+"_dividends.csv"),index=False)
        for row in frame.to_dict("records"):
            ex=row.get("dividOperateDate","")
            if not ex:continue
            def number(k):return float(row.get(k) or 0)
            action_map[(ex,code)]=dict(date=ex,code=code,cash_per_share=number("dividCashPsBeforeTax"),
                pay_date=row.get("dividPayDate",""),bonus_per_share=number("dividStocksPs")+number("dividReserveToStockPs"),
                taxable_bonus_per_share=number("dividStocksPs"),available_date=row.get("dividStockMarketDate",""))
        return action_map.get((date,code))
    def quote(plan):
        nonlocal logged
        path=minute_dir/(plan["date"]+"_"+plan["code"]+".csv")
        if path.exists():
            minute=pd.read_csv(path,dtype={"time":str})
        else:
            if not logged:
                assert bs.login().error_code=="0";logged=True
            signal.alarm(20)
            r=bs.query_history_k_data_plus(plan["code"],"date,time,code,open,high,low,close,volume,amount,adjustflag",
                start_date=plan["date"],end_date=plan["date"],frequency="5",adjustflag="3")
            if r.error_code!="0":raise RuntimeError(r.error_msg)
            rows=[]
            while r.next():rows.append(r.get_row_data())
            signal.alarm(0)
            if r.error_code!="0":raise RuntimeError(r.error_msg)
            minute=pd.DataFrame(rows,columns=r.fields)
            minute.to_csv(path,index=False)
            print("minute",plan["date"],plan["code"],len(minute),flush=True)
        return minute_quote(minute,plan)
    try:
      for day_index,date in enumerate(all_dates):
        today=daymap[date]
        if date not in dates:
            previous.update(today);marks.update({c:b["close"] for c,b in today.items() if b["close"]>0});continue
        for code,pos in book.items():
            bar=today.get(code);before=previous.get(code);event=action_map.get((date,code))
            if bar and before and abs(bar["preclose"]-before["close"])>.005 and not event:
                event=resolve_action(date,code)
                if not event:raise ValueError(f"Unresolved corporate action/reference gap: {date} {code}")
            if event:
                if event.get("cash_per_share",0) and (not event.get("pay_date") or event["pay_date"]<date):raise ValueError("Missing/invalid dividend payment date")
                if event.get("bonus_per_share",0) and (not event.get("available_date") or event["available_date"]<date):raise ValueError("Missing/invalid bonus availability date")
                expected=(before["close"]-event.get("cash_per_share",0))/(1+event.get("bonus_per_share",0))
                if abs(expected-bar["preclose"])>.015:raise ValueError("Corporate action reference mismatch")
                amount=money(pos["shares"]*event.get("cash_per_share",0))
                if amount:
                    receivables.append(dict(date=event["pay_date"],amount=amount,code=code))
                    pos["claims"].append(amount)
                exact=pos["shares"]*event.get("bonus_per_share",0)
                if abs(exact-round(exact))>1e-6:raise ValueError("Noninteger corporate action")
                bonus=int(round(exact));pos["claims"].append(money(pos["shares"]*event.get("taxable_bonus_per_share",0)))
                pos["shares"]+=bonus
                if bonus:pos["locked"]=bonus;pos["available"]=event["available_date"]
                marks[code]=bar["preclose"]
                events.append(dict(date=date,code=code,type="ENTITLEMENT",amount=amount,shares_change=bonus,cash_change=0))
            if pos.get("locked",0) and pos["available"]<=date:pos["locked"]=0
        for r in list(receivables):
            if r["date"]<=date:
                cash=money(cash+r["amount"]);receivables.remove(r)
                events.append(dict(date=date,code=r["code"],type="DIVIDEND_PAID",amount=r["amount"],shares_change=0,cash_change=r["amount"]))
        opening_equity=cash+sum(p["shares"]*marks[c] for c,p in book.items())
        review=False;hold_period=1
        if args.dynamic_legacy:
            daily=[]
            q=qi.loc[date];target=int(q.recommended_count)
            rows=candidates[candidates.date==date].sort_values("xuan_score",ascending=False).head(target)
            review=day_index>=next_review and target>0 and len(rows)>=target
            if review:
                hold_period=max(1,int(round(float(rows.stock_hold_days.median()))))
                selected=set(rows.code)
                for code,pos in book.items():
                    if code not in selected and not pos.get("t1_reschedule") and not any(p["code"]==code for p in pending):
                        daily.append(dict(plan_id=len(generated)+len(daily),date=date,code=code,side="SELL",planned_time=pos["planned_sell_time"],target_count=target))
                allowed=bool(q.buy_allowed_soft) and q.new_position_gate in {"开","半开"}
                if allowed:
                    for row in rows.to_dict("records"):
                        if row["code"] in book:continue
                        daily.append(dict(plan_id=len(generated)+len(daily),date=date,code=row["code"],side="BUY",planned_time=str(row["stock_buy_time"]),target_count=target,planned_sell_time=str(row["stock_sell_time"]),stock_hold_days=int(row["stock_hold_days"])))
                generated.extend(daily)
        else:
            daily=[dict(p) for p in plans if p["date"]==date]
        for code,pos in book.items():
            if not pos.get("t1_reschedule") or any(p["code"]==code for p in pending):continue
            point=reassess_t1_exit(profile_map[code],qi.loc[date],pos["buy_date"],date,all_dates)
            t1_checks.append(dict(code=code,**point,original_signal=pos["t1_reschedule"]))
            if point["eligible"]:
                # Replace the blocked signal with a newly justified model point.
                daily=[p for p in daily if not(p["side"]=="SELL" and p["code"]==code)]
                daily.append(dict(plan_id=len(generated)+len(daily),date=date,code=code,side="SELL",planned_time=point["planned_time"],target_count=0,t1_basis=point))
        for p in pending:
            p=dict(p);p["date"]=date;daily.append(p)
        pending=[];scheduled=[]
        for p in daily:
            quoted=quote(p)
            p["quote"]=quoted
            scheduled.append(p)
        scheduled.sort(key=lambda p:((p["quote"] or {}).get("time",p["planned_time"]),0 if p["side"]=="SELL" else 1,p["plan_id"]))
        for plan in scheduled:
            code=plan["code"];side=plan["side"];bar=today.get(code);pxq=plan["quote"]
            reason=""
            if not pxq or not bar or bar["tradestatus"]!=1:reason="missing_or_suspended_at_plan"
            if side=="SELL" and code not in book:reason="no_position_from_original_plan"
            if side=="BUY" and code in book:reason="position_already_held"
            if side=="SELL" and code in book and book[code]["buy_date"]>=date:reason="T+1"
            if not reason:
                px=pxq["price"];rate=limit_rate(code,bar["isST"]==1,date)
                up,down=money(bar["preclose"]*(1+rate)),money(bar["preclose"]*(1-rate))
                if side=="BUY" and px>=up-.005:reason="limit_at_planned_time"
                if side=="SELL" and px<=down+.005:reason="limit_at_planned_time"
            if reason:
                orders.append(dict(date=date,code=code,side=side,time=plan["planned_time"],status="UNFILLED",reason=reason))
                if side=="SELL" and code in book:
                    if reason=="T+1":
                        book[code]["t1_reschedule"]=dict(date=date,time=plan["planned_time"],plan_id=plan["plan_id"])
                    else:pending.append(plan)
                continue
            if side=="BUY":
                weight=1/max(1,plan["target_count"])
                if args.small_position_cap and plan["target_count"]<=2:weight=min(weight,args.small_position_cap)
                budget=min(cash,opening_equity*weight)
                qty=hundred_share_buy(code,min(int(budget/px),pxq["volume"]))
                while qty:
                    gross=money(qty*px);commission,transfer,stamp=fees(gross,side,cfg)
                    total=money(gross+commission+transfer)
                    if total<=budget:break
                    qty=hundred_share_buy(code,qty-1)
                if not qty:
                    orders.append(dict(date=date,code=code,side=side,time=pxq["time"],status="UNFILLED",reason="cash_or_lot_at_planned_time"));continue
                cash=money(cash-total);tax=0.
                book[code]=dict(shares=qty,cost=total,buy_date=date,claims=[],planned_sell_time=plan.get("planned_sell_time",entry_times.get(code,"14:50")))
                if int(plan.get("stock_hold_days",1))==0:
                    blocked=dict(date=date,time=book[code]["planned_sell_time"],plan_id=plan["plan_id"])
                    book[code]["t1_reschedule"]=blocked
                    orders.append(dict(date=date,code=code,side="SELL",time=blocked["time"],status="DEFERRED",reason="T+1_find_new_xuan_point"))
            else:
                pos=book[code];qty=min(pos["shares"]-pos.get("locked",0),pxq["volume"])
                if qty<pos["shares"]:qty=buy_quantity(code,qty)
                if qty<=0:pending.append(plan);continue
                gross=money(qty*px);commission,transfer,stamp=fees(gross,side,cfg)
                ratio=qty/pos["shares"];tax=money(dividend_tax(pos["claims"],pos["buy_date"],date)*ratio)
                cash=money(cash+gross-commission-transfer-stamp-tax)
                pos["cost"]=money(pos["cost"]*(1-ratio));pos["shares"]-=qty;pos["claims"]=[a*(1-ratio) for a in pos["claims"]]
                if pos["shares"]:pending.append(plan)
                else:del book[code]
            trades.append(dict(date=date,code=code,name=names.get(code,code),side=side,shares=qty,price=px,
                               planned_time=plan["planned_time"],execution_time=pxq["time"],cash_after=cash,
                               gross=gross,commission=commission,transfer_fee=transfer,stamp_tax=stamp,dividend_tax=tax,
                               plan_id=plan["plan_id"]))
            orders.append(dict(date=date,code=code,side=side,time=pxq["time"],status="FILLED",reason="original_intent_at_own_time"))
        if args.dynamic_legacy and review:
            next_review=day_index+hold_period if book else day_index+1
        marks.update({c:b["close"] for c,b in today.items() if b["close"]>0})
        value=money(sum(p["shares"]*marks[c] for c,p in book.items()))
        receivable=money(sum(r["amount"] for r in receivables))
        tax=money(sum(dividend_tax(p["claims"],p["buy_date"],date) for p in book.values()))
        total=money(cash+value+receivable-tax);peak=max(peak,total)
        equity.append(dict(date=date,cash=cash,market_value=value,receivable=receivable,tax_liability=tax,equity=total,drawdown=total/peak-1,holding_count=len(book)))
        for code,p in book.items():holdings.append(dict(date=date,code=code,name=names.get(code,code),**p,market_value=money(p["shares"]*marks[code])))
        previous.update(today)
      label="original_weights" if not args.small_position_cap else f"small_cap_{args.small_position_cap}"
      if args.dynamic_legacy:label="dynamic_legacy_"+label
      dest=out/label;dest.mkdir(exist_ok=True)
      for key,rows in [("trades",trades),("orders",orders),("equity",equity),("holdings",holdings),("corporate_actions",events),("t1_reassessments",t1_checks)]:
          frame=pd.DataFrame(rows)
          if frame.empty:
              columns={"trades":["date","code","side","shares","gross","commission","transfer_fee","stamp_tax","dividend_tax","cash_after","execution_time","planned_time"],"orders":["date","code","side","time","status","reason"],"holdings":["date","code","shares","cost","market_value"],"corporate_actions":["date","code","type","amount","shares_change","cash_change"],"t1_reassessments":["date","code","eligible","reason","original_signal"]}.get(key,["date"])
              frame=pd.DataFrame(columns=columns)
          frame.to_csv(dest/(key+".csv"),index=False)
      if args.dynamic_legacy:pd.DataFrame(generated).to_csv(dest/"generated_intents.csv",index=False)
      (dest/"state.json").write_text(json.dumps(dict(initial_cash=initial_cash,last_processed_date=dates[-1],cash=cash,positions=book,pending_sell_orders=[{k:v for k,v in p.items() if k!="quote"} for p in pending],receivables=receivables,next_review_index=next_review),ensure_ascii=False,indent=2))
      summary=dict(mode="dynamic legacy review; own planned minutes" if args.dynamic_legacy else "frozen original order intents; actual planned minutes, next 5-minute bar open",initial_cash=initial_cash,final_equity=equity[-1]["equity"],total_return=equity[-1]["equity"]/initial_cash-1,max_drawdown=min(r["drawdown"] for r in equity),fills=len(trades),unfilled=len([r for r in orders if r["status"]!="FILLED"]),small_position_cap=args.small_position_cap,t1_reassessments=len(t1_checks))
      (dest/"summary.json").write_text(json.dumps(summary,ensure_ascii=False,indent=2));print(json.dumps(summary,ensure_ascii=False,indent=2))
    finally:
      signal.alarm(0)
      if logged:bs.logout()
      lock.close()


if __name__=="__main__":
    p=argparse.ArgumentParser(description=__doc__);p.add_argument("--small-position-cap",type=float,default=0.)
    p.add_argument("--dynamic-legacy",action="store_true",help="Recompute original review decisions from the actual executed account")
    p.add_argument("--start-date",default="2024-01-02")
    p.add_argument("--end-date",required=True)
    p.add_argument("--signals-dir")
    p.add_argument("--output-dir")
    p.add_argument("--minute-dir")
    p.add_argument("--initial-cash",type=float,default=100000.)
    replay(p.parse_args())
