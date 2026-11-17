import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

from components import data, ui
from components.theme import ACCENT, ACCENT2, LEVEL_COLORS, LEVEL_ORDER, MUTED, VIOLET, WARN, show

data.require("balls_light", "batter_rankings", "bowler_rankings")
balls = data.load("balls_light")
rb, rw = data.load("batter_rankings"), data.load("bowler_rankings")
S = data.summary()

ui.command_bar("Analytics · Overview", "The pressure landscape",
               "Every IPL and T20I delivery since 2022, scored for pressure on both sides. Each player is measured against "
               "<b>his own baseline</b>, against <b>comparable players in the same state</b>, and on how <b>consistently</b> he delivers.",
               ui.default_chips())

with ui.filter_bar():
    f1, f2, f3 = st.columns([2, 2, 3], gap="medium")
    comps = sorted(balls.comp_type.unique())
    comp = f1.multiselect("Competition", comps, default=comps)
    years = sorted(balls.year.unique())
    yr = f2.select_slider("Season", options=years, value=(years[0], years[-1]))
    f3.markdown(f"<div class='note' style='margin-top:22px'>{balls.comp_name.nunique()} competitions · filters change the charts, "
                "not the precomputed ratings.</div>", unsafe_allow_html=True)
v = balls[balls.comp_type.isin(comp) & balls.year.between(*yr)]
if v.empty:
    ui.empty()
    st.stop()

players = pd.unique(pd.concat([v.striker_id, v.bowler_id])).size
hp = (v.bat_pressure_ball | v.bowl_pressure_ball).mean()
ui.kpi_row([
    ("Matches analysed", f"{v.match_id.nunique():,}", "after cleaning & validation", ACCENT),
    ("Players analysed", f"{players:,}", "batters and bowlers", ACCENT2),
    ("Deliveries", f"{len(v):,}", "ball-by-ball match states", ACCENT),
    ("High-pressure balls", f"{hp:.0%}", "either side ≥ 67 or knockout", WARN),
    ("Eligible batters", f"{len(rb)}", "active 2026 · min. sample", ACCENT2),
    ("Eligible bowlers", f"{len(rw)}", "active 2026 · min. sample", ACCENT2),
])
st.write("")

c1, c2 = st.columns(2, gap="medium")
with c1:
    with ui.panel("Pressure situation distribution", "batting index, all deliveries in view", "01"):
        lv = v.bat_level.value_counts().reindex(LEVEL_ORDER).fillna(0).reset_index()
        lv.columns = ["Level", "Balls"]
        fig = go.Figure(go.Bar(x=lv.Level, y=lv.Balls, marker_color=[LEVEL_COLORS[l] for l in lv.Level],
                               text=[f"{x:,.0f}" for x in lv.Balls], textposition="outside", textfont=dict(color=MUTED),
                               hovertemplate="%{x}: %{y:,} balls<extra></extra>"))
        fig.update_yaxes(title="Balls", range=[0, lv.Balls.max() * 1.15])
        show(fig, 320)
with c2:
    with ui.panel("Coverage by competition", "matches per season", "02"):
        cov = v.groupby(["year", "comp_type"]).match_id.nunique().reset_index(name="Matches")
        fig = go.Figure()
        for ct, col in zip(["IPL", "T20I", "T20 (Emerging)"], [ACCENT, ACCENT2, VIOLET]):
            x = cov[cov.comp_type == ct]
            if len(x):
                fig.add_bar(x=x.year, y=x.Matches, name=ct, marker_color=col, hovertemplate="%{x}: %{y} matches<extra>" + ct + "</extra>")
        fig.update_layout(barmode="group")
        fig.update_xaxes(dtick=1)
        show(fig, 320)

c3, c4 = st.columns(2, gap="medium")
with c3:
    with ui.panel("Where pressure lives", "share of balls in the top tercile, by innings and phase", "03"):
        ph = v.groupby(["innings", "phase"]).agg(bat=("bat_pressure_ball", "mean"), bowl=("bowl_pressure_ball", "mean")).reset_index()
        ph["Stage"] = ph.innings.map({1: "1st", 2: "2nd"}) + " · " + ph.phase
        order = [f"{i} · {p}" for i in ("1st", "2nd") for p in ("Powerplay", "Middle", "Death")]
        ph = ph.set_index("Stage").reindex(order).reset_index()
        fig = go.Figure()
        fig.add_bar(x=ph.Stage, y=ph.bat, name="Batting pressure", marker_color=ACCENT,
                    hovertemplate="%{x}: %{y:.0%}<extra>Batting</extra>")
        fig.add_bar(x=ph.Stage, y=ph.bowl, name="Bowling pressure", marker_color=ACCENT2,
                    hovertemplate="%{x}: %{y:.0%}<extra>Bowling</extra>")
        fig.update_layout(barmode="group")
        fig.update_yaxes(tickformat=".0%")
        show(fig, 330)
with c4:
    with ui.panel("What pressure does to batters", "dismissal % and strike rate per pressure level", "04"):
        fac = v[v.faced]
        lvl = fac.groupby("bat_level").agg(sr=("runs", "mean"), out=("striker_out", "mean")).reindex(LEVEL_ORDER).reset_index()
        fig = go.Figure(go.Bar(x=lvl.bat_level, y=100 * lvl.out, marker_color=[LEVEL_COLORS[l] for l in lvl.bat_level],
                               text=[f"SR {100 * s:.0f}" for s in lvl.sr], textposition="outside", textfont=dict(color=MUTED),
                               hovertemplate="%{x}: out on %{y:.2f}% of balls<extra></extra>"))
        fig.update_yaxes(title="Dismissal % per ball", range=[0, 100 * lvl.out.max() * 1.25])
        show(fig, 330)

c5, c6 = st.columns(2, gap="medium")
for col, r, lab, colr, ix in [(c5, rb, "Batters", ACCENT, "05"), (c6, rw, "Bowlers", ACCENT2, "06")]:
    with col:
        with ui.panel(f"Top 10 {lab.lower()} under pressure", "rating with 90% bootstrap interval", ix):
            t = r.head(10).iloc[::-1]
            fig = go.Figure(go.Scatter(x=t.rating, y=t.name, mode="markers", marker=dict(size=11, color=colr),
                                       error_x=dict(type="data", symmetric=False, array=t.rating_hi - t.rating,
                                                    arrayminus=t.rating - t.rating_lo, color=MUTED, thickness=1.4, width=0),
                                       customdata=t[["last_team", "p_top10"]],
                                       hovertemplate="<b>%{y}</b> · %{customdata[0]}<br>rating %{x:.1f} · P(top 10) %{customdata[1]:.0%}<extra></extra>"))
            fig.update_xaxes(range=[40, 100], title="Pressure rating")
            show(fig, 380, legend=False)

with ui.panel("Key analytical insights", "computed from the pipeline outputs", "07"):
    vb = data.load("validation_by_level")
    items = []
    if len(vb):
        h = vb[(vb.split == "holdout") & (vb["index"] == "Batting")].set_index("level")
        items.append(("info", f"On the 2025–26 holdout, batters are out on <b>{h.loc['Extreme', 'dismissal_pct']:.1f}%</b> of extreme-pressure "
                              f"balls vs <b>{h.loc['Low', 'dismissal_pct']:.1f}%</b> at low pressure; SR falls from "
                              f"<b>{h.loc['Low', 'strike_rate']:.0f}</b> to <b>{h.loc['Extreme', 'strike_rate']:.0f}</b>."))
    od = S.get("pressure_validation", {}).get("outcome_discrimination", {})
    if od:
        items.append(("sig", f"Mean chase pressure in overs 11–20 calls <b>{od['pressure_index']['holdout_accuracy']:.0%}</b> of holdout "
                             f"chases correctly vs <b>{od['rrr_at_over_11']['holdout_accuracy']:.0%}</b> for the required rate alone."))
    sens = data.load("sensitivity")
    if len(sens):
        items.append(("info", f"Across {len(sens)} sensitivity scenarios the median top-10 overlap is "
                              f"<b>{sens.bat_top10_overlap.median():.0f}/10</b> (batters) and <b>{sens.bowl_top10_overlap.median():.0f}/10</b> (bowlers)."))
    ui.feed(items)
