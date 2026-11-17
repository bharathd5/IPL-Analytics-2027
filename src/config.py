"""Central configuration for the SupeRR pressure-performance system.

Every threshold and weight used anywhere in the pipeline lives here so the
methodology page, the report and the code can never drift apart.
"""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / "data" / "raw"
PROCESSED = ROOT / "data" / "processed"
OUT = ROOT / "outputs"

RANDOM_STATE = 42
N_FOLDS = 5                       # cross-fitting folds (grouped by match)

# ---------------------------------------------------------------- ball rules
ILLEGAL_EXTRAS = {"wide", "Overstep", "other"}     # do not count as a legal ball
BOWLER_CHARGED_EXTRAS = {"wide", "Overstep", "other"}
BOWLER_WICKETS = {"Caught", "Bowled", "LBW", "Stump", "Hit Wicket"}
KNOCKOUT_STAGES = {"Final", "Qualifier", "Eliminator", "Semi Final"}
SEMI_STAKES_STAGES = {"Super 4"}

# Associate / development sides (opposition-strength tier used in expected models)
ASSOCIATE_TEAMS = {
    "Hong Kong", "Kuwait", "Singapore", "United Arab Emirates", "Oman", "Nepal",
    "Japan", "Canada", "United States Of America", "Netherlands", "Scotland",
    "India A", "Pakistan A", "Bangladesh A", "Sri Lanka A", "Afghanistan A",
}
EXCLUDED_NATIONAL_TEAM_IDS = {25, 341}   # Pakistan, Pakistan A (owner rule)
ACTIVE_YEAR = 2026                       # pressure rankings require a 2026 appearance

# ---------------------------------------------------------- pressure engine
# Component weights (each component is scaled to [0, 1] before weighting)
BAT_PI_WEIGHTS = {
    "difficulty": 0.25,   # resource-adjusted chase difficulty / first-innings par gap
    "rate": 0.15,         # RRR (chase) or CRR shortfall vs par (1st innings)
    "wickets": 0.15,      # wickets lost
    "balls": 0.10,        # scarcity of balls remaining
    "stage": 0.10,        # death overs / powerplay collapse / recent collapse
    "closeness": 0.15,    # how close the contest is (win-probability balance x lateness)
    "partnership": 0.10,  # new batter at crease / tail-ender at the other end
}
BOWL_PI_WEIGHTS = {
    "difficulty": 0.25,   # batting side ahead of requirement / above par
    "momentum": 0.15,     # opposition run rate over the last 12 legal balls
    "wickets": 0.10,      # wickets in hand for the batting side (harder to defend)
    "balls": 0.10,
    "stage": 0.10,        # death overs (1.0) / powerplay (0.5)
    "closeness": 0.20,
    "partnership": 0.10,  # established partnership that must be broken
}
DEAD_GAME_WP = 0.03       # win prob below / above (1 - x) -> dead-rubber dampener
DEAD_GAME_FACTOR = 0.60
STAKES = {"knockout": 1.20, "super4": 1.08, "dls": 1.05}

PRESSURE_THRESHOLD = 67           # top tercile of the 0-100 percentile index
SENSITIVITY_THRESHOLDS = [60, 67, 75]
LEVELS = [(0, 34, "Low"), (34, 67, "Moderate"), (67, 90, "High"), (90, 101, "Extreme")]

# -------------------------------------------------------- consistency rules
BAT_MIN_PRESSURE_BALLS_INNINGS = 3      # or dismissed on a pressure ball
BAT_IMPACT_RUNS = 20                    # pressure runs only
BAT_QUAL_RUNS_SR = (10, 156)            # >=10 runs at SR >= 156
BAT_QUAL_RUNS_SITUATION = 15            # >=15 runs and SR > situation SR
BOWL_MIN_PRESSURE_BALLS_SPELL = 6       # or took a pressure wicket
BOWL_IMPACT_WKTS = 2
DOT_THRESHOLD = 0.45
SENSITIVITY_DOT = [0.40, 0.45, 0.50]
KNOCKOUT_INNINGS_WEIGHT = 1.5

# ------------------------------------------------------------- eligibility
BAT_MIN_PRESSURE_INNINGS = 12
BAT_MIN_PRESSURE_BALLS = 120
BOWL_MIN_PRESSURE_SPELLS = 12
BOWL_MIN_PRESSURE_BALLS = 150

# --------------------------------------------------------------- shrinkage
PRIOR_INNINGS = 10        # beta-binomial prior strength for innings-level rates
PRIOR_BALLS = 80          # prior strength for per-ball rates
PRIOR_KO = 3              # prior matches for knockout component

# ------------------------------------------------------------ rating weights
BAT_WEIGHTS = {"consistency": 0.35, "contribution": 0.20, "delta": 0.15,
               "wpa": 0.15, "standout": 0.10, "knockout": 0.05}
BOWL_WEIGHTS = dict(BAT_WEIGHTS)

WEIGHT_SCENARIOS = {
    "Base (report weights)": None,
    "Equal weights": {k: 1 / 6 for k in BAT_WEIGHTS},
    "Consistency-heavy": {"consistency": 0.50, "contribution": 0.15, "delta": 0.10,
                          "wpa": 0.10, "standout": 0.10, "knockout": 0.05},
    "Contribution-heavy": {"consistency": 0.25, "contribution": 0.30, "delta": 0.15,
                           "wpa": 0.15, "standout": 0.10, "knockout": 0.05},
    "No WPA": {"consistency": 0.40, "contribution": 0.25, "delta": 0.15,
               "wpa": 0.0, "standout": 0.15, "knockout": 0.05},
    "No knockout": {"consistency": 0.37, "contribution": 0.21, "delta": 0.16,
                    "wpa": 0.16, "standout": 0.10, "knockout": 0.0},
}
N_BOOTSTRAP = 300
