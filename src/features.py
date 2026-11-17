"""Stage 7 - owner feature tables (Features 1-3, ideas 1-8, Paper 7 context).

* bat_zones / bowl_zones : long tables of performance by dimension
  (delivery style, pace/spin, line, stroke, venue country, innings, phase,
  collapse context, opposition momentum, batter quality...) split by
  pressure vs normal - covers venue/zone strengths, innings split,
  recovery after quick wickets and length/line analysis.
* wickets      : every dismissal with stage, pressure, style, stroke, delivery,
                 batter's score at dismissal (wicket clustering by stage).
* matchups     : batter vs bowler head-to-head, overall and under pressure.
* over_sequence: bowler over-by-over within a match, incl. the previous over
                 (in-match adjustment / bounce-back after an expensive over).
"""
import numpy as np
import pandas as pd


def _collapse(b):
    return ((b.wkts_last18 >= 2) | ((b.overid <= 6) & (b.wkts_before >= 2)))


def bat_zones(b, flag):
    d = b[b.faced].copy()
    d["pressure"] = np.where(flag[b.faced.values], "Pressure", "Normal")
    d["collapse_context"] = np.where(_collapse(d), "After quick wickets", "Stable")
    d["match_type"] = np.where(d.is_knockout, "Knockout", "League / bilateral")
    d["innings_lbl"] = np.where(d.innings == 1, "1st innings", "2nd innings")
    dims = {"delivery_style": "delivery_style", "pace_or_spin": "pace_or_spin",
            "line": "on_or_off", "stroke": "stroke", "bowling_type": "bowling_type",
            "venue_country": "venue_country", "innings": "innings_lbl", "phase": "phase",
            "collapse": "collapse_context", "match_type": "match_type",
            "competition": "comp_type"}
    out = []
    for dim, col in dims.items():
        g = d.groupby(["striker_id", "pressure", col], observed=True)
        x = g.agg(balls=("faced", "sum"), runs=("runs", "sum"), outs=("striker_out", "sum"),
                  dots=("is_dot_bat", "sum"), boundaries=("is_boundary", "sum"),
                  contrib=("bat_contrib", "sum")).reset_index().rename(columns={col: "value", "striker_id": "player_id"})
        x["dim"] = dim
        out.append(x)
    # collapse context x delivery style (feature 2.1)
    c = d[_collapse(d)]
    g = c.groupby(["striker_id", "pressure", "delivery_style"])
    x = g.agg(balls=("faced", "sum"), runs=("runs", "sum"), outs=("striker_out", "sum"),
              dots=("is_dot_bat", "sum"), boundaries=("is_boundary", "sum"),
              contrib=("bat_contrib", "sum")).reset_index().rename(columns={"delivery_style": "value", "striker_id": "player_id"})
    x["dim"] = "delivery_after_collapse"
    out.append(x)
    z = pd.concat(out, ignore_index=True)
    z["sr"] = 100 * z.runs / z.balls.clip(lower=1)
    return z


def bowl_zones(b, flag):
    d = b.copy()
    d["pressure"] = np.where(flag, "Pressure", "Normal")
    d["momentum"] = np.where(d.rr12 >= 10, "Opposition scoring 10+ rpo", "Normal scoring")
    d["match_type"] = np.where(d.is_knockout, "Knockout", "League / bilateral")
    d["innings_lbl"] = np.where(d.innings == 1, "Bowling 1st", "Bowling 2nd (defending)")
    q = d.bat_form_sr.rank(pct=True)
    d["batter_quality"] = np.where(q >= 2 / 3, "Strong batter (top third SR)",
                                   np.where(q >= 1 / 3, "Average batter", "Weaker batter"))
    d["wih"] = pd.cut(10 - d.wkts_before, [-1, 4, 7, 10], labels=["0-4 in hand", "5-7 in hand", "8-10 in hand"]).astype(str)
    dims = {"delivery_style": "delivery_style", "line": "on_or_off", "angle": "over_or_around",
            "batting_type": "batting_type", "venue_country": "venue_country", "innings": "innings_lbl",
            "phase": "phase", "momentum": "momentum", "match_type": "match_type",
            "batter_quality": "batter_quality", "wickets_in_hand": "wih", "competition": "comp_type"}
    out = []
    for dim, col in dims.items():
        g = d.groupby(["bowler_id", "pressure", col], observed=True)
        x = g.agg(balls=("is_legal", "sum"), runs=("bowler_runs", "sum"), wkts=("bowler_wicket", "sum"),
                  dots=("is_dot_bowl", "sum"), boundaries=("is_boundary", "sum"),
                  xr=("x_runs_bowl", "sum"), contrib=("bowl_contrib", "sum")).reset_index().rename(
            columns={col: "value", "bowler_id": "player_id"})
        x["dim"] = dim
        out.append(x)
    z = pd.concat(out, ignore_index=True)
    z["econ"] = 6 * z.runs / z.balls.clip(lower=1)
    z["dot_pct"] = 100 * z.dots / z.balls.clip(lower=1)
    return z


def wickets_table(b, bat_flag, bowl_flag):
    w = b[b.is_wicket].copy()
    w["bat_pressure"] = bat_flag[w.index.values]
    w["bowl_pressure"] = bowl_flag[w.index.values]
    w["batter_score_at_dismissal"] = np.where(w.dismissed_player_id == w.striker_id,
                                              w.striker_runs_before + w.runs, np.nan)
    w["set_batter"] = w.batter_score_at_dismissal >= 20
    cols = ["match_id", "match_date", "year", "comp_type", "comp_name", "stage", "is_knockout",
            "innings", "overid", "over_ball_num", "phase", "batting_team", "bowling_team",
            "striker_id", "striker_name", "batting_type", "batting_order", "dismissed_player_id",
            "bowler_id", "bowler_name", "bowling_type", "pace_or_spin", "delivery_style",
            "on_or_off", "over_or_around", "stroke", "dismissal_type", "bowler_wicket",
            "bat_pi", "bowl_pi", "bat_pressure", "bowl_pressure", "wkts_before", "rrr",
            "batter_score_at_dismissal", "set_batter", "venue_country", "wicket_run_value", "wpa_bat"]
    return w[cols].reset_index(drop=True)


def matchups(b, bat_flag):
    d = b[b.faced].copy()
    d["p"] = bat_flag[b.faced.values]
    d["p_runs"] = d.runs * d.p
    d["p_out"] = d.striker_out & d.p
    g = d.groupby(["striker_id", "bowler_id"])
    m = g.agg(batter=("striker_name", "first"), bowler=("bowler_name", "first"),
              balls=("faced", "sum"), runs=("runs", "sum"), outs=("striker_out", "sum"),
              dots=("is_dot_bat", "sum"), boundaries=("is_boundary", "sum"),
              p_balls=("p", "sum"), p_runs=("p_runs", "sum"), p_outs=("p_out", "sum"),
              matches=("match_id", "nunique")).reset_index()
    m["sr"] = 100 * m.runs / m.balls.clip(lower=1)
    m["p_sr"] = np.where(m.p_balls > 0, 100 * m.p_runs / m.p_balls.clip(lower=1), np.nan)
    return m


def over_sequence(b, bowl_flag):
    d = b.copy()
    d["p"] = bowl_flag
    g = d.groupby(["match_id", "bowler_id", "innings", "overid"])
    o = g.agg(bowler=("bowler_name", "first"), runs=("bowler_runs", "sum"), wkts=("bowler_wicket", "sum"),
              dots=("is_dot_bowl", "sum"), balls=("is_legal", "sum"), pressure_share=("p", "mean"),
              bowl_pi=("bowl_pi", "mean")).reset_index().sort_values(["match_id", "bowler_id", "overid"])
    o["spell_over_no"] = o.groupby(["match_id", "bowler_id"]).cumcount() + 1
    o["prev_over_runs"] = o.groupby(["match_id", "bowler_id"]).runs.shift(1)
    o["after_expensive_over"] = o.prev_over_runs >= 12
    return o


def bounce_back(over_seq):
    """Economy in the over that follows an expensive (12+) over in the same match."""
    x = over_seq[over_seq.after_expensive_over]
    g = x.groupby("bowler_id")
    return pd.DataFrame({"bounce_overs": g.size(),
                         "bounce_econ": 6 * g.runs.sum() / g.balls.sum().clip(lower=1),
                         "bounce_wkts": g.wkts.sum()}).reset_index().rename(columns={"bowler_id": "player_id"})
