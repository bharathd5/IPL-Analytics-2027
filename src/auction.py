"""IPL 2027 auction module: who is available, what Rajasthan Royals' retained squad
lacks under pressure, and which available players fill those gaps best.

Everything is computed from the same pressure outputs as the rankings. The only
external input is the retention-day status table in ``ipl2027_data``.

Run:  python -m src.auction      (after src.pipeline; takes a few seconds)
"""
import json

import numpy as np
import pandas as pd

from . import config as C
from . import ipl2027_data as D

TEAM = "Rajasthan Royals"
PHASES = ["Powerplay", "Middle", "Death"]
SPIN = ("break", "orthodox", "chinaman", "googly", "offbreak")
EXTRA_ALIASES = {"KL Rahul": "Lokesh Rahul", "Vijaykumar Vyshak": "Vyshak Kumar", "Will Jacks": "William Jacks",
                 "Pat Cummins": "Patrick Cummins", "Nitish Kumar Reddy": "Nitish Reddy",
                 "Tilak Varma": "Namboori Tilak Varma"}


# ------------------------------------------------------------------ name resolution
def _resolver(reg, ids_in_data):
    r = reg[reg.player_id.isin(ids_in_data)].copy()
    r["lname"] = r.player_name.str.lower()

    def resolve(name, team_hint=None):
        n = {**D.ALIASES, **EXTRA_ALIASES}.get(name, name).lower()
        m = r[r.lname == n]
        if len(m) > 1 and team_hint is not None:
            m2 = m[m.ipl_team == team_hint]
            m = m2 if len(m2) else m
        if len(m) >= 1:
            return int(m.player_id.iat[0])
        first, last = n.split()[0], n.split()[-1]
        m = r[(r.lname.str.split().str[-1] == last) & (r.lname.str.split().str[0].str[:3] == first[:3])]
        if len(m) == 1:
            return int(m.player_id.iat[0])
        return None
    return resolve


def status_table(reg, ab, aw):
    ids = set(ab.player_id) | set(aw.player_id)
    resolve = _resolver(reg, ids)
    rows = []
    for team, names in D.RETAINED.items():
        for n in names:
            rows.append(dict(report_name=n, status="Retained", team_2027=team, team_2026=None, player_id=resolve(n, team)))
    for team, names in D.RELEASED.items():
        for n in names:
            rows.append(dict(report_name=n, status="Released", team_2027=None, team_2026=team, player_id=resolve(n, team)))
    s = pd.DataFrame(rows)
    s["flag"] = s.report_name.map(lambda n: D.NOTES.get(n, ("", ""))[0])
    s["note"] = s.report_name.map(lambda n: D.NOTES.get(n, ("", ""))[1])
    s["last_contract_cr"] = s.report_name.map(D.LAST_CONTRACT_CR)
    # a player in both lists (Ghazanfar) keeps the conflict flag and is shown as released-but-disputed
    s = s.sort_values("status", ascending=False).drop_duplicates("report_name", keep="first")
    s["availability"] = np.select(
        [s.flag.eq("retired"), s.status.eq("Retained"), s.flag.eq("conflict") & s.status.eq("Released"),
         s.flag.eq("availability")],
        ["Not available (retired)", "Retained", "Released · disputed", "Released · availability doubtful"],
        default="Released")
    return s


# ------------------------------------------------------------------ squad needs
def _phase_tables(bz, wz, ids_bat, ids_bowl):
    zb = bz[(bz.dim == "phase") & (bz.pressure == "Pressure")]
    zw = wz[(wz.dim == "phase") & (wz.pressure == "Pressure")]
    pool_b = zb.groupby("value").apply(lambda x: 100 * x.runs.sum() / x.balls.sum(), include_groups=False)
    pool_w = zw.groupby("value").apply(lambda x: 6 * x.runs.sum() / x.balls.sum(), include_groups=False)
    sb = zb[zb.player_id.isin(ids_bat)].groupby("value").agg(runs=("runs", "sum"), balls=("balls", "sum"),
                                                              contrib=("contrib", "sum"), outs=("outs", "sum"))
    sw = zw[zw.player_id.isin(ids_bowl)].groupby("value").agg(runs=("runs", "sum"), balls=("balls", "sum"),
                                                               contrib=("contrib", "sum"), wkts=("wkts", "sum"))
    out = []
    for ph in PHASES:
        b = sb.loc[ph] if ph in sb.index else None
        w = sw.loc[ph] if ph in sw.index else None
        out.append(dict(
            phase=ph,
            bat_sr=100 * b.runs / b.balls if b is not None and b.balls else np.nan, pool_bat_sr=pool_b.get(ph, np.nan),
            bat_rae100=100 * b.contrib / b.balls if b is not None and b.balls else np.nan,
            bat_balls=int(b.balls) if b is not None else 0,
            bowl_econ=6 * w.runs / w.balls if w is not None and w.balls else np.nan, pool_bowl_econ=pool_w.get(ph, np.nan),
            bowl_saved100=100 * w.contrib / w.balls if w is not None and w.balls else np.nan,
            bowl_balls=int(w.balls) if w is not None else 0))
    return pd.DataFrame(out)


def player_phase(z, metric_dim="phase"):
    """Per-player pressure contribution per 100 balls by phase (pressure balls only)."""
    x = z[(z.dim == metric_dim) & (z.pressure == "Pressure")]
    x = x.assign(v=100 * x.contrib / x.balls.clip(lower=1))
    return x.pivot_table(index="player_id", columns="value", values="v"), \
        x.pivot_table(index="player_id", columns="value", values="balls")


def build(out_dir=C.OUT):
    reg = pd.read_parquet(out_dir / "player_registry.parquet")
    ab, aw = pd.read_parquet(out_dir / "batters_all.parquet"), pd.read_parquet(out_dir / "bowlers_all.parquet")
    rb, rw = pd.read_parquet(out_dir / "batter_rankings.parquet"), pd.read_parquet(out_dir / "bowler_rankings.parquet")
    bz, wz = pd.read_parquet(out_dir / "bat_zones.parquet"), pd.read_parquet(out_dir / "bowl_zones.parquet")

    st = status_table(reg, ab, aw)

    # ---- RR 2027 squad profile
    rr = st[(st.team_2027 == TEAM)].copy()
    bat_cols = ["player_id", "matches", "p_balls", "p_sr", "n_sr", "impact_rate", "qual_rate", "pc_per_ball", "n_pinn"]
    bowl_cols = ["player_id", "matches", "p_balls", "p_econ", "n_econ", "wicket_rate", "dot_rate", "pc_per_ball", "n_pspells", "bowling_type"]
    rr = rr.merge(ab[bat_cols].add_prefix("bat_").rename(columns={"bat_player_id": "player_id"}), on="player_id", how="left")
    rr = rr.merge(aw[bowl_cols].add_prefix("bowl_").rename(columns={"bowl_player_id": "player_id"}), on="player_id", how="left")
    rr = rr.merge(rb[["player_id", "rating", "rank"]].rename(columns={"rating": "bat_rating", "rank": "bat_rank"}), on="player_id", how="left")
    rr = rr.merge(rw[["player_id", "rating", "rank"]].rename(columns={"rating": "bowl_rating", "rank": "bowl_rank"}), on="player_id", how="left")
    rr["role"] = np.where(rr.bowl_p_balls.fillna(0) >= 120,
                          np.where(rr.bat_p_balls.fillna(0) >= 120, "All-rounder", "Bowler"),
                          np.where(rr.bat_p_balls.fillna(0) > 0, "Batter", "Limited data"))
    rr.loc[rr.role.eq("Bowler"), "role"] = np.where(rr.loc[rr.role.eq("Bowler"), "bowl_bowling_type"].astype(str).str.lower()
                                                    .str.contains("|".join(SPIN)), "Spinner", "Seamer")

    # RR players' pressure batting/bowling phase coverage (players with any pressure balls)
    rr_bat_ids = rr.loc[rr.bat_p_balls.fillna(0) >= 30, "player_id"].dropna().astype(int).tolist()
    rr_bowl_ids = rr.loc[rr.bowl_p_balls.fillna(0) >= 30, "player_id"].dropna().astype(int).tolist()
    phase = _phase_tables(bz, wz, rr_bat_ids, rr_bowl_ids)
    phase["bat_gap"] = phase.pool_bat_sr - phase.bat_sr            # >0 = RR slower than pool
    phase["bowl_gap"] = phase.bowl_econ - phase.pool_bowl_econ     # >0 = RR more expensive than pool

    # ---- needs: weights for each phase from the size of the gap (+ structural needs from releases)
    def norm(v):
        v = np.clip(np.asarray(v, float), 0, None)
        return v / v.sum() if v.sum() > 0 else np.ones_like(v) / len(v)
    # need weight per phase = how far RR's pressure contribution in that phase sits below its best phase
    # (context-adjusted runs above expected for batting; runs saved incl. wicket value for bowling)
    b = phase.bat_rae100.fillna(phase.bat_rae100.min())
    w = phase.bowl_saved100.fillna(phase.bowl_saved100.min())
    bat_need = dict(zip(PHASES, norm(b.max() - b.values + 1e-6)))
    bowl_need = dict(zip(PHASES, norm(w.max() - w.values + 1e-6)))

    # ---- auction pool: released (incl. disputed / doubtful), not retired, in our data, non-Pakistan
    pool = st[st.status.eq("Released") & ~st.flag.eq("retired") & st.player_id.notna()].copy()
    pool["player_id"] = pool.player_id.astype(int)
    pak = set(reg.loc[reg.is_pakistan, "player_id"])
    # wildcards: ranked internationals with no IPL squad in the data (would have to register for the auction)
    listed = set(st.player_id.dropna().astype(int))
    no_ipl = set(reg.loc[reg.ipl_team.isna(), "player_id"])
    wild_ids = (set(rb.player_id) | set(rw.player_id)) & no_ipl - listed
    wild = reg[reg.player_id.isin(wild_ids)][["player_id", "player_name"]].rename(columns={"player_name": "report_name"})
    wild = wild.assign(status="Not in an IPL squad", team_2027=None, team_2026=None, flag="wildcard",
                       note="Not in any IPL 2026 squad in the data; must register for the auction.", last_contract_cr=np.nan,
                       availability="Wildcard · must register")
    pool = pd.concat([pool, wild], ignore_index=True)
    pool = pool[~pool.player_id.isin(pak)]
    nat = reg.set_index("player_id").national_team
    pool["overseas"] = pool.player_id.map(nat).fillna("India").ne("India")

    bphase, bballs = player_phase(bz)
    wphase, wballs = player_phase(wz)

    def targets(kind):
        is_bat = kind == "bat"
        allp = ab if is_bat else aw
        rk = rb if is_bat else rw
        need = bat_need if is_bat else bowl_need
        ph, phb = (bphase, bballs) if is_bat else (wphase, wballs)
        x = pool.merge(allp, on="player_id", how="inner", suffixes=("", "_a"))
        # primary-role filter: batters must bat more than they bowl; bowlers must bowl at least half as much as they bat
        bb = ab.set_index("player_id").balls.reindex(x.player_id).fillna(0).values
        wb = aw.set_index("player_id").balls.reindex(x.player_id).fillna(0).values
        x = x[(bb >= wb) if is_bat else (wb >= 0.5 * bb)]
        x = x[x.p_balls >= (60 if is_bat else 72)]
        x = x.merge(rk[["player_id", "rating", "rank", "rating_lo", "rating_hi", "p_top10", "reliability"]], on="player_id", how="left")
        # phase fit: need-weighted pressure contribution per 100 balls, shrunk by balls in each phase
        fit = np.zeros(len(x))
        for p in PHASES:
            v = ph.get(p, pd.Series(dtype=float)).reindex(x.player_id).fillna(0).values
            n = phb.get(p, pd.Series(dtype=float)).reindex(x.player_id).fillna(0).values
            fit += need[p] * (v * n / (n + 40))
        x["phase_fit"] = fit
        for p in PHASES:
            x[f"pc100_{p.lower()}"] = ph.get(p, pd.Series(dtype=float)).reindex(x.player_id).values
            x[f"balls_{p.lower()}"] = phb.get(p, pd.Series(dtype=float)).reindex(x.player_id).values
        # pressure quality: rating if eligible, otherwise a provisional score from shrunk contribution
        prov = 50 + 10 * ((x.pc_per_ball * x.p_balls / (x.p_balls + C.PRIOR_BALLS)) - x.pc_per_ball.mean()) / x.pc_per_ball.std()
        x["pressure_score"] = x.rating.fillna(prov.clip(20, 80))
        x["score_source"] = np.where(x.rating.notna(), "Ranked rating", "Provisional (below ranking sample or inactive in 2026)")
        z = (x.phase_fit - x.phase_fit.mean()) / (x.phase_fit.std() or 1)
        x["rr_fit"] = 0.6 * x.pressure_score + 0.4 * (50 + 15 * z)
        x["active_2026"] = x.last_year >= 2026
        x.loc[~x.active_2026, "rr_fit"] -= 5   # inactive in 2026: small recency penalty
        x.loc[x.flag.eq("wildcard"), "rr_fit"] -= 3   # registration and IPL adaptation risk
        x = x.sort_values("rr_fit", ascending=False)
        x["target_rank"] = np.arange(1, len(x) + 1)
        return x

    tb, tw = targets("bat"), targets("bowl")
    for t in (tb, tw):
        t["group"] = np.where(t.flag.eq("wildcard"), "Wildcard watch list",
                              np.where(t.availability.eq("Released"), "Confirmed release", "Conditional (disputed / doubtful)"))
        t["is_pace"] = ~t.get("bowling_type", pd.Series("", index=t.index)).astype(str).str.lower().str.contains("|".join(SPIN))

    # ---- 6-slot plan: confirmed releases only, max 3 overseas, role quotas from the needs
    def pick(pool_b, pool_w, slots=6, overseas=3):
        chosen, os_used = [], 0
        def take(df, n, label, cond=None):
            nonlocal os_used
            d = df if cond is None else df[cond(df)]
            for _, r in d.iterrows():
                if n == 0:
                    break
                if r.player_id in [c["player_id"] for c in chosen]:
                    continue
                if r.overseas and os_used >= overseas:
                    continue
                chosen.append(dict(player_id=r.player_id, name=r.report_name, slot=label, overseas=bool(r.overseas),
                                   rr_fit=r.rr_fit, pressure_score=r.pressure_score, team_2026=r.team_2026,
                                   last_contract_cr=r.last_contract_cr, score_source=r.score_source, kind=r.kind))
                os_used += int(bool(r.overseas))
                n -= 1
        b = pool_b.assign(kind="Batter")
        w = pool_w.assign(kind="Bowler")
        take(w, 2, "Death / new-ball seamer", lambda d: d.is_pace)
        take(w, 1, "Best available bowler")
        take(b, 1, "Finisher (death-overs batting)", lambda d: d.balls_death.fillna(0) >= 30)
        take(b, 1, "Batting depth")
        allc = pd.concat([b, w]).sort_values("rr_fit", ascending=False)
        take(allc, slots - len(chosen), "Best remaining fit")
        return pd.DataFrame(chosen)

    conf_b = tb[tb.group.eq("Confirmed release")]
    conf_w = tw[tw.group.eq("Confirmed release")]
    plan = pick(conf_b, conf_w)
    plan["plan"] = "Core plan (confirmed releases)"
    floor = plan.rr_fit.min()
    upg = pd.concat([tw.assign(kind="Bowler"), tb.assign(kind="Batter")])
    upg = upg[upg.group.eq("Conditional (disputed / doubtful)") & (upg.rr_fit > floor)].sort_values("rr_fit", ascending=False)
    upg = pd.DataFrame(dict(player_id=upg.player_id, name=upg.report_name, slot="Upgrade if available",
                            overseas=upg.overseas, rr_fit=upg.rr_fit, pressure_score=upg.pressure_score,
                            team_2026=upg.team_2026, last_contract_cr=upg.last_contract_cr,
                            score_source=upg.score_source, kind=upg.kind, plan="Conditional upgrade"))
    plan = pd.concat([plan, upg], ignore_index=True)
    plan.to_parquet(out_dir / "rr_auction_plan.parquet", index=False)
    needs = {"bat_need": bat_need, "bowl_need": bowl_need,
             "purse": D.PURSE[TEAM], "auction": D.AUCTION, "squad_size": int(len(rr)),
             "overseas_in_squad": int(rr.player_id.map(nat).fillna("India").ne("India").sum())}

    st.to_parquet(out_dir / "ipl2027_status.parquet", index=False)
    rr.to_parquet(out_dir / "rr_squad_2027.parquet", index=False)
    phase.to_parquet(out_dir / "rr_phase_coverage.parquet", index=False)
    tb.to_parquet(out_dir / "rr_targets_bat.parquet", index=False)
    tw.to_parquet(out_dir / "rr_targets_bowl.parquet", index=False)
    (out_dir / "rr_needs.json").write_text(json.dumps(needs, indent=2, default=float), encoding="utf-8")
    return st, rr, phase, tb, tw, needs


if __name__ == "__main__":
    st, rr, phase, tb, tw, needs = build()
    pd.set_option("display.width", 250)
    print(st.availability.value_counts())
    print(rr[["report_name", "role", "bat_p_balls", "bat_p_sr", "bat_rating", "bowl_p_balls", "bowl_p_econ", "bowl_rating"]].round(1).to_string())
    print(phase.round(2).to_string())
    print(json.dumps(needs, indent=1, default=float))
    cols = ["target_rank", "report_name", "team_2026", "availability", "overseas", "pressure_score", "score_source", "phase_fit", "rr_fit", "p_balls"]
    print(tb[cols + ["p_sr", "n_sr", "pc100_death"]].head(15).round(2).to_string())
    print(tw[cols + ["p_econ", "n_econ", "pc100_death", "bowling_type"]].head(15).round(2).to_string())
    print(pd.read_parquet(C.OUT / "rr_auction_plan.parquet").round(1).to_string())
