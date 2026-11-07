"""Generate entirely synthetic prices, company labels and five-minute bars."""
import json
from pathlib import Path

import pandas as pd
from prepare_data import build_inputs


def main():
    days=pd.bdate_range("2024-01-01",periods=45)
    start=days[1].strftime("%Y-%m-%d");end=days[-1].strftime("%Y-%m-%d")
    raw=Path("data/market/raw_unadjusted");raw.mkdir(parents=True,exist_ok=True)
    minute=Path("data/minute");minute.mkdir(parents=True,exist_ok=True)
    Path("data/raw").mkdir(parents=True,exist_ok=True)
    codes=[f"sz.{i:06d}" for i in range(1,9)]
    labels=pd.DataFrame([dict(code=c,code_name="合成示例"+str(i),industry_name="电子设备") for i,c in enumerate(codes)])
    all_bars=[]
    for i,code in enumerate(codes):
        rows=[];price=10.+i
        for day in days:
            date=day.strftime("%Y-%m-%d")
            row=dict(date=date,code=code,open=price,high=price+.1,low=price-.1,close=price,
                     preclose=price,volume=1000000,amount=price*1000000,turn=1.,pctChg=0.,isST=0,tradestatus=1)
            rows.append(row)
            ends=list(pd.date_range(date+" 09:35",date+" 11:30",freq="5min"))+list(pd.date_range(date+" 13:05",date+" 15:00",freq="5min"))
            pd.DataFrame([dict(date=date,time=t.strftime("%Y%m%d%H%M%S")+"000",code=code,open=price,high=price+.1,
                               low=price-.1,close=price,volume=100000,amount=price*100000,adjustflag=3) for t in ends]).to_csv(minute/(date+"_"+code+".csv"),index=False)
        frame=pd.DataFrame(rows);frame.to_csv(raw/(code+".csv"),index=False);all_bars.append(frame)
    (raw.parent/"raw_manifest.json").write_text(json.dumps(dict(adjustflag="3",start=days[0].strftime("%Y-%m-%d"),end=end,codes=codes,synthetic=True),indent=2))
    build_inputs(labels,pd.concat(all_bars,ignore_index=True),start,end,synthetic=True)
    print("Synthetic fixtures only; business-day calendar is NOT an exchange calendar.")
    print("Next: python src/run_natural_account.py --end-date",end,"--initial-cash 30000")


if __name__=="__main__":main()
