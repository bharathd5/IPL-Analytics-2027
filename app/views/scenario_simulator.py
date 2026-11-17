"""War Room - Scenario Simulator: set a live match state, read its pressure, get the best-fit players."""
import numpy as np
import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from components import data, ui
from components.theme import ACCENT, ACCENT2, BORDER2, FAINT, LEVEL_COLORS, MUTED, NEG, POS, TEXT, WARN, show

data.require("balls_light", "batter_rankings", "bowler_rankings")
bl = data.load("balls_light")
rb, rw = data.load("batter_rankings"), data.load("bowler_rankings")

ui.command_bar("War room · Scenario simulator", "What does this moment demand?",
               "Set a match state. The simulator finds every comparable delivery in five seasons of data, reads off the "
               "pressure on each side and the model's win probability, then ranks the eligible players who have "
               "performed best in that exact kind of situation.", ui.default_chips())

PRESETS = {
    "Custom": None,
    "Tight chase: 38 off 18, 5 down": dict(inn="2nd innings (chase)", target=180, score=142, balls=18, wkts=5),
    "Collapse: 3 down in the powerplay": dict(inn="2nd innings (chase)", target=190, score=34, balls=88, wkts=3),
    "Death defend: 12 off 6": dict(inn="2nd innings (chase)", target=170, score=158, balls=6, wkts=6),
    "Set-up innings: 92/1 after 10": dict(inn="1st innings", target=0, score=92, balls=60, wkts=1),
    "Rebuild: 48/4 after 8": dict(inn="1st innings", target=0, score=48, balls=72, wkts=4),
}

with ui.filter_bar():
    f = st.columns([2.2, 1.6, 1, 1, 1, 1, 1.6], gap="small")
    preset = f[0].selectbox("Preset", list(PRESETS), index=1)
    p = PRESETS[preset] or dict(inn="2nd innings (chase)", target=180, score=120, balls=36, wkts=4)
    inn = f[1].selectbox("Innings", ["1st innings", "2nd innings (chase)"],
                         index=0 if p["inn"].startswith("1st") else 1, key=f"inn_{preset}")
    chase = inn.startswith("2nd")
    target = f[2].number_input("Target", 60, 300, int(p["target"] or 180), step=1, disabled=not chase, key=f"t_{preset}")
    score = f[3].number_input("Score", 0, 299, int(p["score"]), step=1, key=f"s_{preset}")
    balls = f[4].number_input("Balls left", 1, 120, int(p["balls"]), step=1, key=f"b_{preset}")
    wkts = f[5].number_input("Wkts down", 0, 9, int(p["wkts"]), step=1, key=f"w_{preset}")
    comp = f[6].selectbox("Competition", ["All", "IPL", "T20I"], index=0)
    teams = sorted(set(rb.last_team.dropna()) | set(rw.last_team.dropna()))
    pool_team = st.selectbox("Selection pool", ["All eligible players"] + teams, index=0,
                             help="Restrict recommendations to one franchise or national side (by the player's latest team).")


# ---------------------------------------------------------- comparable deliveries
over_now = int((120 - balls) // 6) + 1
runs_req = target - score if chase else np.nan
rrr = runs_req * 6 / balls if chase else np.nan
crr = score * 6 / max(120 - balls, 1)
d = bl[(bl.innings == (2 if chase else 1)) & bl.balls_rem.between(balls - 6, balls + 6) & bl.wkts_before.between(wkts - 1, wkts + 1)]
if comp != "All":
    d = d[d.comp_type == comp]
if chase:
    tol = max(6, 0.12 * runs_req)
    d = d[(d.runs_req - runs_req).abs() <= tol]
else:
    est_runs = d.crr * (120 - d.balls_rem) / 6
    d = d[(est_runs - score).abs() <= max(10, 0.12 * score)]

if len(d) < 30:
    ui.empty(f"Only {len(d)} comparable deliveries in the data. Widen the state (e.g. competition = All) for a reliable read.")
    st.stop()

bpi, wpi, wp = d.bat_pi.median(), d.bowl_pi.median(), d.wp_before.mean()
lvl_b = next(n for lo, hi, n in [(0, 34, "Low"), (34, 67, "Moderate"), (67, 90, "High"), (90, 101, "Extreme")] if lo <= bpi < hi)
lvl_w = next(n for lo, hi, n in [(0, 34, "Low"), (34, 67, "Moderate"), (67, 90, "High"), (90, 101, "Extreme")] if lo <= wpi < hi)
phase = "Powerplay" if over_now <= 6 else ("Middle" if over_now <= 15 else "Death")


def gauge(value, title, color, suffix=""):
    fig = go.Figure(go.Indicator(
        mode="gauge+number", value=value, number=dict(suffix=suffix, font=dict(size=34, color=TEXT)),
        title=dict(text=title, font=dict(size=12, color=MUTED)),
        gauge=dict(axis=dict(range=[0, 100], tickcolor=FAINT, tickfont=dict(size=9, color=FAINT), nticks=6),
                   bar=dict(color=color, thickness=0.28), bgcolor="rgba(0,0,0,0)", borderwidth=0,
                   steps=[dict(range=[0, 34], color="rgba(47,74,99,.35)"), dict(range=[34, 67], color="rgba(66,216,208,.12)"),
                          dict(range=[67, 90], color="rgba(245,185,66,.14)"), dict(range=[90, 100], color="rgba(241,108,117,.18)")],
                   threshold=dict(line=dict(color=TEXT, width=2), thickness=0.8, value=67))))
    fig.update_layout(margin=dict(l=30, r=30, t=36, b=0))
    return fig


g1, g2, g3, g4 = st.columns([1, 1, 1, 1.25], gap="medium")
with g1:
    with ui.panel("Batting pressure", lvl_b):
        show(gauge(bpi, "Batting index (0–100)", LEVEL_COLORS[lvl_b]), 190, legend=False)
with g2:
    with ui.panel("Bowling pressure", lvl_w):
        show(gauge(wpi, "Bowling index (0–100)", LEVEL_COLORS[lvl_w]), 190, legend=False)
with g3:
    with ui.panel("Win probability", "batting side"):
        show(gauge(100 * wp, "Batting side wins", ACCENT if wp >= 0.5 else NEG, "%"), 190, legend=False)
with g4:
    with ui.panel("Situation read", f"{len(d):,} balls · {d.match_id.nunique()} matches"):
        rows = [("Phase", f"{phase} (over {over_now})"),
                ("Required rate" if chase else "Current rate", f"{rrr:.2f}" if chase else f"{crr:.2f}"),
                ("Runs needed" if chase else "Score", f"{runs_req:.0f} off {balls}" if chase else f"{score}/{wkts}"),
                ("Wickets in hand", f"{10 - wkts}"),
                ("Historic SR in this state", f"{100 * d[d.faced].runs.mean():.0f}"),
                ("Dismissal per ball", f"{100 * d[d.faced].striker_out.mean():.1f}%")]
        st.markdown("<table class='board'>" + "".join(
            f"<tr><td style='width:auto;text-align:left'><span class='mut'>{a}</span></td><td class='num' style='text-align:right'>{b}</td></tr>"
            for a, b in rows) + "</table>", unsafe_allow_html=True)

# ---------------------------------------------------------- best-fit players
K = 30  # shrinkage prior (balls)
inn_n = 2 if chase else 1
ctx_b = bl[(bl.innings == inn_n) & (bl.phase == phase) & (bl.bat_level == lvl_b) & bl.faced]
ctx_w = bl[(bl.innings == inn_n) & (bl.phase == phase) & (bl.bowl_level == lvl_w) & bl.is_legal]

pool_b = rb if pool_team.startswith("All") else rb[rb.last_team == pool_team]
pool_w = rw if pool_team.startswith("All") else rw[rw.last_team == pool_team]

gb = ctx_b[ctx_b.striker_id.isin(pool_b.player_id)].groupby("striker_id").agg(
    balls=("faced", "size"), runs=("runs", "sum"), outs=("striker_out", "sum"), c=("bat_contrib", "sum")).reset_index()
gb["fit"] = 100 * gb.c / (gb.balls + K)
gb = gb[gb.balls >= 12].merge(pool_b[["player_id", "name", "last_team", "rating", "rank"]], left_on="striker_id", right_on="player_id")
gb["sr"] = 100 * gb.runs / gb.balls
gb["out_pct"] = 100 * gb.outs / gb.balls
gb = gb.sort_values("fit", ascending=False)

gw = ctx_w[ctx_w.bowler_id.isin(pool_w.player_id)].groupby("bowler_id").agg(
    balls=("is_legal", "size"), runs=("bowler_runs", "sum"), wk=("bowler_wicket", "sum"), c=("bowl_contrib", "sum")).reset_index()
gw["fit"] = 100 * gw.c / (gw.balls + K)
gw = gw[gw.balls >= 12].merge(pool_w[["player_id", "name", "last_team", "rating", "rank"]], left_on="bowler_id", right_on="player_id")
gw["econ"] = 6 * gw.runs / gw.balls
gw["wkt_pct"] = 100 * gw.wk / gw.balls
gw = gw.sort_values("fit", ascending=False)


def fit_chart(df, label, xlab):
    t = df.head(10).iloc[::-1]
    fig = go.Figure(go.Bar(x=t.fit, y=t.name, orientation="h",
                           marker_color=[ACCENT if v > 0 else NEG for v in t.fit],
                           customdata=t[["balls", "last_team", "rank", "rating"]],
                           hovertemplate="<b>%{y}</b> · %{customdata[1]}<br>fit %{x:+.1f} " + xlab +
                                         "<br>%{customdata[0]} balls in this context · overall #%{customdata[2]} (%{customdata[3]:.1f})<extra></extra>"))
    fig.add_vline(x=0, line=dict(color=BORDER2, width=1))
    fig.update_xaxes(title=xlab)
    return fig


c1, c2 = st.columns(2, gap="medium")
with c1:
    with ui.panel("Who do we send in?", f"batters · {inn.split(' ')[0]} innings · {phase} · {lvl_b} batting pressure", "A"):
        if gb.empty:
            ui.empty("No eligible batter has 12+ balls in this context.")
        else:
            show(fit_chart(gb, "Batters", "runs above expected / 100 balls (shrunk)"), 380, legend=False)
            st.dataframe(gb.head(10)[["name", "last_team", "balls", "sr", "out_pct", "fit", "rank"]].rename(columns={
                "name": "Batter", "last_team": "Team", "balls": "Balls in context", "sr": "SR", "out_pct": "Out %/ball",
                "fit": "Fit", "rank": "Overall rank"}), hide_index=True, width="stretch", height=260,
                column_config={"SR": st.column_config.NumberColumn(format="%.0f"),
                               "Out %/ball": st.column_config.NumberColumn(format="%.1f"),
                               "Fit": st.column_config.NumberColumn(format="%+.1f")})
with c2:
    with ui.panel("Who bowls the next over?", f"bowlers · {inn.split(' ')[0]} innings · {phase} · {lvl_w} bowling pressure", "B"):
        if gw.empty:
            ui.empty("No eligible bowler has 12+ balls in this context.")
        else:
            show(fit_chart(gw, "Bowlers", "runs saved / 100 balls incl. wickets (shrunk)"), 380, legend=False)
            st.dataframe(gw.head(10)[["name", "last_team", "balls", "econ", "wkt_pct", "fit", "rank"]].rename(columns={
                "name": "Bowler", "last_team": "Team", "balls": "Balls in context", "econ": "Econ", "wkt_pct": "Wkt %/ball",
                "fit": "Fit", "rank": "Overall rank"}), hide_index=True, width="stretch", height=260,
                column_config={"Econ": st.column_config.NumberColumn(format="%.2f"),
                               "Wkt %/ball": st.column_config.NumberColumn(format="%.1f"),
                               "Fit": st.column_config.NumberColumn(format="%+.1f")})

with ui.panel("How comparable situations played out", "win probability across the matched deliveries", "C"):
    s = d.sample(min(len(d), 1500), random_state=3)
    fig = go.Figure(go.Histogram(x=100 * s.wp_before, nbinsx=30, marker_color=ACCENT2, opacity=0.85,
                                 hovertemplate="WP %{x:.0f}%: %{y} balls<extra></extra>"))
    fig.add_vline(x=100 * wp, line=dict(color=ACCENT, width=2), annotation_text=f"mean {100 * wp:.0f}%",
                  annotation_font_color=ACCENT)
    fig.update_xaxes(title="Batting side win probability before the ball (%)", range=[0, 100])
    fig.update_yaxes(title="Deliveries")
    show(fig, 240, legend=False)
ui.foot("Fit = player's runs above expected (batters) or runs saved incl. wicket value (bowlers) on balls from the same innings, "
        "phase and pressure level, shrunk with a 30-ball prior so tiny samples cannot top the list. Comparable deliveries: "
        "±6 balls remaining, ±1 wicket, and ±12% of runs required (chase) or of the score (1st innings).")
