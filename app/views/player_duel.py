"""War Room - Player Duel: two candidates for one slot, side by side on every pressure measure."""
import numpy as np
import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from components import data, ui
from components.theme import ACCENT, ACCENT2, BORDER2, LEVEL_ORDER, MUTED, show

data.require("batter_rankings", "bowler_rankings", "balls_light", "batter_innings", "bowler_spells")
rb, rw = data.load("batter_rankings"), data.load("bowler_rankings")

ui.command_bar("War room · Player duel", "Two candidates, one slot",
               "Head-to-head on every pressure measure, scaled against the eligible pool, with the rating components, "
               "pressure-level splits and consistency side by side.", ui.default_chips())

with ui.filter_bar():
    f = st.columns([1, 2, 2], gap="small")
    role = f[0].segmented_control("Role", ["Batters", "Bowlers"], default="Batters", key="duel_role")
    df = rb if role != "Bowlers" else rw
    names = df.name.tolist()
    a = f[1].selectbox("Player A", names, index=0, key=f"duel_a_{role}")
    b = f[2].selectbox("Player B", names, index=1, key=f"duel_b_{role}")
A, B = df[df.name == a].iloc[0], df[df.name == b].iloc[0]
is_bat = role != "Bowlers"
CA, CB = ACCENT, ACCENT2

h1, h2 = st.columns(2, gap="medium")
for col, r, c in [(h1, A, CA), (h2, B, CB)]:
    with col:
        chips = (ui.chip(f"Rank <b>#{int(r['rank'])}</b>", "acc") + ui.chip(f"Reliability <b>{r.reliability}</b>",
                 {"High": "pos", "Medium": "warn"}.get(r.reliability, "neg")) + ui.chip(f"P(top 10) <b>{r.p_top10:.0%}</b>"))
        sample = f"{int(r.n_pinn)} pressure innings · {int(r.p_balls)} balls" if is_bat else \
            f"{int(r.n_pspells)} pressure spells · {r.p_overs:.0f} overs"
        ui.hero(r["name"], f"{r.last_team} · {sample}", f"<span style='color:{c}'>{r.rating:.1f}</span>", "Pressure rating", chips)
st.write("")

if is_bat:
    M = [("Pressure SR", "p_sr", True, "{:.0f}"), ("Impact rate (20+)", "impact_rate", True, "{:.0%}"),
         ("Qualifying rate", "qual_rate", True, "{:.0%}"), ("Runs above exp /100b", "pc_per_ball", True, "{:+.3f}"),
         ("Clutch score", "clutch", True, "{:+.1f}"), ("WPA per pressure inns", "wpa_per_pinn", True, "{:+.1f}"),
         ("Pressure average", "p_avg", True, "{:.1f}"), ("Pressure dot %", "p_dot_pct", False, "{:.0f}%"),
         ("SR delta vs normal", None, True, "{:+.0f}"), ("Knockout innings", "ko_innings", True, "{:.0f}")]
else:
    M = [("Pressure economy", "p_econ", False, "{:.2f}"), ("1+ wicket spells", "wicket_rate", True, "{:.0%}"),
         ("2+ wicket spells", "impact_rate", True, "{:.0%}"), ("Dot-reliable spells", "dot_rate", True, "{:.0%}"),
         ("Runs saved /100b", "pc_per_ball", True, "{:+.3f}"), ("Clutch score", "clutch", True, "{:+.1f}"),
         ("WPA per pressure spell", "wpa_per_pspell", True, "{:+.1f}"), ("Pressure dot %", "p_dot_pct", True, "{:.0f}%"),
         ("Econ delta vs normal", None, True, "{:+.2f}"), ("Knockout matches", "ko_innings", True, "{:.0f}")]


def series(col):
    if col is None:
        return (df.p_sr - df.n_sr) if is_bat else (df.n_econ - df.p_econ)
    return df[col]


rows = []
for lab, col, up, fmt in M:
    s = series(col)
    va, vb = s[df.name == a].iat[0], s[df.name == b].iat[0]
    pa = (s < va).mean() * 100 if up else (s > va).mean() * 100
    pb_ = (s < vb).mean() * 100 if up else (s > vb).mean() * 100
    rows.append((lab, va, vb, pa, pb_, fmt))
T = pd.DataFrame(rows, columns=["m", "va", "vb", "pa", "pb", "fmt"])
wins_a, wins_b = int((T.pa > T.pb).sum()), int((T.pb > T.pa).sum())

c1, c2 = st.columns([7, 5], gap="medium")
with c1:
    with ui.panel("Tale of the tape", "bar = percentile in the eligible pool (better →) · label = raw value", "01"):
        t = T.iloc[::-1]
        fig = go.Figure()
        fig.add_bar(y=t.m, x=-t.pa, orientation="h", name=a, marker_color=CA,
                    text=[f.format(v) for f, v in zip(t.fmt, t.va)], textposition="outside", textfont=dict(color="#E2E8F0", size=11),
                    customdata=t.pa, hovertemplate="%{y}<br>" + a + ": %{text} · pctl %{customdata:.0f}<extra></extra>")
        fig.add_bar(y=t.m, x=t.pb, orientation="h", name=b, marker_color=CB,
                    text=[f.format(v) for f, v in zip(t.fmt, t.vb)], textposition="outside", textfont=dict(color="#E2E8F0", size=11),
                    customdata=t.pb, hovertemplate="%{y}<br>" + b + ": %{text} · pctl %{customdata:.0f}<extra></extra>")
        fig.add_vline(x=0, line=dict(color=BORDER2, width=1))
        fig.update_layout(barmode="overlay", bargap=0.35)
        fig.update_xaxes(range=[-135, 135], tickvals=[-100, -50, 0, 50, 100], ticktext=["100", "50", "0", "50", "100"],
                         title="Pool percentile")
        show(fig, 470)
with c2:
    with ui.panel("Component radar", "the six rating components (0–100)", "02"):
        comps = ["consistency", "contribution", "delta", "wpa", "standout", "knockout"]
        labs = ["Consistency", "Contribution", "Delta", "WPA", "Standout", "Knockout"]
        fig = go.Figure()
        for r, c in [(A, CA), (B, CB)]:
            v = [r[f"score_{k}"] for k in comps]
            fig.add_scatterpolar(r=v + v[:1], theta=labs + labs[:1], name=r["name"], line=dict(color=c, width=2),
                                 fill="toself", opacity=0.35)
        fig.update_layout(polar=dict(radialaxis=dict(range=[0, 100])))
        show(fig, 470)

c3, c4 = st.columns(2, gap="medium")
bl = data.load("balls_light")
with c3:
    with ui.panel("By pressure level", "strike rate (batters) or economy (bowlers) as pressure rises", "03"):
        fig = go.Figure()
        for r, c in [(A, CA), (B, CB)]:
            if is_bat:
                x = bl[(bl.striker_id == r.player_id) & bl.faced].groupby("bat_level").agg(v=("runs", "mean"), n=("runs", "size"))
                y = 100 * x.v.reindex(LEVEL_ORDER)
            else:
                x = bl[(bl.bowler_id == r.player_id) & bl.is_legal].groupby("bowl_level").agg(v=("bowler_runs", "mean"), n=("bowler_runs", "size"))
                y = 6 * x.v.reindex(LEVEL_ORDER)
            fig.add_scatter(x=LEVEL_ORDER, y=y, name=r["name"], mode="lines+markers", line=dict(color=c, width=2.5),
                            marker=dict(size=9), customdata=x.n.reindex(LEVEL_ORDER),
                            hovertemplate="%{x}: %{y:.1f} (%{customdata} balls)<extra>" + r["name"] + "</extra>")
        fig.update_yaxes(title="Strike rate" if is_bat else "Economy")
        show(fig, 340)
with c4:
    with ui.panel("Consistency distribution", "pressure runs per innings (batters) or pressure wickets per spell (bowlers)", "04"):
        fig = go.Figure()
        if is_bat:
            inn = data.load("batter_innings")
            for r, c in [(A, CA), (B, CB)]:
                x = inn[(inn.striker_id == r.player_id) & inn.is_p_innings]
                fig.add_box(y=x.p_runs, name=r["name"], marker_color=c, boxpoints="all", jitter=0.4, pointpos=0,
                            marker=dict(size=5, opacity=0.6), line=dict(width=1.5))
            fig.add_hline(y=20, line=dict(color="#F5B942", dash="dash", width=1))
            fig.update_yaxes(title="Pressure runs in innings")
        else:
            sp = data.load("bowler_spells")
            for r, c in [(A, CA), (B, CB)]:
                x = sp[(sp.bowler_id == r.player_id) & sp.is_p_spell].p_wkts.value_counts().sort_index()
                fig.add_bar(x=x.index, y=100 * x / x.sum(), name=r["name"], marker_color=c,
                            hovertemplate="%{x} wickets: %{y:.0f}% of spells<extra>" + r["name"] + "</extra>")
            fig.update_xaxes(title="Pressure wickets in spell", dtick=1)
            fig.update_yaxes(title="% of pressure spells")
            fig.update_layout(barmode="group")
        show(fig, 340)

with ui.panel("Verdict", "", "05"):
    lead = a if A.rating > B.rating else b
    gap = abs(A.rating - B.rating)
    ui.feed([
        ("sig", f"<b>{lead}</b> leads on the composite rating by {gap:.1f} points. Head-to-head measures: "
                f"{a} {wins_a}, {b} {wins_b}" + (" (split evenly)." if wins_a == wins_b else ".")),
        ("info" if gap > 5 else "watch",
         "The gap is larger than typical ranking noise in this zone." if gap > 5 else
         "The gap is within ranking noise: both players' 90% rating intervals overlap, so pick on role fit and current form."),
        ("info", f"Current form (2025–26 vs career, per 100 pressure balls): {a} {100 * (A.form_pc_per_ball - A.pc_per_ball):+.1f}, "
                 f"{b} {100 * (B.form_pc_per_ball - B.pc_per_ball):+.1f}."),
    ])
