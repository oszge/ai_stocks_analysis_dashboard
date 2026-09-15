# Stock Intelligence

A live Streamlit stock dashboard for tracking market performance, comparing symbols, and generating verified daily summaries from real market data.

This project is designed for real deployment on Streamlit and is built around a simple idea: deliver market snapshots, historical analysis, and AI-assisted summaries using validated data rather than free-form commentary.

## Live app

This project is intended to run as a Streamlit application in a hosted environment, including Streamlit Community Cloud or a similar managed deployment.

The app entry point is:

- `app.py`

The dashboard expects runtime secrets or environment variables for the market and AI providers.

## Overview

Stock Intelligence provides:

- Live market quotes and freshness checks
- Historical price analysis and normalized performance charts
- Benchmark comparisons against a selected reference index
- Daily session validation and data-quality warnings
- Optional OpenAI-backed fact selection for English daily reports
- CSV export of the daily history used in visualizations

The app is optimized for a clean, data-first layout and uses Plotly for interactive charts and Streamlit for the UI.

## Features

### Live market monitoring

- Real-time quote polling using EODHD market data
- Market-status banner for regular session versus outside-hours state
- Freshness checks for stale quotes
- Color-coded daily move indicators
- Auto-refresh support with configurable polling intervals

### Historical analysis

- Normalized price view across the selected symbol set
- Candlestick chart for a chosen symbol
- 20-day moving average overlay
- Daily volume chart
- Weekly comparison and return table
- Downloadable CSV of validated daily market history

### Data validation

The dashboard does not blindly trust the feed. It validates:

- Symbol coverage and session completeness
- OHLC integrity and positive finite prices
- Volume sanity checks
- Duplicate and missing-date checks
- Last-session coverage logic

Symbols with incomplete history are excluded from historical comparisons and shown explicitly in the UI.

### AI report generation

The project includes a verified summary workflow:

- Templates are rendered from validated numeric facts only
- OpenAI can be used to select the facts to prioritize, but it does not invent data
- Reports are blocked if required data is incomplete or the market session is closed
- The app can run without OpenAI, using verified template summaries based on real data

## Tech stack

- Python 3.11+
- Streamlit
- Pandas
- Plotly
- OpenAI Python SDK
- EODHD market data API
- SQLite for local data support where required

## Project structure

```text
ai_stocks_analysis_dashboard/
├── app.py                         # main Streamlit app
├── dashboard.css                 # custom styling
├── dashboard_style.py            # UI helpers and chart wrappers
├── requirements.txt              # runtime dependencies
├── requirements-dev.txt          # dev/test dependencies
├── .streamlit/
│   └── secrets.toml              # local secrets; keep out of source control
├── data/                         # local data artifacts
├── jobs/
│   └── daily_summary.py          # report worker entry point
├── prompts/
│   └── daily_summary.txt         # report prompt template
├── stocks/
│   ├── __init__.py
│   ├── config.py                 # environment and secrets management
│   ├── live.py                   # market API integration and freshness rules
│   ├── market.py                 # market data transformation and metrics
│   ├── pipeline.py               # report pipeline orchestration
│   ├── storage.py                # persistence support
│   └── summary.py                # summary/report logic
├── tests/                        # application tests
├── README.md                     # project documentation
└── .gitignore
```

## Setup

### 1. Clone the project

```bash
git clone <your-repository-url>
cd ai_stocks_analysis_dashboard
```

### 2. Create a virtual environment

```bash
python -m venv .venv
```

On Windows:

```powershell
.venv\Scripts\Activate.ps1
```

On macOS/Linux:

```bash
source .venv/bin/activate
```

### 3. Install dependencies

```bash
pip install -r requirements.txt
pip install -r requirements-dev.txt
```

### 4. Configure secrets

Create a `.streamlit/secrets.toml` file in the project root.

```toml
EODHD_API_KEY = "your_eodhd_api_key"
OPENAI_API_KEY = "your_openai_api_key"
OPENAI_MODEL = "gpt-4o-mini"
REPORT_SYMBOLS = "OTP.BUD,MOL.BUD,RICHTER.BUD,MTELEKOM.BUD,4IG.BUD,ANY.BUD,WABERERS.BUD,GRAPHISOFT.BUD"
```

Notes:

- The app reads secrets from `.streamlit/secrets.toml` when present.
- Environment variables override the values in the TOML file.
- Do not commit real credentials to version control.

## Run locally

```bash
streamlit run app.py
```

The app will open in the default browser at the local Streamlit URL, usually:

```text
http://localhost:8501
```

## Deployment on Streamlit

To deploy this app on Streamlit Community Cloud or a Streamlit-hosted environment:

1. Push the project to a GitHub repository.
2. Connect the repository in Streamlit Cloud.
3. Set the app main file to `app.py`.
4. Add the required secrets under Streamlit app settings:
   - `EODHD_API_KEY`
   - `OPENAI_API_KEY`
   - `OPENAI_MODEL`
   - `REPORT_SYMBOLS`
5. Deploy the app.

Make sure the environment uses Python 3.11+ and installs dependencies from `requirements.txt`.

## Configuration

The secret and environment configuration lives in `stocks/config.py`.

The default settings include:

- `EODHD_API_KEY`
- `OPENAI_API_KEY`
- `OPENAI_MODEL`
- `DATABASE_URL`
- `REPORT_SYMBOLS`

If you are using a different market universe, update the symbol list in the secret or environment variable.

## Usage guide

### Dashboard sections

The application includes:

- Latest trades panel
- Overview with normalized price trends and volume
- Comparison view for changes and benchmark deltas
- AI Analysis tab for validated summaries
- Data quality section for validation results

### Automatic refresh

The app supports periodic refreshes while the page stays open. You can configure:

- refresh interval in seconds
- automatic refresh toggle
- symbol selection in the sidebar

### Report generation

The report workflow can be invoked directly from the dashboard or through the job module.

Example:

```bash
python -m jobs.daily_summary --template
python -m jobs.daily_summary --symbols OTP.BUD,MOL.BUD,BUX.BUD
python -m jobs.daily_summary --watch
```

This generates summaries based on the previous trading session and validates the data before producing output.

## Data sources and limitations

This project relies on EODHD for market data. The dashboard expects market coverage from that provider and explicitly surfaces missing or invalid data rather than fabricating values.

Important constraints:

- Data is not a full consolidated exchange feed; coverage depends on the provider and the selected symbol
- Missing history is not filled with synthetic values
- Benchmarks and comparisons depend on available overlapping sessions
- AI-generated text is limited to validated facts and does not provide unrestricted forecasting or commentary

## Testing

Run the test suite with:

```bash
pytest -q --tb=short
```

The project uses isolated fixtures and mocked market responses so tests do not depend on live credentials or external services.

## Security notes

- Never commit `.streamlit/secrets.toml` to Git
- Never hard-code API keys into source files
- Prefer environment variables or deployment secret management for cloud hosting
- Keep the OpenAI key and market API key separate from any public logs

## License

This project is intended for educational and portfolio-analysis use. Add your preferred license file if you plan to distribute or publish the code publicly.

## Contact and contribution

This is a personal project and may be extended with:

- additional market screens
- richer AI analysis views
- more benchmarks and comparison logic
- additional export and alerting features

Contributions are welcome if they improve validation, deployment safety, or user experience.
