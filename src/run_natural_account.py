"""Natural execution of the legacy cultural strategy, with audited snapshots."""
import argparse
from argparse import Namespace
from datetime import datetime
import fcntl
import json
import os
from pathlib import Path

import pandas as pd
import run_xuan_lab as strategy
from replay_original_orders import replay
from xuan_execution_rules import capital_amount


def audit(snapshot, initial_cash=None):
    trades=pd.read_csv(snapshot/"trades.csv")
    equity=pd.read_csv(snapshot/"equity.csv")
    events=pd.read_csv(snapshot/"corporate_actions.csv")
    state=json.loads((snapshot/"state.json").read_text())
    cash=capital_amount(initial_cash if initial_cash is not None else state["initial_cash"]);shares={};buys={}
    for date in equity.date:
        for r in events[events.date==date].itertuples():
            cash=round(cash+r.cash_change,2)
            shares[r.code]=shares.get(r.code,0)+r.shares_change
        previous_time="00:00"
        for r in trades[trades.date==date].itertuples():
            assert r.execution_time>=r.planned_time
            assert r.execution_time>=previous_time
            previous_time=r.execution_time
            assert r.shares==int(r.shares) and r.shares>0
            if r.side=="BUY":
                assert r.shares%100==0
                cash=round(cash-r.gross-r.commission-r.transfer_fee,2)
                shares[r.code]=shares.get(r.code,0)+r.shares;buys[r.code]=date
            else:
                assert buys[r.code]<date
                cash=round(cash+r.gross-r.commission-r.transfer_fee-r.stamp_tax-r.dividend_tax,2)
                shares[r.code]-=r.shares
            assert abs(cash-r.cash_after)<.011
            assert cash>=0 and shares[r.code]>=0
        row=equity[equity.date==date].iloc[0]
        assert abs(cash-row.cash)<.011
        assert abs(row.equity-(row.cash+row.market_value+row.receivable-row.tax_liability))<.011
    state=json.loads((snapshot/"state.json").read_text())
    assert {c:q for c,q in shares.items() if q}=={c:p["shares"] for c,p in state["positions"].items()}
    report=dict(checks="cash,fees,T+1,chronology,planned-time ordering,share conservation,equity passed",fills=len(trades))
    (snapshot/"audit.json").write_text(json.dumps(report,indent=2))


def main(args):
    initial_cash=capital_amount(args.initial_cash)
    root=Path(".")
    strategy_manifest=json.loads((root/"data/strategy/manifest.json").read_text())
    start_date=args.start_date or strategy_manifest["start_date"]
    if start_date<"2023-08-28":raise ValueError("Current tax configuration supports dates from 2023-08-28")
    account=root/"outputs/accounts"/f"capital_{initial_cash:.2f}"
    account.mkdir(exist_ok=True,parents=True)
    lock=(account/".lock").open("a");fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
    manifest=json.loads((root/"data/market/raw_manifest.json").read_text())
    if manifest["adjustflag"]!="3" or manifest["end"]<args.end_date:raise ValueError("Download unadjusted data through the requested session first")
    stamp=datetime.now().strftime("%Y%m%d_%H%M%S_%f")
    staging=account/"staging"/stamp;staging.mkdir(parents=True)
    source=root/"data/strategy"
    profiles=pd.read_csv(source/"stock_xuan_profile.csv")
    candles=pd.concat([pd.read_csv(root/"data/market/raw_unadjusted"/(c+".csv")) for c in profiles.code],ignore_index=True)
    candles=candles[candles.date<=args.end_date]
    counts=candles.groupby("date").code.nunique()
    if counts.get(args.end_date,0)/counts.max()<.97:raise ValueError("Incomplete universe coverage")
    q=pd.read_csv(source/"daily_qi_profile.csv")
    c=pd.read_csv(source/"daily_candidates.csv",float_precision="round_trip")
    # Archive compatibility is explicit. Extend future calendar-only decisions
    # using prior-session eligibility, without replacing archived model rankings.
    days=sorted(candles.date.unique())
    newdays=[d for d in days if d>q.date.max()]
    if newdays:
        newqi=strategy.build_daily_qi([pd.Timestamp(d) for d in newdays])
        frames=[]
        for day in newdays:
            previous=days[days.index(day)-1]
            frame=candles[candles.date==previous].copy();frame["date"]=pd.Timestamp(day)
            frames.append(frame)
        fresh=strategy.build_candidates(pd.concat(frames,ignore_index=True),profiles,newqi,30)
        q=pd.concat([q,newqi],ignore_index=True);c=pd.concat([c,fresh],ignore_index=True)
    signals=staging/"signals";signals.mkdir()
    q.to_csv(signals/"daily_qi_profile.csv",index=False)
    c.to_csv(signals/"daily_candidates.csv",index=False)
    replay(Namespace(dynamic_legacy=True,small_position_cap=0.,initial_cash=initial_cash,start_date=start_date,end_date=args.end_date,
        signals_dir=str(signals),output_dir=str(staging),minute_dir=str(root/"data/minute")))
    result=staging/"dynamic_legacy_original_weights"
    audit(result,initial_cash)
    pointer=account/"latest.json"
    if pointer.exists():
        prior=account/json.loads(pointer.read_text())["snapshot"]
        oldstate=json.loads((prior/"state.json").read_text())
        if oldstate["initial_cash"]!=initial_cash:raise ValueError("Initial capital differs from the saved account")
        if json.loads((prior/"policy.json").read_text())["start_date"]!=start_date:raise ValueError("Cannot change account start date")
        if oldstate["last_processed_date"]>args.end_date:raise ValueError("Cannot rewind account")
        for name in ["equity","trades"]:
            old=pd.read_csv(prior/(name+".csv"));new=pd.read_csv(result/(name+".csv")).iloc[:len(old)]
            pd.testing.assert_frame_equal(old,new.reset_index(drop=True),check_dtype=False,rtol=1e-10,atol=1e-6)
        if oldstate["last_processed_date"]==args.end_date:
            print("NO_NEW_DATA: chronology, trades and equity verified; no snapshot committed")
            return
    summary=json.loads((result/"summary.json").read_text())
    text=("# 玄学策略自然执行账户\n\n"
      f"截至 {args.end_date}：权益 {summary['final_equity']:,.2f} 元，收益 {summary['total_return']:.2%}，最大回撤 {summary['max_drawdown']:.2%}。\n\n"
      "保持旧玄学排序、当日历法信号、组合复评及推荐股票数量；7–8只仍按原排名选入，不新增二次筛选。\n\n"
      "按每只股票原定买入/卖出时辰排序执行，不统一改为次日开盘。股票只有从账户真实成交后才进入持仓，未成交会影响后续复评。\n\n"
      f"初始模拟资金{initial_cash:,.2f}元；按算法目标数量等权预算并受真实可用现金约束，不设单票比例上限，不从账户外补钱或融资。盈亏与分红改变后续可用资金。\n\n"
      "每次买入均为100股整数倍；科创板同时满足最低200股。卖出保留交易所允许的剩余零股处理。\n\n"
      "当日买入遇到同日卖出信号，保留原信号并逐日重新计算玄学持有期和卖出时辰，直到实际已持有交易日满足当日算法条件；不强制下一日卖出，也不设置最长等待天数。\n\n"
      "整手、T+1、现金不足、实际停牌/时点涨跌停、费用和分红送转仍处理；不设昨日成交量1%上限或同日卖后禁止买入。\n\n"
      "时辰成交以计划时刻之后第一个五分钟区间开盘价近似，订单按有效成交时刻排序；不使用更早区间价格，也不借用稍后卖出的资金提前购买。\n\n"
      "佣金万三最低5元、过户费十万分之一双边、卖出印花税万五。没有逐笔盘口与真实排队，不计额外盘口滑点；分钟成交量只作上限，不保证全量成交。\n\n"
      "旧档案保留的股票池有研究样本选择限制，历法为工程近似；本结果不是独立盲测，亦不代表可保证的真实成交。\n")
    (result/"report.md").write_text(text)
    (result/"policy.json").write_text(json.dumps(dict(strategy="legacy_review",start_date=start_date,signal="same_day_calendar_preopen",stock_times=True,initial_cash=initial_cash,buy_lot_multiple=100,discretionary_position_cap=None,t1_resolution="recompute current xuan holding horizon and sell time each later session",wide_count_user_choice="ranked_entries",execution_proxy="next five-minute bar open; zero extra slippage"),ensure_ascii=False,indent=2))
    dest=account/"runs"/stamp;dest.parent.mkdir(exist_ok=True)
    os.replace(result,dest)
    # Keep signal and provenance files with the committed account snapshot.
    os.replace(signals,dest/"signals")
    temp=account/"latest.tmp";temp.write_text(json.dumps(dict(snapshot=str(dest.relative_to(account)),end_date=args.end_date),indent=2));os.replace(temp,pointer)
    print(text);print("snapshot:",dest)


if __name__=="__main__":
    p=argparse.ArgumentParser(description=__doc__);p.add_argument("--end-date",required=True)
    p.add_argument("--initial-cash",type=float,default=100000.)
    p.add_argument("--start-date",help="Defaults to the prepared strategy manifest")
    main(p.parse_args())
