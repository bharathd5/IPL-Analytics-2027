import numpy as np
import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from components import data, ui
from components.theme import arr, txt, ACCENT, ACCENT2, BORDER2, DIVERGING, DIVERGING_REV, MUTED, NEG, POS, SERIES, show

data.require("batter_rankings", "bowler_rankings", "bat_zones", "bowl_zones")
rb, rw = data.load("batter_rankings"), data.load("bowler_rankings")

ui.command_bar("Players · Lab", "Performance Lab",
               "Expected-versus-actual on pressure balls (Paper 5), clutch weighting (Paper 3) and situational deviations for the "
               "eligible pool. Nothing here changes the ratings.", ui.default_chips())

with ui.filter_bar():
    f = st.columns([1.2, 3], gap="medium")
    role = f[0].segmented_control("Role", ["Batting", "Bowling"], default="Batting", key="lab_role") or "Batting"
    topn = f[1].slider("Highlight top N by rating", 5, 30, 10)
is_bat = role == "Batting"
df = rb if is_bat else rw
top = df["rank"] <= topn
REST = "#3B5574"

c1, c2 = st.columns(2, gap="medium")
with c1:
    hint = "above the line = beat comparable batters" if is_bat else "below the line = cheaper than comparable bowlers"
    with ui.panel("Expected vs actual under pressure", hint, "01"):
        fig = go.Figure()
        m = max(df.p_xr.max(), df.p_runs.max()) * 1.05
        fig.add_scatter(x=[0, m], y=[0, m], mode="lines", line=dict(color=BORDER2, dash="dot", width=1), hoverinfo="skip", showlegend=False)
        for sel, nm, col, sz in [(~top, "Rest of pool", REST, 7), (top, f"Top {topn}", ACCENT, 10)]:
            x = df[sel]
            fig.add_scatter(x=x.p_xr, y=x.p_runs, mode="markers", name=nm, text=x.name,
                            marker=dict(size=sz, color=col, line=dict(color="#0B1220", width=1)), customdata=x[["rank", "p_balls"]],
                            hovertemplate="<b>%{text}</b> #%{customdata[0]}<br>expected %{x:.0f} · actual %{y:.0f} · %{customdata[1]} balls<extra></extra>")
        fig.update_xaxes(title="Expected runs (pressure balls)" if is_bat else "Expected runs conceded (pressure balls)")
        fig.update_yaxes(title="Actual runs" if is_bat else "Actual runs conceded")
        show(fig, 400)
with c2:
    with ui.panel("Contribution vs clutch", "rate on pressure balls × difficulty-weighted rate on all balls", "02"):
        fig = go.Figure()
        for sel, nm, col in [(~top, "Rest of pool", REST), (top, f"Top {topn}", ACCENT)]:
            x = df[sel]
            fig.add_scatter(x=100 * x.pc_per_ball, y=x.clutch, mode="markers", name=nm, text=x.name,
                            marker=dict(size=np.clip(x.p_balls / 30, 6, 22), color=col, line=dict(color="#0B1220", width=1)),
                            hovertemplate="<b>%{text}</b><br>contribution %{x:+.1f} · clutch %{y:+.1f}<extra></extra>")
        fig.add_vline(x=0, line=dict(color=BORDER2, width=1, dash="dot"))
        fig.add_hline(y=0, line=dict(color=BORDER2, width=1, dash="dot"))
        fig.update_xaxes(title="Contribution per 100 pressure balls")
        fig.update_yaxes(title="Clutch per 100 balls")
        show(fig, 400)

t = df[top].copy()
with ui.panel("Pressure deviations from own baseline", "cells = pressure minus normal · colour = z-score across these players, green = better under pressure", "03"):
    if is_bat:
        dev = pd.DataFrame({"SR (pts)": t.p_sr - t.n_sr, "Average": t.p_avg - t.n_avg, "Dot % (↓ better)": -(t.p_dot_pct - t.n_dot_pct),
                            "Boundary %": t.p_bnd_pct - t.n_bnd_pct, "Runs above exp /100b": 100 * (t.pc_per_ball - t.nc_per_ball)}).set_index(t.name)
    else:
        dev = pd.DataFrame({"Economy (↓ better)": -(t.p_econ - t.n_econ), "Dot %": t.p_dot_pct - t.n_dot_pct,
                            "Wickets /100b": 100 * (t.p_wpb - t.n_wpb), "Runs saved /100b": 100 * (t.pc_per_ball - t.nc_per_ball)}).set_index(t.name)
    dev = pd.DataFrame(arr(dev), index=dev.index, columns=dev.columns)
    zm = (dev - dev.mean()) / dev.std(ddof=0).replace(0, 1)
    fig = go.Figure(go.Heatmap(z=arr(zm), x=dev.columns, y=dev.index, colorscale=DIVERGING, zmin=-2.5, zmax=2.5, zmid=0,
                               text=txt(dev, 1), texttemplate="%{text}", textfont=dict(size=11), showscale=False,
                               hovertemplate="%{y} · %{x}: %{text}<extra></extra>"))
    fig.update_yaxes(autorange="reversed")
    fig.update_xaxes(side="top")
    show(fig, 70 + 30 * len(t), legend=False)

c3, c4 = st.columns(2, gap="medium")
with c3:
    z = data.load("bat_zones" if is_bat else "bowl_zones")
    dims = ({"Phase": "phase", "Innings": "innings", "Pace / spin": "pace_or_spin", "After quick wickets": "collapse",
             "Knockout vs other": "match_type", "Competition": "competition"} if is_bat else
            {"Phase": "phase", "Innings": "innings", "Batter quality": "batter_quality", "Wickets in hand": "wickets_in_hand",
             "Opposition momentum": "momentum", "Knockout vs other": "match_type", "Competition": "competition"})
    with ui.panel("Situational performance", "pressure balls only · top N", "04"):
        dim = dims[st.selectbox("Dimension", list(dims), label_visibility="collapsed")]
        x = z[(z.dim == dim) & z.player_id.isin(t.player_id) & (z.pressure == "Pressure") & (z.balls >= 6)].merge(t[["player_id", "name"]], on="player_id")
        metric = "sr" if is_bat else "econ"
        if x.empty:
            ui.empty()
        else:
            hm = x.pivot_table(index="name", columns="value", values=metric).reindex(t.name).dropna(how="all")
            fig = go.Figure(go.Heatmap(z=arr(hm), x=hm.columns, y=hm.index, colorscale=DIVERGING if is_bat else DIVERGING_REV,
                                       text=txt(hm, 1), texttemplate="%{text}", textfont=dict(size=11),
                                       colorbar=dict(title="SR" if is_bat else "Econ"),
                                       hovertemplate="%{y} · %{x}: %{z:.1f}<extra></extra>"))
            fig.update_yaxes(autorange="reversed")
            fig.update_xaxes(side="top")
            show(fig, 70 + 30 * len(hm), legend=False)
with c4:
    with ui.panel("Trend by season", "contribution per 100 pressure balls · seasons with <12 pressure balls hidden", "05"):
        sel = st.multiselect("Players", df.name.tolist(), default=df.name.head(4).tolist(), max_selections=6, label_visibility="collapsed")
        if sel:
            ids = df.set_index("name").loc[sel].player_id
            tab = data.load("batter_innings" if is_bat else "bowler_spells")
            key, nm = ("striker_id", "striker_name") if is_bat else ("bowler_id", "bowler_name")
            s = tab[tab[key].isin(ids)].groupby([nm, "year"]).agg(c=("p_contrib", "sum"), n=("p_balls", "sum")).reset_index()
            s = s[s.n >= 12]
            fig = go.Figure()
            for i, p in enumerate(sel):
                x = s[s[nm] == p]
                fig.add_scatter(x=x.year, y=100 * x.c / x.n, name=p, mode="lines+markers", line=dict(color=SERIES[i], width=2.2),
                                marker=dict(size=8), customdata=x.n, hovertemplate="%{x}: %{y:+.1f} (%{customdata} balls)<extra>" + p + "</extra>")
            fig.add_hline(y=0, line=dict(color=BORDER2, width=1, dash="dot"))
            fig.update_xaxes(dtick=1)
            show(fig, 380)
