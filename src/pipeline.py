"""End-to-end pipeline: raw CSVs -> master file -> pressure engine -> ratings ->
reliability checks -> every output the dashboard reads.

Run:  python -m src.pipeline            (full, ~5-8 minutes)
      python -m src.pipeline --quick    (fewer bootstrap draws)
"""
import argparse
import faulthandler
import json
import sys
import time

import numpy as np
import pandas as pd
from scipy.stats import spearmanr

from . import config as C
from . import data_prep, expected, features, metrics, models, pressure, state


def log(msg, t0=[time.time()]):
    print(f"[{time.time() - t0[0]:6.1f}s] {msg}", flush=True)


# ------------------------------------------------------------------ helpers
def eligibility(ab, aw, reg, active=True, exclude_pak=True):
    pak = set(reg.loc[reg.is_pakistan, "player_id"])
    eb = (ab.n_pinn >= C.BAT_MIN_PRESSURE_INNINGS) & (ab.p_balls >= C.BAT_MIN_PRESSURE_BALLS)
    ew = (aw.n_pspells >= C.BOWL_MIN_PRESSURE_SPELLS) & (aw.p_balls >= C.BOWL_MIN_PRESSURE_BALLS)
    if active:
        eb &= ab.last_year >= C.ACTIVE_YEAR
        ew &= aw.last_year >= C.ACTIVE_YEAR
    if exclude_pak:
        eb &= ~ab.player_id.isin(pak)
        ew &= ~aw.player_id.isin(pak)
    return eb, ew


def build_tables(b, threshold=C.PRESSURE_THRESHOLD, knockout_rule=True, dot=C.DOT_THRESHOLD):
    fb, fw = pressure.pressure_flags(b, threshold, knockout_rule)
    bi = metrics.batter_innings(b, fb)
    bs = metrics.set_dot_threshold(metrics.bowler_spells(b, fw), dot)
    return fb, fw, bi, bs, metrics.aggregate_batters(bi), metrics.aggregate_bowlers(bs)


def rank(ab, aw, reg, weights=None):
    eb, ew = eligibility(ab, aw, reg)
    return metrics.rate_batters(ab, eb, weights), metrics.rate_bowlers(aw, ew, weights)


def compare(base, alt, key="player_id"):
    m = base[[key, "rank"]].merge(alt[[key, "rank"]], on=key, suffixes=("", "_alt"))
    rho = spearmanr(m["rank"], m["rank_alt"]).statistic if len(m) > 2 else np.nan
    top_b = set(base.nsmallest(10, "rank")[key])
    top_a = set(alt.nsmallest(10, "rank")[key])
    return float(rho), len(top_b & top_a)


# ---------------------------------------------------------------- bootstrap
def bootstrap(bi, bs, ab_base, aw_base, rb, rw, n_boot):
    eb_ids, ew_ids = set(rb.player_id), set(rw.player_id)
    bi_e = bi[bi.striker_id.isin(eb_ids)]
    bs_e = bs[bs.bowler_id.isin(ew_ids)]
    rec_b, rec_w = [], []
    rng = np.random.default_rng(C.RANDOM_STATE)
    for r in range(n_boot):
        sb = bi_e.groupby("striker_id", group_keys=False).sample(frac=1, replace=True, random_state=rng.integers(1e9))
        sw = bs_e.groupby("bowler_id", group_keys=False).sample(frac=1, replace=True, random_state=rng.integers(1e9))
        ab = metrics.aggregate_batters(sb)
        aw = metrics.aggregate_bowlers(sw)
        xb = metrics.rate_batters(ab, ab.player_id.isin(eb_ids))
        xw = metrics.rate_bowlers(aw, aw.player_id.isin(ew_ids))
        rec_b.append(xb[["player_id", "rating", "rank"]].assign(draw=r))
        rec_w.append(xw[["player_id", "rating", "rank"]].assign(draw=r))

    def summ(rec):
        d = pd.concat(rec)
        g = d.groupby("player_id")
        return pd.DataFrame({
            "boot_rating_mean": g.rating.mean(), "rating_lo": g.rating.quantile(0.05),
            "rating_hi": g.rating.quantile(0.95), "rank_lo": g["rank"].quantile(0.05),
            "rank_hi": g["rank"].quantile(0.95), "rank_median": g["rank"].median(),
            "p_top10": g["rank"].apply(lambda r: (r <= 10).mean()),
            "p_top20": g["rank"].apply(lambda r: (r <= 20).mean())}).reset_index()
    return summ(rec_b), summ(rec_w)


def reliability_label(row):
    """High: in the bootstrap top 10 at least half the time AND never worse than
    15th in any sensitivity scenario. Medium: P(top 10) >= 25% or worst scenario
    rank <= 20. Low: otherwise (rank driven by a thin or fragile sample)."""
    if row.p_top10 >= 0.5 and row.scen_rank_worst <= 15:
        return "High"
    if row.p_top10 >= 0.25 or row.scen_rank_worst <= 20:
        return "Medium"
    return "Low"


# ------------------------------------------------------------------- main
def main(n_boot=C.N_BOOTSTRAP):
    C.OUT.mkdir(parents=True, exist_ok=True)
    C.PROCESSED.mkdir(parents=True, exist_ok=True)

    log("1/8 load, clean, validate, merge")
    master, matches, reg, d, qlog = data_prep.run()

    log("2/8 ball-by-ball match state")
    b = state.add_state(master)

    log("3/8 resource table + win probability (cross-fitted)")
    rm = models.ResourceModel().fit(b)
    b = models.add_resource_features(b, rm)
    b, wp_metrics = models.fit_win_probability(b, rm)

    log("4/8 batting & bowling pressure indices")
    b = pressure.add_pressure(b)
    validation = pressure.validate_index(b)

    log("5/8 pre-match form + expected performance models (cross-fitted)")
    b = expected.add_prematch_form(b)
    b = expected.add_expected(b)

    log("6/8 innings/spell tables, consistency, ratings")
    fb, fw, bi, bs, ab, aw = build_tables(b)
    b["bat_pressure_ball"], b["bowl_pressure_ball"] = fb, fw
    rb, rw = rank(ab, aw, reg)

    log(f"7/8 reliability: bootstrap x{n_boot} + sensitivity scenarios")
    bb, bw = bootstrap(bi, bs, ab, aw, rb, rw, n_boot)
    rb = rb.merge(bb, on="player_id", how="left")
    rw = rw.merge(bw, on="player_id", how="left")

    sens_rows, sens_ranks_b, sens_ranks_w = [], [rb[["player_id", "rank"]].assign(scenario="Base")], \
        [rw[["player_id", "rank"]].assign(scenario="Base")]

    def record(name, group, xb, xw):
        rho_b, ov_b = compare(rb, xb)
        rho_w, ov_w = compare(rw, xw)
        sens_rows.append({"scenario": name, "group": group, "bat_spearman": rho_b, "bat_top10_overlap": ov_b,
                          "bowl_spearman": rho_w, "bowl_top10_overlap": ov_w,
                          "bat_top10": " | ".join(xb.nsmallest(10, "rank").name),
                          "bowl_top10": " | ".join(xw.nsmallest(10, "rank").name),
                          "eligible_batters": len(xb), "eligible_bowlers": len(xw)})
        sens_ranks_b.append(xb[["player_id", "rank"]].assign(scenario=name))
        sens_ranks_w.append(xw[["player_id", "rank"]].assign(scenario=name))

    for name, w in C.WEIGHT_SCENARIOS.items():
        if w is None:
            continue
        xb, xw = rank(ab, aw, reg, w)
        record(name, "Weights", xb, xw)
    for thr in C.SENSITIVITY_THRESHOLDS:
        if thr == C.PRESSURE_THRESHOLD:
            continue
        *_, xab, xaw = build_tables(b, threshold=thr)
        xb, xw = rank(xab, xaw, reg)
        record(f"Pressure threshold {thr}", "Pressure definition", xb, xw)
    *_, xab, xaw = build_tables(b, knockout_rule=False)
    xb, xw = rank(xab, xaw, reg)
    record("Knockout full-match rule OFF", "Pressure definition", xb, xw)
    for dot in C.SENSITIVITY_DOT:
        if dot == C.DOT_THRESHOLD:
            continue
        *_, xab, xaw = build_tables(b, dot=dot)
        xb, xw = rank(xab, xaw, reg)
        record(f"Dot-ball threshold {int(dot * 100)}%", "Consistency rule", xb, xw)
    nd = b[~b.is_dls].reset_index(drop=True)
    *_, xab, xaw = build_tables(nd)
    xb, xw = rank(xab, xaw, reg)
    record("Exclude DLS-shortened matches", "Data scope", xb, xw)
    for ct in ["IPL", "T20I"]:
        sub = b[b.comp_type == ct].reset_index(drop=True)
        *_, xab, xaw = build_tables(sub)
        xb, xw = rank(xab, xaw, reg)
        record(f"{ct} matches only", "Data scope", xb, xw)

    sens = pd.DataFrame(sens_rows)
    srb = pd.concat(sens_ranks_b).pivot_table(index="player_id", columns="scenario", values="rank")
    srw = pd.concat(sens_ranks_w).pivot_table(index="player_id", columns="scenario", values="rank")
    def add_scen(r, sr):
        st = pd.DataFrame({"scen_rank_median": sr.median(axis=1), "scen_rank_best": sr.min(axis=1),
                           "scen_rank_worst": sr.max(axis=1),
                           "scen_top10_share": (sr <= 10).sum(axis=1) / sr.notna().sum(axis=1)})
        return r.merge(st, left_on="player_id", right_index=True, how="left")
    rb, rw = add_scen(rb, srb), add_scen(rw, srw)
    rb["reliability"] = rb.apply(reliability_label, axis=1)
    rw["reliability"] = rw.apply(reliability_label, axis=1)

    log("8/8 feature tables + write outputs")
    bz = features.bat_zones(b, fb)
    wz = features.bowl_zones(b, fw)
    wk = features.wickets_table(b, fb, fw)
    mu = features.matchups(b, fb)
    ov = features.over_sequence(b, fw)
    bounce = features.bounce_back(ov)
    aw = aw.merge(bounce, on="player_id", how="left")
    rw = rw.merge(bounce, on="player_id", how="left")

    # player registry + all-player career tables (overall explorer keeps everyone)
    reg = reg.copy()
    pak = set(reg.loc[reg.is_pakistan, "player_id"])
    for a in (ab, aw):
        a["is_pakistan"] = a.player_id.isin(pak)
        a["active_2026"] = a.last_year >= C.ACTIVE_YEAR
    eb, ew = eligibility(ab, aw, reg)
    ab["pressure_eligible"], aw["pressure_eligible"] = eb.values, ew.values
    eb0, ew0 = eligibility(ab, aw, reg, active=False, exclude_pak=False)
    ab["sample_eligible"], aw["sample_eligible"] = eb0.values, ew0.values

    # ---- write
    b.to_parquet(C.PROCESSED / "master_ball_by_ball.parquet", index=False)
    b.to_csv(C.PROCESSED / "master_ball_by_ball.csv.gz", index=False, compression="gzip")
    light = ["match_id", "innings", "overid", "over_ball_num", "phase", "year", "comp_type", "comp_name",
             "stage", "is_knockout", "is_dls", "batting_team", "bowling_team", "striker_id", "striker_name",
             "bowler_id", "bowler_name", "runs", "bowler_runs", "team_runs", "is_legal", "faced",
             "is_dot_bat", "is_dot_bowl", "is_boundary", "striker_out", "bowler_wicket",
             "balls_rem", "wkts_before", "runs_req", "rrr", "crr", "z_chase", "z_par", "wp_before",
             "wpa_bat", "bat_pi", "bowl_pi", "bat_level", "bowl_level", "bat_pressure_ball",
             "bowl_pressure_ball", "bat_contrib", "bowl_contrib", "rr12", "batting_order", "pace_or_spin",
             "match_date", "striker_balls_before", "part_runs"] + [c for c in b.columns if c.startswith(("bpc_", "wpc_"))]
    b[light].to_parquet(C.OUT / "balls_light.parquet", index=False)
    matches.to_parquet(C.OUT / "matches.parquet", index=False)
    reg.to_parquet(C.OUT / "player_registry.parquet", index=False)
    bi.to_parquet(C.OUT / "batter_innings.parquet", index=False)
    bs.to_parquet(C.OUT / "bowler_spells.parquet", index=False)
    ab.to_parquet(C.OUT / "batters_all.parquet", index=False)
    aw.to_parquet(C.OUT / "bowlers_all.parquet", index=False)
    rb.to_parquet(C.OUT / "batter_rankings.parquet", index=False)
    rw.to_parquet(C.OUT / "bowler_rankings.parquet", index=False)
    bz.to_parquet(C.OUT / "bat_zones.parquet", index=False)
    wz.to_parquet(C.OUT / "bowl_zones.parquet", index=False)
    wk.to_parquet(C.OUT / "wickets.parquet", index=False)
    mu.to_parquet(C.OUT / "matchups.parquet", index=False)
    ov.to_parquet(C.OUT / "over_sequence.parquet", index=False)
    sens.to_parquet(C.OUT / "sensitivity.parquet", index=False)
    srb.reset_index().to_parquet(C.OUT / "sensitivity_ranks_bat.parquet", index=False)
    srw.reset_index().to_parquet(C.OUT / "sensitivity_ranks_bowl.parquet", index=False)
    rm.table().to_parquet(C.OUT / "resource_table.parquet", index=False)
    validation["by_level"].to_parquet(C.OUT / "validation_by_level.parquet", index=False)

    top_cols_b = ["rank", "name", "last_team", "matches", "n_pinn", "p_balls", "p_runs", "p_sr", "n_sr",
                  "impact_rate", "qual_rate", "pc_per_ball", "wpa_per_pinn", "rating", "rating_lo",
                  "rating_hi", "p_top10", "reliability"]
    top_cols_w = ["rank", "name", "last_team", "matches", "n_pspells", "p_overs", "p_wkts", "p_econ",
                  "n_econ", "wicket_rate", "impact_rate", "dot_rate", "pc_per_ball", "wpa_per_pspell",
                  "rating", "rating_lo", "rating_hi", "p_top10", "reliability"]
    rb.head(10)[top_cols_b].to_csv(C.OUT / "FINAL_TOP10_BATTERS.csv", index=False)
    rw.head(10)[top_cols_w].to_csv(C.OUT / "FINAL_TOP10_BOWLERS.csv", index=False)
    rb[top_cols_b].to_csv(C.OUT / "batter_rankings_full.csv", index=False)
    rw[top_cols_w].to_csv(C.OUT / "bowler_rankings_full.csv", index=False)

    summary = {
        "data_quality": qlog,
        "win_probability_model": wp_metrics,
        "resource_model_training_balls": rm.train_rows,
        "pressure_validation": {k: v for k, v in validation.items() if k != "by_level"},
        "pressure_share": {"bat_pressure_balls": float(fb.mean()), "bowl_pressure_balls": float(fw.mean())},
        "counts": {"matches": int(b.match_id.nunique()), "deliveries": int(len(b)),
                   "batters": int(b.striker_id.nunique()), "bowlers": int(b.bowler_id.nunique()),
                   "players": int(pd.unique(pd.concat([b.striker_id, b.bowler_id])).size),
                   "eligible_batters": int(len(rb)), "eligible_bowlers": int(len(rw)),
                   "sample_eligible_batters": int(ab.sample_eligible.sum()),
                   "sample_eligible_bowlers": int(aw.sample_eligible.sum()),
                   "excluded_pakistan_players": int(len(pak)),
                   "knockout_matches": int(b[b.is_knockout].match_id.nunique()),
                   "dls_matches": int(b[b.is_dls].match_id.nunique())},
        "config": {k: getattr(C, k) for k in dir(C) if k.isupper() and not k.startswith(("ROOT", "RAW", "PROC", "OUT"))},
        "n_bootstrap": n_boot,
        "generated": time.strftime("%Y-%m-%d %H:%M"),
    }
    with open(C.OUT / "summary.json", "w", encoding="utf-8") as f:
        json.dump(summary, f, indent=2, default=lambda o: list(o) if isinstance(o, set) else str(o))
    log("IPL 2027 auction module (retention status, RR needs, targets)")
    try:
        from . import auction
    except ImportError as e:
        print(f"         - skipped: {e}. Copy src/auction.py and src/ipl2027_data.py to enable it.", flush=True)
    else:
        auction.build()
    log("done")
    print("\nTOP 10 BATTERS\n", rb.head(10)[["rank", "name", "rating", "rating_lo", "rating_hi", "p_top10"]].to_string(index=False))
    print("\nTOP 10 BOWLERS\n", rw.head(10)[["rank", "name", "rating", "rating_lo", "rating_hi", "p_top10"]].to_string(index=False))
    return summary


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--quick", action="store_true")
    args = ap.parse_args()
    # If Python itself crashes (native code in pandas/pyarrow/scikit-learn), print where;
    # if a step appears stuck, print where it is every 5 minutes.
    C.OUT.mkdir(parents=True, exist_ok=True)
    faulthandler.enable(file=sys.stderr, all_threads=False)
    faulthandler.dump_traceback_later(300, repeat=True, file=sys.stderr)
    try:
        from . import preflight
    except ImportError:
        preflight = None  # older copies of the project have no preflight.py
    if preflight is not None and preflight.check(verbose=False):
        preflight.check(verbose=True)
        raise SystemExit("\nFix the problems above, then run the pipeline again.")
    try:
        main(n_boot=40 if args.quick else C.N_BOOTSTRAP)
    except BaseException as e:  # write a shareable log for any failure
        import platform
        import traceback
        if isinstance(e, SystemExit) and not e.code:
            raise
        C.OUT.mkdir(parents=True, exist_ok=True)
        err = C.OUT / "pipeline_error.log"
        tips = {
            "MemoryError": "Not enough RAM: close other apps, or use 64-bit Python with 8 GB+ RAM.",
            "ModuleNotFoundError": "Run: python -m pip install -r requirements.txt",
            "ImportError": "Run: python -m pip install --upgrade -r requirements.txt",
            "FileNotFoundError": "Run: python -m src.preflight to see which file is missing.",
            "PermissionError": "Close any file open in Excel, or move the project out of OneDrive.",
            "KeyboardInterrupt": "Stopped by Ctrl+C. The full run takes 5-15 minutes; let it finish.",
        }
        tip = tips.get(type(e).__name__, "Send outputs/pipeline_error.log for diagnosis.")
        import pandas, numpy, sklearn
        env = (f"Python {platform.python_version()} | {platform.platform()} | pandas {pandas.__version__} | "
               f"numpy {numpy.__version__} | scikit-learn {sklearn.__version__}")
        err.write_text(env + "\n\n" + traceback.format_exc(), encoding="utf-8")
        print(f"\nPIPELINE FAILED: {type(e).__name__}: {e}\nTip: {tip}\nFull log: {err}")
        raise SystemExit(1)
