"""Shared leaderboard page for batters and bowlers."""
import numpy as np
import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from . import data, ui
from .theme import (arr, txt, ACCENT, ACCENT2, BORDER2, DIVERGING, LEVEL_COLORS, LEVEL_ORDER, MUTED, NEG, POS, SERIES, VIOLET,
                    WARN, show)

COMP_LABELS = {"consistency": "Consistency", "contribution": "Contribution", "delta": "Delta vs baseline",
               "wpa": "Win prob. added", "standout": "Team standout", "knockout": "Knockout"}


def render(kind: str):
    is_bat = kind == "bat"
    df = data.load("batter_rankings" if is_bat else "bowler_rankings")
    if df.empty:
        data.require("batter_rankings" if is_bat else "bowler_rankings")
    noun = "Batters" if is_bat else "Bowlers"
    ui.command_bar("Rankings", f"{noun} under pressure",
                   "Composite pressure rating (0–100, 50 = pool average): consistency 35% · contribution vs expected 20% · "
                   "delta vs own baseline 15% · win probability added 15% · team standout 10% · knockout impact 5%. "
                   "Eligible = active in 2026, not a Pakistan player, minimum pressure sample.", ui.default_chips())

    with ui.filter_bar():
        f = st.columns([3, 2, 2, 2], gap="small")
        q = f[0].text_input("Search player or team", "", placeholder="e.g. Klaasen, Mumbai Indians")
        comps = sorted({c.strip() for s in df.comp_types for c in s.split(",")})
        csel = f[1].multiselect("Played in competition", comps, default=comps)
        yrs = sorted({int(y) for s in df.years for y in s.split(",")})
        ysel = f[2].multiselect("Played in season", yrs, default=yrs)
        rel = f[3].multiselect("Reliability", ["High", "Medium", "Low"], default=["High", "Medium", "Low"])
    mask = df.comp_types.apply(lambda s: any(c.strip() in csel for c in s.split(",")))
    mask &= df.years.apply(lambda s: any(int(y) in ysel for y in s.split(",")))
    mask &= df.reliability.isin(rel)
    if q:
        mask &= df.name.str.contains(q, case=False, regex=False) | df.last_team.str.contains(q, case=False, regex=False)
    v = df[mask.astype(bool)]

    # podium
    cols = st.columns(4, gap="small")
    for c, (_, r) in zip(cols[:3], df.head(3).iterrows()):
        with c:
            stat = f"SR {r.p_sr:.0f} vs {r.n_sr:.0f} normally" if is_bat else f"econ {r.p_econ:.2f} vs {r.n_econ:.2f}"
            ui.kpi(f"#{int(r['rank'])} · {r.last_team}", f"{r['name']}",
                   f"<span style='color:{ACCENT};font-weight:700'>{r.rating:.1f}</span> · {stat} · P(top10) {r.p_top10:.0%}",
                   ACCENT if r["rank"] == 1 else ACCENT2)
    with cols[3]:
        ui.kpi("Eligible pool", f"{len(df)}", f"{(df.reliability == 'High').sum()} High · {(df.reliability == 'Medium').sum()} Medium reliability", WARN)
    st.write("")
    if v.empty:
        ui.empty()
        return

    with ui.panel(f"Leaderboard · {len(v)} of {len(df)} eligible {noun.lower()}",
                  "click a header to sort · filters narrow the list; ratings are always full-data values", "01"):
        view = ui.bat_rank_view(v) if is_bat else ui.bowl_rank_view(v)
        stat27 = data.load("ipl2027_status")
        if len(stat27):
            s27 = stat27.dropna(subset=["player_id"]).drop_duplicates("player_id").set_index("player_id")
            lab = np.where(s27.status.eq("Retained"), "Retained · " + s27.team_2027.fillna(""), s27.availability)
            view.insert(3, "IPL 2027", v.player_id.map(pd.Series(lab, index=s27.index)).fillna("Not in published lists").values)
        st.dataframe(view, hide_index=True, width="stretch", height=420, column_config=ui.col_config(view))
        st.download_button("Download leaderboard (CSV)", view.to_csv(index=False).encode(), f"{kind}_pressure_rankings.csv", "text/csv")

    c1, c2 = st.columns(2, gap="medium")
    with c1:
        if is_bat:
            x, y, xl, yl, hint = "n_sr", "p_sr", "Normal strike rate", "Pressure strike rate", "above the diagonal = better under pressure"
        else:
            x, y, xl, yl, hint = "n_econ", "p_econ", "Normal economy", "Pressure economy", "below the diagonal = cheaper under pressure"
        with ui.panel("Normal vs pressure", hint, "02"):
            lo, hi = min(v[x].min(), v[y].min()), max(v[x].max(), v[y].max())
            pad = (hi - lo) * 0.06
            fig = go.Figure()
            fig.add_scatter(x=[lo - pad, hi + pad], y=[lo - pad, hi + pad], mode="lines", line=dict(color=BORDER2, dash="dot", width=1),
                            hoverinfo="skip", showlegend=False)
            fig.add_scatter(x=v[x], y=v[y], mode="markers", showlegend=False,
                            marker=dict(size=9, color=v.rating, colorscale=[[0, "#2C4A66"], [1, ACCENT]], cmin=40, cmax=95,
                                        line=dict(color="#0B1220", width=1), colorbar=dict(title="Rating")),
                            text=v.name, customdata=v[["rank", "last_team"]],
                            hovertemplate="<b>%{text}</b> #%{customdata[0]} · %{customdata[1]}<br>" + xl + " %{x:.2f}<br>" + yl + " %{y:.2f}<extra></extra>")
            fig.update_xaxes(title=xl)
            fig.update_yaxes(title=yl)
            show(fig, 420, legend=False)
    with c2:
        top = v.head(15).iloc[::-1]
        if is_bat:
            with ui.panel("Consistency: how often he delivers", "% of pressure innings · top 15", "03"):
                fig = go.Figure()
                fig.add_bar(y=top.name, x=100 * top.impact_rate, name="Impact (20+ pressure runs)", orientation="h", marker_color=ACCENT,
                            hovertemplate="%{y}: %{x:.0f}%<extra>Impact</extra>")
                fig.add_bar(y=top.name, x=100 * top.qual_rate, name="Qualifying (SR 156+ / beat situation)", orientation="h",
                            marker_color=ACCENT2, hovertemplate="%{y}: %{x:.0f}%<extra>Qualifying</extra>")
                fig.update_layout(barmode="group", bargap=0.3)
                fig.update_xaxes(title="% of pressure innings", range=[0, 100])
                show(fig, 420)
        else:
            with ui.panel("Consistency: wickets and dots", "% of pressure spells · top 15", "03"):
                fig = go.Figure()
                for col, nm, c in [("wicket_rate", "1+ wicket", ACCENT), ("impact_rate", "2+ wickets", VIOLET), ("dot_rate", "Dot-reliable (≥45%)", ACCENT2)]:
                    fig.add_bar(y=top.name, x=100 * top[col], name=nm, orientation="h", marker_color=c,
                                hovertemplate="%{y}: %{x:.0f}%<extra>" + nm + "</extra>")
                fig.update_layout(barmode="group", bargap=0.25)
                fig.update_xaxes(title="% of pressure spells", range=[0, 100])
                show(fig, 420)

    with ui.panel("Rating breakdown", "component scores for the top 15 · 50 = pool average · green above, red below", "04"):
        t = v.head(15)
        m = t.set_index("name")[[f"score_{k}" for k in COMP_LABELS]]
        fig = go.Figure(go.Heatmap(z=arr(m), x=list(COMP_LABELS.values()), y=m.index, colorscale=DIVERGING, zmin=0, zmax=100, zmid=50,
                                   text=txt(m, 0), texttemplate="%{text}", textfont=dict(size=11), showscale=False,
                                   hovertemplate="%{y} · %{x}: %{z:.1f}<extra></extra>"))
        fig.update_yaxes(autorange="reversed")
        fig.update_xaxes(side="top")
        show(fig, 80 + 30 * len(m), legend=False)

    bl = data.load("balls_light")
    ids, order = v.head(10).player_id.tolist(), v.head(10).name.tolist()
    c3, c4 = st.columns(2, gap="medium")
    with c3:
        with ui.panel("By pressure category", ("strike rate" if is_bat else "economy") + " per level · top 10", "05"):
            if is_bat:
                x = bl[bl.striker_id.isin(ids) & bl.faced].groupby(["striker_name", "bat_level"]).runs.agg(["sum", "size"]).reset_index()
                x["v"], nmcol, lvcol = 100 * x["sum"] / x["size"], "striker_name", "bat_level"
            else:
                x = bl[bl.bowler_id.isin(ids) & bl.is_legal].groupby(["bowler_name", "bowl_level"]).bowler_runs.agg(["sum", "size"]).reset_index()
                x["v"], nmcol, lvcol = 6 * x["sum"] / x["size"], "bowler_name", "bowl_level"
            fig = go.Figure()
            for L in LEVEL_ORDER:
                y = x[x[lvcol] == L].set_index(nmcol).reindex(order)
                fig.add_bar(x=order, y=y.v, name=L, marker_color=LEVEL_COLORS[L], customdata=y["size"],
                            hovertemplate="%{x}: %{y:.1f} (%{customdata} balls)<extra>" + L + "</extra>")
            fig.update_layout(barmode="group", bargap=0.2)
            fig.update_xaxes(tickangle=-30)
            fig.update_yaxes(title="Strike rate" if is_bat else "Economy")
            show(fig, 400)
    with c4:
        if is_bat:
            with ui.panel("Consistency across matches", "pressure runs per pressure innings · dashed = 20-run impact line", "06"):
                inn = data.load("batter_innings")
                x = inn[inn.striker_id.isin(ids) & inn.is_p_innings]
                fig = go.Figure()
                for n in order:
                    y = x[x.striker_name == n].p_runs
                    fig.add_box(y=y, name=n, marker_color=ACCENT, boxpoints="all", jitter=0.45, pointpos=0,
                                marker=dict(size=4, opacity=0.55), line=dict(width=1.3), fillcolor="rgba(184,243,107,.10)", showlegend=False)
                fig.add_hline(y=20, line=dict(color=WARN, dash="dash", width=1))
                fig.update_xaxes(tickangle=-30)
                fig.update_yaxes(title="Pressure runs")
                show(fig, 400, legend=False)
        else:
            with ui.panel("Wicket-taking effectiveness", "balls per pressure wicket vs pressure economy · bottom-left is best", "06"):
                fig = go.Figure(go.Scatter(x=v.p_econ, y=v.p_bowl_sr, mode="markers", text=v.name,
                                           marker=dict(size=np.clip(v.p_overs / 4, 6, 24), color=v.rating,
                                                       colorscale=[[0, "#2C4A66"], [1, ACCENT2]], line=dict(color="#0B1220", width=1)),
                                           hovertemplate="<b>%{text}</b><br>econ %{x:.2f} · %{y:.1f} balls per wicket<extra></extra>"))
                fig.update_xaxes(title="Pressure economy")
                fig.update_yaxes(title="Balls per pressure wicket")
                show(fig, 400, legend=False)

    with ui.panel("Quick comparison", "up to four players on the six components · open Player Duel for a full head-to-head", "07"):
        picks = st.multiselect("Players", df.name.tolist(), default=df.name.head(3).tolist(), max_selections=4,
                               label_visibility="collapsed")
        if picks:
            t = df.set_index("name").loc[picks]
            cats = list(COMP_LABELS.values())
            fig = go.Figure()
            for i, (n, r) in enumerate(t.iterrows()):
                vals = [r[f"score_{k}"] for k in COMP_LABELS]
                fig.add_scatterpolar(r=vals + vals[:1], theta=cats + cats[:1], name=f"{n} (#{int(r['rank'])})",
                                     line=dict(color=SERIES[i], width=2), fill="toself", opacity=0.3)
            fig.update_layout(polar=dict(radialaxis=dict(range=[0, 100])))
            show(fig, 440)
