"""War Room - Command Centre: the one screen a selector opens first."""
import numpy as np
import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from components import data, ui
from components.theme import ACCENT, ACCENT2, BORDER2, FAINT, MUTED, NEG, POS, REL_COLORS, WARN, show

data.require("batter_rankings", "bowler_rankings", "balls_light", "sensitivity")
rb, rw = data.load("batter_rankings"), data.load("bowler_rankings")
S = data.summary()
sens = data.load("sensitivity")
c = S.get("counts", {})
od = S.get("pressure_validation", {}).get("outcome_discrimination", {})

ui.command_bar("War room · Command centre", "Who do we trust when it matters?",
               "One screen for the selection meeting: current pressure leaderboards, who is rising or fading, where each "
               "player sits on the clutch matrix, and the signals the model wants you to see.", ui.default_chips())

ui.kpi_row([
    ("Rated batters", f"{len(rb)}", "active 2026 · min. sample", ACCENT),
    ("Rated bowlers", f"{len(rw)}", "active 2026 · min. sample", ACCENT2),
    ("Pressure balls", f"{S.get('pressure_share', {}).get('bat_pressure_balls', 0):.0%}",
     "index ≥ 67 or knockout match", WARN),
    ("Holdout accuracy", f"{od.get('pressure_index', {}).get('holdout_accuracy', 0):.0%}",
     f"chase result · RRR alone {od.get('rrr_at_over_11', {}).get('holdout_accuracy', 0):.0%}", POS),
    ("Ranking stability", f"{sens.bat_top10_overlap.median():.0f}/10 · {sens.bowl_top10_overlap.median():.0f}/10",
     f"top-10 overlap · {len(sens)} scenarios", ACCENT2),
    ("High-reliability", f"{(rb.head(10).reliability == 'High').sum() + (rw.head(10).reliability == 'High').sum()}/20",
     "top-10 players labelled High", ACCENT),
])
st.write("")

c1, c2 = st.columns(2, gap="medium")
with c1:
    with ui.panel("Selection board · Batters", "SR P/N = pressure / normal · form = 2025–26 vs career · P10 = top-10 in resamples · dot = reliability", "01"):
        ui.selection_board(rb, "bat")
with c2:
    with ui.panel("Selection board · Bowlers", "Econ P/N = pressure / normal · form = 2025–26 vs career · P10 = top-10 in resamples · dot = reliability", "02"):
        ui.selection_board(rw, "bowl")

c3, c4 = st.columns([7, 5], gap="medium")
with c3:
    with ui.panel("Clutch matrix", "consistency (how often) × contribution vs expected (how much)", "03"):
        role = st.segmented_control("Role", ["Batters", "Bowlers"], default="Batters", key="cm_role",
                                    label_visibility="collapsed")
        df = rb if role != "Bowlers" else rw
        x, y = df.score_consistency, df.score_contribution
        fig = go.Figure()
        for (x0, x1, y0, y1, lab, col) in [(50, 100, 50, 100, "ELITE CLOSERS", POS), (0, 50, 50, 100, "IMPACT, NOT REPEATABLE", WARN),
                                           (50, 100, 0, 50, "RELIABLE, LOW CEILING", ACCENT2), (0, 50, 0, 50, "WATCH LIST", NEG)]:
            fig.add_shape(type="rect", x0=x0, x1=x1, y0=y0, y1=y1, line_width=0, fillcolor=col, opacity=0.035, layer="below")
            fig.add_annotation(x=(x0 + x1) / 2, y=(y0 + y1) / 2, text=lab, showarrow=False,
                               font=dict(size=15, color=col), opacity=0.28)
        fig.add_hline(y=50, line=dict(color=BORDER2, width=1, dash="dot"))
        fig.add_vline(x=50, line=dict(color=BORDER2, width=1, dash="dot"))
        top = df["rank"] <= 10
        fig.add_scatter(x=x[~top], y=y[~top], mode="markers", name="Rest of pool",
                        marker=dict(size=7, color="#3B5574", line=dict(width=0)), text=df.name[~top],
                        customdata=df.loc[~top, ["rank", "rating"]],
                        hovertemplate="<b>%{text}</b> #%{customdata[0]} · rating %{customdata[1]:.1f}<br>"
                                      "consistency %{x:.0f} · contribution %{y:.0f}<extra></extra>")
        fig.add_scatter(x=x[top], y=y[top], mode="markers", name="Top 10", text=df.name[top],
                        marker=dict(size=11, color=ACCENT, line=dict(color="#0B1220", width=1.5)),
                        customdata=df.loc[top, ["rank", "rating"]],
                        hovertemplate="<b>%{text}</b> #%{customdata[0]} · rating %{customdata[1]:.1f}<br>"
                                      "consistency %{x:.0f} · contribution %{y:.0f}<extra></extra>")
        t3 = df[df["rank"] <= 3]
        for _, r in t3.iterrows():
            fig.add_annotation(x=r.score_consistency, y=r.score_contribution, text=f"#{int(r['rank'])} {r['name']}",
                               showarrow=True, arrowhead=0, arrowcolor="#64748B", ax=-60, ay=28 + 22 * (int(r["rank"]) - 1),
                               font=dict(size=10, color="#E2E8F0"), bgcolor="rgba(11,18,32,.85)", borderpad=3)
        fig.update_xaxes(range=[0, 101], title="Consistency score (0–100)")
        fig.update_yaxes(range=[0, 104], title="Contribution vs expected (0–100)")
        show(fig, 470)

with c4:
    with ui.panel("Intel feed", "auto-generated from the model outputs", "04"):
        items = []
        b1, w1 = rb.iloc[0], rw.iloc[0]
        items.append(("sig", f"<b>{b1['name']}</b> tops the batters: 20+ pressure runs in {b1.impact_rate:.0%} of "
                             f"{b1.n_pinn:.0f} pressure innings, SR {b1.p_sr:.0f} vs {b1.n_sr:.0f} normally."))
        items.append(("sig", f"<b>{w1['name']}</b> tops the bowlers: a pressure wicket in {w1.wicket_rate:.0%} of "
                             f"{w1.n_pspells:.0f} spells, P(top 10) {w1.p_top10:.0%}."))
        eco = rw.nsmallest(1, "p_econ").iloc[0]
        items.append(("info", f"Cheapest under pressure: <b>{eco['name']}</b> at {eco.p_econ:.2f} rpo "
                              f"({eco.p_overs:.0f} pressure overs)."))
        rise = rb[rb.form_p_balls >= 60].assign(d=lambda d: d.form_pc_per_ball - d.pc_per_ball).nlargest(1, "d")
        if len(rise):
            r = rise.iloc[0]
            items.append(("sig", f"Biggest riser (batters): <b>{r['name']}</b> improved from {100 * r.pc_per_ball:+.0f} (career) to "
                                 f"{100 * r.form_pc_per_ball:+.0f} (2025–26) runs above expected per 100 pressure balls."))
        fall = rw[rw.form_p_balls >= 60].assign(d=lambda d: d.form_pc_per_ball - d.pc_per_ball).nsmallest(1, "d")
        if len(fall):
            r = fall.iloc[0]
            items.append(("risk", f"Biggest faller (bowlers): <b>{r['name']}</b> dropped from {100 * r.pc_per_ball:+.0f} (career) to "
                                  f"{100 * r.form_pc_per_ball:+.0f} (2025–26) runs saved per 100 pressure balls."))
        fragile = pd.concat([rb.head(10).assign(k="batter"), rw.head(10).assign(k="bowler")])
        fragile = fragile[fragile.reliability != "High"].nsmallest(1, "p_top10")
        if len(fragile):
            r = fragile.iloc[0]
            items.append(("watch", f"Least certain top-10 pick: <b>{r['name']}</b> ({r.k}), in the top 10 in only "
                                   f"{r.p_top10:.0%} of resamples; scenario rank range {r.scen_rank_best:.0f}–{r.scen_rank_worst:.0f}."))
        ko = rb[rb.ko_innings >= 4].nlargest(1, "score_knockout")
        if len(ko):
            r = ko.iloc[0]
            items.append(("info", f"Big-match batter: <b>{r['name']}</b>, knockout score {r.score_knockout:.0f} over "
                                  f"{r.ko_innings:.0f} knockout innings."))
        ui.feed(items)

c5, c6 = st.columns([7, 5], gap="medium")
with c5:
    with ui.panel("Form movers", "pressure contribution per 100 balls · career (○) → 2025–26 (●) · min 60 recent pressure balls", "05"):
        role2 = st.segmented_control("Role ", ["Batters", "Bowlers"], default="Batters", key="fm_role",
                                     label_visibility="collapsed")
        df = (rb if role2 != "Bowlers" else rw)
        df = df[df.form_p_balls >= 60].assign(d=lambda d: 100 * (d.form_pc_per_ball - d.pc_per_ball))
        mv = pd.concat([df.nlargest(7, "d"), df.nsmallest(7, "d")]).drop_duplicates("player_id").sort_values("d")
        fig = go.Figure()
        for _, r in mv.iterrows():
            col = POS if r.d > 0 else NEG
            fig.add_shape(type="line", x0=100 * r.pc_per_ball, x1=100 * r.form_pc_per_ball, y0=r["name"], y1=r["name"],
                          line=dict(color=col, width=3))
        fig.add_scatter(x=100 * mv.pc_per_ball, y=mv.name, mode="markers", name="Career",
                        marker=dict(size=9, color="#0B1220", line=dict(color=MUTED, width=2)),
                        hovertemplate="%{y}: career %{x:+.1f}<extra></extra>")
        fig.add_scatter(x=100 * mv.form_pc_per_ball, y=mv.name, mode="markers", name="2025–26",
                        marker=dict(size=10, color=[POS if v > 0 else NEG for v in mv.d]),
                        hovertemplate="%{y}: 2025–26 %{x:+.1f}<extra></extra>")
        fig.add_vline(x=0, line=dict(color=BORDER2, width=1))
        fig.update_xaxes(title="Runs above expected per 100 pressure balls" if role2 != "Bowlers" else "Runs saved per 100 pressure balls")
        show(fig, 430)
with c6:
    with ui.panel("Pressure pulse", "all batters · SR on pressure vs other balls", "06"):
        bl = data.load("balls_light")
        f = bl[bl.faced]
        g = f.groupby(["year", f.bat_pi >= 67]).agg(sr=("runs", "mean"), out=("striker_out", "mean")).reset_index()
        g.columns = ["year", "pressure", "sr", "out"]
        fig = go.Figure()
        for p, col, nm in [(True, ACCENT, "Pressure balls"), (False, ACCENT2, "Other balls")]:
            x = g[g.pressure == p]
            fig.add_scatter(x=x.year, y=100 * x.sr, name=nm, mode="lines+markers", line=dict(color=col, width=2.5),
                            marker=dict(size=8), customdata=100 * x.out,
                            hovertemplate="%{x}: SR %{y:.0f} · dismissal %{customdata:.1f}% per ball<extra>" + nm + "</extra>")
        fig.update_xaxes(dtick=1, title=None)
        fig.update_yaxes(title="Strike rate")
        show(fig, 430)
ui.foot("Form = runs above expected (batters) or runs saved incl. wicket value (bowlers) per 100 pressure balls, 2025–26 vs whole career. "
        "Clutch matrix axes are the 0–100 component scores used in the rating.")
