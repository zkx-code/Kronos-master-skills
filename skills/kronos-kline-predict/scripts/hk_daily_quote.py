"""Fetch completed HK daily quotes from Yahoo; enrich and cross-check with Eastmoney."""
from __future__ import annotations

import argparse
import hashlib
import importlib.metadata
import json
from pathlib import Path

import exchange_calendars as xc
import numpy as np
import pandas as pd

from us_market import normalize_symbol, validate_identity

EM_URL = 'https://33.push2his.eastmoney.com/api/qt/stock/kline/get'
PRICES = ['open', 'high', 'low', 'close']
EM_COLUMNS = ['date', 'open', 'close', 'high', 'low', 'volume', 'amount',
              'amplitude_pct', 'change_pct', 'change', 'turnover_pct']


def write_json(path, data):
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2, allow_nan=False) + '\n', encoding='utf-8')


def completed_session(date, now):
    target = pd.Timestamp(date)
    if target.tzinfo is not None or target != target.normalize():
        raise ValueError('date must be a calendar date without a time or timezone')
    cal = xc.get_calendar('XHKG')
    if not cal.is_session(target):
        raise ValueError('Requested date is not an XHKG trading day')
    finalized = cal.session_close(target) + pd.Timedelta(minutes=10)
    if pd.Timestamp(now).tz_convert('UTC') < finalized:
        raise ValueError('Requested daily bar is not completed, including closing auction')
    return target, cal.previous_session(target)


def validate_prices(frame):
    values = frame[PRICES].to_numpy(dtype=float)
    if not np.isfinite(values).all() or (values <= 0).any():
        raise ValueError('Missing, nonfinite or nonpositive OHLC')
    if ((frame.high < frame[['open', 'low', 'close']].max(axis=1)) |
            (frame.low > frame[['open', 'high', 'close']].min(axis=1))).any():
        raise ValueError('Invalid OHLC relations; source data was not repaired')


def parse_eastmoney(payload, code, target):
    data = payload.get('data')
    if payload.get('rc') != 0 or not isinstance(data, dict):
        raise ValueError('Eastmoney returned an error or empty data')
    if str(data.get('code')) != code or data.get('market') != 116 or not data.get('name'):
        raise ValueError('Eastmoney security identity does not match requested HK code')
    rows = [line.split(',') for line in data.get('klines', [])]
    if not rows or any(len(row) != len(EM_COLUMNS) for row in rows):
        raise ValueError('Eastmoney daily schema is empty or has changed')
    frame = pd.DataFrame(rows, columns=EM_COLUMNS)
    frame['date'] = pd.to_datetime(frame.date, errors='raise')
    if frame.date.duplicated().any() or not frame.date.is_monotonic_increasing:
        raise ValueError('Eastmoney dates are duplicated or out of order')
    for column in EM_COLUMNS[1:]:
        frame[column] = pd.to_numeric(frame[column], errors='raise')
    row = frame.loc[frame.date.eq(target)]
    if len(row) != 1:
        raise ValueError('Eastmoney has no unique daily bar for requested date')
    validate_prices(row)
    quantities = row[['volume', 'amount', 'turnover_pct']].to_numpy(dtype=float)
    if not np.isfinite(quantities).all() or (quantities < 0).any():
        raise ValueError('Eastmoney volume, amount or turnover is missing or invalid')
    if row.volume.iloc[0] > 0 and row.amount.iloc[0] == 0:
        raise ValueError('Eastmoney returned zero amount with positive traded volume')
    return row.iloc[0], data['name']


def yahoo_row(frame, target):
    if not isinstance(frame.index, pd.DatetimeIndex) or frame.index.tz is None:
        raise ValueError('Yahoo must return timezone-aware dates')
    dates = frame.index.tz_convert('Asia/Hong_Kong').tz_localize(None).normalize()
    if dates.has_duplicates or not dates.is_monotonic_increasing:
        raise ValueError('Yahoo dates are duplicated or out of order')
    row = frame.loc[dates == target].rename(columns=str.lower)
    if len(row) != 1:
        raise ValueError('Yahoo has no unique daily bar for requested date')
    validate_prices(row)
    volume = float(row.volume.iloc[0])
    if not np.isfinite(volume) or volume < 0:
        raise ValueError('Yahoo volume is missing or invalid')
    return row.iloc[0]


def combine(yahoo, eastmoney, symbol, date):
    differences = {key: float(eastmoney[key] - yahoo[key]) for key in PRICES}
    # Only allow floating-point representation noise, not a guessed HK tick size.
    tolerances = {key: max(1e-6, abs(float(np.spacing(np.float32(yahoo[key])))) * 2)
                  for key in PRICES}
    matched = all(abs(differences[key]) <= tolerances[key] for key in PRICES)
    result = {'symbol': symbol, 'date': str(date.date()), 'currency': 'HKD',
              **{key: float(yahoo[key]) for key in PRICES},
              'volume_yahoo_shares': float(yahoo.volume),
              'volume_eastmoney_shares': float(eastmoney.volume),
              'amount_hkd': float(eastmoney.amount),
              'turnover_pct': float(eastmoney.turnover_pct)}
    checks = {'ohlc_match': matched, 'eastmoney_minus_yahoo': differences,
              'rounding_tolerance': tolerances,
              'volume_difference_shares': float(eastmoney.volume - yahoo.volume),
              'quantity_discrepancy_reason': ('None observed' if eastmoney.volume == yahoo.volume
                                              else 'Not established; both source values retained'),
              'note': 'Matching OHLC alone does not prove identical volume/session coverage.'}
    return result, checks


def run(args):
    symbol = normalize_symbol(args.symbol, 'hk')
    code = f'{int(symbol.removesuffix(".HK")):05d}'
    now = pd.Timestamp.now(tz='Asia/Hong_Kong')
    target, previous = completed_session(args.date, now)
    if args.timeout <= 0:
        raise ValueError('timeout must be positive')
    out = args.output_dir.resolve()
    out.mkdir(parents=True, exist_ok=False)
    record = {'status': 'fetching', 'symbol': symbol, 'eastmoney_code': code,
              'date': str(target.date()), 'fetched_at': str(now),
              'timezone': 'Asia/Hong_Kong', 'calendar': 'XHKG',
              'eastmoney_connection': 'direct' if args.direct else 'environment proxy settings',
              'field_sources': {'open/high/low/close': 'Yahoo Finance',
                                'amount_hkd/turnover_pct': 'Eastmoney',
                                'volume_yahoo_shares': 'Yahoo Finance',
                                'volume_eastmoney_shares': 'Eastmoney'},
              'adjustment': {'yahoo': 'auto_adjust=False; Yahoo supplied OHLC may reflect splits',
                             'eastmoney': 'fqt=0 (unadjusted)'},
              'units': {'price': 'HKD', 'amount_hkd': 'HKD', 'volume': 'shares',
                        'turnover_pct': 'percent (e.g. 0.33 means 0.33%)'},
              'scope': 'Provider daily bars, including each source auction coverage; not forecast input',
              'calendar_limit': 'No separate instrument suspension or historical code-reuse check'}
    stage = 'Yahoo daily history'
    try:
        import yfinance as yf
        from curl_cffi import requests
        ticker = yf.Ticker(symbol)
        history = ticker.history(start=str(previous.date()),
                                 end=str((target + pd.Timedelta(days=1)).date()),
                                 interval='1d', auto_adjust=False, back_adjust=False,
                                 prepost=False, repair=False, actions=True, keepna=True,
                                 timeout=args.timeout)
        history.to_csv(out / 'yahoo-source.csv', encoding='utf-8-sig')
        meta = ticker.get_history_metadata()
        identity = {key: meta.get(key) for key in ('symbol', 'longName', 'shortName',
                    'exchangeName', 'exchangeTimezoneName', 'currency', 'instrumentType')}
        write_json(out / 'yahoo-identity.json', identity)
        validate_identity(symbol, identity, 'hk')
        record['name'] = identity.get('longName') or identity.get('shortName')
        record['yahoo_url'] = f'https://finance.yahoo.com/quote/{symbol}/history/'
        observed = yahoo_row(history, target)
        stage = 'Eastmoney daily history'
        params = {'secid': f'116.{code}', 'fields1': 'f1,f2,f3,f4,f5,f6',
                  'fields2': 'f51,f52,f53,f54,f55,f56,f57,f58,f59,f60,f61',
                  'klt': '101', 'fqt': '0', 'beg': str(previous.date()).replace('-', ''),
                  'end': args.date.replace('-', ''), 'lmt': '10'}
        record['eastmoney_request'] = {'url': EM_URL, 'params': params}
        with requests.Session(impersonate='chrome', trust_env=not args.direct) as session:
            response = session.get(EM_URL, params=params, timeout=args.timeout)
            (out / 'eastmoney-response.txt').write_text(response.text, encoding='utf-8')
            record['eastmoney_http_status'] = response.status_code
            response.raise_for_status()
            payload = response.json()
        write_json(out / 'eastmoney-source.json', payload)
        eastmoney, record['eastmoney_name'] = parse_eastmoney(payload, code, target)
        result, checks = combine(observed, eastmoney, symbol, target)
        write_json(out / 'cross-check.json', checks)
        record['status'] = 'complete' if checks['ohlc_match'] else 'complete_with_price_discrepancy'
        record['cross_check'] = checks
        record['result'] = result
        pd.DataFrame([result]).to_csv(out / 'daily-quote.csv', index=False, encoding='utf-8-sig')
    except Exception as exc:
        record.update(status='failed', failed_stage=stage, error_type=type(exc).__name__)
        # Error messages may contain proxy credentials; preserve type/stage and raw provider responses.
        write_json(out / 'data-source.json', record)
        raise
    record['versions'] = {name: importlib.metadata.version(name)
                          for name in ('yfinance', 'curl_cffi', 'pandas', 'exchange_calendars')}
    record['raw_sha256'] = {name: hashlib.sha256((out / name).read_bytes()).hexdigest()
                            for name in ('yahoo-source.csv', 'yahoo-identity.json', 'eastmoney-response.txt')}
    write_json(out / 'data-source.json', record)
    print(json.dumps(record, ensure_ascii=False, indent=2, allow_nan=False))
    return record


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--symbol', required=True, help='e.g. 09992 or 9992.HK')
    parser.add_argument('--date', required=True, help='YYYY-MM-DD, Hong Kong trading date')
    parser.add_argument('--output-dir', type=Path, required=True, help='New directory')
    parser.add_argument('--direct', action='store_true', help='Explicit direct Eastmoney connection only')
    parser.add_argument('--timeout', type=float, default=20)
    run(parser.parse_args())


if __name__ == '__main__':
    main()
