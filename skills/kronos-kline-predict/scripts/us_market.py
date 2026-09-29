"""Yahoo US/HK regular-session OHLCV adapters for Kronos price-only inputs."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import re

import exchange_calendars as xc
import numpy as np
import pandas as pd

import predict

TIMEZONE = 'America/New_York'
INTERVALS = ('1d', '1', '5', '15', '30', '60', '120')
EXCHANGES = {'NYQ', 'NMS', 'NGM', 'NCM', 'ASE', 'PCX', 'BTS'}
MARKETS = {
    'us': {'timezone': TIMEZONE, 'calendar': 'XNYS', 'currency': 'USD',
           'exchanges': EXCHANGES, 'instruments': ('EQUITY', 'ETF'),
           'reference': 'https://www.nyse.com/markets/hours-calendars'},
    'hk': {'timezone': 'Asia/Hong_Kong', 'calendar': 'XHKG', 'currency': 'HKD',
           'exchanges': {'HKG'}, 'instruments': ('EQUITY',),
           'reference': 'https://www.hkex.com.hk/Services/Trading/Securities/Overview/Trading-Hours?sc_lang=en'},
}


def config(market):
    if market not in MARKETS:
        raise ValueError('market must be us or hk')
    return MARKETS[market]


def normalize_symbol(symbol, market='us'):
    config(market)
    value = symbol.strip().upper()
    if market == 'hk':
        code = value.removesuffix('.HK')
        if not re.fullmatch(r'[0-9]{1,5}', code) or int(code) == 0:
            raise ValueError('Use a Hong Kong stock code, e.g. 700, 00700 or 0700.HK')
        return f'{int(code):04d}.HK'
    if not re.fullmatch(r'[A-Z][A-Z0-9.-]{0,14}', value):
        raise ValueError('Provide the exact Yahoo US ticker, e.g. AAPL or BRK-B')
    return value


def bar_grid(start, end, interval, market='us'):
    """Calendar sessions, close labels; shortened final bars are explicit."""
    if interval not in INTERVALS:
        raise ValueError(f'interval must be one of {INTERVALS}')
    settings = config(market)
    calendar = xc.get_calendar(settings['calendar'])
    sessions = calendar.sessions_in_range(pd.Timestamp(start).normalize(), pd.Timestamp(end).normalize())
    rows = []
    for session in sessions:
        schedule = calendar.schedule.loc[session]
        opened = schedule.open.tz_convert(settings['timezone']).tz_localize(None)
        closed = schedule.close.tz_convert(settings['timezone']).tz_localize(None)
        if interval == '1d':
            # HK daily prices may include the closing auction, unlike continuous intraday bars.
            finalized = closed + pd.Timedelta(minutes=10) if market == 'hk' else closed
            rows.append((session.tz_localize(None), opened, finalized, False))
            continue
        step = pd.Timedelta(minutes=int(interval))
        legs = [(opened, closed)]
        if pd.notna(schedule.break_start):
            legs = [(opened, schedule.break_start.tz_convert(settings['timezone']).tz_localize(None)),
                    (schedule.break_end.tz_convert(settings['timezone']).tz_localize(None), closed)]
        for leg_start, leg_end in legs:
            for left in pd.date_range(leg_start, leg_end, freq=step, inclusive='left'):
                right = min(left + step, leg_end)
                rows.append((right, left, right, right - left < step))
    return pd.DataFrame(rows, columns=['timestamps', 'bar_start', 'bar_end', 'partial_bar'])


def validate_identity(symbol, meta, market='us'):
    settings = config(market)
    if str(meta.get('symbol', '')).upper() != symbol:
        raise ValueError('Yahoo returned a different or missing symbol')
    if meta.get('exchangeName') not in settings['exchanges']:
        raise ValueError(f"Unsupported {market} listing exchange: {meta.get('exchangeName')}")
    if meta.get('exchangeTimezoneName') != settings['timezone'] or meta.get('currency') != settings['currency']:
        raise ValueError(f'Unexpected currency/timezone for {market}')
    if meta.get('instrumentType') not in settings['instruments']:
        raise ValueError(f'Unsupported instrument type for {market}')


def fetch(symbol, interval, adjustment, market='us', period=None):
    import yfinance as yf
    symbol = normalize_symbol(symbol, market)
    source_interval = '60m' if interval in ('60', '120') else ('1d' if interval == '1d' else interval + 'm')
    default_period = ('2y' if market == 'hk' else '5y') if interval == '1d' else ('7d' if interval == '1' else ('2y' if interval in ('60', '120') else '1mo'))
    if market == 'hk' and interval in ('60', '120'):
        # 30m boundaries align with both HK session legs. Yahoo native 60m may cross lunch.
        source_interval, default_period = '30m', '1mo'
    period = period or default_period
    ticker = yf.Ticker(symbol)
    frame = ticker.history(period=period, interval=source_interval, auto_adjust=adjustment == 'auto',
                           back_adjust=False, prepost=False, repair=False, actions=True,
                           keepna=True, raise_errors=True)
    if frame.empty:
        raise ValueError(f'Yahoo returned no {source_interval} data for {symbol}')
    meta = ticker.get_history_metadata()
    validate_identity(symbol, meta, market)
    return frame, {
        'symbol': symbol, 'market': market, 'exchange': meta['exchangeName'],
        'name': meta.get('longName') or meta.get('shortName'),
        'instrument_type': meta['instrumentType'], 'currency': meta['currency'],
        'provider': 'Yahoo Finance via yfinance', 'yfinance_version': yf.__version__,
        'source_url': f'https://finance.yahoo.com/quote/{symbol}/history/',
        'source_interval': source_interval, 'requested_period': period,
        'adjustment': ('Yahoo auto_adjust OHLC using Adj Close ratio' if adjustment == 'auto'
                       else 'Yahoo supplied OHLC; auto_adjust=False; not guaranteed raw unadjusted prices'),
        'cross_check': 'Single source; independent price verification required before forecasting',
    }


def normalize(frame, interval, as_of, market='us'):
    """Validate actual bars against XNYS; aggregate 120m from complete 60m groups."""
    settings = config(market)
    if frame.empty:
        raise ValueError('Source data is empty')
    if not isinstance(frame.index, pd.DatetimeIndex) or frame.index.tz is None:
        raise ValueError('Yahoo timestamps must be timezone-aware')
    if frame.index.hasnans or not frame.index.is_unique or not frame.index.is_monotonic_increasing:
        raise ValueError('Source times contain NaT, duplicates or out-of-order rows')
    local = frame.index.tz_convert(settings['timezone']).tz_localize(None)
    data = frame.rename(columns={'Open': 'open', 'High': 'high', 'Low': 'low',
                                 'Close': 'close', 'Volume': 'volume'}).copy()
    cols = predict.PRICE + ['volume']
    data = data[cols].apply(pd.to_numeric, errors='raise')
    data.index = local.normalize() if interval == '1d' else local
    base_interval = '60' if interval == '120' else interval
    if market == 'hk' and interval in ('60', '120'):
        base_interval = '30'
    base = bar_grid(local[0], local[-1], base_interval, market)
    label = 'timestamps' if interval == '1d' else 'bar_start'
    expected = pd.DatetimeIndex(base[label])
    unexpected = data.index.difference(expected)
    excluded = []
    if market == 'hk' and interval != '1d' and len(unexpected):
        calendar = xc.get_calendar('XHKG')
        for stamp in unexpected:
            row = data.loc[stamp]
            if row[predict.PRICE].isna().all() and row.volume == 0:
                excluded.append({'source_timestamp': stamp.isoformat(),
                                 'reason': 'Yahoo nontrading placeholder: all OHLC missing and zero volume'})
                continue
            day = stamp.normalize()
            if day not in calendar.schedule.index:
                raise ValueError(f'Data on a closed HK session: {stamp}')
            session = calendar.schedule.loc[day]
            close = session.close.tz_convert(settings['timezone']).tz_localize(None)
            reason = None
            if pd.notna(session.break_start):
                left = session.break_start.tz_convert(settings['timezone']).tz_localize(None)
                right = session.break_end.tz_convert(settings['timezone']).tz_localize(None)
                row = data.loc[stamp]
                if left <= stamp < right and row[predict.PRICE].isna().all() and row.volume == 0:
                    reason = 'Yahoo lunch placeholder: all OHLC missing and zero volume'
            if close <= stamp <= close + pd.Timedelta(minutes=10):
                reason = 'Outside continuous session: closing auction/post-close source record'
            if reason is None:
                raise ValueError(f'Unexpected HK bar outside supported session: {stamp}')
            excluded.append({'source_timestamp': stamp.isoformat(), 'reason': reason})
        data = data.drop(index=unexpected)
        unexpected = data.index.difference(expected)
    if len(unexpected):
        raise ValueError(f'Unexpected session or bar labels: {list(unexpected[:5])}')
    if data.empty:
        raise ValueError('No continuous-session source bars remain')
    completed = base.loc[(base.bar_end <= as_of) & (base[label] >= data.index[0])].copy()
    missing = pd.DatetimeIndex(completed[label]).difference(data.index)
    if len(missing):
        raise ValueError(f'Missing completed source bars (no filling): {list(missing[:5])}')
    values = data.reindex(pd.DatetimeIndex(completed[label])).reset_index(drop=True)
    check = values.assign(amount=0.)
    if not np.isfinite(values.to_numpy()).all():
        invalid = ~np.isfinite(values.to_numpy()).all(axis=1)
        times = completed.loc[invalid, label].head(5).astype(str).tolist()
        raise ValueError(f'Completed source OHLCV failed validation: missing/nonfinite rows at {times}; no filling')
    if any(predict.quality(check).values()):
        raise ValueError('Completed source OHLCV failed validation; values were not repaired')
    completed = pd.concat([completed.reset_index(drop=True), values], axis=1)
    completed.attrs['excluded_source_rows'] = excluded
    if interval == base_interval or completed.empty:
        return completed
    grid = bar_grid(local[0], local[-1], interval, market)
    rows = []
    for bar in grid.itertuples():
        if bar.bar_end > as_of or bar.bar_start < completed.bar_start.iloc[0]:
            continue
        part = completed.loc[(completed.bar_start >= bar.bar_start) & (completed.bar_end <= bar.bar_end)]
        if part.empty or part.bar_start.iloc[0] != bar.bar_start or part.bar_end.iloc[-1] != bar.bar_end:
            raise ValueError(f'Incomplete {interval}-minute aggregation group')
        rows.append(dict(timestamps=bar.timestamps, bar_start=bar.bar_start, bar_end=bar.bar_end,
                         partial_bar=bar.partial_bar, open=part.open.iloc[0], high=part.high.max(),
                         low=part.low.min(), close=part.close.iloc[-1], volume=part.volume.sum()))
    aggregated = pd.DataFrame(rows, columns=list(completed.columns))
    aggregated.attrs['excluded_source_rows'] = excluded
    return aggregated


def future_grid(last_end, interval, count, market='us'):
    calendar = xc.get_calendar(config(market)['calendar'])
    day = pd.Timestamp(last_end).normalize()
    pos = calendar.sessions.searchsorted(day)
    # Even 120m on an early close has at least one bar per session.
    end_pos = min(pos + count + 1, len(calendar.sessions) - 1)
    grid = bar_grid(day, calendar.sessions[end_pos], interval, market)
    result = grid.loc[grid.bar_end > last_end].head(count).reset_index(drop=True)
    if len(result) != count:
        raise ValueError('Forecast exceeds the installed exchange calendar coverage')
    return result


def prepare(args, market='us'):
    settings = config(market)
    if args.output_dir.exists():
        raise FileExistsError('Choose a new output directory')
    limit = predict.MODELS[args.model][2]
    if not 2 <= args.lookback <= limit or not 1 <= args.pred_len <= limit:
        raise ValueError(f'lookback must be 2..{limit}; pred-len must be 1..{limit}')
    if not args.price_only:
        raise ValueError('Yahoo has no traded amount; explicitly pass --price-only')
    now = pd.Timestamp.now(tz=settings['timezone'])
    as_of = pd.Timestamp(args.as_of) if args.as_of else now.tz_localize(None)
    if pd.isna(as_of) or as_of.tzinfo is not None or as_of > now.tz_localize(None):
        raise ValueError(f"as-of must be local time in {settings['timezone']}, no later than now")
    raw, source = fetch(args.symbol, args.interval, args.adjust, market, getattr(args, 'period', None))
    bars = normalize(raw, args.interval, as_of, market)
    if len(bars) < args.lookback:
        raise ValueError(f'Only {len(bars)} complete bars available; requested {args.lookback}. '
                         'Yahoo intraday history is limited; reduce lookback explicitly or use verified CSV.')
    history = bars.tail(args.lookback).reset_index(drop=True)
    # Check stale data against the last completed exchange bar, not the latest fetched row.
    recent = bar_grid(history.bar_start.iloc[-1], as_of, args.interval, market)
    ended = recent.loc[recent.bar_end <= as_of]
    if not ended.empty and ended.bar_end.iloc[-1] != history.bar_end.iloc[-1]:
        raise ValueError('Yahoo data has not reached the latest completed bar at as-of; '
                         'provider may be delayed. Choose an explicit earlier as-of after checking it.')
    schedule = future_grid(history.bar_end.iloc[-1], args.interval, args.pred_len, market)
    args.output_dir.mkdir(parents=True, exist_ok=False)
    raw.to_csv(args.output_dir / 'source.csv', index_label='source_timestamp')
    history.to_csv(args.output_dir / 'normalized.csv', index=False)
    history[['timestamps'] + predict.PRICE].to_csv(args.output_dir / 'history.csv', index=False)
    schedule[['timestamps']].to_csv(args.output_dir / 'future.csv', index=False)
    schedule.to_csv(args.output_dir / 'schedule.csv', index=False)
    exclusions = bars.attrs.get('excluded_source_rows', [])
    pd.DataFrame(exclusions, columns=['source_timestamp', 'reason']).to_csv(args.output_dir / 'excluded-source-rows.csv', index=False)
    source.update({
        'timezone': settings['timezone'], 'calendar': settings['calendar'],
        'calendar_version': xc.__version__, 'calendar_reference': settings['reference'],
        'session_scope': ('Yahoo daily bar including source auction coverage; HK completion waits until close+10min'
                          if market == 'hk' and args.interval == '1d'
                          else 'regular continuous trading only; no separate auction bars'),
        'excluded_source_rows': len(exclusions), 'exclusion_audit': 'excluded-source-rows.csv',
        'prepost': False, 'interval': args.interval, 'as_of': str(as_of), 'fetched_at': now.isoformat(),
        'history_cutoff': str(history.bar_end.iloc[-1]), 'lookback': len(history),
        'prediction_length': len(schedule), 'price_only': True,
        'volume_unit': 'shares, retained in normalized.csv only', 'amount': 'not supplied; not estimated',
        'bar_label': 'session date for daily; interval close for intraday',
        'partial_bar_policy': 'retain shortened final session bar; flagged in schedule.csv',
        'prediction_start': str(schedule.bar_start.iloc[0]), 'prediction_end': str(schedule.bar_end.iloc[-1]),
        'source_note': args.data_note,
        'source_sha256': predict.sha256(args.output_dir / 'source.csv'),
        'history_sha256': predict.sha256(args.output_dir / 'history.csv'),
        'future_sha256': predict.sha256(args.output_dir / 'future.csv'),
    })
    (args.output_dir / 'data-source.json').write_text(json.dumps(source, ensure_ascii=False, indent=2), encoding='utf-8')
    print(json.dumps(source, ensure_ascii=False, indent=2))


def main(default_market='us'):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--symbol', required=True)
    parser.add_argument('--market', choices=tuple(MARKETS), default=default_market)
    parser.add_argument('--interval', choices=INTERVALS, default='1d')
    parser.add_argument('--period', choices=('1d','5d','7d','1mo','3mo','6mo','1y','2y','5y','10y','max'),
                        help='Explicit Yahoo history window; availability still depends on interval')
    parser.add_argument('--adjust', choices=('yahoo', 'auto'), default='yahoo')
    parser.add_argument('--as-of', help='Exchange-local cutoff; default now')
    parser.add_argument('--lookback', type=int, default=400)
    parser.add_argument('--pred-len', type=int, default=20)
    parser.add_argument('--model', choices=predict.MODELS, default='small')
    parser.add_argument('--price-only', action='store_true', required=True)
    parser.add_argument('--data-note', default='Single-source Yahoo data; independent verification pending')
    parser.add_argument('--output-dir', type=Path, required=True)
    args = parser.parse_args()
    prepare(args, args.market)


if __name__ == '__main__':
    main()
