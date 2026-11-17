"""Stage 2 - ball-by-ball match state, computed BEFORE each delivery.

Everything here is the situation the bowler runs in to: balls remaining, wickets
lost, runs required, RRR/CRR, momentum, collapse and partnership context.
"""
import numpy as np
import pandas as pd


def _shifted_cumsum(g, col):
    return g[col].cumsum() - g[col]


def add_state(b: pd.DataFrame) -> pd.DataFrame:
    b = b.sort_values(["match_id", "innings", "innings_ball_num"]).reset_index(drop=True)
    b["legal_i"] = b.is_legal.astype(int)
    b["wkt_i"] = b.is_wicket.astype(int)
    g = b.groupby(["match_id", "innings"], sort=False)

    b["legal_before"] = g.legal_i.cumsum() - b.legal_i
    b["runs_before"] = g.team_runs.cumsum() - b.team_runs
    b["wkts_before"] = g.wkt_i.cumsum() - b.wkt_i
    b["sched_balls"] = np.where(b.innings == 1, b.sched_balls_1, b.sched_balls_2)
    b["balls_rem"] = (b.sched_balls - b.legal_before).clip(lower=1)
    b["progress"] = (b.legal_before / b.sched_balls).clip(0, 1)
    b["crr"] = np.where(b.legal_before > 0, b.runs_before * 6 / b.legal_before.clip(lower=1), 0.0)

    # targets: revised target if DLS, else first-innings total + 1
    inn1 = b[b.innings == 1].groupby("match_id").team_runs.sum()
    b["inn1_total"] = b.match_id.map(inn1)
    b["target"] = np.where(b.innings == 2, b.revised_target.fillna(b.inn1_total + 1), np.nan)
    b["runs_req"] = np.where(b.innings == 2, b.target - b.runs_before, np.nan)
    b["rrr"] = np.where(b.innings == 2, b.runs_req * 6 / b.balls_rem, np.nan)

    # momentum and collapse windows (previous deliveries only)
    b["rr12"] = (g.team_runs.transform(lambda s: s.shift(1).rolling(12, min_periods=1).sum())
                 .fillna(0) * 6 / 12)
    b["wkts_last18"] = g.wkt_i.transform(lambda s: s.shift(1).rolling(18, min_periods=1).sum()).fillna(0)

    # partnership context
    b["part_id"] = g.wkt_i.cumsum() - b.wkt_i
    gp = b.groupby(["match_id", "innings", "part_id"], sort=False)
    b["part_runs"] = gp.team_runs.cumsum() - b.team_runs
    b["part_balls"] = gp.legal_i.cumsum() - b.legal_i
    b["faced_i"] = b.faced.astype(int)
    gs = b.groupby(["match_id", "innings", "striker_id"], sort=False)
    b["striker_balls_before"] = gs.faced_i.cumsum() - b.faced_i
    b["striker_runs_before"] = gs.runs.cumsum() - b.runs
    b["non_striker_tail"] = (b.non_striker_order.fillna(0) >= 8).astype(int)
    b["is_ipl"] = (b.comp_type == "IPL").astype(int)
    b["bat_won"] = np.where(b.no_result, np.nan,
                            np.where(b.win_team_id == b.batting_team_id, 1.0, 0.0))
    return b
