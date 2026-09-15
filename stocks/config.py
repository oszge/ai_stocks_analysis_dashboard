import os
import tomllib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def settings():
    path = ROOT / '.streamlit' / 'secrets.toml'
    values = tomllib.loads(path.read_text(encoding='utf-8')) if path.exists() else {}
    defaults = dict(OPENAI_API_KEY='', OPENAI_MODEL='',
                    DATABASE_URL=f'sqlite:///{(ROOT / "data/stocks.db").as_posix()}',
                    ALPACA_API_KEY='', ALPACA_SECRET_KEY='',
                    REPORT_SYMBOLS='AAPL,MSFT,NVDA')
    return {k: os.environ.get(k, values.get(k, v)) for k, v in defaults.items()}
