import unittest
import pandas as pd
from replay_original_orders import minute_quote
from execution_simulator import Config, ExecutionPolicy, simulate
import test_execution_simulator as fixtures


class NaturalTimingTests(unittest.TestCase):
    def test_never_use_bar_that_started_before_order(self):
        frame=pd.DataFrame([dict(date="2026-05-28",code="sz.000887",time=t,
                   open=p,high=p+1,low=p-1,close=p,volume=10000,adjustflag=3)
                   for t,p in [("20260528094500000",10),("20260528095000000",12)]])
        result=minute_quote(frame,dict(date="2026-05-28",code="sz.000887",planned_time="09:43"))
        self.assertEqual(result["time"],"09:45")
        self.assertEqual(result["price"],12)

    def test_missing_market_window_does_not_backdate_fill(self):
        frame=pd.DataFrame([dict(date="2026-05-28",code="sz.000887",time="20260528150000000",
                   open=10,high=11,low=9,close=10,volume=100,adjustflag=3)])
        self.assertIsNone(minute_quote(frame,dict(date="2026-05-28",code="sz.000887",planned_time="14:59")))
        frame.loc[0,"adjustflag"]=2
        with self.assertRaisesRegex(ValueError,"Adjusted"):
            minute_quote(frame,dict(date="2026-05-28",code="sz.000887",planned_time="14:50"))

    def test_legacy_review_keeps_ranked_existing_position(self):
        ds,b,c,q=fixtures.BrokerTests().inputs(hold=1)
        r=simulate(b,c,q,policy=ExecutionPolicy(holding_mode="legacy_review"))
        self.assertEqual(list(r["trades"].side),["BUY"])

    def test_calendar_signal_is_not_forced_one_day_late(self):
        ds,b,c,q=fixtures.BrokerTests().inputs()
        q.loc[q.date==ds[0],"new_position_gate"]="闭"
        r=simulate(b,c,q,policy=ExecutionPolicy(signal_timing="calendar_preopen"))
        self.assertEqual(r["trades"].iloc[0].date,ds[1])
        self.assertEqual(r["trades"].iloc[0].signal_date,ds[1])


if __name__=="__main__":unittest.main()
