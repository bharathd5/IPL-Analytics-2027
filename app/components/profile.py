"""Player profile building blocks shared by the two explorer pages."""
import numpy as np
import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from . import data, ui
from .theme import (ACCENT, ACCENT2, BORDER2, LEVEL_COLORS, LEVEL_ORDER, MUTED, NEG, PN_COLORS, POS, SLATE, VIOLET, WARN,
                    show)

COMPS = ["consistency", "contribution", "delta", "wpa", "standout", "knockout"]
COMP_LABS = ["Consistency", "Contribution", "Delta vs baseline", "Win prob. added", "Team standout", "Knockout"]


def zone_chart(z, dim, metric, ylab, min_balls=6, order=None, height=300, top=12):
    x = z[(z.dim == dim) & (z.balls >= min_balls)]
    if x.empty:
        ui.empty("Not enough balls for this split.")
        return
    vol = x.groupby("value").balls.sum().sort_values(ascending=False)
    if order is None and len(vol) > 6:
        cats = list(vol.head(top).index)[::-1]          # horizontal: most-faced at the top
        fig = go.Figure()
        for p in ["Normal", "Pressure"]:
            y = x[x.pressure == p].set_index("value").reindex(cats)
            fig.add_bar(y=cats, x=y[metric], name=p, orientation="h", marker_color=PN_COLORS[p], customdata=y.balls,
                        hovertemplate="%{y}: %{x:.1f} (%{customdata} balls)<extra>" + p + "</extra>")
        fig.update_layout(barmode="group", bargap=0.28)
        fig.update_xaxes(title=ylab)
        show(fig, max(height, 60 + 32 * len(cats)))
        return
    cats = order or list(vol.index)
    fig = go.Figure()
    for p in ["Normal", "Pressure"]:
        y = x[x.pressure == p].set_index("value").reindex(cats)
        fig.add_bar(x=cats, y=y[metric], name=p, marker_color=PN_COLORS[p], customdata=y.balls,
                    hovertemplate="%{x}: %{y:.1f} (%{customdata} balls)<extra>" + p + "</extra>")
    fig.update_layout(barmode="group")
    fig.update_yaxes(title=ylab)
    show(fig, height)


def component_bars(r):
    vals = [r[f"score_{c}"] for c in COMPS]
    fig = go.Figure(go.Bar(y=COMP_LABS[::-1], x=vals[::-1], orientation="h",
                           marker_color=[POS if v >= 60 else (WARN if v >= 40 else NEG) for v in vals[::-1]],
                           text=[f"{v:.0f}" for v in vals[::-1]], textposition="outside", textfont=dict(color=MUTED),
                           hovertemplate="%{y}: %{x:.1f}<extra></extra>"))
    fig.add_vline(x=50, line=dict(color=BORDER2, dash="dot", width=1))
    fig.update_xaxes(range=[0, 110], title="Score (50 = pool average)")
    show(fig, 320, legend=False)


def compare_bars(metrics, normal, pressure):
    fig = go.Figure()
    for k, vals in [("Normal", normal), ("Pressure", pressure)]:
        fig.add_bar(x=metrics, y=vals, name=k, marker_color=PN_COLORS[k], hovertemplate="%{x}: %{y:.2f}<extra>" + k + "</extra>")
    fig.update_layout(barmode="group")
    show(fig, 320)


def form_bars(windows, values, ylab):
    fig = go.Figure(go.Bar(x=windows, y=values, marker_color=[SLATE, ACCENT, ACCENT2],
                           text=[f"{v:+.1f}" for v in values], textposition="outside", textfont=dict(color=MUTED),
                           hovertemplate="%{x}: %{y:+.1f}<extra></extra>"))
    fig.add_hline(y=0, line=dict(color=BORDER2, width=1))
    lo, hi = min(0, min(values)), max(0, max(values))
    fig.update_yaxes(title=ylab, range=[lo - abs(hi - lo) * 0.2 - 1, hi + abs(hi - lo) * 0.2 + 1])
    show(fig, 300, legend=False)


# --------------------------------------------------------------- batting
def batting_pressure(pid, r):
    inn = data.load("batter_innings")
    inn = inn[inn.striker_id == pid].sort_values("match_date")
    z = data.load("bat_zones")
    z = z[z.player_id == pid]
    ui.kpi_row([
        ("Pressure innings", f"{int(r.n_pinn)}", f"{int(r.p_balls)} pressure balls", ACCENT2),
        ("Impact rate", f"{r.impact_rate:.0%}", "20+ pressure runs (KO ×1.5)", ACCENT),
        ("Qualifying rate", f"{r.qual_rate:.0%}", "SR 156+ or beat the situation", ACCENT2),
        ("Pressure SR", f"{r.p_sr:.0f}", f"normal {r.n_sr:.0f} · {ui.delta_html(r.p_sr - r.n_sr, '{:+.0f}')}", POS if r.p_sr >= r.n_sr else NEG),
        ("Runs above exp.", f"{r.p_contrib:+.0f}", f"{100 * r.pc_per_ball:+.1f} per 100 pressure balls", POS if r.p_contrib > 0 else NEG),
        ("Rating interval", f"{r.rating_lo:.0f}–{r.rating_hi:.0f}", f"90% bootstrap · P(top 10) {r.p_top10:.0%}", WARN),
    ])
    st.write("")
    c1, c2 = st.columns(2, gap="medium")
    with c1:
        with ui.panel("Normal vs pressure", "own baseline comparison", "01"):
            compare_bars(["Strike rate", "Average", "Dot %", "Boundary %"], [r.n_sr, r.n_avg, r.n_dot_pct, r.n_bnd_pct],
                         [r.p_sr, r.p_avg, r.p_dot_pct, r.p_bnd_pct])
    with c2:
        with ui.panel("Component scores", "0–100 vs eligible pool", "02"):
            component_bars(r)

    with ui.panel("Match-by-match pressure output", "lime = impact innings · teal = qualifying · ★ knockout · dashed = 20 runs", "03"):
        p = inn[inn.is_p_innings].copy()
        if len(p):
            p["label"] = p.match_date.dt.strftime("%d %b %y") + " v " + p.opp
            fig = go.Figure(go.Bar(x=p.label, y=p.p_runs, marker_color=np.where(p.impact, ACCENT, np.where(p.qualifying, ACCENT2, SLATE)),
                                   customdata=np.stack([p.p_balls, p.p_sr.fillna(0), p.comp_name, p.p_out], axis=1),
                                   hovertemplate="%{x}<br>%{y} pressure runs off %{customdata[0]} balls (SR %{customdata[1]:.0f})"
                                                 "<br>%{customdata[2]} · out on pressure ball: %{customdata[3]}<extra></extra>"))
            ko = p[p.is_knockout]
            if len(ko):
                fig.add_scatter(x=ko.label, y=ko.p_runs + 4, mode="markers", marker=dict(symbol="star", size=11, color=WARN), hoverinfo="skip")
            fig.add_hline(y=20, line=dict(color=WARN, dash="dash", width=1))
            fig.update_xaxes(showticklabels=False, title="Pressure innings in date order")
            fig.update_yaxes(title="Pressure runs")
            show(fig, 300, legend=False)
        else:
            ui.empty("No pressure innings.")

    c3, c4, c5 = st.columns(3, gap="medium")
    with c3:
        with ui.panel("Consistency trend", "rolling 8 innings", "04"):
            if len(p) >= 3:
                p["ri"], p["rq"] = p.impact.rolling(8, min_periods=3).mean(), p.qualifying.rolling(8, min_periods=3).mean()
                fig = go.Figure()
                fig.add_scatter(x=p.match_date, y=p.ri, name="Impact", line=dict(color=ACCENT, width=2.2))
                fig.add_scatter(x=p.match_date, y=p.rq, name="Qualifying", line=dict(color=ACCENT2, width=2.2))
                fig.update_yaxes(tickformat=".0%", range=[0, 1])
                show(fig, 280)
            else:
                ui.empty("Too few pressure innings.")
    with c4:
        with ui.panel("By pressure category", "strike rate per level", "05"):
            bl = data.load("balls_light")
            x = bl[(bl.striker_id == pid) & bl.faced].groupby("bat_level").agg(r=("runs", "sum"), n=("runs", "size")).reindex(LEVEL_ORDER).dropna()
            fig = go.Figure(go.Bar(x=x.index, y=100 * x.r / x.n, marker_color=[LEVEL_COLORS[l] for l in x.index], customdata=x.n,
                                   hovertemplate="%{x}: SR %{y:.0f} (%{customdata} balls)<extra></extra>"))
            fig.update_yaxes(title="Strike rate")
            show(fig, 280, legend=False)
    with c5:
        with ui.panel("Career vs current form", "per 100 pressure balls", "06"):
            e, l = inn[inn.year < 2025], inn[inn.year >= 2025]
            form_bars(["2022–24", "2025–26", "Career"],
                      [100 * e.p_contrib.sum() / max(e.p_balls.sum(), 1), 100 * l.p_contrib.sum() / max(l.p_balls.sum(), 1), 100 * r.pc_per_ball],
                      "Runs above expected")

    with ui.panel("Strong zones", "pressure vs normal · Features 1, 2.1 and 3", "07"):
        t1, t2, t3, t4 = st.tabs(["Delivery type", "Pace / spin & line", "Innings & phase", "After quick wickets"])
        with t1:
            zone_chart(z, "delivery_style", "sr", "Strike rate")
        with t2:
            a, b = st.columns(2)
            with a:
                zone_chart(z, "pace_or_spin", "sr", "Strike rate")
            with b:
                zone_chart(z, "line", "sr", "Strike rate")
        with t3:
            a, b = st.columns(2)
            with a:
                zone_chart(z, "innings", "sr", "Strike rate")
            with b:
                zone_chart(z, "phase", "sr", "Strike rate", order=["Powerplay", "Middle", "Death"])
        with t4:
            a, b = st.columns(2)
            with a:
                zone_chart(z, "collapse", "sr", "Strike rate")
            with b:
                zone_chart(z, "delivery_after_collapse", "sr", "Strike rate", min_balls=4)


# --------------------------------------------------------------- bowling
def bowling_pressure(pid, r):
    sp = data.load("bowler_spells")
    sp = sp[sp.bowler_id == pid].sort_values("match_date")
    z = data.load("bowl_zones")
    z = z[z.player_id == pid]
    ui.kpi_row([
        ("Pressure spells", f"{int(r.n_pspells)}", f"{r.p_overs:.0f} pressure overs", ACCENT2),
        ("1+ wicket spells", f"{r.wicket_rate:.0%}", f"2+ wickets: {r.impact_rate:.0%}", ACCENT),
        ("Dot-reliable spells", f"{r.dot_rate:.0%}", "pressure dot% ≥ 45%", ACCENT2),
        ("Pressure economy", f"{r.p_econ:.2f}", f"normal {r.n_econ:.2f} · {ui.delta_html(r.p_econ - r.n_econ, '{:+.2f}', good_up=False)}",
         POS if r.p_econ <= r.n_econ else WARN),
        ("Runs saved vs exp.", f"{r.p_contrib:+.0f}", f"{100 * r.pc_per_ball:+.1f} per 100 pressure balls", POS if r.p_contrib > 0 else NEG),
        ("Rating interval", f"{r.rating_lo:.0f}–{r.rating_hi:.0f}", f"90% bootstrap · P(top 10) {r.p_top10:.0%}", WARN),
    ])
    st.write("")
    c1, c2 = st.columns(2, gap="medium")
    with c1:
        with ui.panel("Normal vs pressure", "own baseline comparison", "01"):
            compare_bars(["Economy", "Dot %", "Balls/wkt ÷10", "Boundary %"],
                         [r.n_econ, r.n_dot_pct, r.n_bowl_sr / 10, 100 * r.n_bnd / max(r.n_balls, 1)],
                         [r.p_econ, r.p_dot_pct, r.p_bowl_sr / 10, r.p_bnd_pct])
    with c2:
        with ui.panel("Component scores", "0–100 vs eligible pool", "02"):
            component_bars(r)

    with ui.panel("Match-by-match pressure spells", "pressure wickets per spell · lime = 2+ wickets", "03"):
        p = sp[sp.is_p_spell].copy()
        if len(p):
            p["label"] = p.match_date.dt.strftime("%d %b %y") + " v " + p.opp
            fig = go.Figure(go.Bar(x=p.label, y=p.p_wkts, marker_color=np.where(p.p_wkts >= 2, ACCENT, np.where(p.p_wkts == 1, ACCENT2, SLATE)),
                                   customdata=np.stack([p.p_balls, p.p_runs, p.comp_name], axis=1),
                                   hovertemplate="%{x}<br>%{y} wkts · %{customdata[1]} runs off %{customdata[0]} pressure balls"
                                                 "<br>%{customdata[2]}<extra></extra>"))
            fig.update_xaxes(showticklabels=False, title="Pressure spells in date order")
            fig.update_yaxes(title="Pressure wickets", dtick=1)
            show(fig, 280, legend=False)
        else:
            ui.empty("No pressure spells.")

    c3, c4, c5 = st.columns(3, gap="medium")
    with c3:
        with ui.panel("Consistency trend", "rolling 8 spells", "04"):
            if len(p) >= 3:
                p["rw"], p["rd"] = p.wicket_spell.rolling(8, min_periods=3).mean(), p.dot_reliable.rolling(8, min_periods=3).mean()
                fig = go.Figure()
                fig.add_scatter(x=p.match_date, y=p.rw, name="1+ wicket", line=dict(color=ACCENT, width=2.2))
                fig.add_scatter(x=p.match_date, y=p.rd, name="Dot-reliable", line=dict(color=ACCENT2, width=2.2))
                fig.update_yaxes(tickformat=".0%", range=[0, 1])
                show(fig, 280)
            else:
                ui.empty("Too few pressure spells.")
    with c4:
        with ui.panel("Career vs current form", "per 100 pressure balls", "05"):
            e, l = sp[sp.year < 2025], sp[sp.year >= 2025]
            form_bars(["2022–24", "2025–26", "Career"],
                      [100 * e.p_contrib.sum() / max(e.p_balls.sum(), 1), 100 * l.p_contrib.sum() / max(l.p_balls.sum(), 1), 100 * r.pc_per_ball],
                      "Runs saved")
    with c5:
        with ui.panel("Bounce-back", "after conceding 12+", "06"):
            if pd.notna(r.get("bounce_overs", np.nan)) and r.get("bounce_overs", 0) > 0:
                ui.kpi("Next-over economy", f"{r.bounce_econ:.2f}", f"{int(r.bounce_overs)} overs · {int(r.bounce_wkts)} wkts · career {r.econ:.2f}",
                       POS if r.bounce_econ <= r.econ else WARN)
                ui.note("Lower than career economy = he recovers after being hit; higher = expensive overs tend to compound.")
            else:
                ui.empty("No expensive overs followed by another over.")

    with ui.panel("Length, line & context under pressure", "Paper 7 features + owner features 1–2", "07"):
        t1, t2, t3, t4 = st.tabs(["Delivery type", "Line & angle", "Batter quality & wickets in hand", "Phase & momentum"])
        with t1:
            a, b = st.columns(2)
            with a:
                zone_chart(z, "delivery_style", "econ", "Economy")
            with b:
                zone_chart(z, "delivery_style", "wkts", "Wickets")
        with t2:
            a, b = st.columns(2)
            with a:
                zone_chart(z, "line", "econ", "Economy")
            with b:
                zone_chart(z, "angle", "econ", "Economy")
        with t3:
            a, b = st.columns(2)
            with a:
                zone_chart(z, "batter_quality", "econ", "Economy", order=["Weaker batter", "Average batter", "Strong batter (top third SR)"])
            with b:
                zone_chart(z, "wickets_in_hand", "econ", "Economy", order=["0-4 in hand", "5-7 in hand", "8-10 in hand"])
        with t4:
            a, b = st.columns(2)
            with a:
                zone_chart(z, "phase", "econ", "Economy", order=["Powerplay", "Middle", "Death"])
            with b:
                zone_chart(z, "momentum", "econ", "Economy")

    wk = data.load("wickets")
    w = wk[(wk.bowler_id == pid) & wk.bowler_wicket]
    if len(w):
        with ui.panel("Wicket clusters", "phase × dismissal type, pressure vs normal (Feature 2)", "08"):
            g = w.groupby(["bowl_pressure", "phase", "dismissal_type"]).size().reset_index(name="n")
            a, b = st.columns(2)
            for col, flag, nm in [(a, False, "Normal"), (b, True, "Pressure")]:
                with col:
                    x = g[g.bowl_pressure == flag]
                    fig = go.Figure()
                    for i, dt in enumerate(sorted(g.dismissal_type.unique())):
                        y = x[x.dismissal_type == dt].set_index("phase").reindex(["Powerplay", "Middle", "Death"])
                        fig.add_bar(x=y.index, y=y.n, name=dt, marker_color=[ACCENT, ACCENT2, WARN, VIOLET, NEG, MUTED][i % 6],
                                    showlegend=(flag is False), hovertemplate="%{x}: %{y}<extra>" + dt + "</extra>")
                    fig.update_layout(barmode="stack")
                    fig.update_yaxes(title=f"{nm} wickets")
                    show(fig, 300, legend=(flag is False))
