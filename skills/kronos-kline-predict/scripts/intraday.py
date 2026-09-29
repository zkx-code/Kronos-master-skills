"""Prepare and summarize mainland A-share intraday forecasts using exchange_calendars."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np
import pandas as pd
import exchange_calendars as xc

import predict
from market_adapters import get_adapter


def bar_grid(start, end, minutes, market='cn'):
    """Close-labelled bars; each exchange session leg is anchored independently."""
    if minutes not in (1, 5, 15, 30, 60, 120):
        raise ValueError('Supported intervals are 1, 5, 15, 30, 60 and 120 minutes')
    adapter = get_adapter(market)
    cal = xc.get_calendar(adapter.calendar)
    sessions = cal.sessions_in_range(pd.Timestamp(start).normalize(), pd.Timestamp(end).normalize())
    rows = []
    step = pd.Timedelta(minutes=minutes)
    for session in sessions:
        day = cal.schedule.loc[session]
        for leg, left, right in [('AM', day.open, day.break_start), ('PM', day.break_end, day.close)]:
            left = left.tz_convert(adapter.timezone).tz_localize(None)
            right = right.tz_convert(adapter.timezone).tz_localize(None)
            if (right - left) % step:
                raise ValueError('Session length is not divisible by bar interval')
            for close in pd.date_range(left + step, right, freq=step):
                rows.append({'timestamps': close, 'bar_start': close - step, 'session_leg': leg})
    return pd.DataFrame(rows, columns=['timestamps', 'bar_start', 'session_leg'])


def split_history(frame, column, minutes, target, as_of, lookback, max_context, market='cn'):
    target = pd.Timestamp(target)
    as_of = pd.Timestamp(as_of)
    if target.tzinfo is not None or target != target.normalize():
        raise ValueError('target-date must be a date without timezone or time')
    if as_of.tzinfo is not None:
        raise ValueError('as-of must be exchange-local naive time')
    if not 2 <= lookback <= max_context:
        raise ValueError(f'lookback must be between 2 and {max_context}')
    target_grid = bar_grid(target, target, minutes, market)
    if target_grid.empty:
        raise ValueError('Target date is not a trading day; no automatic date substitution')
    times = predict.read_times(frame, column)
    frame = frame.copy().reset_index(drop=True)
    frame[column] = times
    # Historical-date requests are always predictions made before that session opens.
    cutoff = min(as_of, target + pd.Timedelta(hours=9, minutes=30))
    completed = frame.loc[times.le(cutoff)].copy()
    if len(completed) < lookback:
        raise ValueError(f'Need {lookback} completed historical bars; got {len(completed)}')
    history = completed.tail(lookback).rename(columns={column: 'timestamps'}).reset_index(drop=True)
    h_times = pd.DatetimeIndex(history.timestamps)
    grid = bar_grid(h_times[0], target, minutes, market)
    expected_history = pd.DatetimeIndex(grid.loc[
        grid.timestamps.ge(h_times[0]) & grid.timestamps.le(cutoff), 'timestamps'])
    if not h_times.equals(expected_history):
        missing = expected_history.difference(h_times)
        extra = h_times.difference(expected_history)
        raise ValueError(f'History is stale, has gaps or wrong labels/interval. Missing={list(missing[:8])}; unexpected={list(extra[:8])}')
    future = grid.loc[grid.timestamps.gt(h_times[-1])].reset_index(drop=True)
    if len(future) > max_context:
        raise ValueError(f'Horizon {len(future)} exceeds model context {max_context}; intermediate sessions must not be skipped')
    future['is_target'] = future.timestamps.dt.normalize().eq(target)
    actual = frame.loc[times.dt.normalize().eq(target) & times.le(as_of)].copy()
    return history, future, actual, int(len(frame) - len(completed))


def fetch(args):
    adapter = get_adapter(args.market)
    symbol = adapter.normalize_symbol(args.symbol)
    if args.source not in adapter.automatic_sources:
        allowed = ', '.join(adapter.automatic_sources)
        raise ValueError(f'{adapter.name} 不支持 {args.source} 自动取数；可用来源：{allowed}；已核验本地数据使用 --source csv。未自动换源。')
    import akshare as ak
    if args.source == 'sina':
        if args.adjust != 'none':
            raise ValueError('Sina automatic fetch requires --adjust none; for adjusted data use a verified CSV (AKShare Sina may silently skip adjustment)')
        df = ak.stock_zh_a_minute(symbol=symbol, period=str(args.minutes), adjust='')
        return df.rename(columns={'day': 'timestamps'}), {
            'provider': 'Sina Finance', 'function': 'akshare.stock_zh_a_minute',
            'url': 'https://quotes.sina.cn/cn/api/jsonp_v2.php/=/CN_MarketDataService.getKLineData',
            'volume_unit': 'shares', 'amount_unit': 'CNY', 'akshare_version': ak.__version__,
        }
    provider_symbol = symbol[2:] if args.market == 'cn' else symbol
    if args.minutes == 1 and args.adjust != 'none':
        raise ValueError('Eastmoney 1-minute trends endpoint does not apply adjust; use --adjust none or a verified adjusted CSV')
    df = ak.stock_zh_a_hist_min_em(symbol=provider_symbol, period=str(args.minutes),
                                 adjust='' if args.adjust == 'none' else args.adjust)
    if df.empty:
        raise ValueError(f'Eastmoney returned no {args.minutes}-minute data for {args.market}:{symbol}; verify listing/code changes and source coverage. No automatic source switch.')
    return df.rename(columns={'时间':'timestamps','开盘':'open','最高':'high','最低':'low',
                              '收盘':'close','成交量':'volume','成交额':'amount'}), {
        'provider': 'Eastmoney', 'function': 'akshare.stock_zh_a_hist_min_em',
        'url': ('https://push2his.eastmoney.com/api/qt/stock/trends2/get' if args.minutes == 1
                else 'https://push2his.eastmoney.com/api/qt/stock/kline/get'),
        'volume_unit': 'lots (hands), verify current source documentation', 'amount_unit': 'CNY',
        'akshare_version': ak.__version__,
        'provider_symbol': provider_symbol,
    }


def prepare(args):
    if args.output_dir.exists():
        raise FileExistsError('Choose a new output directory')
    adapter = get_adapter(args.market)
    args.symbol = adapter.normalize_symbol(args.symbol)
    fetched_at = pd.Timestamp.now(tz=adapter.timezone)
    as_of = pd.Timestamp(args.as_of) if args.as_of else fetched_at.tz_localize(None)
    if as_of.tzinfo is not None or as_of > fetched_at.tz_localize(None):
        raise ValueError('as-of must be local naive time no later than current time')
    if args.source == 'csv':
        if args.csv is None:
            raise ValueError('--csv is required for source=csv')
        raw = pd.read_csv(args.csv)
        source = {'provider': 'User/agent supplied CSV', 'input': str(args.csv.resolve()),
                  'input_sha256': predict.sha256(args.csv)}
    else:
        if args.csv is not None:
            raise ValueError('--csv is only valid with --source csv')
        if args.time_column != 'timestamps':
            raise ValueError('Automatic fetch normalizes the timestamp column to timestamps')
        raw, source = fetch(args)
    context = predict.MODELS[args.model][2]
    history, future, actual, excluded = split_history(
        raw, args.time_column, args.minutes, args.target_date, as_of, args.lookback, context, args.market)
    columns = predict.PRICE if args.price_only else predict.FEATURES
    missing = set(columns) - set(history.columns)
    if missing:
        raise ValueError(f'Missing {sorted(missing)}; explicitly select --price-only if OHLC-only is intended')
    history = history[['timestamps'] + columns].copy()
    values = history[columns].apply(pd.to_numeric, errors='raise')
    if args.price_only:
        values['volume'] = 0.
        values['amount'] = 0.
    if not np.isfinite(values.to_numpy()).all() or any(predict.quality(values).values()):
        raise ValueError('Historical OHLCVA values failed validation; no automatic repairs')
    history[columns] = values[columns]
    args.output_dir.mkdir(parents=True, exist_ok=False)
    raw.to_csv(args.output_dir/'source.csv', index=False, encoding='utf-8-sig')
    history.to_csv(args.output_dir/'history.csv', index=False, encoding='utf-8-sig')
    future[['timestamps']].to_csv(args.output_dir/'future.csv', index=False, encoding='utf-8-sig')
    future.to_csv(args.output_dir/'schedule.csv', index=False, encoding='utf-8-sig')
    if not actual.empty:
        actual.to_csv(args.output_dir/'held-out-actual.csv', index=False, encoding='utf-8-sig')
    source.update({
        'market':args.market, 'exchange':adapter.exchange, 'symbol':args.symbol,
        'interval_minutes':args.minutes, 'target_date':args.target_date,
        'adjustment':args.adjust, 'timezone':adapter.timezone, 'bar_label':'close',
        'source_note':args.data_note, 'fetched_at':str(fetched_at), 'as_of':str(as_of),
        'history_cutoff':str(history.timestamps.iloc[-1]), 'lookback':len(history),
        'prediction_length':len(future), 'target_bars':int(future.is_target.sum()),
        'excluded_from_context_rows':excluded, 'price_only':args.price_only,
        'calendar':adapter.calendar, 'calendar_version':xc.__version__,
        'calendar_note':adapter.calendar_note, 'calendar_reference':adapter.calendar_reference,
        'source_sha256':predict.sha256(args.output_dir/'source.csv'),
        'history_sha256':predict.sha256(args.output_dir/'history.csv'),
        'future_sha256':predict.sha256(args.output_dir/'future.csv'),
        'held_out_rows':len(actual), 'cross_check':'Not performed by this script; record evidence in data_note or sidecar',
    })
    (args.output_dir/'data-source.json').write_text(json.dumps(source,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print(json.dumps(source, ensure_ascii=False, indent=2))


def summarize(args):
    prep = args.prepared_dir
    run = json.loads((args.forecast_dir/'run.json').read_text(encoding='utf-8'))
    meta = json.loads((prep/'data-source.json').read_text(encoding='utf-8'))
    if run['input_sha256'] != predict.sha256(prep/'history.csv') or run['future_csv_sha256'] != predict.sha256(prep/'future.csv'):
        raise ValueError('Forecast was not produced from this prepared input')
    schedule = pd.read_csv(prep/'schedule.csv', parse_dates=['timestamps','bar_start'])
    pred = pd.read_csv(args.forecast_dir/'forecast.csv', parse_dates=['timestamps'])
    if len(pred)!=len(schedule) or not pred.timestamps.equals(schedule.timestamps):
        raise ValueError('Forecast and trading schedule do not align')
    if not np.isfinite(pred[predict.FEATURES].to_numpy()).all():
        raise ValueError('Nonfinite model output')
    result = schedule.merge(pred,on='timestamps',validate='one_to_one')
    previous = result.close.shift(1)
    previous.iloc[0] = run['last_observed_close']
    result['close_change_pct'] = (result.close/previous-1)*100
    result['candle_change_pct'] = (result.close/result.open-1)*100
    result['ohlc_valid'] = (result[predict.PRICE]>0).all(axis=1) & (result.high>=result[['open','low','close']].max(axis=1)) & (result.low<=result[['open','high','close']].min(axis=1))
    result['volume_valid'] = (result[['volume','amount']]>=0).all(axis=1)
    result['direction'] = np.where(result.close>previous,'涨',np.where(result.close<previous,'跌','平'))
    result['comparison'] = '上一根收盘'
    result.loc[0,'comparison'] = '最后真实收盘（含开盘跳空）'
    gap = result.bar_start > result.timestamps.shift(1)
    result.loc[gap,'comparison'] = '上一交易时段收盘（含休市跳空）'
    target = result.loc[result.is_target].copy()
    target.to_csv(args.forecast_dir/'intraday.csv',index=False,encoding='utf-8-sig')
    lines = [f'# {meta["symbol"]} {meta["target_date"]} 盘中预测', '',
             f'周期 {meta["interval_minutes"]} 分钟，目标日 {len(target)} 根。上下文截止 {meta["history_cutoff"]}。',
             f'Kronos-{run["parameters"]["model"]}；sample_count={run["parameters"]["sample_count"]}；seed={run["parameters"]["seed"]}。', '',
             '“涨/跌”按该根预测收盘相对上一根收盘判断；开盘和午休后的比较包含跳空。它描述模型路径，不是确定的买卖时点。',
             '时间是 K 线覆盖区间；即使该根收涨，区间内也可能先跌后涨。日线与分钟线独立推理，结果不保证一致。', '',
             f'异常 OHLC：{int((~target.ohlc_valid).sum())} 根；负成交量/额：{int((~target.volume_valid).sum())} 根。原值保留。', '',
             '| 时段 | 开盘 | 最高 | 最低 | 收盘 | 相邻收盘变化 | 根内变化 | 方向 | 检查 |',
             '| --- | ---: | ---: | ---: | ---: | ---: | ---: | --- | --- |']
    for r in target.itertuples():
        state = '通过' if r.ohlc_valid and r.volume_valid else '异常'
        lines.append(f'| {r.bar_start:%H:%M}–{r.timestamps:%H:%M} | {r.open:.2f} | {r.high:.2f} | {r.low:.2f} | {r.close:.2f} | {r.close_change_pct:+.3f}% | {r.candle_change_pct:+.3f}% | {r.direction} | {state} |')
    if target.ohlc_valid.all():
        hi=target.loc[target.high.idxmax()]; lo=target.loc[target.low.idxmin()]
        lines += ['', f'本路径最高价 {hi.high:.2f} 所在区间：{hi.bar_start:%H:%M}–{hi.timestamps:%H:%M}；最低价 {lo.low:.2f} 所在区间：{lo.bar_start:%H:%M}–{lo.timestamps:%H:%M}。区间内的具体发生时刻未知。']
    lines += ['', f'末根预测收盘 {target.close.iloc[-1]:.2f}；相对最后真实收盘 {run["last_observed_close"]:.2f} 的变化为 {(target.close.iloc[-1]/run["last_observed_close"]-1)*100:+.3f}%。',
              '',f'数据口径：{meta["adjustment"]}；来源说明：{meta["source_note"]}。',
              '历史留出真值若存在，保存在 prepared 目录中，未作为模型上下文；本摘要不自动声称回测准确率。']
    (args.forecast_dir/'盘中预测.md').write_text('\n'.join(lines)+'\n',encoding='utf-8')
    print(target[['bar_start','timestamps','close','direction','ohlc_valid']].to_string(index=False))
    print('Report:', args.forecast_dir/'盘中预测.md')


def main():
    p=argparse.ArgumentParser(description=__doc__)
    subs=p.add_subparsers(dest='command',required=True)
    a=subs.add_parser('prepare')
    a.add_argument('--source',choices=['csv','sina','eastmoney'],required=True)
    a.add_argument('--csv',type=Path)
    a.add_argument('--market',choices=['cn','bse'],default='cn', help='cn=沪深A股, bse=北交所')
    a.add_argument('--symbol',required=True)
    a.add_argument('--time-column',default='timestamps')
    a.add_argument('--minutes',type=int,choices=[1,5,15,30,60,120],default=5)
    a.add_argument('--target-date',required=True)
    a.add_argument('--as-of')
    a.add_argument('--lookback',type=int,default=400)
    a.add_argument('--model',choices=predict.MODELS,default='small')
    a.add_argument('--adjust',choices=['none','qfq','hfq'],default='none')
    a.add_argument('--price-only',action='store_true')
    a.add_argument('--data-note',required=True)
    a.add_argument('--output-dir',type=Path,required=True)
    a.set_defaults(func=prepare)
    s=subs.add_parser('summarize')
    s.add_argument('--prepared-dir',type=Path,required=True)
    s.add_argument('--forecast-dir',type=Path,required=True)
    s.set_defaults(func=summarize)
    args=p.parse_args()
    args.func(args)


if __name__=='__main__':
    main()


