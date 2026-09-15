from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

import pandas as pd
import plotly.graph_objects as go
import streamlit as st
from dashboard_style import apply_style, chart_layout, show_chart
from stocks.config import settings
from stocks.market import DEFAULT_SYMBOLS, BENCHMARK, sessions, validate, metrics
from stocks.live import EODHDProvider, MarketDataError, freshness, market_open
from stocks.pipeline import run

st.set_page_config(page_title='Stock Intelligence', page_icon='📈', layout='wide')
apply_style()
config = settings()
credentials = {'EODHD_API_KEY': config['EODHD_API_KEY']}
st.html('''<div class="hero"><div><div class="eyebrow">STOCK INTELLIGENCE / MARKET OVERVIEW</div>
<h1>Stock Intelligence<span style="color:#9bb1c5">.</span></h1>
<p>Live prices and verified market analysis.</p></div>
<div class="hero-badge">EODHD / BUD</div></div>''')

@st.cache_data(ttl=300, show_spinner=False)
def history(symbols, start, end, credentials):
    return EODHDProvider(credentials).history(symbols, start, end)

@st.cache_data(ttl=10, show_spinner=False)
def quotes(symbols, credentials):
    return EODHDProvider(credentials).snapshots(symbols)

with st.sidebar:
    st.html('<div class="brand"><span class="brand-mark">◈</span> INTELLIGENCE</div>')
    st.header('Stocks & filters')
    st.caption('Real market data · EODHD delayed · HUF')
    if st.button('Refresh data', width='stretch'):
        history.clear()
        quotes.clear()

with st.sidebar:
    selected = st.multiselect('Stocks (5–8)', DEFAULT_SYMBOLS,
                              default=list(DEFAULT_SYMBOLS),
                              help='Choose up to eight Hungarian stocks; BET.BUD is added as the benchmark.')
    window = st.selectbox('History (calendar days)', [30, 60, 90], index=1)
    auto = st.toggle('Automatic refresh', value=True)
    interval = st.select_slider('Refresh interval (seconds)', [15, 30, 60], value=30)
    st.caption('Benchmark: BET.BUD · Budapest trading calendar')
    st.caption('EODHD covers one exchange. BET.BUD is included as the benchmark.')
    st.caption('Refresh runs while this page is open and does not call OpenAI.')

if not selected:
    st.info('Select at least one stock in the sidebar.')
    st.stop()
symbols = tuple(dict.fromkeys(selected + [BENCHMARK]))

@st.fragment(run_every=f'{interval}s' if auto else None)
def live_panel():
    state = 'Regular session open' if market_open() else 'Outside regular trading hours'
    refresh_label = f'{interval}s polling' if auto else 'Automatic refresh off'
    st.info(f'EODHD delayed · {refresh_label} · {state}')
    try:
        live = quotes(symbols, credentials).copy()
        live['status'] = live.apply(lambda r: freshness(r.timestamp) if pd.notna(r.timestamp) else r.status, axis=1)
        previous_day = datetime.now(ZoneInfo('America/New_York')).date() - timedelta(days=1)
        end = sessions(previous_day - timedelta(days=15), previous_day)[-1].date()
        daily_frame = history(symbols, end - timedelta(days=5), end, credentials)
        daily_table = metrics(daily_frame)
    except MarketDataError as exc:
        st.error(str(exc))
        return
    except Exception:
        st.error('Latest trades could not be loaded. No cached prices are presented as current.')
        return
    for start in range(0, min(len(selected), 6), 3):
        subset = selected[start:start + 3]
        for col, symbol in zip(st.columns(len(subset)), subset):
            row = live.loc[symbol]
            daily = daily_table.loc[symbol] if symbol in daily_table.index else None
            delta = f'{daily.change_usd:+.2f} HUF ({daily.change_pct:+.2f}%)' if daily is not None else None
            col.metric(symbol + ' · latest trade', f'{row.price:,.2f} HUF' if pd.notna(row.price) else 'Unavailable', delta)
            stamp = row.timestamp.tz_convert('Europe/Budapest').strftime('%Y-%m-%d %H:%M:%S %Z') if pd.notna(row.timestamp) else 'No timestamp'
            col.caption(f'{stamp} · {row.status}')
    st.dataframe(live.rename(columns={'price': 'Last trade (HUF)', 'timestamp': 'Trade time (UTC)',
                                     'status': 'Availability', 'source': 'Source'}), width='stretch')
    st.caption('All selected stocks are listed above. Prices reflect the latest available EODHD trade, not a consolidated market quote.')

live_panel()

@st.fragment(run_every='300s' if auto else None)
def analysis_panel():
    previous_day = datetime.now(ZoneInfo('America/New_York')).date() - timedelta(days=1)
    end = sessions(previous_day - timedelta(days=15), previous_day)[-1].date()
    try:
        frame = history(symbols, end - timedelta(days=window), end, credentials)
    except MarketDataError as exc:
        st.error(str(exc))
        return
    except Exception:
        st.error('Historical data could not be loaded.')
        return
    available, excluded = [], []
    for symbol in symbols:
        subset = frame[frame.symbol == symbol]
        errors = validate(subset, end, (symbol,))
        if errors:
            excluded.append({'Symbol': symbol, 'Reason': '; '.join(errors)})
        else:
            available.append(symbol)
    if excluded:
        st.warning('Some stocks have unavailable or incomplete EODHD daily history. They are excluded from historical comparisons.')
        st.dataframe(pd.DataFrame(excluded), hide_index=True, width='stretch')
    usable = [s for s in selected if s in available]
    if not usable:
        st.info('No selected stock has validated history for this period. Latest trades remain available above.')
        return
    valid_frame = frame[frame.symbol.isin(available)]
    table = metrics(valid_frame)
    st.caption(f'Latest completed daily session: {end} · EODHD/BUD · HUF · Split-adjusted prices')
    overview, comparison, ai_tab, quality = st.tabs(['Overview', 'Comparison', 'AI analysis', 'Data quality'])
    with overview:
        st.subheader('Relative price · first common session = 100')
        pivot = valid_frame.pivot(index='date', columns='symbol', values='close').sort_index()
        common = pivot.dropna()
        if common.empty:
            st.info('No common sessions are available for a normalized comparison.')
        else:
            normalized = common.div(common.iloc[0]).mul(100)
            fig = go.Figure()
            for symbol in normalized:
                fig.add_trace(go.Scatter(x=normalized.index, y=normalized[symbol], name=symbol,
                                        mode='lines', line=dict(width=2.3, dash='dot' if symbol == BENCHMARK else 'solid')))
            chart_layout(fig, 380).update_layout(hovermode='x unified')
            show_chart(fig, 'normalized')
        st.caption('Daily split-adjusted price returns exclude dividends. Missing sessions are not filled with invented prices.')
        symbol = st.selectbox('Detailed price history', usable)
        bars = valid_frame[valid_frame.symbol == symbol].sort_values('date')
        fig = go.Figure(go.Candlestick(x=bars.date, open=bars.open, high=bars.high, low=bars.low,
                                      close=bars.close, name=symbol,
                                      increasing_line_color='#639b90', decreasing_line_color='#bc8190'))
        fig.add_trace(go.Scatter(x=bars.date, y=bars.close.rolling(20).mean(), name='20-observation moving average',
                                line=dict(color='#8cabc4', width=2)))
        chart_layout(fig, 360).update_layout(xaxis_rangeslider_visible=False)
        fig.update_yaxes(ticksuffix=' HUF')
        show_chart(fig, 'candles')
        st.caption('The moving average requires 20 available daily bars. Gaps may span multiple trading sessions.')
        volume = go.Figure(go.Bar(x=bars.date, y=bars.volume, name='EODHD volume (shares)', marker_color='#a6b6d0'))
        show_chart(chart_layout(volume, 220), 'volume')
        st.download_button('Download daily history (CSV)', valid_frame.to_csv(index=False).encode('utf-8'),
                           'stock_history.csv', 'text/csv')
    with comparison:
        st.subheader('Weekly comparison')
        st.caption('Current week versus the previous completed week, based on daily closing prices.')
        daily = valid_frame.pivot(index='date', columns='symbol', values='close').sort_index()
        current_end = daily.index.max()
        current_start = current_end - pd.Timedelta(days=6)
        previous_end = current_start - pd.Timedelta(days=1)
        previous_start = previous_end - pd.Timedelta(days=6)
        weekly_rows = []
        for symbol in daily.columns:
            current = daily.loc[daily.index.to_series().between(current_start, current_end), symbol].dropna()
            previous = daily.loc[daily.index.to_series().between(previous_start, previous_end), symbol].dropna()
            if current.empty or previous.empty:
                continue
            weekly_rows.append({'Symbol': symbol, 'Current week return (%)': (current.iloc[-1] / current.iloc[0] - 1) * 100,
                                'Previous week return (%)': (previous.iloc[-1] / previous.iloc[0] - 1) * 100})
        if weekly_rows:
            weekly = pd.DataFrame(weekly_rows).set_index('Symbol').round(2)
            st.caption(f'Current: {current_start} to {current_end} · Previous: {previous_start} to {previous_end}')
            fig = go.Figure()
            fig.add_bar(x=weekly.index, y=weekly['Current week return (%)'], name='Current week')
            fig.add_bar(x=weekly.index, y=weekly['Previous week return (%)'], name='Previous week')
            chart_layout(fig, 340).update_layout(barmode='group')
            fig.update_yaxes(ticksuffix='%')
            show_chart(fig, 'weekly_comparison')
            st.dataframe(weekly, width='stretch')
        st.subheader('Latest completed session')
        changes = table.change_pct
        fig = go.Figure(go.Bar(x=changes.index, y=changes.values,
                              marker_color=['#8cb7ab' if v >= 0 else '#c494a0' for v in changes]))
        chart_layout(fig).update_yaxes(ticksuffix='%')
        show_chart(fig, 'daily_change')
        st.dataframe(table.rename(columns={
            'close': 'Close (HUF)', 'change_HUF': 'Daily change (HUF)', 'change_pct': 'Daily change (%)',
            'volume': 'EODHD volume (shares)', 'range_pct': 'Daily range / close (%)',
            'vs_BET.BUD_pp': 'Difference from BET.BUD (percentage points)'}).round(2), width='stretch')
        if BENCHMARK not in available:
            st.warning('BET.BUD history is unavailable. Benchmark differences are not calculated.')
        if not common.empty:
            st.subheader('Price return over common sessions')
            st.caption(f'{common.index[0]} to {common.index[-1]}')
            st.dataframe(((common.iloc[-1] / common.iloc[0] - 1) * 100).rename('Price return (%)').round(2), width='stretch')
    with ai_tab:
        st.subheader('Verified daily report')
        st.caption('Reports cover all selected stocks plus BET.BUD for the previous calendar day in Budapest. Live trades are not included.')
        enabled = bool(config['OPENAI_API_KEY'] and config['OPENAI_MODEL'])
        if not enabled:
            st.info('Set OPENAI_API_KEY and OPENAI_MODEL for AI fact selection. Verified templates can run without OpenAI.')
        ai = st.checkbox('Use OpenAI fact selection', disabled=not enabled,
                         help='When enabled, OpenAI selects which validated facts to prioritize. It cannot add numbers, news or recommendations.')
        if st.button('Validate and generate report', type='primary'):
            try:
                with st.spinner('Validating market data and generating the report…'):
                    result = run(config, use_ai=ai, symbols=selected)
                if result['status'] == 'PASSED':
                    st.session_state['last_report'] = result
                elif result['status'] == 'NO_SESSION':
                    st.info(result['message'])
                else:
                    st.error('FAILED · ' + '; '.join(result['errors']))
            except Exception as exc:
                st.error(f'Report generation failed: {exc}')
        result = st.session_state.get('last_report')
        if result and result.get('language') == 'en' and set(result.get('symbols', [])) == set(symbols):
            st.success('PASSED · ' + result['mode'])
            st.write(result['summary'])
    with quality:
        st.success('Displayed daily history passed internal validation.')
        st.caption('Schema, OHLC, finite positive prices, volume, duplicates, trading dates and last-session coverage checked.')
        st.dataframe(valid_frame, width='stretch', hide_index=True)

analysis_panel()






