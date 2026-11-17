import numpy as np
import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from components import data, profile, ui
from components.theme import ACCENT, ACCENT2, VIOLET, WARN, show

data.require("batters_all", "bowlers_all", "batter_innings", "bowler_spells", "player_registry")
ab, aw = data.load("batters_all"), data.load("bowlers_all")
bi, bs = data.load("batter_innings"), data.load("bowler_spells")
reg = data.registry()

ui.command_bar("Players · Career", "Overall Player Explorer",
               "Whole-career profiles for every player in the data (2022–2026), including those last seen in 2025 or earlier. "
               "Pressure figures here are descriptive; ranked ratings live on the rankings pages.", ui.default_chips())

ids = pd.Index(pd.unique(pd.concat([ab.player_id, aw.player_id])))
pl = reg.set_index("player_id").reindex(ids)
pl["name"] = pl.player_name.fillna(ab.set_index("player_id").name.reindex(ids)).fillna(aw.set_index("player_id").name.reindex(ids))
pl["vol"] = ab.set_index("player_id").balls.reindex(ids).fillna(0) + aw.set_index("player_id").balls.reindex(ids).fillna(0)

with ui.filter_bar():
    c1, c2 = st.columns([4, 1], gap="small")
    show_pak = c2.toggle("Include Pakistan players", value=False)
    if not show_pak:
        pl = pl[~pl.is_pakistan.fillna(False).astype(bool)]
    pl = pl.dropna(subset=["name"]).sort_values("vol", ascending=False)
    labels = [f"{r['name']} — {r.national_team if pd.notna(r.national_team) else ''}"
              f"{(' / ' + r.ipl_team) if pd.notna(r.ipl_team) else ''}" for _, r in pl.iterrows()]
    pick = c1.selectbox("Search any player", labels, index=0)
pid = pl.index[labels.index(pick)]
info = pl.loc[pid]
bat = ab[ab.player_id == pid]
bowl = aw[aw.player_id == pid]
bat = bat.iloc[0] if len(bat) else None
bowl = bowl.iloc[0] if len(bowl) else None

years = sorted(set(bat.years.split(",") if bat is not None else []) | set(bowl.years.split(",") if bowl is not None else []))
role = "Batter" if bowl is None or (bat is not None and bat.balls > 2 * bowl.balls) else (
    "Bowler" if bat is None or bowl.balls > 2 * bat.balls else "All-rounder")
chips = ui.chip(f"<b>{role}</b>", "acc") + ui.chip("Seasons <b>" + ", ".join(years) + "</b>")
elig = [x for x, a in [("batter", bat), ("bowler", bowl)] if a is not None and a.pressure_eligible]
chips += ui.chip("Ranked " + " & ".join(elig), "pos") if elig else ui.chip("Not in pressure rankings", "warn")
chips += data.ipl2027_chip(int(pid))
if bool(info.get("is_pakistan", False)):
    chips += ui.chip("Pakistan player · excluded from rankings", "neg")
career = (bat.matches if bat is not None else 0)
career = max(career, bowl.matches if bowl is not None else 0)
ui.hero(info["name"], f"National team: {info.national_team if pd.notna(info.national_team) else '—'} · "
        f"Latest IPL team: {info.ipl_team if pd.notna(info.ipl_team) else '—'}", f"{int(career)}", "Matches", chips)
st.write("")


def log_table(df, cols, rename, fmt):
    st.dataframe(df[cols].sort_values("match_date", ascending=False).rename(columns=rename), hide_index=True, width="stretch",
                 height=360, column_config={**{k: st.column_config.NumberColumn(format=v) for k, v in fmt.items()},
                                            "Date": st.column_config.DateColumn(format="DD MMM YYYY")})


tab_bat, tab_bowl = st.tabs(["Batting", "Bowling"])
with tab_bat:
    if bat is None or bat.balls == 0:
        ui.empty("No batting record.")
    else:
        inn = bi[bi.striker_id == pid].sort_values("match_date")
        pos = inn.batting_order.mode().iat[0] if len(inn) else np.nan
        cohort = {1: "Opener", 2: "Opener", 3: "Top order", 4: "Top order"}.get(pos, "Middle order" if pos <= 7 else "Lower order")
        ui.kpi_row([
            ("Innings", f"{int(bat.innings)}", f"role cohort: {cohort}", ACCENT),
            ("Runs", f"{int(bat.runs):,}", f"average {bat.avg:.1f}", ACCENT2),
            ("Strike rate", f"{bat.sr:.1f}", f"boundary {100 * bat.bnd / max(bat.balls, 1):.0f}% of balls", ACCENT),
            ("Pressure SR", f"{bat.p_sr:.0f}" if bat.p_balls else "—", f"{int(bat.p_balls)} pressure balls", WARN),
            ("Normal SR", f"{bat.n_sr:.0f}", f"{int(bat.n_balls)} normal balls", ACCENT2),
            ("Runs above exp.", f"{bat.contrib:+.0f}", "all balls vs comparable batters", ACCENT),
        ])
        st.write("")
        y = inn.groupby("year").agg(Inns=("runs", "size"), Runs=("runs", "sum"), Balls=("balls", "sum"), Outs=("out", "sum"),
                                    PR=("p_runs", "sum"), PB=("p_balls", "sum")).reset_index()
        y["SR"] = 100 * y.Runs / y.Balls.clip(lower=1)
        y["PSR"] = np.where(y.PB > 0, 100 * y.PR / y.PB.clip(lower=1), np.nan)
        y["Avg"] = y.Runs / y.Outs.clip(lower=1)
        a, b = st.columns(2, gap="medium")
        with a:
            with ui.panel("Season by season", "strike rate overall vs on pressure balls", "01"):
                fig = go.Figure()
                fig.add_scatter(x=y.year, y=y.SR, name="Strike rate", mode="lines+markers", line=dict(color=ACCENT2, width=2.5), marker_size=8)
                fig.add_scatter(x=y.year, y=y.PSR, name="Pressure SR", mode="lines+markers", line=dict(color=ACCENT, width=2.5), marker_size=8)
                fig.update_xaxes(dtick=1)
                show(fig, 300)
        with b:
            with ui.panel("Runs by competition", "innings count on each bar", "02"):
                comp = inn.groupby("comp_type").agg(Runs=("runs", "sum"), Balls=("balls", "sum"), Inns=("runs", "size")).reset_index()
                fig = go.Figure(go.Bar(x=comp.comp_type, y=comp.Runs, marker_color=[ACCENT, ACCENT2, VIOLET][:len(comp)],
                                       text=[f"{i} inns" for i in comp.Inns], textposition="outside",
                                       hovertemplate="%{x}: %{y} runs<extra></extra>"))
                fig.update_yaxes(range=[0, comp.Runs.max() * 1.2])
                show(fig, 300, legend=False)
        with ui.panel("Season table", "", "03"):
            st.dataframe(y[["year", "Inns", "Runs", "Balls", "Avg", "SR", "PSR"]].rename(columns={"year": "Season", "PSR": "Pressure SR"}),
                         hide_index=True, width="stretch",
                         column_config={c: st.column_config.NumberColumn(format="%.1f") for c in ["Avg", "SR", "Pressure SR"]})
        z = data.load("bat_zones")
        z = z[z.player_id == pid]
        with ui.panel("Splits", "pressure vs normal", "04"):
            t1, t2, t3, t4 = st.tabs(["Venue country", "Delivery & bowler type", "Innings & match type", "Match log"])
            with t1:
                profile.zone_chart(z, "venue_country", "sr", "Strike rate", min_balls=12)
            with t2:
                a, b = st.columns(2)
                with a:
                    profile.zone_chart(z, "delivery_style", "sr", "Strike rate")
                with b:
                    profile.zone_chart(z, "bowling_type", "sr", "Strike rate")
            with t3:
                a, b = st.columns(2)
                with a:
                    profile.zone_chart(z, "innings", "sr", "Strike rate")
                with b:
                    profile.zone_chart(z, "match_type", "sr", "Strike rate")
            with t4:
                log = inn.assign(wpa=100 * inn.wpa)
                log_table(log, ["match_date", "comp_name", "stage", "opp", "batting_order", "runs", "balls", "out", "p_runs", "p_balls", "contrib", "wpa"],
                          {"match_date": "Date", "comp_name": "Competition", "stage": "Stage", "opp": "Opponent", "batting_order": "Pos",
                           "runs": "Runs", "balls": "Balls", "out": "Out", "p_runs": "Pressure runs", "p_balls": "Pressure balls",
                           "contrib": "Runs above exp.", "wpa": "WPA (pts)"},
                          {"Runs above exp.": "%.1f", "WPA (pts)": "%.1f"})

with tab_bowl:
    if bowl is None or bowl.balls == 0:
        ui.empty("No bowling record.")
    else:
        sp = bs[bs.bowler_id == pid].sort_values("match_date")
        ui.kpi_row([
            ("Matches", f"{int(bowl.matches)}", str(bowl.bowling_type), ACCENT),
            ("Overs", f"{bowl.overs:.0f}", f"{int(bowl.balls)} legal balls", ACCENT2),
            ("Wickets", f"{int(bowl.wkts)}", f"strike rate {bowl.balls / max(bowl.wkts, 1):.1f}", ACCENT),
            ("Economy", f"{bowl.econ:.2f}", f"dot {100 * bowl.dots / max(bowl.balls, 1):.0f}%", ACCENT2),
            ("Pressure economy", f"{bowl.p_econ:.2f}" if bowl.p_balls else "—", f"{int(bowl.p_wkts)} pressure wickets", WARN),
            ("Runs saved vs exp.", f"{bowl.contrib:+.0f}", "all balls vs comparable bowlers", ACCENT),
        ])
        st.write("")
        y = sp.groupby("year").agg(Runs=("runs", "sum"), Balls=("balls", "sum"), Wkts=("wkts", "sum"),
                                   PR=("p_runs", "sum"), PB=("p_balls", "sum")).reset_index()
        y["Econ"] = 6 * y.Runs / y.Balls.clip(lower=1)
        y["PEcon"] = np.where(y.PB > 0, 6 * y.PR / y.PB.clip(lower=1), np.nan)
        a, b = st.columns(2, gap="medium")
        with a:
            with ui.panel("Season by season", "economy overall vs on pressure balls", "01"):
                fig = go.Figure()
                fig.add_scatter(x=y.year, y=y.Econ, name="Economy", mode="lines+markers", line=dict(color=ACCENT2, width=2.5), marker_size=8)
                fig.add_scatter(x=y.year, y=y.PEcon, name="Pressure economy", mode="lines+markers", line=dict(color=ACCENT, width=2.5), marker_size=8)
                fig.update_xaxes(dtick=1)
                show(fig, 300)
        with b:
            with ui.panel("Wickets by season", "", "02"):
                fig = go.Figure(go.Bar(x=y.year, y=y.Wkts, marker_color=ACCENT, text=y.Wkts, textposition="outside",
                                       hovertemplate="%{x}: %{y} wickets<extra></extra>"))
                fig.update_xaxes(dtick=1)
                fig.update_yaxes(range=[0, max(y.Wkts.max(), 1) * 1.25])
                show(fig, 300, legend=False)
        z = data.load("bowl_zones")
        z = z[z.player_id == pid]
        with ui.panel("Splits", "pressure vs normal", "03"):
            t1, t2, t3 = st.tabs(["Venue & phase", "Delivery & batter hand", "Match log"])
            with t1:
                a, b = st.columns(2)
                with a:
                    profile.zone_chart(z, "venue_country", "econ", "Economy", min_balls=12)
                with b:
                    profile.zone_chart(z, "phase", "econ", "Economy", order=["Powerplay", "Middle", "Death"])
            with t2:
                a, b = st.columns(2)
                with a:
                    profile.zone_chart(z, "delivery_style", "econ", "Economy")
                with b:
                    profile.zone_chart(z, "batting_type", "econ", "Economy")
            with t3:
                log = sp.assign(wpa=100 * sp.wpa)
                log_table(log, ["match_date", "comp_name", "stage", "opp", "balls", "runs", "wkts", "dots", "p_balls", "p_wkts", "contrib", "wpa"],
                          {"match_date": "Date", "comp_name": "Competition", "stage": "Stage", "opp": "Opponent", "balls": "Balls",
                           "runs": "Runs", "wkts": "Wkts", "dots": "Dots", "p_balls": "Pressure balls", "p_wkts": "Pressure wkts",
                           "contrib": "Runs saved vs exp.", "wpa": "WPA (pts)"},
                          {"Runs saved vs exp.": "%.1f", "WPA (pts)": "%.1f"})
