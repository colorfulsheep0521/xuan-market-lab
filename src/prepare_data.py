"""Build portable strategy inputs from public labels and unadjusted bars."""
import argparse
from argparse import Namespace
import json
from pathlib import Path

import pandas as pd
import baostock as bs
import run_xuan_lab as strategy
from download_paper_data import download


def build_inputs(labels, bars, start_date, end_date, synthetic=False):
    source=Path("data/strategy");source.mkdir(parents=True,exist_ok=True)
    profiles=strategy.build_stock_profiles(labels)
    profiles.to_csv(source/"stock_xuan_profile.csv",index=False)
    bars=bars.copy();bars["date"]=pd.to_datetime(bars.date)
    days=sorted(bars.date.unique())
    qi=strategy.build_daily_qi([pd.Timestamp(d) for d in days])
    previous=[]
    for before,now in zip(days,days[1:]):
        if pd.Timestamp(now)<pd.Timestamp(start_date):continue
        frame=bars[bars.date==before].copy();frame["date"]=now;previous.append(frame)
    if not previous:raise ValueError("Need at least one prior session to prepare pre-open eligibility")
    candidates=strategy.build_candidates(pd.concat(previous,ignore_index=True),profiles,qi,30)
    qi.to_csv(source/"daily_qi_profile.csv",index=False)
    candidates.to_csv(source/"daily_candidates.csv",index=False)
    # Compatibility schema only; dynamic accounts never import somebody's trades.
    pd.DataFrame(columns=["date","action","code","buy_time","sell_time"]).to_csv(source/"xuan_trades.csv",index=False)
    (source/"manifest.json").write_text(json.dumps(dict(start_date=start_date,end_date=end_date,synthetic=synthetic),indent=2))
    return profiles


def main(args):
    source=Path("data/strategy");source.mkdir(parents=True,exist_ok=True)
    if args.labels:
        labels=pd.read_csv(args.labels)
    else:
        if bs.login().error_code!="0":raise RuntimeError("Public data provider login failed")
        try:
            result=bs.query_stock_industry()
            if result.error_code!="0":raise RuntimeError(result.error_msg)
            records=[]
            while result.next():records.append(result.get_row_data())
            if result.error_code!="0":raise RuntimeError(result.error_msg)
            labels=pd.DataFrame(records,columns=result.fields).rename(columns={"industry":"industry_name"})
        finally:bs.logout()
    labels=labels[labels.code.str.startswith(("sh.6","sz.0","sz.3"))].copy()
    if args.codes:labels=labels[labels.code.isin(args.codes)]
    if labels.empty:raise ValueError("No eligible public company labels")
    profiles=strategy.build_stock_profiles(labels)
    profiles.to_csv(source/"stock_xuan_profile.csv",index=False)
    if not args.skip_download:
        download(Namespace(profiles=str(source/"stock_xuan_profile.csv"),output_dir="data/market",
                            start_date=(pd.Timestamp(args.start_date)-pd.Timedelta(days=14)).strftime("%Y-%m-%d"),end_date=args.end_date))
    frames=[pd.read_csv(Path("data/market/raw_unadjusted")/(c+".csv")) for c in profiles.code]
    bars=pd.concat(frames,ignore_index=True)
    bars=bars[bars.date<=args.end_date]
    build_inputs(labels,bars,args.start_date,args.end_date)
    print("Prepared public-data strategy inputs; companies:",len(profiles))


if __name__=="__main__":
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("--start-date",required=True);p.add_argument("--end-date",required=True)
    p.add_argument("--labels",help="Optional public CSV with code,code_name,industry_name")
    p.add_argument("--codes",nargs="*",help="Optional explicit public security codes")
    p.add_argument("--skip-download",action="store_true")
    main(p.parse_args())
