"""IPL 2027 retention tracker: every franchise's purse, slots, and player status with pressure ratings."""
import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from components import data, ui
from components.theme import ACCENT, ACCENT2, BORDER2, MUTED, NEG, WARN, show
from src import ipl2027_data as D

data.require("ipl2027_status", "batter_rankings", "bowler_rankings")
st_ = data.load("ipl2027_status")
rb, rw = data.load("batter_rankings"), data.load("bowler_rankings")
ab, aw = data.load("batters_all"), data.load("bowlers_all")

ui.command_bar("IPL 2027 Auction · Retention tracker", "Who is retained, who is in the pool",
               "Retention-day status for all ten franchises (17 Nov 2026), joined to the pressure ratings. Disputed reports are "
               "flagged rather than resolved.", [("Status as of <b>17 Nov 2026</b>", "warn"),
                                                 f"Auction <b>{D.AUCTION['date']}</b> · {D.AUCTION['venue']}",
                                                 f"Salary cap <b>₹{D.AUCTION['salary_cap_cr']:.0f} Cr</b>"])

pur = pd.DataFrame([(t, *v) for t, v in D.PURSE.items()], columns=["Team", "Purse", "Slots", "Overseas"]).sort_values("Purse")
ui.kpi_row([
    ("Players retained", f"{(st_.status == 'Retained').sum()}", "named in published lists", ACCENT2),
    ("Players released", f"{(st_.status == 'Released').sum()}", "named in published lists", ACCENT),
    ("Disputed / doubtful", f"{st_.availability.str.contains('disputed|doubtful').sum()}", "flagged, not resolved", WARN),
    ("Open slots", f"{pur.Slots.sum()}", f"{pur.Overseas.sum()} overseas", ACCENT2),
    ("Total purse", f"₹{pur.Purse.sum():.1f} Cr", "across 10 franchises", ACCENT),
])
st.write("")

c1, c2 = st.columns([3, 2], gap="medium")
with c1:
    with ui.panel("Auction purse by franchise", "₹ crore remaining · label = open slots (overseas)", "01"):
        fig = go.Figure(go.Bar(y=pur.Team, x=pur.Purse, orientation="h",
                               marker_color=["#EA1A85" if t == "Rajasthan Royals" else "#3B5574" for t in pur.Team],
                               text=[f"₹{p:.2f} Cr · {s} ({o})" for p, s, o in zip(pur.Purse, pur.Slots, pur.Overseas)],
                               textposition="outside", textfont=dict(color=MUTED, size=11),
                               hovertemplate="%{y}: ₹%{x:.2f} Cr<extra></extra>"))
        fig.update_xaxes(range=[0, pur.Purse.max() * 1.45], title="₹ crore")
        show(fig, 380, legend=False)
with c2:
    with ui.panel("Released players with a pressure rating", "best available by role · rating 0–100", "02"):
        rel = st_[st_.status.eq("Released") & st_.player_id.notna()]
        x = pd.concat([rel.merge(rb[["player_id", "rating"]], on="player_id").assign(role="Bat"),
                       rel.merge(rw[["player_id", "rating"]], on="player_id").assign(role="Bowl")]).sort_values("rating", ascending=False).head(12)
        x = x.iloc[::-1]
        fig = go.Figure(go.Bar(y=x.report_name + " (" + x.role + ")", x=x.rating, orientation="h",
                               marker_color=[ACCENT if r == "Bowl" else ACCENT2 for r in x.role],
                               customdata=x[["team_2026", "availability"]],
                               hovertemplate="%{y}: %{x:.1f}<br>%{customdata[0]} · %{customdata[1]}<extra></extra>"))
        fig.update_xaxes(range=[0, 100], title="Pressure rating")
        show(fig, 380, legend=False)

with ui.panel("Player status", "search, filter, and see each player's pressure rating", "03"):
    with ui.filter_bar():
        f = st.columns([2, 2, 2], gap="small")
        teams = sorted(set(st_.team_2027.dropna()) | set(st_.team_2026.dropna()))
        tsel = f[0].multiselect("Team", teams, default=[])
        ssel = f[1].multiselect("Status", sorted(st_.availability.unique()), default=[])
        q = f[2].text_input("Search", "", placeholder="player name")
    v = st_.merge(rb[["player_id", "rating", "rank"]].rename(columns={"rating": "Bat rating", "rank": "Bat rank"}), on="player_id", how="left") \
           .merge(rw[["player_id", "rating", "rank"]].rename(columns={"rating": "Bowl rating", "rank": "Bowl rank"}), on="player_id", how="left")
    v["Team"] = v.team_2027.fillna(v.team_2026)
    if tsel:
        v = v[v.Team.isin(tsel)]
    if ssel:
        v = v[v.availability.isin(ssel)]
    if q:
        v = v[v.report_name.str.contains(q, case=False, regex=False)]
    v["In data"] = v.player_id.notna()
    if v.empty:
        ui.empty()
    else:
        st.dataframe(v[["report_name", "Team", "availability", "Bat rating", "Bat rank", "Bowl rating", "Bowl rank", "last_contract_cr", "In data", "note"]]
                     .rename(columns={"report_name": "Player", "availability": "Status", "last_contract_cr": "Last contract ₹Cr", "note": "Note"})
                     .sort_values(["Team", "Status", "Player"]),
                     hide_index=True, width="stretch", height=460,
                     column_config={"Bat rating": st.column_config.NumberColumn(format="%.1f"),
                                    "Bowl rating": st.column_config.NumberColumn(format="%.1f"),
                                    "Bat rank": st.column_config.NumberColumn(format="%d"),
                                    "Bowl rank": st.column_config.NumberColumn(format="%d")})
    ui.foot("Some franchises published only their core retained players on deadline day; players not named in any list are not shown. "
            "\"In data\" = the player has deliveries in the supplied ball-by-ball data.")
