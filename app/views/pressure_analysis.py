import numpy as np
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

from components import data, ui
from components.theme import arr, txt, ACCENT, ACCENT2, LEVEL_COLORS, LEVEL_ORDER, MUTED, SEQ, WARN, show

data.require("balls_light")
balls = data.load("balls_light")

ui.command_bar("Analytics · Pressure engine", "Pressure Analysis",
               "Two indices rebuilt before every delivery: <b>batting pressure</b> (how hard the state is for the batting side) and "
               "<b>bowling pressure</b> (how hard it is for the fielding side). 0–100 percentile; 67+ is the top tercile and counts as a "
               "pressure ball, and every ball of a knockout match counts.", ui.default_chips())

with ui.filter_bar():
    f = st.columns([2.2, 2, 2], gap="medium")
    comps = sorted(balls.comp_type.unique())
    comp = f[0].multiselect("Competition", comps, default=comps)
    years = sorted(balls.year.unique())
    yr = f[1].select_slider("Season", options=years, value=(years[0], years[-1]))
    sit = f[2].selectbox("Match situation", ["All", "Knockout only", "League / bilateral only", "DLS-shortened only"])
    g = st.columns([1.2, 1.6, 3.4], gap="medium")
    idx = g[0].segmented_control("Index", ["Batting", "Bowling"], default="Batting")
    inn = g[1].multiselect("Innings", [1, 2], default=[1, 2], format_func=lambda i: f"Innings {i}")
    lv_sel = g[2].multiselect("Pressure category", LEVEL_ORDER, default=LEVEL_ORDER)
idx = idx or "Batting"
v = balls[balls.comp_type.isin(comp) & balls.year.between(*yr) & balls.innings.isin(inn)]
v = {"Knockout only": v[v.is_knockout], "League / bilateral only": v[~v.is_knockout],
     "DLS-shortened only": v[v.is_dls]}.get(sit, v)
pi, lvl = ("bat_pi", "bat_level") if idx == "Batting" else ("bowl_pi", "bowl_level")
v = v[v[lvl].isin(lv_sel)]
if v.empty:
    ui.empty()
    st.stop()

ui.kpi_row([
    ("Deliveries in view", f"{len(v):,}", f"{v.match_id.nunique():,} matches", ACCENT),
    ("Mean index", f"{v[pi].mean():.1f}", f"{idx.lower()} side · 0–100", ACCENT2),
    ("Pressure balls", f"{(v[pi] >= 67).mean():.0%}", "index ≥ 67", WARN),
    ("Extreme balls", f"{(v[pi] >= 90).mean():.0%}", "index ≥ 90", "#F16C75"),
])
st.write("")

c1, c2 = st.columns(2, gap="medium")
with c1:
    with ui.panel("Index distribution", "coloured by pressure category", "01"):
        fig = go.Figure()
        for L in LEVEL_ORDER:
            x = v[v[lvl] == L]
            if len(x):
                fig.add_histogram(x=x[pi], name=L, marker_color=LEVEL_COLORS[L], xbins=dict(start=0, end=100, size=2),
                                  hovertemplate="%{x}: %{y:,} balls<extra>" + L + "</extra>")
        fig.update_layout(barmode="stack", bargap=0.04)
        fig.update_xaxes(title=f"{idx} pressure index")
        fig.update_yaxes(title="Balls")
        show(fig, 330)
with c2:
    with ui.panel("Batting vs bowling pressure", "the same ball reads differently for each side (Paper 2)", "02"):
        s = v.sample(min(len(v), 5000), random_state=1)
        fig = go.Figure()
        for i, col in [(1, ACCENT), (2, ACCENT2)]:
            x = s[s.innings == i]
            fig.add_scatter(x=x.bat_pi, y=x.bowl_pi, mode="markers", name=f"Innings {i}",
                            marker=dict(size=4, color=col, opacity=0.4),
                            hovertemplate="Bat %{x:.0f} · Bowl %{y:.0f}<extra>Innings " + str(i) + "</extra>")
        fig.update_xaxes(title="Batting pressure", range=[0, 100])
        fig.update_yaxes(title="Bowling pressure", range=[0, 100])
        show(fig, 330)

c3, c4 = st.columns(2, gap="medium")
with c3:
    with ui.panel("Pressure by required run rate", "2nd innings · mean index per RRR band", "03"):
        ch = v[(v.innings == 2) & v.rrr.notna()].copy()
        if len(ch):
            ch["band"] = pd.cut(ch.rrr.clip(0, 24), [0, 6, 8, 10, 12, 14, 18, 24.01],
                                labels=["<6", "6–8", "8–10", "10–12", "12–14", "14–18", "18+"], right=False)
            g = ch.groupby("band", observed=True).agg(bat=("bat_pi", "mean"), bowl=("bowl_pi", "mean"), n=("bat_pi", "size")).reset_index()
            fig = go.Figure()
            fig.add_bar(x=g.band.astype(str), y=g.bat, name="Batting", marker_color=ACCENT, customdata=g.n,
                        hovertemplate="RRR %{x}: %{y:.1f} · %{customdata:,} balls<extra>Batting</extra>")
            fig.add_bar(x=g.band.astype(str), y=g.bowl, name="Bowling", marker_color=ACCENT2,
                        hovertemplate="RRR %{x}: %{y:.1f}<extra>Bowling</extra>")
            fig.update_layout(barmode="group")
            fig.update_xaxes(title="Required run rate")
            fig.update_yaxes(title="Mean index", range=[0, 100])
            show(fig, 330)
        else:
            ui.empty("No second-innings balls in view.")
with c4:
    with ui.panel("Wickets lost × balls remaining", f"mean {idx.lower()} index", "04"):
        h = v.copy()
        h["Balls left"] = pd.cut(h.balls_rem, [0, 12, 24, 36, 60, 90, 121], labels=["1–12", "13–24", "25–36", "37–60", "61–90", "91–120"])
        h["Wkts lost"] = h.wkts_before.clip(upper=8).astype(int).astype(str).replace("8", "8+")
        hm = h.pivot_table(index="Wkts lost", columns="Balls left", values=pi, aggfunc="mean", observed=True)
        fig = go.Figure(go.Heatmap(z=arr(hm), x=hm.columns.astype(str), y=hm.index, colorscale=SEQ, zmin=0, zmax=100,
                                   text=txt(hm, 0), texttemplate="%{text}", textfont=dict(size=10),
                                   colorbar=dict(title="Index"),
                                   hovertemplate="Wickets lost %{y}, balls left %{x}<br>mean index %{z:.1f}<extra></extra>"))
        fig.update_xaxes(title="Balls remaining")
        fig.update_yaxes(title="Wickets lost")
        show(fig, 330, legend=False)

c5, c6 = st.columns(2, gap="medium")
with c5:
    with ui.panel("Pressure through the innings", "median and inter-quartile band by over", "05"):
        g = v.groupby("overid")[pi].quantile([0.25, 0.5, 0.75]).unstack()
        col = ACCENT if idx == "Batting" else ACCENT2
        fig = go.Figure()
        fig.add_scatter(x=g.index, y=g[0.75], mode="lines", line=dict(width=0), showlegend=False, hoverinfo="skip")
        fig.add_scatter(x=g.index, y=g[0.25], mode="lines", line=dict(width=0), fill="tonexty",
                        fillcolor="rgba(184,243,107,.14)" if idx == "Batting" else "rgba(66,216,208,.14)", name="25–75%", hoverinfo="skip")
        fig.add_scatter(x=g.index, y=g[0.5], mode="lines+markers", line=dict(color=col, width=2.5), marker=dict(size=6),
                        name="Median", hovertemplate="Over %{x}: median %{y:.0f}<extra></extra>")
        fig.add_hline(y=67, line=dict(color=WARN, dash="dash", width=1))
        fig.update_xaxes(title="Over", dtick=2)
        fig.update_yaxes(title=f"{idx} index", range=[0, 100])
        show(fig, 330)
with c6:
    with ui.panel("What drives the index", "mean component value (0–1) by pressure category", "06"):
        pref = "bpc_" if idx == "Batting" else "wpc_"
        cols = [c for c in v.columns if c.startswith(pref)]
        m = v.groupby(lvl)[cols].mean().reindex(LEVEL_ORDER).dropna(how="all")
        fig = go.Figure(go.Heatmap(z=arr(m), x=[c.replace(pref, "").title() for c in cols], y=m.index, colorscale=SEQ,
                                   zmin=0, zmax=1, text=txt(m, 2), texttemplate="%{text}", textfont=dict(size=10),
                                   showscale=False, hovertemplate="%{y} · %{x}: %{z:.2f}<extra></extra>"))
        show(fig, 330, legend=False)

with ui.panel("Ball-by-ball pressure trace", "pick a match to watch pressure rise and fall · dashed line = pressure threshold", "07"):
    mm = v.groupby("match_id").agg(t1=("batting_team", "first"), t2=("bowling_team", "first"),
                                   comp=("comp_name", "first"), stage=("stage", "first"), d=("match_date", "first")).reset_index()
    mm = mm.sort_values("d", ascending=False)
    mm["label"] = mm.t1 + " v " + mm.t2 + " — " + mm.comp + " (" + mm.stage + ")"
    pick = st.selectbox("Match", mm.label.tolist(), index=0, label_visibility="collapsed")
    mid = mm.loc[mm.label == pick, "match_id"].iat[0]
    tr = balls[balls.match_id == mid].reset_index(drop=True)
    tr["ball"] = tr.groupby("innings").cumcount() + 1
    fig = go.Figure()
    for i, dash in [(1, "solid"), (2, "dot")]:
        x = tr[tr.innings == i]
        if x.empty:
            continue
        fig.add_scatter(x=x.ball, y=x.bat_pi, name=f"Inns {i} · batting", line=dict(color=ACCENT, width=2, dash=dash),
                        customdata=x[["overid", "over_ball_num", "striker_name", "bowler_name", "wkts_before"]],
                        hovertemplate="Over %{customdata[0]}.%{customdata[1]} · %{customdata[2]} v %{customdata[3]}"
                                      "<br>wkts %{customdata[4]} · batting %{y:.0f}<extra></extra>")
        fig.add_scatter(x=x.ball, y=x.bowl_pi, name=f"Inns {i} · bowling", line=dict(color=ACCENT2, width=2, dash=dash),
                        hovertemplate="bowling %{y:.0f}<extra></extra>")
        w = x[x.striker_out]
        fig.add_scatter(x=w.ball, y=w.bat_pi, mode="markers", name=f"Inns {i} · wicket", showlegend=(i == 1),
                        marker=dict(symbol="x", size=9, color="#F16C75"), hovertemplate="Wicket: %{y:.0f}<extra></extra>")
    fig.add_hline(y=67, line=dict(color=WARN, dash="dash", width=1))
    fig.update_xaxes(title="Delivery in innings")
    fig.update_yaxes(title="Index", range=[0, 101])
    show(fig, 360)
