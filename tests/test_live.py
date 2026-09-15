from datetime import date
from urllib.error import HTTPError
import pandas as pd
import pytest
from stocks.live import AlpacaProvider, MarketDataError, freshness

CONFIG = {'ALPACA_API_KEY': 'test', 'ALPACA_SECRET_KEY': 'test'}


def test_credentials_required():
    with pytest.raises(MarketDataError):
        AlpacaProvider({})


def test_history_pagination_and_new_york_dates(monkeypatch):
    client = AlpacaProvider(CONFIG)
    bar = {'t': '2026-09-14T04:00:00Z', 'o': 100, 'h': 102, 'l': 99, 'c': 101, 'v': 10}
    pages = iter([{'bars': {'AAPL': [bar]}, 'next_page_token': 'next'}, {'bars': {'SPY': [bar]}}])
    calls = []
    def get(endpoint, params):
        calls.append(params.copy())
        return next(pages)
    monkeypatch.setattr(client, '_get', get)
    frame = client.history(('AAPL', 'SPY'), date(2026, 9, 1), date(2026, 9, 14))
    assert frame.symbol.tolist() == ['AAPL', 'SPY']
    assert frame.date.tolist() == [date(2026, 9, 14)] * 2
    assert calls[1]['page_token'] == 'next'
    assert calls[0]['adjustment'] == 'split'
    assert calls[0]['end'].startswith('2026-09-14T23:59:59')


@pytest.mark.parametrize('price', [0, -1, float('nan'), float('inf')])
def test_invalid_quotes_rejected(monkeypatch, price):
    client = AlpacaProvider(CONFIG)
    monkeypatch.setattr(client, '_get', lambda *_: {'AAPL': {'latestTrade': {'p': price, 't': '2026-09-14T14:00:00Z'}}})
    result = client.snapshots(('AAPL',))
    assert pd.isna(result.loc['AAPL', 'price'])
    assert 'No valid' in result.loc['AAPL', 'status']


def test_missing_symbol_rejected(monkeypatch):
    client = AlpacaProvider(CONFIG)
    monkeypatch.setattr(client, '_get', lambda *_: {})
    result = client.snapshots(('AAPL',))
    assert pd.isna(result.loc['AAPL', 'price'])
    assert 'No valid' in result.loc['AAPL', 'status']


def test_freshness_market_hours_and_future():
    now = pd.Timestamp('2026-09-14T14:00:00Z')
    assert freshness(now - pd.Timedelta(seconds=90), now) == 'Fresh'
    assert freshness(now - pd.Timedelta(minutes=3), now).startswith('Stale')
    assert freshness(now, pd.Timestamp('2026-09-14T22:00:00Z')) == 'Outside regular trading hours'
    with pytest.raises(MarketDataError):
        freshness(now + pd.Timedelta(minutes=5), now)


@pytest.mark.parametrize('status', [401, 403, 429, 500])
def test_http_errors_never_expose_credentials(monkeypatch, status):
    def fail(*_, **__):
        raise HTTPError('https://example.test/SECRET', status, 'SECRET', {}, None)
    monkeypatch.setattr('stocks.live.urlopen', fail)
    with pytest.raises(MarketDataError) as exc:
        AlpacaProvider(CONFIG)._get('snapshots', {})
    assert 'SECRET' not in str(exc.value)


def test_dashboard_without_credentials(monkeypatch):
    from streamlit.testing.v1 import AppTest
    monkeypatch.setenv('ALPACA_API_KEY', '')
    monkeypatch.setenv('ALPACA_SECRET_KEY', '')
    from pathlib import Path
    app = AppTest.from_file(Path(__file__).resolve().parents[1] / 'app.py', default_timeout=30).run()
    assert not app.exception
    assert any('ALPACA_API_KEY' in error.value for error in app.error)



def test_snapshots_batch_requests_and_keep_partial_results(monkeypatch):
    client = AlpacaProvider(CONFIG)
    requests = []
    def get(endpoint, params):
        requests.append(params)
        return {'STK0': {'latestTrade': {'p': 100, 't': pd.Timestamp.now(tz='UTC').isoformat()}}}
    monkeypatch.setattr(client, '_get', get)
    result = client.snapshots([f'STK{i}' for i in range(205)])
    assert len(requests) == 3
    assert all(r['feed'] == 'iex' for r in requests)
    assert len(result) == 205
    assert result.loc['STK0', 'price'] == 100
    assert pd.isna(result.loc['STK204', 'price'])


def test_history_repeated_page_is_rejected(monkeypatch):
    client = AlpacaProvider(CONFIG)
    monkeypatch.setattr(client, '_get', lambda *_: {'bars': {}, 'next_page_token': 'same'})
    with pytest.raises(MarketDataError, match='pagination'):
        client.history(('AAPL',), date(2026, 9, 1), date(2026, 9, 14))
