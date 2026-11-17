"""Stage 5 - expected performance per ball (Paper 5 Expected Run Differential idea,
Paper 7 batter-quality adjustment, Paper 3 clutch weighting).

* Pre-match form: each player's career-to-date (strictly before the match) strike
  rate / economy, shrunk toward the league mean - used as opponent quality.
* Batter models: expected runs off the bat and expected dismissal probability for
  a comparable batter in the same state, role cohort, competition and opponent.
* Bowler models: expected runs conceded and wicket probability for a comparable
  bowler in the same state, phase, competition, pace/spin and batter quality.
All predictions are cross-fitted by match.
"""
import numpy as np
import pandas as pd
from sklearn.ensemble import HistGradientBoostingClassifier, HistGradientBoostingRegressor
from sklearn.model_selection import GroupKFold

from . import config as C

K_FORM = 60   # balls of league-average prior in the form estimate


def add_prematch_form(b):
    order = b.groupby("match_id").match_date.first().rank(method="first")
    b["_mord"] = b.match_id.map(order)

    bat = (b[b.faced].groupby(["striker_id", "match_id"])
           .agg(r=("runs", "sum"), n=("faced", "sum"), o=("striker_out", "sum"), mord=("_mord", "first"))
           .reset_index().sort_values(["striker_id", "mord"]))
    lg_rpb = bat.r.sum() / bat.n.sum()
    gb = bat.groupby("striker_id")
    bat["cr"], bat["cn"] = gb.r.cumsum() - bat.r, gb.n.cumsum() - bat.n
    bat["bat_form_sr"] = 100 * (bat.cr + K_FORM * lg_rpb) / (bat.cn + K_FORM)
    bat["bat_exp_balls"] = bat.cn
    b = b.merge(bat[["striker_id", "match_id", "bat_form_sr", "bat_exp_balls"]],
                on=["striker_id", "match_id"], how="left")

    bw = (b.groupby(["bowler_id", "match_id"])
          .agg(r=("bowler_runs", "sum"), n=("is_legal", "sum"), w=("bowler_wicket", "sum"), mord=("_mord", "first"))
          .reset_index().sort_values(["bowler_id", "mord"]))
    lg_rpb_b = bw.r.sum() / bw.n.sum()
    lg_wpb = bw.w.sum() / bw.n.sum()
    gw = bw.groupby("bowler_id")
    bw["cr"], bw["cn"], bw["cw"] = gw.r.cumsum() - bw.r, gw.n.cumsum() - bw.n, gw.w.cumsum() - bw.w
    bw["bowl_form_econ"] = 6 * (bw.cr + K_FORM * lg_rpb_b) / (bw.cn + K_FORM)
    bw["bowl_form_wpb"] = (bw.cw + K_FORM * lg_wpb) / (bw.cn + K_FORM)
    b = b.merge(bw[["bowler_id", "match_id", "bowl_form_econ", "bowl_form_wpb"]],
                on=["bowler_id", "match_id"], how="left")
    b["bat_form_sr"] = b.bat_form_sr.fillna(100 * lg_rpb)
    b["bat_exp_balls"] = b.bat_exp_balls.fillna(0)
    return b.drop(columns="_mord")


BAT_FEATS = ["innings", "overid", "balls_rem", "wkts_before", "rrr_c", "z_par_c", "bat_pi",
             "is_ipl", "year", "opp_is_associate", "batting_order", "is_spin",
             "bowl_form_econ", "bowl_form_wpb", "striker_balls_before"]
BOWL_FEATS = ["innings", "overid", "balls_rem", "wkts_before", "rrr_c", "z_par_c", "bowl_pi",
              "is_ipl", "year", "bat_opp_is_associate", "batting_order", "is_spin",
              "bat_form_sr", "striker_balls_before"]


def _reg():
    return HistGradientBoostingRegressor(max_iter=250, learning_rate=0.05, max_leaf_nodes=31,
                                         min_samples_leaf=200, l2_regularization=1.0,
                                         random_state=C.RANDOM_STATE)


def _clf():
    return HistGradientBoostingClassifier(max_iter=250, learning_rate=0.05, max_leaf_nodes=31,
                                          min_samples_leaf=200, l2_regularization=1.0,
                                          random_state=C.RANDOM_STATE)


def _crossfit(df, feats, target, kind):
    pred = np.zeros(len(df))
    for tr, te in GroupKFold(n_splits=C.N_FOLDS).split(df, groups=df.match_id):
        X, y = df.iloc[tr][feats], df.iloc[tr][target]
        if kind == "reg":
            pred[te] = _reg().fit(X, y).predict(df.iloc[te][feats])
        else:
            pred[te] = _clf().fit(X, y.astype(int)).predict_proba(df.iloc[te][feats])[:, 1]
    return pred


def add_expected(b):
    b["is_spin"] = (b.pace_or_spin == "Spin").astype(int)
    b["rrr_c"] = b.rrr.clip(0, 36).fillna(0)
    b["z_par_c"] = b.z_par.fillna(0)

    fac = b.index[b.faced]
    d = b.loc[fac]
    b.loc[fac, "x_runs_bat"] = _crossfit(d, BAT_FEATS, "runs", "reg")
    b.loc[fac, "x_out_bat"] = _crossfit(d, BAT_FEATS, "striker_out", "clf")

    b["x_runs_bowl"] = _crossfit(b, BOWL_FEATS, "bowler_runs", "reg")
    b["x_wkt_bowl"] = _crossfit(b, BOWL_FEATS, "bowler_wicket", "clf")

    # contributions (Paper 5): runs above expected, wickets valued at the
    # resource destroyed (DLS-style run value of a wicket at that state)
    rv = b.wicket_run_value
    b["bat_contrib"] = np.where(b.faced, (b.runs - b.x_runs_bat) - rv * (b.striker_out - b.x_out_bat), np.nan)
    b["bowl_contrib"] = (b.x_runs_bowl - b.bowler_runs) + rv * (b.bowler_wicket - b.x_wkt_bowl)
    return b
