"""SUPERR INTELLIGENCE - Pressure Performance Analytics Platform.

Run from the project root:  streamlit run app/Home.py
"""
import sys
from pathlib import Path

import streamlit as st

APP = Path(__file__).resolve().parent
sys.path.insert(0, str(APP))
sys.path.insert(0, str(APP.parent))

st.set_page_config(page_title="SUPERR Intelligence", page_icon=str(APP / "assets" / "icon.svg"), layout="wide",
                   initial_sidebar_state="auto")

from components import data, ui  # noqa: E402
from components import theme  # noqa: E402,F401  (registers plotly template)

ui.inject_css()
st.logo(str(APP / "assets" / "logo.svg"), size="large", icon_image=str(APP / "assets" / "icon.svg"))

P = APP / "views"
pages = {
    "War Room": [
        st.Page(P / "command_centre.py", title="Command Centre", icon=":material/radar:", default=True),
        st.Page(P / "scenario_simulator.py", title="Scenario Simulator", icon=":material/tune:"),
        st.Page(P / "squad_builder.py", title="Pressure XI Builder", icon=":material/groups:"),
        st.Page(P / "player_duel.py", title="Player Duel", icon=":material/swords:"),
    ],
    "IPL 2027 Auction": [
        st.Page(P / "rr_auction.py", title="RR Auction War Room", icon=":material/gavel:"),
        st.Page(P / "retention_tracker.py", title="Retention Tracker", icon=":material/fact_check:"),
    ],
    "Analytics": [
        st.Page(P / "overview.py", title="Overview", icon=":material/space_dashboard:"),
        st.Page(P / "pressure_analysis.py", title="Pressure Analysis", icon=":material/speed:"),
    ],
    "Rankings": [
        st.Page(P / "batter_rankings.py", title="Batter Rankings", icon=":material/sports_cricket:"),
        st.Page(P / "bowler_rankings.py", title="Bowler Rankings", icon=":material/sports_baseball:"),
        st.Page(P / "matchups.py", title="Match-Up Analysis", icon=":material/compare_arrows:"),
    ],
    "Players": [
        st.Page(P / "pressure_profiles.py", title="Pressure Player Explorer", icon=":material/bolt:"),
        st.Page(P / "player_explorer.py", title="Overall Player Explorer", icon=":material/person_search:"),
        st.Page(P / "performance_lab.py", title="Performance Lab", icon=":material/science:"),
    ],
    "Model": [
        st.Page(P / "model_reliability.py", title="Model Reliability", icon=":material/verified:"),
        st.Page(P / "methodology.py", title="Methodology", icon=":material/menu_book:"),
    ],
}
nav = st.navigation(pages, expanded=True)

S = data.summary()
c = S.get("counts", {})
st.sidebar.markdown(
    f"<div class='sb-status'><span class='dot live'></span><b>Model v1 · live</b><br/>"
    f"{c.get('matches', 0):,} matches · {c.get('deliveries', 0):,} balls<br/>"
    f"{c.get('eligible_batters', 0)} batters · {c.get('eligible_bowlers', 0)} bowlers rated<br/>"
    f"Pipeline run: {S.get('generated', '—')}<br/>"
    f"<span style='color:#64748B'>Filters change the view, never the model.</span></div>", unsafe_allow_html=True)
nav.run()
