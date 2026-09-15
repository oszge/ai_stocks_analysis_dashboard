"""Read-only Alpaca IEX data and the paper-account US equity catalog."""
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


class AlpacaProvider:
    def __init__(self, config):
        self.key = config.get('ALPACA_API_KEY', '')
        self.secret = config.get('ALPACA_SECRET_KEY', '')
        if not self.key or not self.secret:
            raise MarketDataError('Set ALPACA_API_KEY and ALPACA_SECRET_KEY in .streamlit/secrets.toml.')

    def _get(self, endpoint, params):
        url = 'https://data.alpaca.markets/v2/stocks/' + endpoint
        request = Request(url + '?' + urlencode(params),
                          headers={'APCA-API-KEY-ID': self.key, 'APCA-API-SECRET-KEY': self.secret})
        try:
            with urlopen(request, timeout=15) as response:
                return json.load(response)
        except HTTPError as exc:
            messages = {401: 'Invalid Alpaca credentials. Use your paper-account key pair.',
                        403: 'Your account cannot access the requested Alpaca resource.',
                        429: 'Alpaca rate limit reached. Wait and use a longer refresh interval.'}
            raise MarketDataError(messages.get(exc.code, 'Alpaca is unavailable.')) from None
        except (URLError, TimeoutError, ValueError):
            raise MarketDataError('The data provider timed out or returned an invalid response.') from None

    def history(self, symbols, start, end):
        zone = ZoneInfo('America/New_York')
        now = datetime.now(zone)
        if end > now.date() or (end == now.date() and market_open(now)):
            raise MarketDataError('Daily history requires a completed trading session.')
        rows = []
        for group in batches(symbols):
            params = dict(symbols=','.join(group), timeframe='1Day',
                          start=datetime.combine(start, time.min, zone).isoformat(),
                          end=datetime.combine(end, time.max, zone).isoformat(),
                          adjustment='split', feed='iex', limit=10000, sort='asc')
            seen = set()
            while True:
                payload = self._get('bars', params)
                if not isinstance(payload, dict):
                    raise MarketDataError('Invalid historical data response.')
                for symbol, bars in (payload.get('bars') or {}).items():
                    for bar in bars:
                        day = pd.Timestamp(bar['t']).tz_convert(zone).date()
                        rows.append(dict(date=day, symbol=symbol, open=bar['o'], high=bar['h'],
                                         low=bar['l'], close=bar['c'], volume=bar['v'], currency='USD',
                                         source='ALPACA/IEX/SPLIT', final=True))
                token = payload.get('next_page_token')
                if not token:
                    break
                if token in seen:
                    raise MarketDataError('The provider returned a repeated pagination token.')
                seen.add(token)
                params['page_token'] = token
        return pd.DataFrame(rows, columns=BAR_COLUMNS)

    def snapshots(self, symbols):
        rows = []
        for group in batches(symbols):
            payload = self._get('snapshots', {'symbols': ','.join(group), 'feed': 'iex'})
            if not isinstance(payload, dict):
                raise MarketDataError('Invalid snapshot response.')
            for symbol in group:
                price, timestamp, status = None, pd.NaT, 'No valid IEX trade available'
                try:
                    trade = payload[symbol]['latestTrade']
                    candidate = float(trade['p'])
                    stamp = pd.Timestamp(trade['t'])
                    if not math.isfinite(candidate) or candidate <= 0 or pd.isna(stamp) or stamp.tzinfo is None:
                        raise ValueError()
                    status = freshness(stamp)
                    price, timestamp = candidate, stamp
                except (KeyError, TypeError, ValueError):
                    pass
                rows.append(dict(symbol=symbol, price=price, timestamp=timestamp,
                                 status=status, source='ALPACA/IEX'))
        return pd.DataFrame(rows, columns=['symbol', 'price', 'timestamp', 'status', 'source']).set_index('symbol')
