"""War Room - Pressure XI Builder: assemble the XI you would trust in a knockout and see its gaps."""
import numpy as np
import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from components import data, ui
from components.theme import arr, ACCENT, ACCENT2, DIVERGING, DIVERGING_REV, NEG, POS, WARN, show

data.require("batter_rankings", "bowler_rankings", "bat_zones", "bowl_zones")
rb, rw = data.load("batter_rankings"), data.load("bowler_rankings")
bz, wz = data.load("bat_zones"), data.load("bowl_zones")

ui.command_bar("War room · Pressure XI", "Build the XI you would trust in a final",
               "Auto-picks the strongest pressure XI from any pool: all eligible players, one franchise, or one national "
               "side. Swap players in and out, then check phase-by-phase coverage and the gaps the model flags.",
               ui.default_chips())

SPIN = ("break", "orthodox", "chinaman", "offbreak")
is_spin = lambda t: any(s in str(t).lower() for s in SPIN)  # noqa: E731

teams = sorted(set(rb.last_team.dropna()) | set(rw.last_team.dropna()))
with ui.filter_bar():
    f = st.columns([2.2, 1, 1, 1.2], gap="small")
    pool = f[0].selectbox("Selection pool", ["All eligible players"] + teams, index=0)
    n_bat = f[1].number_input("Batting slots", 4, 8, 6)
    n_bowl = f[2].number_input("Bowling slots", 3, 7, 5)
    min_spin = f[3].number_input("Min. spinners", 0, 4, 1)

pb = rb if pool.startswith("All") else rb[rb.last_team == pool]
pw = rw if pool.startswith("All") else rw[rw.last_team == pool]
if pb.empty and pw.empty:
    ui.empty("No eligible players in this pool.")
    st.stop()

# ---- auto pick: best batters, then best bowlers (with a spin quota), all-rounders count once
auto_bat = pb.head(int(n_bat)).name.tolist()
spinners = pw[pw.bowling_type.apply(is_spin) & ~pw.name.isin(auto_bat)].head(int(min_spin)).name.tolist()
rest = pw[~pw.name.isin(auto_bat + spinners)].name.tolist()
auto_bowl = spinners + rest[: max(0, int(n_bowl) - len(spinners))]
auto_bowl = pw[pw.name.isin(auto_bowl)].name.tolist()  # keep rank order

k = f"{pool}_{n_bat}_{n_bowl}_{min_spin}"
c1, c2 = st.columns(2, gap="medium")
bats = c1.multiselect("Batters", pb.name.tolist(), default=auto_bat, key=f"xb_{k}")
bowls = c2.multiselect("Bowlers", pw.name.tolist(), default=auto_bowl, key=f"xw_{k}")
xi = list(dict.fromkeys(bats + bowls))

B = pb[pb.name.isin(bats)]
W = pw[pw.name.isin(bowls)]
spin_n = int(W.bowling_type.apply(is_spin).sum())

ui.kpi_row([
    ("Players selected", f"{len(xi)}/11", "all-rounders count once" if len(xi) <= 11 else "over 11: trim the list",
     ACCENT if len(xi) == 11 else (WARN if len(xi) < 11 else NEG)),
    ("Batting unit rating", f"{B.rating.mean():.1f}" if len(B) else "–", f"pool mean {rb.rating.mean():.1f}", ACCENT),
    ("Bowling unit rating", f"{W.rating.mean():.1f}" if len(W) else "–", f"pool mean {rw.rating.mean():.1f}", ACCENT2),
    ("Batting runs above exp.", f"{100 * (B.p_contrib.sum() / max(B.p_balls.sum(), 1)):+.1f}" if len(B) else "–",
     "per 100 pressure balls, unit total", POS),
    ("Bowling runs saved", f"{100 * (W.p_contrib.sum() / max(W.p_balls.sum(), 1)):+.1f}" if len(W) else "–",
     "per 100 pressure balls, unit total", POS),
    ("Pace / spin", f"{len(W) - spin_n} / {spin_n}", f"min. spinners {int(min_spin)}", WARN if spin_n < min_spin else ACCENT2),
])
st.write("")

with ui.panel("The XI", "pressure rating shown for each player's main role", "01"):
    cards = []
    for i, n in enumerate(xi, 1):
        if n in set(B.name) and n in set(W.name):
            rb_r, rw_r = B[B.name == n].iloc[0], W[W.name == n].iloc[0]
            cards.append(dict(role=f"{i:02d} · All-rounder", name=n, sub=f"{rb_r.last_team}",
                              metric=f"BAT {rb_r.rating:.0f} · BOWL {rw_r.rating:.0f}"))
        elif n in set(B.name):
            r = B[B.name == n].iloc[0]
            cards.append(dict(role=f"{i:02d} · Batter", name=n, sub=f"{r.last_team} · SR {r.p_sr:.0f} under pressure",
                              metric=f"{r.rating:.1f}  #{int(r['rank'])}"))
        else:
            r = W[W.name == n].iloc[0]
            cards.append(dict(role=f"{i:02d} · {'Spinner' if is_spin(r.bowling_type) else 'Seamer'}", name=n,
                              sub=f"{r.last_team} · econ {r.p_econ:.2f} under pressure", metric=f"{r.rating:.1f}  #{int(r['rank'])}"))
    ui.xi_cards(cards)

c3, c4 = st.columns(2, gap="medium")
with c3:
    with ui.panel("Batting coverage by phase", "pressure strike rate · green = above pool median for that phase", "02"):
        z = bz[(bz.dim == "phase") & (bz.pressure == "Pressure")]
        med = z[z.player_id.isin(rb.player_id)].groupby("value").apply(lambda x: 100 * x.runs.sum() / x.balls.sum(), include_groups=False)
        x = z[z.player_id.isin(B.player_id)].merge(B[["player_id", "name"]], on="player_id")
        x = x[x.balls >= 6]
        if x.empty:
            ui.empty("Select batters to see coverage.")
        else:
            m = x.pivot_table(index="name", columns="value", values="sr").reindex(columns=["Powerplay", "Middle", "Death"])
            m = m.reindex([n for n in bats if n in m.index])
            rel = m - med.reindex(m.columns).values
            fig = go.Figure(go.Heatmap(z=arr(rel), x=m.columns, y=m.index, text=m.round(0).astype("float64").map(lambda v: "" if pd.isna(v) else f"{v:.0f}").values, texttemplate="%{text}", textfont=dict(color="#F1F5F9"),
                                       colorscale=DIVERGING, zmid=0, zmin=-60, zmax=60, showscale=False,
                                       hovertemplate="%{y} · %{x}: SR %{text}<extra></extra>"))
            fig.update_yaxes(autorange="reversed")
            show(fig, 60 + 34 * len(m), legend=False)
            gaps = [ph for ph in m.columns if (rel[ph] > 0).sum() < 2]
            if gaps:
                ui.feed([("risk", f"Fewer than two batters above the pool median in: <b>{', '.join(gaps)}</b>.")])
with c4:
    with ui.panel("Bowling coverage by phase", "pressure economy · green = below pool median for that phase", "03"):
        z = wz[(wz.dim == "phase") & (wz.pressure == "Pressure")]
        med = z[z.player_id.isin(rw.player_id)].groupby("value").apply(lambda x: 6 * x.runs.sum() / x.balls.sum(), include_groups=False)
        x = z[z.player_id.isin(W.player_id)].merge(W[["player_id", "name"]], on="player_id")
        x = x[x.balls >= 6]
        if x.empty:
            ui.empty("Select bowlers to see coverage.")
        else:
            m = x.pivot_table(index="name", columns="value", values="econ").reindex(columns=["Powerplay", "Middle", "Death"])
            m = m.reindex([n for n in bowls if n in m.index])
            rel = m - med.reindex(m.columns).values
            fig = go.Figure(go.Heatmap(z=arr(rel), x=m.columns, y=m.index, text=m.astype("float64").map(lambda v: "" if pd.isna(v) else f"{v:.2f}").values, texttemplate="%{text}", textfont=dict(color="#F1F5F9"),
                                       colorscale=DIVERGING_REV, zmid=0, zmin=-3, zmax=3, showscale=False,
                                       hovertemplate="%{y} · %{x}: econ %{text}<extra></extra>"))
            fig.update_yaxes(autorange="reversed")
            show(fig, 60 + 34 * len(m), legend=False)
            gaps = [ph for ph in m.columns if (rel[ph] < 0).sum() < 2]
            if gaps:
                ui.feed([("risk", f"Fewer than two bowlers below the pool median economy in: <b>{', '.join(gaps)}</b>.")])

with ui.panel("Unit profile vs pool", "component scores averaged across the selected unit (0–100, 50 = pool average)", "04"):
    comps = ["consistency", "contribution", "delta", "wpa", "standout", "knockout"]
    labs = ["Consistency", "Contribution", "Delta vs baseline", "Win prob. added", "Team standout", "Knockout"]
    fig = go.Figure()
    for df, nm, col in [(B, "Batting unit", ACCENT), (W, "Bowling unit", ACCENT2)]:
        if len(df):
            v = [df[f"score_{c}"].mean() for c in comps]
            fig.add_scatterpolar(r=v + v[:1], theta=labs + labs[:1], name=nm, line=dict(color=col, width=2), fill="toself", opacity=0.35)
    fig.update_layout(polar=dict(radialaxis=dict(range=[0, 100])))
    show(fig, 400)

ui.foot("Auto-pick: top batters by pressure rating, then the minimum number of spinners, then the best remaining bowlers. "
        "A player chosen in both lists counts once (all-rounder). Pool = latest team in the data.")
