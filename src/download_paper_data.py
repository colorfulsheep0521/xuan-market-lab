"""Download validated unadjusted daily data for the frozen experimental universe."""
import argparse
import fcntl
import json
import signal
from pathlib import Path

import baostock as bs
import pandas as pd


def download(args):
    out=Path(args.output_dir)
    raw=out/"raw_unadjusted"
    raw.mkdir(parents=True,exist_ok=True)
    codes=sorted(pd.read_csv(args.profiles).code.unique())
    Path("data/raw").mkdir(parents=True,exist_ok=True)
    lock=Path("data/raw/.daily_download.lock").open("a")
    fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
    def timeout(*unused):
        raise TimeoutError("Provider timed out; no account state has been changed")
    signal.signal(signal.SIGALRM,timeout)
    signal.alarm(20)
    login=bs.login()
    signal.alarm(0)
    if login.error_code!="0":
        raise RuntimeError(login.error_msg)
    fields="date,code,open,high,low,close,preclose,volume,amount,turn,pctChg,isST,tradestatus"
    try:
        for i,code in enumerate(codes):
            path=raw/(code+".csv")
            old=pd.read_csv(path) if path.exists() else pd.DataFrame()
            start=args.start_date
            if not old.empty:
                # Requery final session as well, to detect upstream corrections.
                start=max(start,str(old.date.max()))
            signal.alarm(20)
            r=bs.query_history_k_data_plus(code,fields,start_date=start,end_date=args.end_date,
                                            frequency="d",adjustflag="3")
            if r.error_code!="0":
                raise RuntimeError((code,r.error_msg))
            rows=[]
            while r.next(): rows.append(r.get_row_data())
            signal.alarm(0)
            if r.error_code!="0":
                raise RuntimeError((code,r.error_msg))
            frame=pd.DataFrame(rows,columns=r.fields)
            if not frame.empty:
                if set(frame.code)!={code} or not frame.date.between(start,args.end_date).all():
                    raise ValueError(f"Provider returned wrong security/date: {code}")
            merged=pd.concat([old,frame],ignore_index=True).drop_duplicates(["date","code"],keep="last")
            merged=merged.sort_values("date")
            temp=path.with_suffix(".tmp")
            merged.to_csv(temp,index=False)
            temp.replace(path)
            if i%25==0: print(i,len(codes),code,flush=True)
        manifest={"adjustflag":"3","start":args.start_date,"end":args.end_date,"codes":codes,
                  "provider":"baostock","price_basis":"unadjusted"}
        temp=out/"raw_manifest.tmp"
        temp.write_text(json.dumps(manifest,indent=2))
        temp.replace(out/"raw_manifest.json")
    finally:
        signal.alarm(0)
        bs.logout()
        lock.close()


if __name__=="__main__":
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("--profiles",default="data/strategy/stock_xuan_profile.csv")
    p.add_argument("--output-dir",default="data/market")
    p.add_argument("--start-date",required=True)
    p.add_argument("--end-date",required=True)
    download(p.parse_args())
