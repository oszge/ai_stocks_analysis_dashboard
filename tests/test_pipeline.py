from datetime import date, datetime
from zoneinfo import ZoneInfo
import pytest
from stocks.config import settings
from stocks.live import AlpacaProvider
import pandas as pd
from stocks.market import DEFAULT_SYMBOLS, BENCHMARK, validate, metrics
from stocks.pipeline import run, yesterday
from stocks.summary import facts_for, validate_selection, render

TARGET = date(2026, 9, 14)
SYMBOLS = (*DEFAULT_SYMBOLS, BENCHMARK)


@pytest.fixture
def frame(sample_bars):
    return sample_bars(SYMBOLS, date(2026, 9, 1), TARGET)


def test_valid_data_and_benchmark(frame):
    assert validate(frame, TARGET, SYMBOLS) == []
    assert metrics(frame).loc['SPY', 'vs_spy_pp'] == 0


@pytest.mark.parametrize('failure', ['nan', 'negative', 'ohlc', 'duplicate', 'missing', 'unfinal', 'future'])
def test_invalid_data_blocked(frame, failure):
    if failure == 'nan':
        frame.loc[0, 'close'] = float('nan')
    elif failure == 'negative':
        frame.loc[0, 'volume'] = -1
    elif failure == 'ohlc':
        frame.loc[0, 'high'] = 1
    elif failure == 'duplicate':
        import pandas as pd
        frame = pd.concat([frame, frame.iloc[:1]])
    elif failure == 'missing':
        frame = frame[~((frame.symbol == 'AAPL') & (frame.date == TARGET))]
    elif failure == 'unfinal':
        frame.loc[0, 'final'] = False
    else:
        frame.loc[0, 'date'] = date(2026, 9, 15)
    assert validate(frame, TARGET, SYMBOLS)


def test_hallucination_and_coverage_blocked(frame):
    facts = facts_for(metrics(frame), TARGET)
    assert validate_selection(['made-up'], facts)
    assert validate_selection(['AAPL:daily'], facts)
    with pytest.raises(ValueError):
        render(list(facts) + ['invented news'], facts)


def test_idempotent_report(tmp_path):
    config = settings()
    calls = []
    def select(facts, _):
        calls.append(1)
        return list(facts)
    first = run(config, TARGET, use_ai=True, selector=select)
    assert first['status'] == 'PASSED'
    second = run(config, TARGET, use_ai=True, selector=select)
    assert second['status'] == 'PASSED'
    assert len(calls) == 1


def test_failed_output_not_persisted(tmp_path):
    config = settings()
    result = run(config, TARGET, use_ai=True, selector=lambda *_: ['unknown'])
    assert result['status'] == 'FAILED'
    assert 'summary' not in result
    assert result['status'] == 'FAILED'


def test_failed_input_never_calls_ai(monkeypatch, frame, tmp_path):
    frame.loc[0, 'close'] = -1
    monkeypatch.setattr(AlpacaProvider, 'history', lambda *_: frame)
    config = settings()
    def forbidden(*_):
        pytest.fail('AI must not be called before data PASSED')
    assert run(config, TARGET, use_ai=True, selector=forbidden)['status'] == 'FAILED'


@pytest.mark.parametrize('target', [date(2026, 9, 13), date(2026, 9, 7)])
def test_closed_market(target):
    assert run(settings(), target)['status'] == 'NO_SESSION'


def test_budapest_date():
    now = datetime(2026, 9, 14, 23, 30, tzinfo=ZoneInfo('UTC'))
    assert yesterday(now) == date(2026, 9, 14)


@pytest.mark.parametrize('status,parsed', [('incomplete', None), ('completed', None)])
def test_openai_incomplete_or_refusal(monkeypatch, status, parsed):
    from types import SimpleNamespace
    import openai
    from stocks.summary import select_with_openai
    fake = SimpleNamespace(responses=SimpleNamespace(parse=lambda **_: SimpleNamespace(
        status=status, output_parsed=parsed)))
    monkeypatch.setattr(openai, 'OpenAI', lambda **_: fake)
    with pytest.raises(ValueError):
        select_with_openai({}, {'OPENAI_API_KEY': 'test', 'OPENAI_MODEL': 'test'})


def test_streamlit_smoke():
    from pathlib import Path
    from streamlit.testing.v1 import AppTest
    app = AppTest.from_file(Path(__file__).resolve().parents[1] / 'app.py').run(timeout=30)
    assert not app.exception
    assert len(app.metric) == 6


@pytest.fixture(autouse=True)
def mock_market(monkeypatch, sample_bars):
    monkeypatch.setattr(AlpacaProvider, 'history', lambda self, symbols, start, end: sample_bars(symbols, start, end))
    monkeypatch.setattr(AlpacaProvider, 'snapshots', lambda self, symbols: pd.DataFrame([
        dict(symbol=s, price=100.0, timestamp=pd.Timestamp.now(tz='UTC'), status='Fresh', source='ALPACA/IEX')
        for s in symbols]).set_index('symbol'))


def test_custom_report_universe_and_english(tmp_path):
    config = settings()
    result = run(config, TARGET, symbols=['TSLA', 'SPY', 'TSLA'])
    assert result['status'] == 'PASSED'
    assert result['symbols'] == ['TSLA', 'SPY']
    assert 'TSLA closed at' in result['summary']
    assert result['language'] == 'en'
    assert 'USD' in result['summary']


def test_dashboard_searchable_catalog_and_empty_selection():
    from pathlib import Path
    from streamlit.testing.v1 import AppTest
    app = AppTest.from_file(Path(__file__).resolve().parents[1] / 'app.py', default_timeout=30).run()
    assert not app.exception
    app.multiselect[0].set_value(['TSLA']).run()
    assert not app.exception
    assert len(app.metric) == 1
    assert 'TSLA' in app.metric[0].label
    app.multiselect[0].set_value([]).run()
    assert not app.exception
    assert any('Select at least one' in info.value for info in app.info)
