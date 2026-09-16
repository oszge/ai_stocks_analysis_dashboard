# Stock Intelligence

A live US equity dashboard with interactive Plotly charts,
verified English daily reports, and an Alpaca IEX market-data connection.

## Start locally

Requires Python 3.11 or later.

```powershell
python -m venv .venv
.venv/Scripts/python -m pip install -r requirements-dev.txt
.venv/Scripts/python -m streamlit run app.py --server.port 8502
```

Open http://127.0.0.1:8502. Configure your paper-account credentials in
`.streamlit/secrets.toml`, which is excluded from Git:

```toml
ALPACA_API_KEY = "your-paper-api-key-id"
ALPACA_SECRET_KEY = "your-paper-secret-key"
OPENAI_API_KEY = "your-openai-key"
OPENAI_MODEL = "gpt-5.6-luna"
REPORT_SYMBOLS = "AAPL,MSFT,NVDA"
```

Environment variables override these settings. Never commit credentials.
Alpaca credentials are required. There are no alternative market-data modes or
feed selectors. All stock data requests explicitly use IEX.

## Stock universe

The dashboard focuses on seven major US stocks—AAPL, MSFT, NVDA, AMZN, GOOGL,
META and TSLA—plus SPY as the benchmark. You can select five to seven stocks;
SPY is added automatically. Requests are batched and paginated where needed.

IEX represents one exchange, not consolidated US market volume. Some equities,
including OTC securities, may not have IEX trades. Missing or invalid trades
are displayed as unavailable, not as zero. Missing history excludes that symbol
from historical comparisons and displays a reason. Other symbols remain usable.

## Dashboard

- **Latest trades:** real IEX prices with provider timestamps, availability,
  freshness and green/red day-over-day deltas. The selected stocks have cards; the table includes all
  selected stocks and SPY. Refresh every 15, 30 or 60 seconds while the page is open.
- **Overview:** normalized daily prices, candlesticks, a 20-observation moving
  average, IEX share volume and history CSV export.
- **Comparison:** daily absolute/percentage price change, daily range, SPY
  differences in percentage points and price return over common available sessions.
- **AI analysis:** verified English reports for the selected stocks plus SPY.
- **Data quality:** validated daily bars and explicit coverage failures.

Live prices are polled using REST, not streamed on every tick. A successful
HTTP request does not imply a new trade. Trades older than two minutes during
regular hours are labeled stale. Outside regular hours the session label is
shown together with the exact timestamp, which may be from a previous session.

Daily history ends on the last trading date before the current New York date.
It refreshes every five minutes while automatic refresh is enabled. Prices are
split-adjusted and exclude dividends; returns are price returns, not total returns.
Normalized comparisons use common dates without filling missing bars. Moving
averages require 20 available observations, which may span more than 20 sessions.
If SPY is unavailable, benchmark differences are left missing.

## Reports and AI

The active English system prompt is `prompts/daily_summary.txt`. It requires
USD labels, unchanged input values, supplied evidence only, and relevant SPY
comparisons. The model selects fact identifiers; validated templates render the
English report. It does not write unrestricted commentary or generate forecasts.
Risk or monitoring recommendations can only be selected if supplied as facts.
The current fact catalog contains daily prices, absolute/percentage changes,
volume and benchmark comparisons.

Without an OpenAI key, verified template reports still use real Alpaca data.
Automatic market refresh never triggers an AI call. Reports require complete,
validated data for all requested symbols and SPY; incomplete input blocks the
report rather than silently dropping requested stocks. A closed target date
returns NO_SESSION. Failed validation returns FAILED and saves no summary.

Reports are generated in memory for the current session. No database, SQLAlchemy
connection, report archive or persistence layer is used.

## Daily worker

```powershell
# One report using real data and verified templates, without an OpenAI call:
.venv/Scripts/python -m jobs.daily_summary --template
# One report for a custom selection:
.venv/Scripts/python -m jobs.daily_summary --symbols TSLA,AMD,SPY
# Daily AI report at 08:00 Europe/Budapest:
.venv/Scripts/python -m jobs.daily_summary --watch
```

`REPORT_SYMBOLS` sets the worker's default selection; `--symbols` overrides it.
SPY is added once automatically. Reports target the previous calendar day in
Budapest. Closed dates produce no report. Run only one worker to avoid duplicate
AI calls. The computer must remain awake. Starting after 08:00 catches up the
current day's job, but not earlier missed jobs. The dashboard does not start the
worker or install an operating-system schedule.

## Tests

```powershell
.venv/Scripts/python -m pytest -q --tb=short
```

Tests use isolated fixtures and mocked market responses.
They never use local credentials or make external calls. Runtime application
code has no synthetic market-data generator.

## Official references

- [Alpaca IEX coverage](https://docs.alpaca.markets/us/docs/market-data-faq)
- [Historical bars and pagination](https://docs.alpaca.markets/us/reference/stockbars)
- [Streamlit timed fragments](https://docs.streamlit.io/develop/api-reference/execution-flow/st.fragment)
