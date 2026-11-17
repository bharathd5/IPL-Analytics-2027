"""Exercise the main widgets on each interactive page (headless AppTest)."""
from pathlib import Path

from streamlit.testing.v1 import AppTest

H = str(Path(__file__).resolve().parents[1] / "app" / "Home.py")
FAIL = []


def page(p):
    at = AppTest.from_file(H, default_timeout=300)
    at.run()
    if p != "command_centre":
        at.switch_page(f"views/{p}.py")
        at.run()
    return at


def ok(at, label):
    ex = [e.value[:300] for e in at.exception]
    if ex:
        FAIL.append(label)
    print(f"{label:48s} exceptions={len(ex)}", ex)


def seg(at, key, value):
    w = [s for s in at.get("button_group") if getattr(s, "key", None) == key]
    w[0].set_value(value).run()


at = page("command_centre")
seg(at, "cm_role", "Bowlers"); seg(at, "fm_role", "Bowlers"); ok(at, "command centre: bowlers")

at = page("scenario_simulator")
for i in range(len(at.selectbox[0].options)):
    at.selectbox[0].select_index(i).run(); ok(at, f"simulator: preset {i}")
at.selectbox[2].select_index(2).run(); ok(at, "simulator: T20I only")
at.selectbox[3].select_index(5).run(); ok(at, "simulator: team pool")
at.number_input[3].set_value(1).run(); ok(at, "simulator: extreme state")

at = page("squad_builder")
for i in [1, 5, 12]:
    at.selectbox[0].select_index(i).run(); ok(at, f"squad: pool {i}")
at.number_input[2].set_value(3).run(); ok(at, "squad: 3 spinners")

at = page("player_duel")
at.selectbox[1].select_index(30).run(); ok(at, "duel: batter B #31")
seg(at, "duel_role", "Bowlers"); ok(at, "duel: bowlers")


at = page("rr_auction")
ok(at, "rr auction: default")
for i in [1, 5, 9]:
    at.selectbox[0].select_index(i).run(); ok(at, f"rr auction: impact target {i}")

at = page("retention_tracker")
at.text_input[0].input("Hasaranga").run(); ok(at, "retention: search")
at.text_input[0].input("zzzz").run(); ok(at, "retention: empty search")

at = page("pressure_profiles")
seg(at, "pp_role", "Bowler"); ok(at, "profiles: bowler #1")
at.selectbox[0].select_index(40).run(); ok(at, "profiles: bowler #41")

at = page("performance_lab")
seg(at, "lab_role", "Bowling"); ok(at, "lab: bowling")
for i in range(len(at.selectbox[0].options)):
    at.selectbox[0].select_index(i).run()
ok(at, "lab: all bowling dimensions")

at = page("matchups")
at.selectbox[1].select_index(1).run(); ok(at, "matchups: specific bowler")

at = page("player_explorer")
for i in [5, 150, 400, 700]:
    at.selectbox[0].select_index(i).run(); ok(at, f"explorer: player idx {i}")
at.toggle[0].set_value(True).run(); ok(at, "explorer: include Pakistan")

at = page("batter_rankings")
at.text_input[0].input("Iyer").run(); ok(at, "rankings: search")
at.text_input[0].input("zzzz").run(); ok(at, "rankings: empty search")
at = page("bowler_rankings"); ok(at, "bowler rankings")

at = page("model_reliability")
seg(at, "rel_role", "Bowlers"); ok(at, "reliability: bowlers")

at = page("pressure_analysis")
at.selectbox[0].select_index(1).run(); ok(at, "pressure: knockout only")
at.selectbox[0].select_index(3).run(); ok(at, "pressure: DLS only")

print("\nFAILED:" if FAIL else "\nALL PASSED", FAIL)
