import streamlit as st

from components import data, profile, ui

data.require("batter_rankings", "bowler_rankings", "batter_innings", "bowler_spells", "bat_zones", "bowl_zones")
rb, rw = data.load("batter_rankings"), data.load("bowler_rankings")

ui.command_bar("Players · Pressure", "Pressure Player Explorer",
               "Pressure profiles for every <b>eligible</b> player: active in 2026, not a Pakistan player, and with enough pressure "
               "innings or spells to be rated. Players last seen in 2025 or earlier appear only in the Overall Player Explorer.",
               ui.default_chips())

with ui.filter_bar():
    c1, c2 = st.columns([1, 4], gap="small")
    role = c1.segmented_control("Role", ["Batter", "Bowler"], default="Batter", key="pp_role") or "Batter"
    df = rb if role == "Batter" else rw
    labels = [f"#{int(r['rank'])}  {r['name']} — {r.last_team}" for _, r in df.iterrows()]
    pick = c2.selectbox("Search player", labels, index=0, key=f"pp_pick_{role}")
r = df.iloc[labels.index(pick)]

chips = (ui.chip(f"Rank <b>#{int(r['rank'])}</b> of {len(df)}", "acc")
         + ui.chip(f"Reliability <b>{r.reliability}</b>", {"High": "pos", "Medium": "warn"}.get(r.reliability, "neg"))
         + ui.chip(f"P(top 10) <b>{r.p_top10:.0%}</b>")
         + ui.chip(f"Scenario ranks <b>{int(r.scen_rank_best)}–{int(r.scen_rank_worst)}</b>")
         + ui.chip(f"Seasons <b>{r.years.replace(',', ', ')}</b>") + ui.chip(r.comp_types)
         + data.ipl2027_chip(int(r.player_id)))
meta = f"{r.last_team} · {int(r.matches)} matches · {int(r.ko_innings)} knockout {'innings' if role == 'Batter' else 'matches'}"
if role == "Bowler":
    meta += f" · {r.bowling_type}"
ui.hero(r["name"], meta, f"{r.rating:.1f}", "Pressure rating", chips)
st.write("")

if role == "Batter":
    profile.batting_pressure(r.player_id, r)
else:
    profile.bowling_pressure(r.player_id, r)
