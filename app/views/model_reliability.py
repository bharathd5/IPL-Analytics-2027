import numpy as np
import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from components import data, ui
from components.theme import arr, txt, ACCENT, ACCENT2, LEVEL_ORDER, MUTED, NEG, POS, REL_COLORS, SEQ, WARN, show

data.require("batter_rankings", "bowler_rankings", "sensitivity", "validation_by_level")
rb, rw = data.load("batter_rankings"), data.load("bowler_rankings")
sens, vbl = data.load("sensitivity"), data.load("validation_by_level")
S = data.summary()
wp = S.get("win_probability_model", {})
pv = S.get("pressure_validation", {})
od = pv.get("outcome_discrimination", {})

ui.command_bar("Model · Reliability", "How much can you trust a ranking?",
               "Four checks: (1) does the pressure index separate hard states from easy ones on unseen seasons, (2) how wide is each "
               "player's uncertainty, (3) do rankings survive other weights and definitions, (4) how big are the samples.",
               ui.default_chips())

ui.kpi_row([
    ("Win-prob AUC · chase", f"{wp.get('innings_2', {}).get('auc', np.nan):.3f}", "cross-fitted by match", ACCENT),
    ("Win-prob AUC · 1st inns", f"{wp.get('innings_1', {}).get('auc', np.nan):.3f}", "first innings is less decided", ACCENT2),
    ("Holdout accuracy", f"{od.get('pressure_index', {}).get('holdout_accuracy', np.nan):.0%}",
     f"index · RRR alone {od.get('rrr_at_over_11', {}).get('holdout_accuracy', np.nan):.0%}", POS),
    ("Top-10 overlap", f"{sens.bat_top10_overlap.median():.0f} / {sens.bowl_top10_overlap.median():.0f}",
     f"median bat / bowl · {len(sens)} scenarios", ACCENT2),
    ("Bootstrap draws", f"{S.get('n_bootstrap', '—')}", "innings resampled per player", WARN),
])
st.write("")


def split_bars(d, y, ytitle, colors):
    fig = go.Figure()
    for sp in ["train", "holdout"]:
        x = d[d.split == sp].set_index("level").reindex(LEVEL_ORDER)
        fig.add_bar(x=LEVEL_ORDER, y=x[y], name="Train 2022–24" if sp == "train" else "Holdout 2025–26", marker_color=colors[sp],
                    customdata=x.balls, hovertemplate="%{x}: %{y:.2f} (%{customdata:,} balls)<extra></extra>")
    fig.update_layout(barmode="group")
    fig.update_yaxes(title=ytitle)
    return fig


c1, c2 = st.columns(2, gap="medium")
with c1:
    with ui.panel("Batters get out more as batting pressure rises", "dismissal % per ball by level", "1A"):
        show(split_bars(vbl[vbl["index"] == "Batting"], "dismissal_pct", "Dismissal % per ball", {"train": "#3B5574", "holdout": ACCENT}), 320)
with c2:
    with ui.panel("Each ball matters more as bowling pressure rises", "mean |win-probability swing| per ball", "1B"):
        show(split_bars(vbl[vbl["index"] == "Bowling"], "mean_abs_wp_swing", "Mean |WP swing| (pts)", {"train": "#3B5574", "holdout": ACCENT2}), 320)
c3, c4 = st.columns(2, gap="medium")
with c3:
    with ui.panel("Information beyond RRR", "holdout AUC on chase balls", "1C"):
        inc = pv.get("incremental_auc", {})
        d = pd.DataFrame([{"t": k.replace("_", " "), "a": v["auc_rrr_only"], "b": v["auc_rrr_plus_index"]} for k, v in inc.items()])
        fig = go.Figure()
        fig.add_bar(x=d.t, y=d.a, name="RRR only", marker_color="#3B5574", hovertemplate="%{x}: %{y:.3f}<extra>RRR only</extra>")
        fig.add_bar(x=d.t, y=d.b, name="RRR + pressure index", marker_color=ACCENT, hovertemplate="%{x}: %{y:.3f}<extra>+ index</extra>")
        fig.update_layout(barmode="group")
        fig.update_yaxes(range=[0.4, 0.75], title="AUC")
        show(fig, 320)
with c4:
    with ui.panel("Chase outcome from overs 11–20 pressure", "share of chases classified correctly", "1D"):
        d = pd.DataFrame([{"m": k.replace("_", " "), "tr": v["train_accuracy"], "ho": v["holdout_accuracy"]} for k, v in od.items()])
        fig = go.Figure()
        fig.add_bar(x=d.m, y=d.tr, name="Train", marker_color="#3B5574", hovertemplate="%{x}: %{y:.0%}<extra>Train</extra>")
        fig.add_bar(x=d.m, y=d.ho, name="Holdout", marker_color=ACCENT2, hovertemplate="%{x}: %{y:.0%}<extra>Holdout</extra>")
        fig.update_layout(barmode="group")
        fig.update_yaxes(tickformat=".0%", range=[0.5, 1])
        show(fig, 320)

with ui.filter_bar():
    role = st.segmented_control("Role", ["Batters", "Bowlers"], default="Batters", key="rel_role") or "Batters"
df = rb if role == "Batters" else rw
key = "bat" if role == "Batters" else "bowl"

c5, c6 = st.columns([3, 2], gap="medium")
with c5:
    with ui.panel("Player confidence intervals", "rating with 90% bootstrap interval · top 25 · colour = reliability", "2A"):
        t = df.head(25).iloc[::-1]
        fig = go.Figure(go.Scatter(x=t.rating, y=t.name, mode="markers", marker=dict(size=10, color=[REL_COLORS[r] for r in t.reliability]),
                                   error_x=dict(type="data", symmetric=False, array=t.rating_hi - t.rating, arrayminus=t.rating - t.rating_lo,
                                                color=MUTED, thickness=1.4, width=0),
                                   customdata=t[["rank", "p_top10", "reliability", "rank_lo", "rank_hi"]],
                                   hovertemplate="<b>%{y}</b> #%{customdata[0]}<br>rating %{x:.1f} · P(top 10) %{customdata[1]:.0%}"
                                                 "<br>rank 90%% range %{customdata[3]:.0f}–%{customdata[4]:.0f} · %{customdata[2]}<extra></extra>"))
        fig.update_xaxes(title="Pressure rating", range=[20, 100])
        show(fig, 640, legend=False)
with c6:
    with ui.panel("Uncertainty shrinks with sample", "interval width vs pressure innings / spells", "2B"):
        nn = df.n_pinn if role == "Batters" else df.n_pspells
        fig = go.Figure()
        for rel in ["High", "Medium", "Low"]:
            m = df.reliability == rel
            fig.add_scatter(x=nn[m], y=(df.rating_hi - df.rating_lo)[m], mode="markers", name=rel, text=df.name[m],
                            marker=dict(size=8, color=REL_COLORS[rel], opacity=0.85),
                            hovertemplate="<b>%{text}</b><br>%{x} pressure inns · width %{y:.1f}<extra></extra>")
        fig.update_xaxes(title="Pressure innings / spells")
        fig.update_yaxes(title="90% interval width (pts)")
        show(fig, 300)
    with ui.panel("Reliability labels", "High: P(top10) ≥ 50% and never worse than 15th in any scenario", "2C"):
        cnt = df.reliability.value_counts().reindex(["High", "Medium", "Low"]).fillna(0)
        fig = go.Figure(go.Bar(x=cnt.index, y=cnt.values, marker_color=[REL_COLORS[r] for r in cnt.index], text=cnt.values.astype(int),
                               textposition="outside", hovertemplate="%{x}: %{y} players<extra></extra>"))
        fig.update_yaxes(range=[0, cnt.max() * 1.2], title="Players")
        show(fig, 250, legend=False)

c7, c8 = st.columns([2, 3], gap="medium")
with c7:
    with ui.panel("Ranking sensitivity", "players shared with the base top 10", "3A"):
        fig = go.Figure(go.Bar(y=sens.scenario, x=sens[f"{key}_top10_overlap"], orientation="h",
                               marker_color=[ACCENT if v >= 8 else (WARN if v >= 5 else NEG) for v in sens[f"{key}_top10_overlap"]],
                               customdata=sens[[f"{key}_spearman"]], text=sens[f"{key}_top10_overlap"], textposition="outside",
                               hovertemplate="<b>%{y}</b><br>overlap %{x}/10 · Spearman %{customdata[0]:.3f}<extra></extra>"))
        fig.update_xaxes(range=[0, 11], title="Top-10 overlap")
        fig.update_yaxes(autorange="reversed")
        show(fig, 470, legend=False)
with c8:
    with ui.panel("Rank stability for the top 15", "rank in every scenario · brighter = higher", "3B"):
        sr = data.load("sensitivity_ranks_bat" if key == "bat" else "sensitivity_ranks_bowl")
        top = df.head(15)
        m = sr[sr.player_id.isin(top.player_id)].set_index("player_id").reindex(top.player_id)
        m.index = top.name.values
        m = m[["Base"] + [c for c in m.columns if c != "Base"]]
        fig = go.Figure(go.Heatmap(z=arr(m), x=m.columns, y=m.index, zmin=1, zmax=40,
                                   colorscale=[[0, "#5C8F2A"], [0.3, "#1F5F66"], [1, "#0F1E33"]], text=txt(m, 0),
                                   texttemplate="%{text}", textfont=dict(size=10), showscale=False,
                                   hovertemplate="%{y} · %{x}: rank %{z}<extra></extra>"))
        fig.update_xaxes(tickangle=-35, side="top")
        fig.update_yaxes(autorange="reversed")
        show(fig, 470, legend=False)

with ui.panel("Scenario table", "Spearman rank correlation and each scenario's own top 10", "3C"):
    st.dataframe(sens[["group", "scenario", f"{key}_spearman", f"{key}_top10_overlap", f"{key}_top10",
                       f"eligible_{'batters' if key == 'bat' else 'bowlers'}"]].rename(columns={
        "group": "Group", "scenario": "Scenario", f"{key}_spearman": "Spearman", f"{key}_top10_overlap": "Top-10 overlap",
        f"{key}_top10": "Scenario top 10", f"eligible_{'batters' if key == 'bat' else 'bowlers'}": "Eligible"}),
        hide_index=True, width="stretch", column_config={"Spearman": st.column_config.NumberColumn(format="%.3f")})
