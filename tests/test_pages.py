import sys, time
from streamlit.testing.v1 import AppTest
pages=["command_centre","scenario_simulator","squad_builder","player_duel","rr_auction","retention_tracker","overview","pressure_analysis","batter_rankings","bowler_rankings","matchups","pressure_profiles","player_explorer","performance_lab","model_reliability","methodology"]
for p in pages:
    t=time.time()
    at=AppTest.from_file(str(__import__("pathlib").Path(__file__).resolve().parents[1]/"app"/"Home.py"), default_timeout=180)
    at.run()
    if p!="command_centre":
        at.switch_page(f"views/{p}.py"); at.run()
    errs=[e.value for e in at.exception]
    print(f"{p:20s} {time.time()-t:5.1f}s exceptions={len(errs)}", (errs[0][:1500] if errs else ""), flush=True)
