"""Shared platinum theme and interactive chart styling."""

from pathlib import Path

import plotly.graph_objects as go
import streamlit as st

PALETTE = ["#b45cff", "#8e6bff", "#d58cff", "#7357d9", "#c36cff", "#9b8cff"]


def apply_style():
    css = Path(__file__).with_name("dashboard.css").read_text(encoding="utf-8")
    st.html(f"<style>{css}</style>")


def chart_layout(fig, height=340):
    fig.update_layout(
        template="plotly_dark", height=height,
        paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
        font=dict(family="Segoe UI, sans-serif", size=12, color="#d8cbe3"),
        margin=dict(l=12, r=24, t=24, b=20),
        hoverlabel=dict(bgcolor="#211631", bordercolor="#9b5de7", font_color="#f2eaff"),
        legend=dict(orientation="h", y=1.14, x=0, title=None),
        colorway=PALETTE, bargap=0.38,
    )
    fig.update_xaxes(showgrid=False, zeroline=False, title=None, tickfont_size=11)
    fig.update_yaxes(gridcolor="rgba(130,105,155,0.20)", zeroline=False, title=None, tickfont_size=11)
    return fig


def revenue_chart(series):
    fig = go.Figure()
    # Identical geometry on each layer: the halo never changes the data curve.
    for width, opacity in [(10, 0.035), (7, 0.055), (4, 0.09)]:
        fig.add_trace(go.Scatter(x=series.index, y=series.values, mode="lines",
                                line=dict(color=f"rgba(180,92,255,{opacity})", width=width),
                                name="Revenue glow", hoverinfo="skip", showlegend=False))
    fig.add_trace(go.Scatter(
        x=series.index, y=series.values, mode="lines", name="Revenue (EUR)",
        line=dict(color="#b45cff", width=2.3), fill="tozeroy", fillcolor="rgba(180,92,255,0.10)",
        hovertemplate="%{x|%Y. %m. %d.}<br><b>%{y:,.2f} €</b><extra>Revenue</extra>",
        showlegend=False,
    ))
    chart_layout(fig, 360)
    fig.update_layout(hovermode="x unified")
    fig.update_yaxes(rangemode="tozero", tickformat=",.0f", ticksuffix=" €")
    return fig


def ranking_chart(ranking):
    values = ranking.head(10).iloc[::-1]
    fig = go.Figure()
    # A translucent wider bar is a visual halo; the foreground bar remains the data.
    fig.add_trace(go.Bar(
        x=values.values, y=values.index, orientation="h",
        marker=dict(color="rgba(180,92,255,0.06)", line=dict(color="rgba(180,92,255,0.06)", width=4)),
        name="Revenue glow", hoverinfo="skip", showlegend=False,
    ))
    fig.add_trace(go.Bar(
        x=values.values, y=values.index, orientation="h",
        name="Revenue (EUR)", showlegend=False,
        marker=dict(color=[PALETTE[i % len(PALETTE)] for i in range(len(values))],
                    line=dict(color="rgba(255,255,255,0.8)", width=1)),
        hovertemplate="%{y}<br><b>%{x:,.2f} €</b><extra>Revenue</extra>",
    ))
    chart_layout(fig, max(280, len(values) * 36))
    fig.update_xaxes(ticksuffix=" €", showgrid=True, gridcolor="rgba(151,170,189,0.16)")
    fig.update_yaxes(showgrid=False, categoryorder="array", categoryarray=list(values.index))
    return fig


def comparison_chart(comparison):
    fig = go.Figure()
    for label, color in [("Current revenue (EUR)", "#91adc5"), ("Previous revenue (EUR)", "#c7cbd7")]:
        # Soft translucent underlay creates a restrained platinum glow around each bar.
        fig.add_trace(go.Bar(x=comparison.index, y=comparison[label], name=label + " glow",
                             marker=dict(color="rgba(145,173,197,0.06)", line=dict(color="rgba(145,173,197,0.07)", width=4)),
                             hoverinfo="skip", showlegend=False, offsetgroup=label))
        fig.add_trace(go.Bar(x=comparison.index, y=comparison[label], name=label,
                             marker=dict(color=color, line=dict(color="#ffffff", width=1)),
                             hovertemplate="%{x}<br><b>%{y:,.2f} €</b><extra>" + label + "</extra>", offsetgroup=label))
    chart_layout(fig, 380)
    fig.update_layout(barmode="group")
    fig.update_yaxes(ticksuffix=" €")
    return fig


def show_chart(fig, key):
    st.plotly_chart(fig, theme=None, width="stretch", key=key,
                    config={"displayModeBar": False, "scrollZoom": False, "responsive": True})
