"""IPL 2027 Auction · Rajasthan Royals war room."""
import json

import numpy as np
import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from components import data, ui
from components.theme import ACCENT, ACCENT2, BORDER2, MUTED, NEG, POS, VIOLET, WARN, show
from src import auction as A
from src import ipl2027_data as D

data.require("rr_squad_2027", "rr_phase_coverage", "rr_targets_bat", "rr_targets_bowl", "rr_auction_plan", "ipl2027_status")
rr, ph = data.load("rr_squad_2027"), data.load("rr_phase_coverage")
tb, tw, plan = data.load("rr_targets_bat"), data.load("rr_targets_bowl"), data.load("rr_auction_plan")
needs = json.loads((data.OUT / "rr_needs.json").read_text(encoding="utf-8"))
purse, slots, os_slots = needs["purse"]
PINK = "#EA1A85"  # RR accent, used sparingly for the franchise marker only

ui.command_bar("IPL 2027 Auction · Rajasthan Royals", "Where RR's pressure game is thin, and who fills it",
               "Built from the retention lists published on 17 Nov 2026 and the same pressure engine as the rankings. "
               "The retained squad is profiled on pressure balls, gaps are measured phase by phase against the whole player pool, "
               "and every released player is scored on pressure quality and on how well he covers RR's gaps.",
               [(f"<span class='dot' style='background:{PINK}'></span>RR · <b>₹{purse:.2f} Cr</b> purse", "acc"),
                f"<b>{slots}</b> slots · <b>{os_slots}</b> overseas", f"Auction <b>{D.AUCTION['date']}</b> · {D.AUCTION['venue']}",
                ("Status as of <b>17 Nov 2026</b>", "warn")])

bn, wn = needs["bat_need"], needs["bowl_need"]
top_bowl = max(wn, key=wn.get)
top_bat = max(bn, key=bn.get)
ui.kpi_row([
    ("Retained squad", f"{needs['squad_size']}/25", f"{needs['overseas_in_squad']}/8 overseas", ACCENT2),
    ("Purse remaining", f"₹{purse:.2f} Cr", f"avg ₹{purse / slots:.1f} Cr per open slot", ACCENT),
    ("Open slots", f"{slots}", f"{os_slots} overseas", ACCENT2),
    ("#1 bowling need", top_bowl, f"{wn[top_bowl]:.0%} of bowling need weight", NEG),
    ("#1 batting need", top_bat, f"{bn[top_bat]:.0%} of batting need weight", WARN),
    ("Ranked targets", f"{int(tb.rating.notna().sum() + tw.rating.notna().sum())}", "released players with a full pressure rating", ACCENT),
])
st.write("")

# ------------------------------------------------------------------ 01 squad
with ui.panel("Retained squad under pressure", "career pressure numbers for each retained player · ranked = in the pressure rankings", "01"):
    v = rr.copy()
    for c in ["bat_p_sr", "bat_n_sr"]:
        v.loc[v.bat_p_balls.fillna(0) == 0, c] = np.nan
    for c in ["bowl_p_econ", "bowl_n_econ"]:
        v.loc[v.bowl_p_balls.fillna(0) == 0, c] = np.nan
    v.loc[v.bowl_p_balls.fillna(0) == 0, "bowl_p_balls"] = np.nan
    v["Batting"] = np.where(v.bat_rating.notna(), v.bat_rating.round(1).astype(str) + "  (#" + v.bat_rank.fillna(0).astype(int).astype(str) + ")",
                            np.where(v.bat_p_balls.fillna(0) > 0, "not ranked", "–"))
    v["Bowling"] = np.where(v.bowl_rating.notna(), v.bowl_rating.round(1).astype(str) + "  (#" + v.bowl_rank.fillna(0).astype(int).astype(str) + ")",
                            np.where(v.bowl_p_balls.fillna(0) > 0, "not ranked", "–"))
    view = pd.DataFrame({"Player": v.report_name, "Role": v.role, "Batting rating": v.Batting,
                         "Press. balls faced": v.bat_p_balls, "Press. SR": v.bat_p_sr, "Normal SR": v.bat_n_sr,
                         "Bowling rating": v.Bowling, "Press. balls bowled": v.bowl_p_balls, "Press. econ": v.bowl_p_econ,
                         "Normal econ": v.bowl_n_econ, "Note": v.note.fillna("")})
    st.dataframe(view, hide_index=True, width="stretch", height=420,
                 column_config={c: st.column_config.NumberColumn(format="%.1f") for c in ["Press. SR", "Normal SR"]} |
                               {c: st.column_config.NumberColumn(format="%.2f") for c in ["Press. econ", "Normal econ"]})
    ui.foot("Aman Rao Perala has no deliveries in the data; Lhuan Pretorius, Sushant Mishra, Yash Punja and Brijesh Sharma have "
            "very small pressure samples, so they are shown but carry little weight in the gap analysis.")

# ------------------------------------------------------------------ 02 gaps
c1, c2 = st.columns([3, 2], gap="medium")
with c1:
    with ui.panel("Where the squad is thin", "squad pressure contribution per 100 balls by phase · 0 = what a comparable player produces", "02"):
        fig = go.Figure()
        fig.add_bar(x=ph.phase, y=ph.bat_rae100, name="Batting: runs above expected", marker_color=ACCENT,
                    customdata=np.stack([ph.bat_sr, ph.pool_bat_sr, ph.bat_balls], axis=1),
                    hovertemplate="%{x}: %{y:+.1f} per 100 balls<br>SR %{customdata[0]:.0f} vs pool %{customdata[1]:.0f}"
                                  " · %{customdata[2]} balls<extra>Batting</extra>")
        fig.add_bar(x=ph.phase, y=ph.bowl_saved100, name="Bowling: runs saved", marker_color=ACCENT2,
                    customdata=np.stack([ph.bowl_econ, ph.pool_bowl_econ, ph.bowl_balls], axis=1),
                    hovertemplate="%{x}: %{y:+.1f} per 100 balls<br>econ %{customdata[0]:.2f} vs pool %{customdata[1]:.2f}"
                                  " · %{customdata[2]} balls<extra>Bowling</extra>")
        fig.add_hline(y=0, line=dict(color=BORDER2, width=1))
        fig.update_layout(barmode="group")
        fig.update_yaxes(title="Per 100 pressure balls")
        show(fig, 340)
with c2:
    with ui.panel("What RR should buy", "need weights used to score targets", "03"):
        nd = pd.DataFrame({"Phase": A.PHASES, "Batting": [bn[p] for p in A.PHASES], "Bowling": [wn[p] for p in A.PHASES]})
        fig = go.Figure()
        fig.add_bar(y=nd.Phase, x=nd.Bowling, name="Bowling need", orientation="h", marker_color=ACCENT2,
                    hovertemplate="%{y}: %{x:.0%}<extra>Bowling</extra>")
        fig.add_bar(y=nd.Phase, x=nd.Batting, name="Batting need", orientation="h", marker_color=ACCENT,
                    hovertemplate="%{y}: %{x:.0%}<extra>Batting</extra>")
        fig.update_layout(barmode="group")
        fig.update_xaxes(tickformat=".0%", range=[0, 1])
        fig.update_yaxes(autorange="reversed")
        show(fig, 250)
        ui.feed([
            ("risk", f"Bowling leaks most at the <b>death</b> ({ph.set_index('phase').bowl_econ['Death']:.2f} rpo under pressure) "
                     f"and in the <b>powerplay</b>; Deshpande, Maphaka and Milne were released."),
            ("watch", f"Batting is strong up front (powerplay {ph.set_index('phase').bat_rae100['Powerplay']:+.0f} runs per 100 balls) "
                      f"but only {ph.set_index('phase').bat_rae100['Death']:+.1f} at the death after Hetmyer's release."),
        ])

# ------------------------------------------------------------------ 04 plan
with ui.panel("Recommended 6-slot plan", f"confirmed releases only · ≤ {os_slots} overseas · quotas: 2 death/new-ball seamers, 1 bowler, 1 finisher, 1 batter, 1 best fit", "04"):
    core = plan[plan.plan.str.startswith("Core")]
    cards = []
    for _, r in core.iterrows():
        lc = f" · last ₹{r.last_contract_cr:.2f} Cr" if pd.notna(r.last_contract_cr) else ""
        cards.append(dict(role=r.slot, name=r["name"], sub=f"{r.team_2026} · {'Overseas' if r.overseas else 'Indian'}{lc}",
                          metric=f"fit {r.rr_fit:.1f} · pressure {r.pressure_score:.0f}"))
    ui.xi_cards(cards)
    up = plan[plan.plan.str.startswith("Conditional")]
    if len(up):
        st.markdown("<div style='height:10px'></div>", unsafe_allow_html=True)
        st.markdown("<div class='ph'><div class='t' style='font-size:.82rem'>Upgrades if their status is confirmed</div>"
                    "<div class='h'>disputed release or availability in doubt</div></div>", unsafe_allow_html=True)
        ui.xi_cards([dict(role="Upgrade if available", name=r["name"], sub=f"{r.team_2026} · {'Overseas' if r.overseas else 'Indian'}"
                          + (f" · last ₹{r.last_contract_cr:.2f} Cr" if pd.notna(r.last_contract_cr) else ""),
                          metric=f"fit {r.rr_fit:.1f} · pressure {r.pressure_score:.0f}") for _, r in up.iterrows()])
    known = core.last_contract_cr.dropna()
    ui.feed([("watch", f"Budget check: ₹{purse:.2f} Cr for {slots} slots. Last published contracts in this plan add up to "
                       f"₹{known.sum():.2f} Cr ({', '.join(core.loc[core.last_contract_cr.notna(), 'name'])}), so price ceilings are a "
                       "management call; the model ranks fit, not price."),
             ("info", "Fit = 60% pressure quality (ranked rating, or a provisional score for small samples) + 40% phase fit "
                      "(the player's pressure contribution in each phase, weighted by RR's need in that phase).")])

# ------------------------------------------------------------------ 05/06 shortlists
def shortlist(df, kind):
    is_bat = kind == "bat"
    d = df[df.group != "Wildcard watch list"].head(15)
    view = pd.DataFrame({
        "#": np.arange(1, len(d) + 1), "Player": d.report_name, "2026 team": d.team_2026, "Status": d.availability,
        "Overseas": d.overseas, "RR fit": d.rr_fit, "Pressure score": d.pressure_score, "Score basis": d.score_source,
        ("Press. SR" if is_bat else "Press. econ"): d.p_sr if is_bat else d.p_econ,
        ("Normal SR" if is_bat else "Normal econ"): d.n_sr if is_bat else d.n_econ,
        "PP /100": d.pc100_powerplay, "Middle /100": d.pc100_middle, "Death /100": d.pc100_death,
        "Press. balls": d.p_balls, "Last contract ₹Cr": d.last_contract_cr, "Note": d.note.fillna("")})
    if not is_bat:
        view.insert(3, "Type", d.bowling_type)
    cfg = {"RR fit": st.column_config.ProgressColumn("RR fit", min_value=30, max_value=90, format="%.1f"),
           "Pressure score": st.column_config.NumberColumn(format="%.1f"),
           "Press. SR": st.column_config.NumberColumn(format="%.0f"), "Normal SR": st.column_config.NumberColumn(format="%.0f"),
           "Press. econ": st.column_config.NumberColumn(format="%.2f"), "Normal econ": st.column_config.NumberColumn(format="%.2f"),
           "PP /100": st.column_config.NumberColumn(format="%+.1f"), "Middle /100": st.column_config.NumberColumn(format="%+.1f"),
           "Death /100": st.column_config.NumberColumn(format="%+.1f")}
    st.dataframe(view, hide_index=True, width="stretch", height=430, column_config=cfg)


t1, t2 = st.tabs(["Bowling shortlist", "Batting shortlist"])
with t1:
    with ui.panel("Bowling targets", "released players ranked by RR fit · /100 = runs saved per 100 pressure balls in that phase", "05"):
        shortlist(tw, "bowl")
with t2:
    with ui.panel("Batting targets", "released players ranked by RR fit · /100 = runs above expected per 100 pressure balls", "06"):
        shortlist(tb, "bat")

# ------------------------------------------------------------------ 07 impact simulator
with ui.panel("Impact simulator: how one signing changes the squad", "adds the target's pressure record to RR's retained players and recomputes phase coverage", "07"):
    cand = pd.concat([tw.assign(kind="Bowler"), tb.assign(kind="Batter")])
    cand = cand[cand.group != "Wildcard watch list"].sort_values("rr_fit", ascending=False).drop_duplicates("player_id")
    labels = [f"{r.report_name} · {r.kind} · fit {r.rr_fit:.1f}" for _, r in cand.iterrows()]
    pick = st.selectbox("Target", labels, index=0, label_visibility="collapsed")
    t = cand.iloc[labels.index(pick)]
    bz, wz = data.load("bat_zones"), data.load("bowl_zones")
    bat_ids = rr.loc[rr.bat_p_balls.fillna(0) >= 30, "player_id"].dropna().astype(int).tolist()
    bowl_ids = rr.loc[rr.bowl_p_balls.fillna(0) >= 30, "player_id"].dropna().astype(int).tolist()
    before = A._phase_tables(bz, wz, bat_ids, bowl_ids)
    after = A._phase_tables(bz, wz, bat_ids + ([int(t.player_id)] if t.kind == "Batter" else []),
                            bowl_ids + ([int(t.player_id)] if t.kind == "Bowler" else []))
    col, lab = ("bowl_saved100", "Runs saved per 100 pressure balls") if t.kind == "Bowler" else ("bat_rae100", "Runs above expected per 100 pressure balls")
    a, b = st.columns([3, 2], gap="medium")
    with a:
        fig = go.Figure()
        fig.add_bar(x=before.phase, y=before[col], name="Retained squad", marker_color="#3B5574",
                    hovertemplate="%{x}: %{y:+.2f}<extra>Retained squad</extra>")
        fig.add_bar(x=after.phase, y=after[col], name=f"+ {t.report_name}", marker_color=ACCENT,
                    hovertemplate="%{x}: %{y:+.2f}<extra>with signing</extra>")
        fig.add_hline(y=0, line=dict(color=BORDER2, width=1))
        fig.update_layout(barmode="group")
        fig.update_yaxes(title=lab)
        show(fig, 320)
    with b:
        d = (after[col] - before[col]).values
        best = A.PHASES[int(np.nanargmax(d))]
        stat = (f"pressure economy {t.p_econ:.2f} (normal {t.n_econ:.2f})" if t.kind == "Bowler"
                else f"pressure SR {t.p_sr:.0f} (normal {t.n_sr:.0f})")
        ui.feed([
            ("sig", f"<b>{t.report_name}</b> lifts RR most in the <b>{best.lower()}</b> ({d[A.PHASES.index(best)]:+.2f} per 100 squad pressure balls)."),
            ("info", f"Record: {int(t.p_balls)} pressure balls · {stat} · score basis: {t.score_source.lower()}."),
            ("watch" if t.availability != "Released" else "info", f"Status: {t.availability}. {t.note if isinstance(t.note, str) else ''}"),
        ])
    ui.foot("Simulation pools the target's career pressure balls with the retained players'. It shows direction and relative size, "
            "not a forecast of match minutes.")

# ------------------------------------------------------------------ 08 wildcards
with ui.panel("Wildcard watch list", "ranked internationals with no IPL squad in the data · would need to register · not in the plan", "08"):
    w = pd.concat([tw.assign(kind="Bowler"), tb.assign(kind="Batter")])
    w = w[w.group == "Wildcard watch list"].sort_values("rr_fit", ascending=False).drop_duplicates("player_id").head(12)
    reg = data.registry().set_index("player_id")
    st.dataframe(pd.DataFrame({"Player": w.report_name, "Nation": w.player_id.map(reg.national_team), "Role": w.kind,
                               "Pressure score": w.pressure_score, "RR fit": w.rr_fit, "Press. balls": w.p_balls}),
                 hide_index=True, width="stretch",
                 column_config={"Pressure score": st.column_config.NumberColumn(format="%.1f"),
                                "RR fit": st.column_config.NumberColumn(format="%.1f")})
    ui.foot("Most wildcards play much of their cricket against Associate sides. The expected-performance models adjust for "
            "opposition tier, but IPL adaptation risk is not modelled.")

with ui.panel("Sources and caveats", "", "09"):
    ui.feed([
        ("info", "Retention status: owner-supplied summary (17 Nov 2026), reconciled with CricTracker team lists, Outlook India and "
                 "India TV live blogs, SportsCafe and CricketAddictor release lists (all 17 Nov 2026). RR's full 19-player squad is CricTracker's."),
        ("risk", "Allah Ghazanfar's release is disputed (released per CricketAddictor, CricToday, SportsCafe; retained per Sunday Guardian, "
                 "MyKhel). Ravi Bishnoi is listed by the owner under LSG but under RR by CricTracker; RR is used."),
        ("watch", "Travis Head and Mitchell Starc are released but reported to be weighing IPL 2027 availability."),
        ("info", "Prices are not modelled. Last published contracts are shown only where a source reported them."),
    ])
