"""Stage 4 - the continuous, context-aware Pressure Index.

Two separate indices (Paper 2): one for the batting side, one for the bowling
side. Each is a weighted blend of [0, 1] components rebuilt before every ball,
multiplied by match stakes, dampened in dead games, and converted to a 0-100
percentile so 67+ is exactly the top tercile of all deliveries.
Knockout matches are pressure from the first ball (owner rule 4.1).
"""
import numpy as np
import pandas as pd
from scipy.stats import norm, spearmanr
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import roc_auc_score

from . import config as C


def _clip01(x):
    return np.clip(x, 0, 1)


def batting_components(b):
    inn2 = b.innings == 2
    diff = np.where(inn2, norm.cdf(b.z_chase.fillna(0)), norm.cdf(-b.z_par.fillna(0)))
    par_rr = b.par_total * 6 / b.sched_balls
    rate1 = np.where(b.legal_before >= 12, _clip01((par_rr - b.crr) / 3.0), 0.0)
    rate2 = _clip01((b.rrr.fillna(0) - 6) / 8.0)
    stage = np.maximum.reduce([
        (b.overid >= 16).astype(float),
        ((b.overid <= 6) & (b.wkts_before >= 2)).astype(float),
        (b.wkts_last18 >= 2).astype(float)])
    part = 0.5 * (b.striker_balls_before < 8) + 0.5 * b.non_striker_tail
    return pd.DataFrame({
        "difficulty": diff,
        "rate": np.where(inn2, rate2, rate1),
        "wickets": _clip01(b.wkts_before / 7.0),
        "balls": 1 - b.balls_rem / b.sched_balls,
        "stage": stage,
        "closeness": b.closeness * np.sqrt(b.progress),
        "partnership": part,
    }, index=b.index)


def bowling_components(b):
    inn2 = b.innings == 2
    diff = np.where(inn2, norm.cdf(-b.z_chase.fillna(0)), norm.cdf(b.z_par.fillna(0)))
    stage = np.where(b.overid >= 16, 1.0, np.where(b.overid <= 6, 0.5, 0.0))
    part = np.maximum(_clip01(b.part_runs / 60.0), _clip01(b.part_balls / 36.0))
    return pd.DataFrame({
        "difficulty": diff,
        "momentum": _clip01((b.rr12 - 6) / 8.0),
        "wickets": _clip01((10 - b.wkts_before) / 10.0),
        "balls": 1 - b.balls_rem / b.sched_balls,
        "stage": stage,
        "closeness": b.closeness * np.sqrt(b.progress),
        "partnership": part,
    }, index=b.index)


def _stakes(b):
    s = np.ones(len(b))
    s = np.where(b.is_knockout, s * C.STAKES["knockout"], s)
    s = np.where(b.is_super4, s * C.STAKES["super4"], s)
    s = np.where(b.is_dls, s * C.STAKES["dls"], s)
    return s


def _dead(b):
    wp = b.wp_before.fillna(0.5)
    return np.where((wp < C.DEAD_GAME_WP) | (wp > 1 - C.DEAD_GAME_WP), C.DEAD_GAME_FACTOR, 1.0)


def level_of(x):
    out = np.empty(len(x), dtype=object)
    for lo, hi, name in C.LEVELS:
        out[(x >= lo) & (x < hi)] = name
    return out


def add_pressure(b):
    bc, wc = batting_components(b), bowling_components(b)
    for c in bc:
        b[f"bpc_{c}"] = bc[c].values
    for c in wc:
        b[f"wpc_{c}"] = wc[c].values
    raw_bat = sum(bc[k] * w for k, w in C.BAT_PI_WEIGHTS.items())
    raw_bowl = sum(wc[k] * w for k, w in C.BOWL_PI_WEIGHTS.items())
    st, dd = _stakes(b), _dead(b)
    b["bat_pi_raw"] = raw_bat * st * dd
    b["bowl_pi_raw"] = raw_bowl * st * dd
    # 0-100 percentile scale: 67+ == top tercile of all deliveries
    b["bat_pi"] = b.bat_pi_raw.rank(pct=True) * 100
    b["bowl_pi"] = b.bowl_pi_raw.rank(pct=True) * 100
    b["bat_level"] = level_of(b.bat_pi.values)
    b["bowl_level"] = level_of(b.bowl_pi.values)
    return b


def pressure_flags(b, threshold=C.PRESSURE_THRESHOLD, knockout_rule=True):
    bat = b.bat_pi >= threshold
    bowl = b.bowl_pi >= threshold
    if knockout_rule:
        bat = bat | b.is_knockout
        bowl = bowl | b.is_knockout
    return bat.values, bowl.values


# ------------------------------------------------------------- validation
def validate_index(b):
    """Paper 4 style: does the index separate pressure from ordinary balls,
    does it relate to win-probability swing, and does it add to RRR alone?
    Train = 2022-2024, holdout = 2025-2026."""
    res = {}
    b = b.copy()
    b["abs_wpa"] = b.wpa_bat.abs()
    b["holdout"] = b.year >= 2025
    fac = b[b.faced]
    rows = []
    for split, d in [("train", fac[~fac.holdout]), ("holdout", fac[fac.holdout])]:
        for lvl in ["Low", "Moderate", "High", "Extreme"]:
            x = d[d.bat_level == lvl]
            rows.append({"split": split, "index": "Batting", "level": lvl, "balls": len(x),
                         "strike_rate": 100 * x.runs.mean(), "dot_pct": 100 * x.is_dot_bat.mean(),
                         "dismissal_pct": 100 * x.striker_out.mean(),
                         "boundary_pct": 100 * x.is_boundary.mean(),
                         "mean_abs_wp_swing": 100 * x.abs_wpa.mean()})
    lg = b[b.is_legal]
    for split, d in [("train", lg[~lg.holdout]), ("holdout", lg[lg.holdout])]:
        for lvl in ["Low", "Moderate", "High", "Extreme"]:
            x = d[d.bowl_level == lvl]
            rows.append({"split": split, "index": "Bowling", "level": lvl, "balls": len(x),
                         "economy": 6 * x.bowler_runs.mean(), "dot_pct": 100 * x.is_dot_bowl.mean(),
                         "wicket_pct": 100 * x.bowler_wicket.mean(),
                         "boundary_pct": 100 * x.is_boundary.mean(),
                         "mean_abs_wp_swing": 100 * x.abs_wpa.mean()})
    res["by_level"] = pd.DataFrame(rows)

    rho_b = spearmanr(b.bat_pi, b.abs_wpa, nan_policy="omit")
    rho_w = spearmanr(b.bowl_pi, b.abs_wpa, nan_policy="omit")
    rho_bb = spearmanr(b.bat_pi, b.bowl_pi)
    res["spearman"] = {"bat_pi_vs_abs_wp_swing": float(rho_b.statistic),
                       "bowl_pi_vs_abs_wp_swing": float(rho_w.statistic),
                       "bat_pi_vs_bowl_pi": float(rho_bb.statistic)}

    # incremental value over RRR alone (second innings, holdout)
    c2 = b[(b.innings == 2) & b.faced].copy()
    c2["rrr_c"] = c2.rrr.clip(0, 36)
    tr, ho = c2[~c2.holdout], c2[c2.holdout]
    inc = {}
    for target in ["striker_out", "is_dot_bat", "is_boundary"]:
        m1 = LogisticRegression(max_iter=500).fit(tr[["rrr_c"]], tr[target])
        m2 = LogisticRegression(max_iter=500).fit(tr[["rrr_c", "bat_pi"]], tr[target])
        inc[target] = {"auc_rrr_only": float(roc_auc_score(ho[target], m1.predict_proba(ho[["rrr_c"]])[:, 1])),
                       "auc_rrr_plus_index": float(roc_auc_score(ho[target], m2.predict_proba(ho[["rrr_c", "bat_pi"]])[:, 1]))}
    # swing: top-decile WP swing balls
    big = (c2.abs_wpa >= c2.abs_wpa.quantile(0.9)).astype(int)
    tr_y, ho_y = big[~c2.holdout], big[c2.holdout]
    m1 = LogisticRegression(max_iter=500).fit(tr[["rrr_c"]], tr_y)
    m2 = LogisticRegression(max_iter=500).fit(tr[["rrr_c", "bat_pi"]], tr_y)
    inc["high_leverage_ball"] = {"auc_rrr_only": float(roc_auc_score(ho_y, m1.predict_proba(ho[["rrr_c"]])[:, 1])),
                                 "auc_rrr_plus_index": float(roc_auc_score(ho_y, m2.predict_proba(ho[["rrr_c", "bat_pi"]])[:, 1]))}
    res["incremental_auc"] = inc

    # match-outcome discrimination (Paper 4): mean chase pressure in overs 11-20
    late = b[(b.innings == 2) & (b.overid >= 11) & b.bat_won.notna()]
    mm = late.groupby("match_id").agg(pi=("bat_pi", "mean"), rrr=("rrr", "first"),
                                      won=("bat_won", "first"), ho=("holdout", "first"))
    mm["rrr"] = mm.rrr.clip(0, 36)
    mtr, mho = mm[~mm.ho], mm[mm.ho]
    out = {}
    for name, cols in [("rrr_at_over_11", ["rrr"]), ("pressure_index", ["pi"]), ("both", ["rrr", "pi"])]:
        lr = LogisticRegression(max_iter=500).fit(mtr[cols], mtr.won)
        out[name] = {"train_accuracy": float((lr.predict(mtr[cols]) == mtr.won).mean()),
                     "holdout_accuracy": float((lr.predict(mho[cols]) == mho.won).mean()),
                     "holdout_auc": float(roc_auc_score(mho.won, lr.predict_proba(mho[cols])[:, 1])),
                     "train_matches": int(len(mtr)), "holdout_matches": int(len(mho))}
    res["outcome_discrimination"] = out

    # pressure share by context
    res["share_high_by_innings"] = (b.groupby("innings")[["bat_pi", "bowl_pi"]]
                                    .apply(lambda d: (d >= C.PRESSURE_THRESHOLD).mean()).to_dict())
    return res
