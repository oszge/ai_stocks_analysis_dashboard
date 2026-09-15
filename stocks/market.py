from datetime import date, timedelta
import math

import pandas as pd
import pandas_market_calendars as mcal

DEFAULT_SYMBOLS = ('AAPL', 'MSFT', 'NVDA', 'AMZN', 'GOOGL', 'META', 'TSLA')
BENCHMARK = 'SPY'


def sessions(start: date, end: date):
    return mcal.get_calendar('NYSE').schedule(start_date=start, end_date=end).index


def validate(frame, target, symbols):
    errors = []
    required = {'date', 'symbol', 'open', 'high', 'low', 'close', 'volume', 'currency', 'source', 'final'}
    if not required.issubset(frame.columns) or frame.empty:
        return ['Missing or empty data schema.']
    expected_days = sessions(target - timedelta(days=15), target)
    if len(expected_days) < 2 or expected_days[-1].date() != target:
        return ['The target date is not a trading session.']
    previous = expected_days[-2].date()
    if frame.duplicated(['date', 'symbol']).any():
        errors.append('Duplicate symbol/date.')
    numeric = frame[['open', 'high', 'low', 'close', 'volume']]
    if not numeric.map(lambda x: isinstance(x, (int, float)) and math.isfinite(x)).all().all():
        return errors + ['Missing or non-finite number.']
    if (numeric[['open', 'high', 'low', 'close']] <= 0).any().any() or (frame.volume < 0).any():
        errors.append('Invalid price or volume.')
    if ((frame.high < frame[['open', 'close', 'low']].max(axis=1)) |
            (frame.low > frame[['open', 'close', 'high']].min(axis=1))).any():
        errors.append('Inconsistent OHLC data.')
    if (frame.date > target).any() or not frame.final.eq(True).all():
        errors.append('Future or unfinished daily bars.')
    if not frame.currency.eq('USD').all() or frame.source.isna().any() or frame.source.eq('').any():
        errors.append('Missing source or unsupported currency.')
    if not set(frame.date).issubset({x.date() for x in sessions(frame.date.min(), target)}):
        errors.append('Data outside trading sessions.')
    for symbol in symbols:
        dates = set(frame.loc[frame.symbol == symbol, 'date'])
        if not {target, previous}.issubset(dates):
            errors.append(f'{symbol}: missing target or previous trading session.')
    if set(frame.symbol) != set(symbols):
        errors.append('Requested symbols and received symbols differ.')
    return errors


def metrics(frame):
    rows = []
    for symbol, group in frame.groupby('symbol'):
        group = group.sort_values('date')
        last, prev = group.iloc[-1], group.iloc[-2]
        rows.append(dict(symbol=symbol, close=float(last.close),
                         change_usd=float(last.close - prev.close),
                         change_pct=float((last.close / prev.close - 1) * 100),
                         volume=int(last.volume),
                         range_pct=float((last.high - last.low) / last.close * 100)))
    result = pd.DataFrame(rows).set_index('symbol')
    result['vs_spy_pp'] = result.change_pct - (result.loc[BENCHMARK, 'change_pct'] if BENCHMARK in result.index else float('nan'))
    return result
