import unittest
import contextlib
import io
import json
import os
import tempfile
from argparse import Namespace
from pathlib import Path
from unittest.mock import patch
import pandas as pd
from xuan_execution_rules import capital_amount, hundred_share_buy, reassess_t1_exit
from replay_original_orders import replay


class RequestedRulesTests(unittest.TestCase):
    def test_capital_is_parameterized_not_fixed_to_one_hundred_thousand(self):
        for amount in [30000,100000,1000000]:
            self.assertEqual(capital_amount(amount),float(amount))
        for amount in [0,-1,float("nan"),float("inf")]:
            with self.assertRaises(ValueError):capital_amount(amount)

    def test_every_purchase_is_a_hundred_share_multiple(self):
        for code in ["sz.000001","sz.300005","sh.600000","sh.688001"]:
            for capacity in [0,99,100,199,200,201,299,10001]:
                qty=hundred_share_buy(code,capacity)
                self.assertEqual(qty%100,0)
                self.assertLessEqual(qty,capacity)
                if code=="sh.688001":self.assertTrue(qty==0 or qty>=200)

    def test_t1_conflict_recomputes_algorithm_instead_of_forcing_tomorrow(self):
        dates=["2026-05-28","2026-05-29","2026-06-01","2026-06-02","2026-06-03"]
        inputs=[]
        def algorithm(profile,qi,code):
            inputs.append(qi["date"])
            return dict(stock_hold_days=3,stock_sell_time="13:37",stock_timing_reason="daily xuan decision")
        same=reassess_t1_exit({"code":"sz.000001"},{"date":dates[0]},dates[0],dates[0],dates,algorithm)
        self.assertFalse(same["eligible"])
        self.assertEqual(inputs,[])
        tomorrow=reassess_t1_exit({"code":"sz.000001"},{"date":dates[1]},dates[0],dates[1],dates,algorithm)
        self.assertFalse(tomorrow["eligible"])
        later=reassess_t1_exit({"code":"sz.000001"},{"date":dates[3]},dates[0],dates[3],dates,algorithm)
        self.assertTrue(later["eligible"])
        self.assertEqual(later["planned_time"],"13:37")
        self.assertEqual(later["elapsed_sessions"],3)
        self.assertEqual(inputs,[dates[1],dates[3]])

    def test_second_point_can_be_tomorrow_when_model_says_so(self):
        dates=["2026-05-29","2026-06-01"]
        point=reassess_t1_exit({"code":"sz.000001"},{},dates[0],dates[1],dates,
            lambda *a:dict(stock_hold_days=1,stock_sell_time="14:26"))
        self.assertTrue(point["eligible"])
        self.assertEqual(point["elapsed_sessions"],1)
        self.assertEqual(point["planned_time"],"14:26")

    def test_full_broker_defers_same_day_exit_to_new_algorithm_point(self):
        dates=["2026-05-27","2026-05-28","2026-05-29","2026-06-01","2026-06-02"]
        with tempfile.TemporaryDirectory() as directory:
            before=os.getcwd();os.chdir(directory)
            try:
                root=Path(".")
                source=root/"data/strategy";source.mkdir(parents=True)
                raw=root/"data/market/raw_unadjusted";raw.mkdir(parents=True)
                minute=root/"minutes";minute.mkdir()
                out=root/"result";out.mkdir()
                Path("data/raw").mkdir(parents=True)
                pd.DataFrame([dict(code="sz.000001",code_name="Fixture")]).to_csv(source/"stock_xuan_profile.csv",index=False)
                pd.DataFrame(columns=["date","action","code","buy_time","sell_time"]).to_csv(source/"xuan_trades.csv",index=False)
                pd.DataFrame([dict(date=d,recommended_count=1,buy_allowed_soft=i==0,new_position_gate="开") for i,d in enumerate(dates)]).to_csv(source/"daily_qi_profile.csv",index=False)
                pd.DataFrame([dict(date=d,code="sz.000001",xuan_score=1.,stock_buy_time="10:00",stock_sell_time="14:00",stock_hold_days=0) for d in dates]).to_csv(source/"daily_candidates.csv",index=False)
                pd.DataFrame([dict(date=d,code="sz.000001",open=10.,close=10.,preclose=10.,volume=100000,tradestatus=1,isST=0) for d in dates]).to_csv(raw/"sz.000001.csv",index=False)
                for d in dates:
                    pd.DataFrame([dict(date=d,code="sz.000001",time=d.replace("-","")+clock+"000",open=10.,close=10.,high=11.,low=9.,volume=100000,adjustflag=3) for clock in ["100500","142000"]]).to_csv(minute/(d+"_sz.000001.csv"),index=False)
                def reassess(profile,qi,bought,today,calendar):
                    return reassess_t1_exit(profile,qi,bought,today,calendar,
                        lambda *unused:dict(stock_hold_days=3,stock_sell_time="14:15",stock_timing_reason="fixture algorithm requires three sessions"))
                args=Namespace(initial_cash=30000,dynamic_legacy=True,small_position_cap=0.,start_date=dates[0],end_date=dates[-1],signals_dir=None,output_dir=str(out),minute_dir=str(minute))
                with patch("replay_original_orders.reassess_t1_exit",side_effect=reassess),contextlib.redirect_stdout(io.StringIO()):
                    replay(args)
                result=out/"dynamic_legacy_original_weights"
                trades=pd.read_csv(result/"trades.csv")
                self.assertEqual(list(trades.side),["BUY","SELL"])
                self.assertEqual(trades.iloc[0].date,dates[0])
                self.assertEqual(trades.iloc[1].date,dates[3])
                self.assertEqual(trades.iloc[1].planned_time,"14:15")
                self.assertTrue((trades[trades.side=="BUY"].shares%100==0).all())
                self.assertTrue((trades.cash_after>=0).all())
                log=pd.read_csv(result/"t1_reassessments.csv")
                self.assertEqual(list(log.date),dates[1:4])
                self.assertFalse(bool(log.iloc[0].eligible))
                self.assertTrue(bool(log.iloc[-1].eligible))
                state=json.loads((result/"state.json").read_text())
                self.assertEqual(state["initial_cash"],30000)
                self.assertEqual(state["positions"],{})
            finally:
                os.chdir(before)


if __name__=="__main__":unittest.main()
