"""Read-only EODHD market data for Budapest-listed securities."""
from datetime import datetime, time, timezone
from zoneinfo import ZoneInfo
import json
import math
from urllib.request import Request, urlopen
from urllib.parse import urlencode
from urllib.error import HTTPError, URLError

import pandas as pd
import pandas_market_calendars as mcal

BAR_COLUMNS = ['date', 'symbol', 'open', 'high', 'low', 'close', 'volume', 'currency', 'source', 'final']

class MarketDataError(ValueError):
    pass


def market_open(now=None):
    now = pd.Timestamp(now or datetime.now(timezone.utc))
    day = now.tz_convert('America/New_York').date()
    schedule = mcal.get_calendar('NYSE').schedule(day, day)
    return bool(not schedule.empty and schedule.iloc[0].market_open <= now <= schedule.iloc[0].market_close)


def freshness(timestamp, now=None):
    now = pd.Timestamp(now or datetime.now(timezone.utc))
    age = (now - pd.Timestamp(timestamp)).total_seconds()
    if age < -60:
        raise MarketDataError('Future provider timestamp.')
    if not market_open(now):
        return 'Outside regular trading hours'
    return 'Fresh' if age <= 120 else 'Stale (>2 minutes)'


def batches(symbols, size=100):
    symbols = list(dict.fromkeys(symbols))
    for start in range(0, len(symbols), size):
        yield symbols[start:start + size]


class EODHDProvider:
    def __init__(self, config):
        self.key = config.get('EODHD_API_KEY', '')
        if not self.key:
            raise MarketDataError('Set EODHD_API_KEY in .streamlit/secrets.toml.')

    def _get(self, endpoint, params):
        url = 'https://eodhd.com/api/' + endpoint
        params = {**params, 'api_token': self.key, 'fmt': 'json'}
        request = Request(url + '?' + urlencode(params))
        try:
            with urlopen(request, timeout=15) as response:
                return json.load(response)
        except HTTPError as exc:
            messages = {401: 'Invalid EODHD API key.', 403: 'EODHD access denied.', 429: 'EODHD rate limit reached.'}
            raise MarketDataError(messages.get(exc.code, 'EODHD is unavailable.')) from None
        except (URLError, TimeoutError, ValueError):
            raise MarketDataError('The data provider timed out or returned an invalid response.') from None

    def history(self, symbols, start, end):
        if end > datetime.now().date():
            raise MarketDataError('Daily history requires a completed trading session.')
        rows = []
        for symbol in symbols:
            payload = self._get('eod/' + symbol, {'from': start.isoformat(), 'to': end.isoformat(), 'period': 'd', 'order': 'a'})
            if not isinstance(payload, list): raise MarketDataError('Invalid historical data response.')
            for bar in payload:
                rows.append(dict(date=pd.Timestamp(bar['date']).date(), symbol=symbol, open=bar['open'], high=bar['high'], low=bar['low'], close=bar['close'], volume=bar.get('volume', 0), currency='HUF', source='EODHD/BUD', final=True))
        return pd.DataFrame(rows, columns=BAR_COLUMNS)

    def snapshots(self, symbols):
        rows = []
        for group in batches(symbols):
            for symbol in group:
                payload = self._get('real-time/' + symbol, {})
                if not isinstance(payload, dict):
                    payload = {}
                price, timestamp, status = None, pd.NaT, 'No valid delayed quote available'
                try:
                    price = float(payload.get('close') or payload.get('last'))
                    timestamp = pd.Timestamp(payload.get('timestamp') or payload.get('datetime'), unit='s', tz='UTC') if payload.get('timestamp') else pd.Timestamp(payload.get('datetime'), tz='UTC')
                    status = freshness(timestamp)
                except (TypeError, ValueError):
                    pass
                rows.append(dict(symbol=symbol, price=price, timestamp=timestamp, status=status, source='EODHD/BUD'))
        return pd.DataFrame(rows, columns=['symbol', 'price', 'timestamp', 'status', 'source']).set_index('symbol')

AlpacaProvider = EODHDProvider
