import unittest
import pandas as pd
from execution_simulator import Config, simulate, buy_quantity, fees, limit_rate


class BrokerTests(unittest.TestCase):
    def inputs(self, n=6, codes=("sz.000001",), hold=1):
        dates = pd.bdate_range("2026-05-25", periods=n).strftime("%Y-%m-%d").tolist()
        bars = pd.DataFrame([dict(date=d,code=c,open=10.,high=10.5,low=9.5,
                                 close=10.,preclose=10.,volume=1000000,
                                 tradestatus=1,isST=0) for d in dates for c in codes])
        candidates = pd.DataFrame([dict(date=d,code=c,xuan_score=1-i*.1,
                                        stock_hold_days=hold) for d in dates for i,c in enumerate(codes)])
        qi = pd.DataFrame([dict(date=d,recommended_count=1,buy_allowed_soft=True,
                                new_position_gate="开") for d in dates])
        return dates,bars,candidates,qi

    def test_prior_signal_integer_cash_and_t_plus_one(self):
        dates,b,c,q=self.inputs()
        r=simulate(b,c,q)
        t=r["trades"]
        self.assertEqual(t.iloc[0].date,dates[1])
        self.assertEqual(t.iloc[0].signal_date,dates[0])
        self.assertEqual(t.iloc[1].date,dates[2])
        self.assertTrue((t[t.side=="BUY"].shares%100==0).all())
        self.assertTrue((r["equity"].cash>=0).all())
        self.assertEqual(r["holdings"].iloc[0].sellable_shares,0)
        self.assertTrue((t[t.side=="SELL"].stamp_tax>0).all())
        self.assertTrue((t[t.side=="BUY"].stamp_tax==0).all())

    def test_closed_gate_does_not_prevent_due_sale(self):
        ds,b,c,q=self.inputs()
        q.loc[q.date>=ds[1],["recommended_count","buy_allowed_soft"]]=[0,False]
        r=simulate(b,c,q)
        self.assertEqual(list(r["trades"].side),["BUY","SELL"])
        self.assertEqual(r["equity"].iloc[-1].holding_count,0)

    def test_individual_expiry_ignores_rank_change(self):
        ds,b,c,q=self.inputs(codes=("sz.000001","sz.000002"),hold=3)
        c.loc[(c.date>=ds[1])&(c.code=="sz.000002"),"xuan_score"]=10
        r=simulate(b,c,q)
        t=r["trades"]
        self.assertEqual(t.iloc[0].code,"sz.000001")
        self.assertEqual(t.iloc[1].date,ds[4])

    def test_limit_and_suspension_sell_retry(self):
        ds,b,c,q=self.inputs()
        b.loc[b.date==ds[2],["open","high","low","close"]]=[9,9.1,9,9]
        b.loc[b.date==ds[3],"tradestatus"]=0
        b.loc[b.date==ds[3],["open","high","low","close","preclose"]]=9
        b.loc[b.date==ds[4],"preclose"]=9
        # Restore prior close reference so this isn't an unmodeled ex-right event.
        b.loc[b.date==ds[3],"preclose"]=9
        b.loc[b.date==ds[4],["open","high","low","close"]]=[9,9.5,8.5,9]
        b.loc[b.date==ds[5],"preclose"]=9
        r=simulate(b,c,q)
        self.assertEqual(r["trades"].iloc[1].date,ds[4])
        self.assertIn("limit_down_open",list(r["orders"].reason))
        self.assertIn("suspended_or_missing",list(r["orders"].reason))

    def test_insufficient_cash_no_fractional_share(self):
        ds,b,c,q=self.inputs()
        r=simulate(b,c,q,Config(initial_cash=100))
        self.assertTrue(r["trades"].empty)
        self.assertEqual(r["equity"].iloc[-1].equity,100)

    def test_no_terminal_liquidation_and_no_future_dependency(self):
        ds,b,c,q=self.inputs(hold=10)
        short=simulate(b[b.date<=ds[3]],c,q)
        long=simulate(b,c,q)
        pd.testing.assert_frame_equal(short["trades"],long["trades"])
        pd.testing.assert_frame_equal(short["equity"],long["equity"].iloc[:4].reset_index(drop=True))
        self.assertIsNone(short["state"]["positions"]["sz.000001"]["planned_sell_date"])

    def test_corporate_action_stops_instead_of_false_loss(self):
        ds,b,c,q=self.inputs(hold=10)
        b.loc[b.date==ds[2],"preclose"]=9
        with self.assertRaisesRegex(ValueError,"corporate action"):
            simulate(b,c,q)

    def test_missing_bar_cannot_fill_or_free_holding(self):
        ds,b,c,q=self.inputs()
        b=b[~((b.date==ds[2])&(b.code=="sz.000001"))]
        # An additional security preserves the real market calendar.
        other=self.inputs(codes=("sz.000002",))[1]
        r=simulate(pd.concat([b,other]),c,q)
        self.assertEqual(r["trades"].iloc[1].date,ds[3])
        self.assertTrue(r["holdings"].loc[r["holdings"].date==ds[2],"stale_mark"].all())

    def test_partial_sale_and_share_conservation(self):
        ds,b,c,q=self.inputs()
        b.loc[b.date>=ds[1],"volume"]=10000
        r=simulate(b,c,q)
        sells=r["trades"].query("side=='SELL'")
        self.assertGreater(len(sells),1)
        self.assertTrue((sells.shares<=100).all())
        bought=r["trades"].query("side=='BUY'").shares.sum()
        remaining=sum(p["shares"] for p in r["state"]["positions"].values())
        self.assertEqual(bought,sells.shares.sum()+remaining)

    def test_board_lots_and_fees(self):
        self.assertEqual(buy_quantity("sz.300001",299),200)
        self.assertEqual(buy_quantity("sh.688001",199),0)
        self.assertEqual(buy_quantity("sh.688001",201),201)
        self.assertEqual(fees(10000,"BUY",Config()),(5.,.1,0.))
        self.assertEqual(fees(10000,"SELL",Config()),(5.,.1,5.))
        self.assertEqual(limit_rate("sz.000001",True,"2026-07-03"),.05)
        self.assertEqual(limit_rate("sz.000001",True,"2026-07-06"),.10)

    def test_duplicate_data_rejected(self):
        ds,b,c,q=self.inputs()
        with self.assertRaisesRegex(ValueError,"Duplicate"):
            simulate(pd.concat([b,b.iloc[:1]]),c,q)

    def test_cash_dividend_receivable_and_actual_holding_tax(self):
        ds,b,c,q=self.inputs(hold=10)
        b.loc[b.date>=ds[2],["open","close","preclose"]]=9.5
        b.loc[b.date>=ds[2],["low","high"]]=[9.,10.]
        event=dict(date=ds[2],code="sz.000001",cash_per_share=.5,
                   cash_is_gross=True,pay_date=ds[4])
        r=simulate(b,c,q,corporate_actions=[event])
        qty=r["trades"].iloc[0].shares
        day=r["equity"].iloc[2]
        self.assertEqual(day.receivable,qty*.5)
        self.assertEqual(day.dividend_tax_liability,round(qty*.5*.2,2))
        self.assertEqual(r["equity"].iloc[-1].receivable,0)
        self.assertEqual(r["equity"].iloc[-1].cash,round(r["equity"].iloc[1].cash+qty*.5,2))

    def test_bonus_shares_locked_until_listing(self):
        ds,b,c,q=self.inputs(hold=1)
        b.loc[b.date>=ds[2],["open","close","preclose"]]=5.
        b.loc[b.date>=ds[2],["low","high"]]=[4.5,5.5]
        q.loc[q.date>=ds[1],["recommended_count","buy_allowed_soft"]]=[0,False]
        event=dict(date=ds[2],code="sz.000001",bonus_per_share=1.,available_date=ds[4])
        r=simulate(b,c,q,corporate_actions=[event])
        t=r["trades"]
        self.assertEqual(t.iloc[1].shares,t.iloc[0].shares)
        self.assertEqual(t.iloc[2].date,ds[4])
        self.assertEqual(t.iloc[2].shares,t.iloc[0].shares)


if __name__=="__main__":
    unittest.main()
