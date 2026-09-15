"""Tests never read real credentials or connect to external services."""
from datetime import date
import pandas as pd
import pytest
from stocks.market import sessions
from stocks.live import BAR_COLUMNS

@pytest.fixture(autouse=True)
def isolated_settings(monkeypatch, tmp_path):
    values = {
        'OPENAI_API_KEY': '', 'OPENAI_MODEL': 'test-model',
        'DATABASE_URL': f'sqlite:///{tmp_path}/reports.db',
        'ALPACA_API_KEY': 'test', 'ALPACA_SECRET_KEY': 'test',
        'REPORT_SYMBOLS': 'AAPL,MSFT,NVDA',
    }
    for key, value in values.items():
        monkeypatch.setenv(key, value)
    def no_network(*args, **kwargs):
        pytest.fail('Unexpected external network request in a test')
    monkeypatch.setattr('stocks.live.urlopen', no_network)

@pytest.fixture
def sample_bars():
    """Deterministic OHLC fixture, used only by isolated tests."""
    def build(symbols, start=date(2026, 9, 1), end=date(2026, 9, 14)):
        rows = []
        for index, symbol in enumerate(symbols):
            for day in sessions(start, end):
                close = 100.0 + index + day.day / 10
                rows.append(dict(date=day.date(), symbol=symbol, open=close - 1, high=close + 2,
                                 low=close - 2, close=close, volume=1000, currency='USD',
                                 source='ALPACA/IEX/SPLIT', final=True))
        return pd.DataFrame(rows, columns=BAR_COLUMNS)
    return build
