"""Stage 3 - match-state models.

* Empirical resource table (DLS-style, Papers 1 & 3): expected runs still to come
  and its spread for every (balls remaining, wickets lost) state, learned from
  this dataset with monotone gradient boosting.
* Win-probability model (Paper 4 validation idea; used for closeness and WPA),
  cross-fitted by match so no ball is scored by a model that saw its own match.
"""
import numpy as np
import pandas as pd
from scipy.stats import norm
from sklearn.ensemble import HistGradientBoostingClassifier, HistGradientBoostingRegressor
from sklearn.metrics import brier_score_loss, log_loss, roc_auc_score
from sklearn.model_selection import GroupKFold

from . import config as C

RES_FEATS = ["balls_rem", "wkts_before", "is_ipl", "year"]


class ResourceModel:
    def fit(self, b):
        tr = b[(b.innings == 1) & (~b.is_dls) & (~b.no_result) & (b.sched_balls == 120)].copy()
        tot = tr.groupby("match_id").team_runs.sum()
        tr["runs_to_come"] = tr.match_id.map(tot) - tr.runs_before
        X = tr[RES_FEATS]
        self.mean = HistGradientBoostingRegressor(
            max_iter=300, learning_rate=0.05, max_leaf_nodes=31, min_samples_leaf=80,
            monotonic_cst=[1, -1, 0, 0], random_state=C.RANDOM_STATE).fit(X, tr.runs_to_come)
        resid2 = (tr.runs_to_come - self.mean.predict(X)) ** 2
        self.var = HistGradientBoostingRegressor(
            max_iter=200, learning_rate=0.05, min_samples_leaf=200,
            monotonic_cst=[1, -1, 0, 0], random_state=C.RANDOM_STATE).fit(X, resid2)
        self.train_rows = len(tr)
        return self

    def expected(self, balls_rem, wkts, is_ipl, year):
        X = pd.DataFrame({"balls_rem": balls_rem, "wkts_before": np.minimum(wkts, 9),
                          "is_ipl": is_ipl, "year": year})
        e = np.clip(self.mean.predict(X), 0, None)
        return np.where(np.asarray(wkts) >= 10, 0.0, e)

    def sd(self, balls_rem, wkts, is_ipl, year):
        X = pd.DataFrame({"balls_rem": balls_rem, "wkts_before": np.minimum(wkts, 9),
                          "is_ipl": is_ipl, "year": year})
        return np.sqrt(np.clip(self.var.predict(X), 16, None))

    def table(self):
        """Resource table for the methodology page (IPL & T20I, latest season)."""
        rows = []
        for ipl in (0, 1):
            for w in range(10):
                for br in range(6, 121, 6):
                    rows.append((ipl, w, br))
        t = pd.DataFrame(rows, columns=["is_ipl", "wkts_before", "balls_rem"])
        t["year"] = 2026
        t["expected_runs"] = self.expected(t.balls_rem, t.wkts_before, t.is_ipl, t.year)
        t["sd_runs"] = self.sd(t.balls_rem, t.wkts_before, t.is_ipl, t.year)
        return t


def add_resource_features(b, rm: ResourceModel):
    b["exp_runs_rem"] = rm.expected(b.balls_rem, b.wkts_before, b.is_ipl, b.year)
    b["sd_runs_rem"] = rm.sd(b.balls_rem, b.wkts_before, b.is_ipl, b.year)
    start = rm.expected(b.sched_balls, np.zeros(len(b)), b.is_ipl, b.year)
    b["par_total"] = start
    b["sd_start"] = rm.sd(b.sched_balls, np.zeros(len(b)), b.is_ipl, b.year)
    b["proj_total"] = b.runs_before + b.exp_runs_rem
    # chase difficulty (z): runs still needed beyond what the resources usually yield
    b["z_chase"] = np.where(b.innings == 2,
                            (b.runs_req - b.exp_runs_rem) / b.sd_runs_rem.clip(lower=4), np.nan)
    # first innings: projected total vs par (negative = behind par)
    b["z_par"] = np.where(b.innings == 1, (b.proj_total - b.par_total) / b.sd_start, np.nan)
    # run value of a wicket at this state = resources destroyed by one more wicket
    nxt = rm.expected(b.balls_rem, b.wkts_before + 1, b.is_ipl, b.year)
    b["wicket_run_value"] = np.clip(b.exp_runs_rem - nxt, 0, None)
    return b


WP2 = ["runs_req", "balls_rem", "wkts_before", "rrr_c", "z_chase", "is_ipl"]
WP2_MONO = [-1, 1, -1, -1, -1, 0]
WP1 = ["runs_before", "balls_rem", "wkts_before", "proj_total", "z_par", "is_ipl", "year"]
WP1_MONO = [1, 1, -1, 1, 1, 0, 0]


def _wp_model(mono):
    return HistGradientBoostingClassifier(max_iter=250, learning_rate=0.05, max_leaf_nodes=31,
                                          min_samples_leaf=150, l2_regularization=1.0,
                                          monotonic_cst=mono, random_state=C.RANDOM_STATE)


def fit_win_probability(b, rm: ResourceModel):
    """Cross-fitted WP before every ball (batting-team perspective) + WPA chain."""
    b["rrr_c"] = b.rrr.clip(0, 36)
    b["wp_before"] = np.nan
    metrics = {}
    gkf = GroupKFold(n_splits=C.N_FOLDS)
    for inn, feats, mono in [(1, WP1, WP1_MONO), (2, WP2, WP2_MONO)]:
        idx = b.index[b.innings == inn]
        sub = b.loc[idx]
        pred = np.full(len(sub), np.nan)
        for tr_i, te_i in gkf.split(sub, groups=sub.match_id):
            tr = sub.iloc[tr_i]
            tr = tr[tr.bat_won.notna()]
            mdl = _wp_model(mono).fit(tr[feats], tr.bat_won)
            pred[te_i] = mdl.predict_proba(sub.iloc[te_i][feats])[:, 1]
        b.loc[idx, "wp_before"] = pred
        lab = sub.bat_won.notna().values
        y, p = sub.bat_won.values[lab], pred[lab]
        metrics[f"innings_{inn}"] = {"auc": float(roc_auc_score(y, p)),
                                     "brier": float(brier_score_loss(y, p)),
                                     "log_loss": float(log_loss(y, p)), "balls": int(lab.sum())}
    # chase-start WP for the innings-break hand-off
    full = _wp_model(WP2_MONO).fit(b[(b.innings == 2) & b.bat_won.notna()][WP2],
                                   b[(b.innings == 2) & b.bat_won.notna()].bat_won)

    # WP after each ball = WP before the next ball of the same innings
    b = b.sort_values(["match_id", "innings", "innings_ball_num"]).reset_index(drop=True)
    b["wp_after"] = b.groupby(["match_id", "innings"]).wp_before.shift(-1)
    last = b.wp_after.isna()
    # end of first innings: 1 - chasing side's WP at the start of the chase
    l1 = last & (b.innings == 1)
    if l1.any():
        s = b.loc[l1]
        tgt = s.revised_target.fillna(s.inn1_total + 1)
        sb = s.sched_balls_2
        Xs = pd.DataFrame({"runs_req": tgt.values, "balls_rem": sb.values, "wkts_before": 0,
                           "rrr_c": np.clip(tgt.values * 6 / sb.values, 0, 36)})
        e = rm.expected(sb.values, np.zeros(len(s)), s.is_ipl.values, s.year.values)
        sd = rm.sd(sb.values, np.zeros(len(s)), s.is_ipl.values, s.year.values)
        Xs["z_chase"] = (tgt.values - e) / np.clip(sd, 4, None)
        Xs["is_ipl"] = s.is_ipl.values
        b.loc[l1, "wp_after"] = 1 - full.predict_proba(Xs[WP2])[:, 1]
    # end of second innings: the actual result
    l2 = last & (b.innings == 2)
    b.loc[l2, "wp_after"] = b.loc[l2, "bat_won"].fillna(b.loc[l2, "wp_before"])
    b["wpa_bat"] = b.wp_after - b.wp_before
    b.loc[b.no_result, "wpa_bat"] = 0.0          # no contest -> no win value
    b["closeness"] = 1 - (2 * b.wp_before - 1).abs()
    return b, metrics


def phi(x):
    return norm.cdf(x)
