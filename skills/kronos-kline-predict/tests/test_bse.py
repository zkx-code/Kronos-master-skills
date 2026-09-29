"""Offline market-adapter tests. Fixture prices are not real market data."""
import contextlib
import io
import json
from pathlib import Path
import subprocess
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
import intraday
from market_adapters import get_adapter


def fixture(minutes=5):
    # Two ordinary sessions; the second must never enter pre-open history.
    frame = intraday.bar_grid('2026-09-21', '2026-09-22', minutes, 'bse')[['timestamps']].copy()
    price = 20 + np.arange(len(frame)) * .01
    return frame.assign(open=price, high=price+.1, low=price-.1, close=price+.02,
                        volume=100., amount=200000.)


class BSETests(unittest.TestCase):
    def test_symbol_formats_and_market_separation(self):
        bse = get_adapter('bse')
        for symbol in ('430001', '830799', '870001', '920799', 'BJ920799', ' bj920799 '):
            with self.subTest(symbol=symbol):
                self.assertEqual(bse.normalize_symbol(symbol), symbol.strip().lower().removeprefix('bj'))
        for symbol in ('sh600519', 'sz000001', '600519', '000001', '92079', '920799.BJ'):
            with self.subTest(symbol=symbol), self.assertRaises(ValueError):
                bse.normalize_symbol(symbol)
        self.assertEqual(get_adapter('cn').normalize_symbol('SH600519'), 'sh600519')
        with self.assertRaises(ValueError):
            get_adapter('cn').normalize_symbol('bj920799')

    def test_all_intervals_and_lunch_break(self):
        for market in ('cn', 'bse'):
            for minutes, count in ((1,240),(5,48),(15,16),(30,8),(60,4),(120,2)):
                with self.subTest(market=market, minutes=minutes):
                    grid = intraday.bar_grid('2026-09-22', '2026-09-22', minutes, market)
                    self.assertEqual(len(grid), count)
                    self.assertTrue(grid.timestamps.is_unique)
                    self.assertEqual(grid.timestamps.iloc[-1], pd.Timestamp('2026-09-22 15:00'))
                    self.assertTrue((grid.timestamps - grid.bar_start).eq(pd.Timedelta(minutes=minutes)).all())
                    self.assertEqual(grid.loc[grid.session_leg.eq('AM'), 'timestamps'].iloc[-1], pd.Timestamp('2026-09-22 11:30'))
                    self.assertEqual(grid.loc[grid.session_leg.eq('PM'), 'bar_start'].iloc[0], pd.Timestamp('2026-09-22 13:00'))

    def test_closed_days(self):
        for day in ('2026-09-20', '2026-10-01'):
            with self.subTest(day=day):
                self.assertTrue(intraday.bar_grid(day, day, 5, 'bse').empty)
                with self.assertRaisesRegex(ValueError, 'not a trading day'):
                    intraday.split_history(fixture(), 'timestamps', 5, day, day, 48, 512, 'bse')

    def test_target_prices_are_isolated(self):
        hist, future, actual, excluded = intraday.split_history(
            fixture(), 'timestamps', 5, '2026-09-22', '2026-09-22 15:00', 48, 512, 'bse')
        self.assertEqual(len(hist), 48)
        self.assertEqual(hist.timestamps.iloc[-1], pd.Timestamp('2026-09-21 15:00'))
        self.assertEqual(len(future), 48)
        self.assertTrue(future.is_target.all())
        self.assertEqual(len(actual), 48)
        self.assertEqual(excluded, 48)

    def test_unclosed_bar_is_excluded(self):
        hist, future, _, _ = intraday.split_history(
            fixture(), 'timestamps', 5, '2026-09-22', '2026-09-21 14:58', 47, 512, 'bse')
        self.assertEqual(hist.timestamps.iloc[-1], pd.Timestamp('2026-09-21 14:55'))
        self.assertEqual(len(future), 49)

    def test_gaps_and_stale_history_fail(self):
        for index in (20,47):
            with self.subTest(index=index), self.assertRaisesRegex(ValueError, 'stale|gaps'):
                intraday.split_history(fixture().drop(index), 'timestamps', 5,
                                       '2026-09-22', '2026-09-22 09:00', 47, 512, 'bse')

    def test_source_whitelist(self):
        with self.assertRaisesRegex(ValueError, '不支持 sina'):
            intraday.fetch(SimpleNamespace(market='bse', symbol='920799', source='sina'))

    def test_provider_routing_and_column_mapping(self):
        import akshare as ak
        data = pd.DataFrame({'时间':['2026-09-21 09:35'], '开盘':[20.], '最高':[21.],
                             '最低':[19.], '收盘':[20.5], '成交量':[100.], '成交额':[205000.]})
        for market, symbol, requested in (('bse','bj920799','920799'),('cn','sh600519','600519')):
            with self.subTest(market=market), patch.object(ak, 'stock_zh_a_hist_min_em', return_value=data) as client:
                result, meta = intraday.fetch(SimpleNamespace(market=market, symbol=symbol,
                                           source='eastmoney', minutes=5, adjust='qfq'))
                client.assert_called_once_with(symbol=requested, period='5', adjust='qfq')
                self.assertTrue(set(intraday.predict.FEATURES).issubset(result.columns))
                self.assertEqual(meta['provider_symbol'], requested)
                self.assertEqual(result.close.iloc[0], 20.5)

    def test_akshare_builds_beijing_security_request(self):
        # Exercise the installed mature client without claiming a live response.
        import akshare as ak
        response = Mock()
        response.json.return_value = {'data':{'klines':['2026-09-21 09:35,20,20.5,21,19,100,205000,10,2.5,0.5,1']}}
        with patch('requests.get', return_value=response) as request:
            result, _ = intraday.fetch(SimpleNamespace(market='bse', symbol='bj920799',
                                     source='eastmoney', minutes=5, adjust='none'))
        self.assertEqual(request.call_args.kwargs['params']['secid'], '0.920799')
        self.assertEqual(request.call_args.kwargs['params']['klt'], '5')
        self.assertEqual(result.close.iloc[0], 20.5)

    def test_one_minute_adjustment_rejected_before_request(self):
        import akshare as ak
        with patch.object(ak, 'stock_zh_a_hist_min_em') as client:
            with self.assertRaisesRegex(ValueError, 'does not apply adjust'):
                intraday.fetch(SimpleNamespace(market='bse', symbol='920799',
                               source='eastmoney', minutes=1, adjust='qfq'))
            client.assert_not_called()

    def test_empty_response_and_provider_failure_are_not_hidden(self):
        import akshare as ak
        args = SimpleNamespace(market='bse',symbol='920799',source='eastmoney',minutes=5,adjust='none')
        with patch.object(ak,'stock_zh_a_hist_min_em',return_value=pd.DataFrame()):
            with self.assertRaisesRegex(ValueError,'returned no'):
                intraday.fetch(args)
        with patch.object(ak,'stock_zh_a_hist_min_em',side_effect=ConnectionError('provider failure')) as client:
            with self.assertRaisesRegex(ConnectionError,'provider failure'):
                intraday.fetch(args)
            self.assertEqual(client.call_count, 1)

    def test_csv_cli_to_predict_check_only(self):
        with tempfile.TemporaryDirectory() as directory:
            work = Path(directory)
            csv = work/'fixture-not-market-data.csv'
            fixture().to_csv(csv,index=False)
            for market, symbol in (('bse','bj920799'),('cn','sh600519')):
                prepared = work/market
                command = [sys.executable,'-X','utf8','-B',str(ROOT/'scripts/intraday.py'),
                           'prepare','--market',market,'--source','csv','--csv',str(csv),
                           '--symbol',symbol,'--minutes','5','--target-date','2026-09-22',
                           '--as-of','2026-09-22 09:00','--lookback','48',
                           '--data-note','synthetic offline test fixture; not market data',
                           '--output-dir',str(prepared)]
                result = subprocess.run(command,capture_output=True,text=True,encoding='utf-8')
                self.assertEqual(result.returncode,0,result.stderr)
                meta = json.loads((prepared/'data-source.json').read_text(encoding='utf-8'))
                self.assertEqual(meta['market'],market)
                self.assertEqual(meta['target_bars'],48)
                if market == 'bse':
                    self.assertEqual(meta['exchange'],'BSE')
                    self.assertEqual(meta['symbol'],'920799')
                    self.assertIn('proxy',meta['calendar_note'])
                    self.assertEqual(meta['calendar_reference'],'https://www.bse.cn/')
                result = subprocess.run([sys.executable,'-X','utf8','-B',str(ROOT/'scripts/predict.py'),
                    '--csv',str(prepared/'history.csv'),'--future-csv',str(prepared/'future.csv'),
                    '--lookback','48','--pred-len','48','--check-only'],capture_output=True,text=True,encoding='utf-8')
                self.assertEqual(result.returncode,0,result.stderr)


if __name__ == '__main__':
    unittest.main(verbosity=2)
