import numpy as np
import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from components import data, ui
from components.theme import ACCENT, ACCENT2, BORDER2, MUTED, NEG, PN_COLORS, WARN, show

data.require("matchups", "bat_zones", "bowl_zones", "wickets")
mu, bz, wz, wk = data.load("matchups"), data.load("bat_zones"), data.load("bowl_zones"), data.load("wickets")
pak = data.pak_ids()

ui.command_bar("Rankings · Match-ups", "Match-Up Analysis",
               "Head-to-head records between batters and bowlers, overall and on pressure balls, plus the deliveries each batter "
               "scores from or falls to under pressure, and what each bowler's plan looks like when the game is tight.",
               ui.default_chips())

bat_names = mu[~mu.striker_id.isin(pak)].groupby(["striker_id", "batter"]).balls.sum().sort_values(ascending=False).reset_index()
bowl_names = mu[~mu.bowler_id.isin(pak)].groupby(["bowler_id", "bowler"]).balls.sum().sort_values(ascending=False).reset_index()
with ui.filter_bar():
    c1, c2 = st.columns(2, gap="small")
    bat = c1.selectbox("Batter", bat_names.batter.tolist(), index=0)
    bat_id = bat_names.loc[bat_names.batter == bat, "striker_id"].iat[0]
    opp = mu[mu.striker_id == bat_id]
    bowl = c2.selectbox("Bowler", ["(all bowlers)"] + opp.sort_values("balls", ascending=False).bowler.tolist(), index=0)


def grouped(z, metric, xlab, top=12):
    """Horizontal grouped bars: the most-faced categories only, so labels stay readable."""
    cats = list(z.groupby("value").balls.sum().sort_values(ascending=False).head(top).index)[::-1]
    fig = go.Figure()
    for p in ["Normal", "Pressure"]:
        x = z[z.pressure == p].set_index("value").reindex(cats)
        fig.add_bar(y=cats, x=x[metric], name=p, orientation="h", marker_color=PN_COLORS[p], customdata=x.balls,
                    hovertemplate="%{y}: %{x:.1f} (%{customdata} balls)<extra>" + p + "</extra>")
    fig.update_layout(barmode="group", bargap=0.28)
    fig.update_xaxes(title=xlab)
    return fig, 60 + 34 * len(cats)


def chart_or_empty(z, metric, xlab):
    if len(z):
        fig, h = grouped(z, metric, xlab)
        show(fig, h)
    else:
        ui.empty()


if bowl != "(all bowlers)":
    r = opp[opp.bowler == bowl].iloc[0]
    ui.kpi_row([
        ("Balls faced", f"{int(r.balls)}", f"{int(r.matches)} matches", ACCENT),
        ("Runs · SR", f"{int(r.runs)} · {r.sr:.0f}", "all balls", ACCENT2),
        ("Dismissals", f"{int(r.outs)}", f"average {r.runs / max(r.outs, 1):.1f}", NEG),
        ("Pressure balls", f"{int(r.p_balls)}", f"SR {r.p_sr:.0f}" if r.p_balls else "none yet", WARN),
        ("Pressure dismissals", f"{int(r.p_outs)}", "", NEG),
    ])
    st.write("")
    if r.balls < 12:
        ui.note("Fewer than 12 balls in this match-up: treat it as anecdotal.")
    w = wk[(wk.dismissed_player_id == bat_id) & (wk.bowler_name == bowl)]
    if len(w):
        with ui.panel("How the dismissals happened", f"{len(w)} dismissals", "01"):
            st.dataframe(w[["match_date", "comp_name", "overid", "delivery_style", "stroke", "dismissal_type",
                            "batter_score_at_dismissal", "bat_pressure"]].rename(columns={
                "match_date": "Date", "comp_name": "Competition", "overid": "Over", "delivery_style": "Delivery",
                "stroke": "Stroke", "dismissal_type": "How out", "batter_score_at_dismissal": "Score", "bat_pressure": "Pressure ball"}),
                hide_index=True, width="stretch")
else:
    x = opp[opp.balls >= 12]
    with ui.panel(f"{bat} against every bowler", "min 12 balls · bubble = balls faced · colour = pressure SR", "01"):
        if x.empty:
            ui.empty("No bowler has bowled 12+ balls to this batter.")
        else:
            fig = go.Figure(go.Scatter(x=x.sr, y=x.outs, mode="markers", text=x.bowler,
                                       marker=dict(size=np.clip(x.balls / 2.5, 7, 40), color=x.p_sr.fillna(x.sr), cmin=60, cmax=220,
                                                   colorscale=[[0, NEG], [0.5, "#334155"], [1, ACCENT]],
                                                   colorbar=dict(title="Press. SR"), line=dict(color="#0B1220", width=1)),
                                       customdata=x[["balls", "p_balls"]],
                                       hovertemplate="<b>%{text}</b><br>SR %{x:.0f} · %{y} outs · %{customdata[0]} balls"
                                                     " (%{customdata[1]} pressure)<extra></extra>"))
            fig.update_xaxes(title="Strike rate vs this bowler")
            fig.update_yaxes(title="Dismissals")
            show(fig, 400, legend=False)
            st.dataframe(x.sort_values("balls", ascending=False)[["bowler", "matches", "balls", "runs", "sr", "outs", "p_balls", "p_runs", "p_sr", "p_outs"]]
                         .rename(columns={"bowler": "Bowler", "matches": "Matches", "balls": "Balls", "runs": "Runs", "sr": "SR",
                                          "outs": "Outs", "p_balls": "Press. balls", "p_runs": "Press. runs", "p_sr": "Press. SR",
                                          "p_outs": "Press. outs"}),
                         hide_index=True, width="stretch", height=280,
                         column_config={"SR": st.column_config.NumberColumn(format="%.0f"),
                                        "Press. SR": st.column_config.NumberColumn(format="%.0f")})

c3, c4 = st.columns(2, gap="medium")
z = bz[(bz.player_id == bat_id) & (bz.dim == "delivery_style") & (bz.balls >= 6)]
with c3:
    with ui.panel(f"{bat}: scoring by delivery", "strike rate · 12 most-faced deliveries", "02"):
        chart_or_empty(z, "sr", "Strike rate")
with c4:
    with ui.panel(f"{bat}: dismissals by delivery", "12 most-faced deliveries", "03"):
        chart_or_empty(z, "outs", "Dismissals")

with ui.filter_bar():
    bsel = st.selectbox("Bowler for plan", bowl_names.bowler.tolist(), index=0, key="plan")
bid = bowl_names.loc[bowl_names.bowler == bsel, "bowler_id"].iat[0]
c5, c6 = st.columns(2, gap="medium")
with c5:
    with ui.panel(f"{bsel}: economy by delivery", "12 most-bowled deliveries", "04"):
        z = wz[(wz.player_id == bid) & (wz.dim == "delivery_style") & (wz.balls >= 6)]
        chart_or_empty(z, "econ", "Economy")
with c6:
    with ui.panel(f"{bsel}: wicket deliveries", "what has taken his wickets", "05"):
        w = wk[(wk.bowler_id == bid) & wk.bowler_wicket]
        if len(w):
            g = w.groupby(["delivery_style", "bowl_pressure"]).size().reset_index(name="n")
            fig = go.Figure()
            for p, nm in [(False, "Normal"), (True, "Pressure")]:
                x = g[g.bowl_pressure == p]
                fig.add_bar(x=x.delivery_style, y=x.n, name=nm, marker_color=PN_COLORS[nm],
                            hovertemplate="%{x}: %{y} wickets<extra>" + nm + "</extra>")
            fig.update_layout(barmode="stack")
            fig.update_xaxes(tickangle=-35, categoryorder="total descending")
            fig.update_yaxes(title="Wickets")
            show(fig, 420)
        else:
            ui.empty("No wickets recorded.")
