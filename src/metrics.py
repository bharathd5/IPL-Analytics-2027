"""Stage 6 - innings / spell tables, player aggregates, consistency, ratings.

Consistency (owner's key ranking context) is computed on PRESSURE BALLS ONLY:
  batter  impact innings      >= 20 pressure runs
          qualifying innings  >= 10 pressure runs at SR >= 156, or
                              >= 15 pressure runs at SR above the situation SR
  bowler  wicket spell        >= 1 pressure wicket
          impact spell        >= 2 pressure wickets
          dot-reliable spell  pressure dot% >= threshold (45% default)
"""
import numpy as np
import pandas as pd
from scipy.stats import norm

from . import config as C

# ======================================================================= batting
def batter_innings(b, flag):
    d = b[b.faced].copy()
    p = flag[b.faced.values]
    d["p"] = p
    d["sit_rpb"] = np.where(d.innings == 2, d.rrr.clip(0, 36) / 6, d.exp_runs_rem / d.balls_rem)
    d["cw"] = (d.bat_pi / 100) ** 2
    d["out"] = d.striker_out.astype(int)
    d["dot"] = d.is_dot_bat.astype(int)
    d["bnd"] = d.is_boundary.astype(int)
    keys = ["match_id", "innings", "striker_id"]

    def agg(x, pre):
        g = x.groupby(keys)
        return pd.DataFrame({f"{pre}runs": g.runs.sum(), f"{pre}balls": g.faced.sum(),
                             f"{pre}out": g.out.sum(), f"{pre}dots": g.dot.sum(),
                             f"{pre}bnd": g.bnd.sum(), f"{pre}contrib": g.bat_contrib.sum(),
                             f"{pre}xr": g.x_runs_bat.sum(), f"{pre}wpa": g.wpa_bat.sum()})
    allv = agg(d, "")
    pv = agg(d[d.p], "p_")
    nv = agg(d[~d.p], "n_")
    g = d[d.p].groupby(keys)
    extra = pd.DataFrame({"p_sit_rpb": g.sit_rpb.mean(), "p_pi_mean": g.bat_pi.mean()})
    gc = d.groupby(keys)
    clutch = pd.DataFrame({"clutch_num": (d.cw * d.bat_contrib).groupby([d[k] for k in keys]).sum(),
                           "clutch_den": gc.cw.sum()})
    info = gc.agg(striker_name=("striker_name", "first"), team=("batting_team", "first"),
                  opp=("bowling_team", "first"), comp_type=("comp_type", "first"),
                  comp_name=("comp_name", "first"), year=("year", "first"),
                  match_date=("match_date", "first"), is_knockout=("is_knockout", "first"),
                  stage=("stage", "first"), venue_country=("venue_country", "first"),
                  batting_order=("batting_order", "first"), team_won=("bat_won", "first"),
                  is_dls=("is_dls", "first"))
    t = info.join([allv, pv, nv, extra, clutch]).fillna(
        {c: 0 for c in list(pv.columns) + list(nv.columns)}).reset_index()

    # non-striker run-outs etc.: dismissal attributed to the dismissed player
    dis = b[b.is_wicket & b.dismissed_player_id.notna()].copy()
    dis["p"] = flag[dis.index.values] if len(dis) else []
    nonstriker = dis[dis.dismissed_player_id != dis.striker_id]
    ns = nonstriker.groupby(["match_id", "innings", "dismissed_player_id"]).p.agg(["size", "sum"])
    ns.index = ns.index.set_names(keys)
    t = t.set_index(keys)
    t["out"] = t.out.add(ns["size"], fill_value=0).loc[t.index]
    t["p_out"] = t.p_out.add(ns["sum"], fill_value=0).loc[t.index]
    t = t.reset_index()

    t["p_sr"] = np.where(t.p_balls > 0, 100 * t.p_runs / t.p_balls.clip(lower=1), np.nan)
    t["is_p_innings"] = (t.p_balls >= C.BAT_MIN_PRESSURE_BALLS_INNINGS) | (t.p_out > 0)
    t["impact"] = t.p_runs >= C.BAT_IMPACT_RUNS
    r1, s1 = C.BAT_QUAL_RUNS_SR
    t["qualifying"] = ((t.p_runs >= r1) & (t.p_sr >= s1)) | (
        (t.p_runs >= C.BAT_QUAL_RUNS_SITUATION) & (t.p_sr > 100 * t.p_sit_rpb))
    # team-relative standout: own pressure SR minus team-mates' pressure SR, same innings
    tm = t.groupby(["match_id", "innings"])[["p_runs", "p_balls", "p_contrib"]].transform("sum")
    mates_b = tm.p_balls - t.p_balls
    t["mates_p_sr"] = np.where(mates_b >= 6, 100 * (tm.p_runs - t.p_runs) / mates_b.clip(lower=1), np.nan)
    t["standout"] = t.p_sr - t.mates_p_sr
    t["team_p_run_share"] = np.where(tm.p_runs > 0, t.p_runs / tm.p_runs.clip(lower=1), np.nan)
    return t


# ======================================================================= bowling
def bowler_spells(b, flag):
    d = b.copy()
    d["p"] = flag
    d["legal"] = d.is_legal.astype(int)
    d["wkt"] = d.bowler_wicket.astype(int)
    d["dot"] = d.is_dot_bowl.astype(int)
    d["bnd"] = d.is_boundary.astype(int)
    d["wpa_bowl"] = -d.wpa_bat
    d["cw"] = (d.bowl_pi / 100) ** 2
    keys = ["match_id", "bowler_id"]

    def agg(x, pre):
        g = x.groupby(keys)
        return pd.DataFrame({f"{pre}balls": g.legal.sum(), f"{pre}deliv": g.size(),
                             f"{pre}runs": g.bowler_runs.sum(), f"{pre}wkts": g.wkt.sum(),
                             f"{pre}dots": g.dot.sum(), f"{pre}bnd": g.bnd.sum(),
                             f"{pre}contrib": g.bowl_contrib.sum(), f"{pre}xr": g.x_runs_bowl.sum(),
                             f"{pre}xw": g.x_wkt_bowl.sum(), f"{pre}wpa": g.wpa_bowl.sum()})
    allv, pv, nv = agg(d, ""), agg(d[d.p], "p_"), agg(d[~d.p], "n_")
    gc = d.groupby(keys)
    clutch = pd.DataFrame({"clutch_num": (d.cw * d.bowl_contrib).groupby([d[k] for k in keys]).sum(),
                           "clutch_den": gc.cw.sum()})
    info = gc.agg(bowler_name=("bowler_name", "first"), team=("bowling_team", "first"),
                  opp=("batting_team", "first"), comp_type=("comp_type", "first"),
                  comp_name=("comp_name", "first"), year=("year", "first"),
                  match_date=("match_date", "first"), is_knockout=("is_knockout", "first"),
                  stage=("stage", "first"), venue_country=("venue_country", "first"),
                  innings=("innings", "first"), bowling_type=("bowling_type", "first"),
                  team_won=("bat_won", lambda s: 1 - s.iloc[0] if pd.notna(s.iloc[0]) else np.nan),
                  is_dls=("is_dls", "first"))
    t = info.join([allv, pv, nv, clutch]).fillna(
        {c: 0 for c in list(pv.columns) + list(nv.columns)}).reset_index()
    t["p_econ"] = np.where(t.p_balls > 0, 6 * t.p_runs / t.p_balls.clip(lower=1), np.nan)
    t["p_dot_pct"] = np.where(t.p_balls > 0, t.p_dots / t.p_balls.clip(lower=1), np.nan)
    t["is_p_spell"] = (t.p_balls >= C.BOWL_MIN_PRESSURE_BALLS_SPELL) | (t.p_wkts > 0)
    t["wicket_spell"] = t.p_wkts >= 1
    t["impact"] = t.p_wkts >= C.BOWL_IMPACT_WKTS
    t["dot_reliable"] = t.p_dot_pct >= C.DOT_THRESHOLD
    t["qualifying"] = t.wicket_spell | t.dot_reliable
    tm = t.groupby(["match_id", "team"])[["p_runs", "p_balls", "p_wkts"]].transform("sum")
    mb = tm.p_balls - t.p_balls
    t["mates_p_econ"] = np.where(mb >= 12, 6 * (tm.p_runs - t.p_runs) / mb.clip(lower=1), np.nan)
    t["standout"] = t.mates_p_econ - t.p_econ
    t["team_p_wkt_share"] = np.where(tm.p_wkts > 0, t.p_wkts / tm.p_wkts.clip(lower=1), np.nan)
    return t


def set_dot_threshold(spells, thr):
    s = spells.copy()
    s["dot_reliable"] = s.p_dot_pct >= thr
    s["qualifying"] = s.wicket_spell | s.dot_reliable
    return s


# ================================================================ aggregation
def _cv_stability(x):
    x = np.asarray(x, float)
    if len(x) < 2 or np.nanmean(x) <= 0:
        return 0.0
    return float(1 / (1 + np.nanstd(x) / np.nanmean(x)))


def aggregate_batters(t):
    pi = t[t.is_p_innings].copy()
    pi["w"] = np.where(pi.is_knockout, C.KNOCKOUT_INNINGS_WEIGHT, 1.0)
    pi["w_imp"] = pi.w * pi.impact
    pi["w_qual"] = pi.w * pi.qualifying
    g = pi.groupby("striker_id")
    a = pd.DataFrame({
        "n_pinn": g.size(), "w_sum": g.w.sum(),
        "impact_n": g.impact.sum(), "qual_n": g.qualifying.sum(),
        "impact_rate": g.w_imp.sum() / g.w.sum(), "qual_rate": g.w_qual.sum() / g.w.sum(),
        "stability_raw": g.p_runs.apply(_cv_stability),
        "standout_raw": g.apply(lambda x: np.average(x.standout.dropna(), weights=x.loc[x.standout.notna(), "p_balls"])
                                if x.standout.notna().any() else np.nan, include_groups=False),
        "standout_n": g.standout.count(),
        "team_p_run_share": g.team_p_run_share.mean(),
    })
    ga = t.groupby("striker_id")
    s = ga[["runs", "balls", "out", "dots", "bnd", "contrib", "wpa", "p_runs", "p_balls", "p_out",
            "p_dots", "p_bnd", "p_contrib", "p_wpa", "p_xr", "n_runs", "n_balls", "n_out",
            "n_dots", "n_bnd", "n_contrib", "clutch_num", "clutch_den"]].sum()
    s["matches"] = ga.match_id.nunique()
    s["innings"] = ga.size()
    s["name"] = ga.striker_name.first()
    s["last_team"] = t.sort_values("match_date").groupby("striker_id").team.last()
    s["last_year"] = ga.year.max()
    s["years"] = ga.year.apply(lambda y: ",".join(str(v) for v in sorted(set(y))))
    s["comp_types"] = ga.comp_type.apply(lambda y: ", ".join(sorted(set(y))))
    ko = t[t.is_knockout].groupby("striker_id")
    s["ko_innings"] = ko.size()
    s["ko_runs"] = ko.runs.sum()
    s["ko_contrib"] = ko.contrib.sum()
    s["ko_wpa"] = ko.wpa.sum()
    form = t[t.year >= 2025].groupby("striker_id")
    s["form_p_contrib"] = form.p_contrib.sum()
    s["form_p_balls"] = form.p_balls.sum()
    a = s.join(a, how="left")
    a["n_pinn"] = a.n_pinn.fillna(0)
    a["ko_innings"] = a.ko_innings.fillna(0)
    for c in ["ko_runs", "ko_contrib", "ko_wpa"]:
        a[c] = a[c].fillna(0)
    a["p_sr"] = 100 * a.p_runs / a.p_balls.clip(lower=1)
    a["n_sr"] = 100 * a.n_runs / a.n_balls.clip(lower=1)
    a["sr"] = 100 * a.runs / a.balls.clip(lower=1)
    a["p_avg"] = a.p_runs / a.p_out.clip(lower=1)
    a["n_avg"] = a.n_runs / a.n_out.clip(lower=1)
    a["avg"] = a.runs / a.out.clip(lower=1)
    a["p_dot_pct"] = 100 * a.p_dots / a.p_balls.clip(lower=1)
    a["n_dot_pct"] = 100 * a.n_dots / a.n_balls.clip(lower=1)
    a["p_bnd_pct"] = 100 * a.p_bnd / a.p_balls.clip(lower=1)
    a["n_bnd_pct"] = 100 * a.n_bnd / a.n_balls.clip(lower=1)
    a["p_out_rate"] = a.p_out / a.p_balls.clip(lower=1)
    a["n_out_rate"] = a.n_out / a.n_balls.clip(lower=1)
    a["pc_per_ball"] = a.p_contrib / a.p_balls.clip(lower=1)
    a["nc_per_ball"] = a.n_contrib / a.n_balls.clip(lower=1)
    a["clutch"] = 100 * a.clutch_num / a.clutch_den.clip(lower=1e-9)
    a["form_pc_per_ball"] = a.form_p_contrib / a.form_p_balls.clip(lower=1)
    a["wpa_per_pinn"] = 100 * a.p_wpa / a.n_pinn.clip(lower=1)
    a.index.name = "player_id"
    return a.reset_index()


def aggregate_bowlers(t):
    ps = t[t.is_p_spell].copy()
    ps["w"] = np.where(ps.is_knockout, C.KNOCKOUT_INNINGS_WEIGHT, 1.0)
    for c in ["wicket_spell", "impact", "dot_reliable", "qualifying"]:
        ps[f"w_{c}"] = ps.w * ps[c]
    g = ps.groupby("bowler_id")
    a = pd.DataFrame({
        "n_pspells": g.size(), "w_sum": g.w.sum(),
        "wicket_rate": g.w_wicket_spell.sum() / g.w.sum(),
        "impact_rate": g.w_impact.sum() / g.w.sum(),
        "dot_rate": g.w_dot_reliable.sum() / g.w.sum(),
        "qual_rate": g.w_qualifying.sum() / g.w.sum(),
        "impact_n": g.impact.sum(), "wicket_spell_n": g.wicket_spell.sum(),
        "qual_n": g.qualifying.sum(),
        "econ_sd": g.apply(lambda x: float(np.nanstd(x.loc[x.p_balls >= 6, "p_econ"]))
                           if (x.p_balls >= 6).sum() >= 2 else np.nan, include_groups=False),
        "standout_raw": g.apply(lambda x: np.average(x.standout.dropna(), weights=x.loc[x.standout.notna(), "p_balls"])
                                if x.standout.notna().any() else np.nan, include_groups=False),
        "standout_n": g.standout.count(),
        "team_p_wkt_share": g.team_p_wkt_share.mean(),
    })
    # stability: low spread of pressure economy, scaled by the POOL mean economy
    # (dividing by the bowler's own mean would flatter expensive bowlers)
    pool_econ = 6 * ps.p_runs.sum() / max(ps.p_balls.sum(), 1)
    a["stability_raw"] = 1 / (1 + a.econ_sd.fillna(a.econ_sd.median()) / pool_econ)
    ga = t.groupby("bowler_id")
    s = ga[["balls", "runs", "wkts", "dots", "bnd", "contrib", "wpa", "p_balls", "p_runs", "p_wkts",
            "p_dots", "p_bnd", "p_contrib", "p_wpa", "p_xr", "p_xw", "n_balls", "n_runs", "n_wkts",
            "n_dots", "n_bnd", "n_contrib", "clutch_num", "clutch_den"]].sum()
    s["matches"] = ga.match_id.nunique()
    s["name"] = ga.bowler_name.first()
    s["bowling_type"] = ga.bowling_type.first()
    s["last_team"] = t.sort_values("match_date").groupby("bowler_id").team.last()
    s["last_year"] = ga.year.max()
    s["years"] = ga.year.apply(lambda y: ",".join(str(v) for v in sorted(set(y))))
    s["comp_types"] = ga.comp_type.apply(lambda y: ", ".join(sorted(set(y))))
    ko = t[t.is_knockout].groupby("bowler_id")
    s["ko_innings"] = ko.size()
    s["ko_wkts"] = ko.wkts.sum()
    s["ko_contrib"] = ko.contrib.sum()
    s["ko_wpa"] = ko.wpa.sum()
    form = t[t.year >= 2025].groupby("bowler_id")
    s["form_p_contrib"] = form.p_contrib.sum()
    s["form_p_balls"] = form.p_balls.sum()
    a = s.join(a, how="left")
    a["n_pspells"] = a.n_pspells.fillna(0)
    a["ko_innings"] = a.ko_innings.fillna(0)
    for c in ["ko_wkts", "ko_contrib", "ko_wpa"]:
        a[c] = a[c].fillna(0)
    a["overs"] = a.balls / 6
    a["p_overs"] = a.p_balls / 6
    a["econ"] = 6 * a.runs / a.balls.clip(lower=1)
    a["p_econ"] = 6 * a.p_runs / a.p_balls.clip(lower=1)
    a["n_econ"] = 6 * a.n_runs / a.n_balls.clip(lower=1)
    a["p_dot_pct"] = 100 * a.p_dots / a.p_balls.clip(lower=1)
    a["n_dot_pct"] = 100 * a.n_dots / a.n_balls.clip(lower=1)
    a["p_wpb"] = a.p_wkts / a.p_balls.clip(lower=1)
    a["n_wpb"] = a.n_wkts / a.n_balls.clip(lower=1)
    a["p_bowl_sr"] = a.p_balls / a.p_wkts.clip(lower=1)
    a["n_bowl_sr"] = a.n_balls / a.n_wkts.clip(lower=1)
    a["p_bnd_pct"] = 100 * a.p_bnd / a.p_balls.clip(lower=1)
    a["pc_per_ball"] = a.p_contrib / a.p_balls.clip(lower=1)
    a["nc_per_ball"] = a.n_contrib / a.n_balls.clip(lower=1)
    a["clutch"] = 100 * a.clutch_num / a.clutch_den.clip(lower=1e-9)
    a["form_pc_per_ball"] = a.form_p_contrib / a.form_p_balls.clip(lower=1)
    a["wpa_per_pspell"] = 100 * a.p_wpa / a.n_pspells.clip(lower=1)
    a.index.name = "player_id"
    return a.reset_index()


# ==================================================================== rating
def _shrink(x, n, m, mu):
    x = np.where(np.isfinite(x), x, mu)
    return (n * x + m * mu) / (n + m)


def _z(x):
    x = np.asarray(x, float)
    sd = np.nanstd(x)
    return (x - np.nanmean(x)) / (sd if sd > 0 else 1)


def _score(z):
    return 100 * norm.cdf(z)


def rate_batters(a, eligible_mask, weights=None):
    """Return component scores (0-100) and composite rating for eligible batters."""
    w = weights or C.BAT_WEIGHTS
    e = a[eligible_mask].copy()
    n, nb = e.n_pinn.values, e.p_balls.values
    mI, mB, mK = C.PRIOR_INNINGS, C.PRIOR_BALLS, C.PRIOR_KO

    e["impact_rate_s"] = _shrink(e.impact_rate, n, mI, e.impact_rate.mean())
    e["qual_rate_s"] = _shrink(e.qual_rate, n, mI, e.qual_rate.mean())
    e["stability_s"] = _shrink(e.stability_raw, n, mI, e.stability_raw.mean())
    cons = 0.4 * _z(e.impact_rate_s) + 0.4 * _z(e.qual_rate_s) + 0.2 * _z(e.stability_s)

    e["pc_per_ball_s"] = _shrink(e.pc_per_ball, nb, mB, e.pc_per_ball.mean())
    e["clutch_s"] = _shrink(e.clutch, e.balls.values, mB, e.clutch.mean())
    contrib = 0.5 * _z(e.pc_per_ball_s) + 0.5 * _z(e.clutch_s)

    ctx = e.pc_per_ball - e.nc_per_ball
    srd = e.p_sr - e.n_sr
    outd = e.n_out_rate - e.p_out_rate
    e["delta_ctx_s"] = _shrink(ctx, nb, mB, ctx.mean())
    e["delta_sr_s"] = _shrink(srd, nb, mB, srd.mean())
    e["delta_out_s"] = _shrink(outd, nb, mB, outd.mean())
    delta = (_z(e.delta_ctx_s) + _z(e.delta_sr_s) + _z(e.delta_out_s)) / 3

    e["wpa_s"] = _shrink(e.wpa_per_pinn, n, mI, e.wpa_per_pinn.mean())
    e["standout_s"] = _shrink(e.standout_raw, e.standout_n.fillna(0).values, mI, np.nanmean(e.standout_raw))
    ko_n = e.ko_innings.values
    ko_val = np.where(ko_n > 0, e.ko_contrib / np.maximum(ko_n, 1), 0)
    ko_w = np.where(ko_n > 0, 100 * e.ko_wpa / np.maximum(ko_n, 1), 0)
    e["ko_s"] = 0.5 * _z(_shrink(ko_val, ko_n, mK, 0)) + 0.5 * _z(_shrink(ko_w, ko_n, mK, 0))

    comps = {"consistency": cons, "contribution": contrib, "delta": delta,
             "wpa": _z(e.wpa_s), "standout": _z(e.standout_s), "knockout": e.ko_s.values}
    for k, v in comps.items():
        e[f"score_{k}"] = _score(_z(v))
    e["rating"] = sum(e[f"score_{k}"] * w[k] for k in w)
    e = e.sort_values(["rating", "form_pc_per_ball"], ascending=False)
    e["rank"] = np.arange(1, len(e) + 1)
    return e


def rate_bowlers(a, eligible_mask, weights=None):
    w = weights or C.BOWL_WEIGHTS
    e = a[eligible_mask].copy()
    n, nb = e.n_pspells.values, e.p_balls.values
    mI, mB, mK = C.PRIOR_INNINGS, C.PRIOR_BALLS, C.PRIOR_KO
    for c in ["wicket_rate", "impact_rate", "dot_rate", "qual_rate", "stability_raw"]:
        e[f"{c}_s"] = _shrink(e[c], n, mI, e[c].mean())
    cons = (0.25 * _z(e.wicket_rate_s) + 0.15 * _z(e.impact_rate_s) + 0.20 * _z(e.dot_rate_s)
            + 0.20 * _z(e.qual_rate_s) + 0.20 * _z(e.stability_raw_s))

    e["pc_per_ball_s"] = _shrink(e.pc_per_ball, nb, mB, e.pc_per_ball.mean())
    e["clutch_s"] = _shrink(e.clutch, e.balls.values, mB, e.clutch.mean())
    contrib = 0.5 * _z(e.pc_per_ball_s) + 0.5 * _z(e.clutch_s)

    ctx = e.pc_per_ball - e.nc_per_ball
    econd = e.n_econ - e.p_econ
    dotd = e.p_dot_pct - e.n_dot_pct
    wkd = e.p_wpb - e.n_wpb
    e["delta_ctx_s"] = _shrink(ctx, nb, mB, ctx.mean())
    e["delta_econ_s"] = _shrink(econd, nb, mB, econd.mean())
    e["delta_dot_s"] = _shrink(dotd, nb, mB, dotd.mean())
    e["delta_wkt_s"] = _shrink(wkd, nb, mB, wkd.mean())
    delta = (_z(e.delta_ctx_s) + _z(e.delta_econ_s) + _z(e.delta_dot_s) + _z(e.delta_wkt_s)) / 4

    e["wpa_s"] = _shrink(e.wpa_per_pspell, n, mI, e.wpa_per_pspell.mean())
    e["standout_s"] = _shrink(e.standout_raw, e.standout_n.fillna(0).values, mI, np.nanmean(e.standout_raw))
    ko_n = e.ko_innings.values
    ko_val = np.where(ko_n > 0, e.ko_contrib / np.maximum(ko_n, 1), 0)
    ko_w = np.where(ko_n > 0, 100 * e.ko_wpa / np.maximum(ko_n, 1), 0)
    e["ko_s"] = 0.5 * _z(_shrink(ko_val, ko_n, mK, 0)) + 0.5 * _z(_shrink(ko_w, ko_n, mK, 0))

    comps = {"consistency": cons, "contribution": contrib, "delta": delta,
             "wpa": _z(e.wpa_s), "standout": _z(e.standout_s), "knockout": e.ko_s.values}
    for k, v in comps.items():
        e[f"score_{k}"] = _score(_z(v))
    e["rating"] = sum(e[f"score_{k}"] * w[k] for k in w)
    e = e.sort_values(["rating", "form_pc_per_ball"], ascending=False)
    e["rank"] = np.arange(1, len(e) + 1)
    return e
