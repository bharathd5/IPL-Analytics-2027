"""Stage 1 - load, clean, de-duplicate, validate and merge every supplied file.

Output: one ball-level master frame with match, competition, team and player
context attached, plus a player registry and a data-quality log.
"""
import json

import numpy as np
import pandas as pd

from . import config as C


def _say(msg):
    print(f"         - {msg}", flush=True)


def _strip(df):
    """Trim whitespace in text columns using plain Python strings.

    Avoids pandas' pyarrow-backed "string" dtype, which can crash silently on some
    Windows pandas/pyarrow builds. Missing values stay missing.
    """
    for c in df.columns:
        if df[c].dtype == object or pd.api.types.is_string_dtype(df[c].dtype):
            vals = df[c].to_numpy(dtype=object, na_value=None)
            df[c] = pd.Series([v.strip() if isinstance(v, str) else v for v in vals],
                              index=df.index, dtype=pd.StringDtype("python"))
    return df


def _read(name, **kw):
    path = C.RAW / name
    _say(f"reading {name} ({path.stat().st_size / 1e6:.1f} MB)")
    # utf-8-sig also handles CSVs re-saved by Excel (byte-order mark on the first column)
    return pd.read_csv(path, encoding="utf-8-sig", engine="c", **kw)


def load_raw():
    bbb = _read("ball_by_ball.csv", low_memory=False)
    matches = _read("matches.csv")
    comps = _read("competitions.csv")
    teams = _read("teams.csv")
    mapping = _read("competition_team_player_mapping.csv")
    xi = _read("playing_eleven.csv")
    out = {}
    for k, v in dict(bbb=bbb, matches=matches, comps=comps, teams=teams, mapping=mapping, xi=xi).items():
        _say(f"trimming text in {k} ({len(v):,} rows)")
        out[k] = _strip(v)
    return out


def clean(raw):
    log = {}
    out = {}
    for name, df in raw.items():
        n0 = len(df)
        df = df.drop_duplicates()
        log[f"{name}_rows_raw"] = int(n0)
        log[f"{name}_exact_duplicates_removed"] = int(n0 - len(df))
        out[name] = df

    bbb = out["bbb"]
    key = ["match_id", "innings", "innings_ball_num"]
    dup_key = bbb.duplicated(key, keep="first")
    log["bbb_key_duplicates_removed"] = int(dup_key.sum())
    bbb = bbb[~dup_key].copy()

    # super overs (innings 3/4) are not part of the 20-over contest model
    log["bbb_super_over_balls_removed"] = int((bbb.innings > 2).sum())
    bbb = bbb[bbb.innings.isin([1, 2])].copy()

    # normalise text categories
    bbb["dismissal_type"] = bbb["dismissal_type"].replace(
        {"Obstracting the field": "Obstructing the field"})
    bbb["extras_type"] = bbb["extras_type"].replace({"None": pd.NA})
    for c in ["is_four", "is_six", "is_wicket"]:
        bbb[c] = bbb[c].astype(str).str.lower().eq("true")
    # bowl_speed: 0 / -1 / > 170 kph are sensor gaps, not real speeds
    bad_speed = (bbb.bowl_speed <= 0) | (bbb.bowl_speed > 170)
    log["bbb_bowl_speed_set_missing"] = int(bad_speed.sum())
    bbb.loc[bad_speed, "bowl_speed"] = np.nan
    for c in ["stroke", "over_or_around"]:
        bbb[c] = bbb[c].fillna("Unknown")
    out["bbb"] = bbb.sort_values(["match_id", "innings", "innings_ball_num"]).reset_index(drop=True)

    xi = out["xi"]
    n0 = len(xi)
    xi = xi.sort_values("is_played", ascending=False).drop_duplicates(["match_id", "player_id"])
    log["xi_player_duplicates_removed"] = int(n0 - len(xi))
    out["xi"] = xi

    m = out["matches"].drop_duplicates("match_id")
    m["match_date"] = pd.to_datetime(m["match_date"], format="%d-%m-%Y")
    out["matches"] = m
    out["comps"] = out["comps"].drop_duplicates("comp_id")
    out["teams"] = out["teams"].drop_duplicates(["comp_id", "team_id"])
    out["mapping"] = out["mapping"].drop_duplicates(["comp_id", "team_id", "player_id"])
    return out, log


def validate(d, log):
    bbb, m = d["bbb"], d["matches"]
    checks = {}
    checks["balls_with_unknown_match"] = int((~bbb.match_id.isin(m.match_id)).sum())
    checks["matches_without_balls"] = int((~m.match_id.isin(bbb.match_id)).sum())
    checks["negative_runs"] = int((bbb.runs < 0).sum())
    checks["runs_above_7"] = int((bbb.runs > 7).sum())
    checks["wicket_without_type"] = int((bbb.is_wicket & bbb.dismissal_type.isna()).sum())
    checks["type_without_wicket"] = int((~bbb.is_wicket & bbb.dismissal_type.notna()).sum())
    checks["batting_equals_bowling_team"] = int((bbb.batting_team_id == bbb.bowling_team_id).sum())
    checks["striker_name_conflicts"] = int((bbb.groupby("striker_id").striker_name.nunique() > 1).sum())
    checks["bowler_name_conflicts"] = int((bbb.groupby("bowler_id").bowler_name.nunique() > 1).sum())
    legal = ~bbb.extras_type.isin(C.ILLEGAL_EXTRAS)
    per_over = bbb[legal].groupby(["match_id", "innings", "overid"]).size()
    checks["overs_with_more_than_6_legal"] = int((per_over > 6).sum())
    log["validation"] = checks
    return log


def build_player_registry(d):
    """One row per player: name, national team, latest IPL team, Pakistan flag."""
    mp, comps = d["mapping"], d["comps"]
    mp = mp.merge(comps[["comp_id", "match_format", "season"]], on="comp_id", how="left")
    names = (mp.groupby("player_id").player_name.agg(lambda s: s.mode().iat[0]))
    nat = (mp[mp.match_format == "T20I"].groupby("player_id").team_name
           .agg(lambda s: s.value_counts().index[0]).rename("national_team"))
    mp["season_key"] = mp.season.astype(str).str[:4].astype(int)
    ipl = mp[mp.comp_name.str.startswith("IPL")].sort_values("season_key")
    ipl_team = ipl.groupby("player_id").team_name.last().rename("ipl_team")
    pak = mp[mp.team_id.isin(C.EXCLUDED_NATIONAL_TEAM_IDS)].player_id.unique()
    reg = pd.concat([names, nat, ipl_team], axis=1).reset_index().rename(columns={"index": "player_id"})
    reg["is_pakistan"] = reg.player_id.isin(pak)
    return reg


def merge_master(d):
    bbb, m, comps = d["bbb"].copy(), d["matches"].copy(), d["comps"].copy()
    comps["comp_type"] = np.where(comps.comp_name.str.startswith("IPL"), "IPL",
                                  np.where(comps.match_format == "T20I", "T20I", "T20 (Emerging)"))
    m = m.merge(comps[["comp_id", "comp_name", "match_format", "season", "comp_type"]],
                on="comp_id", how="left")
    m["year"] = m.match_date.dt.year
    m["is_knockout"] = m.stage.isin(C.KNOCKOUT_STAGES) | (m.knock_out == 1)
    m["is_super4"] = m.stage.isin(C.SEMI_STAKES_STAGES)
    m["is_dls"] = m.revised_target.notna()
    m["no_result"] = m.win_team_id.isna() | m.result.str.contains("No Result|Abandon", case=False, na=False)
    m["sched_balls_1"] = m.first_inn_revised_overs.fillna(120).astype(int)
    m["sched_balls_2"] = m.second_inn_revised_overs.fillna(120).astype(int)

    team_names = d["teams"].drop_duplicates("team_id").set_index("team_id").team_name
    mcols = ["match_id", "comp_id", "comp_name", "comp_type", "season", "year", "match_date",
             "stage", "is_knockout", "is_super4", "is_dls", "no_result", "venue_id",
             "venue_country", "win_team_id", "revised_target", "sched_balls_1",
             "sched_balls_2", "result"]
    bbb = bbb.merge(m[mcols], on="match_id", how="left")
    bbb["batting_team"] = bbb.batting_team_id.map(team_names)
    bbb["bowling_team"] = bbb.bowling_team_id.map(team_names)
    bbb["opp_is_associate"] = bbb.bowling_team.isin(C.ASSOCIATE_TEAMS).astype(int)
    bbb["bat_opp_is_associate"] = bbb.batting_team.isin(C.ASSOCIATE_TEAMS).astype(int)

    # non-striker batting order from the playing XI
    xi = d["xi"][["match_id", "player_id", "batting_order"]].rename(
        columns={"player_id": "non_striker_id", "batting_order": "non_striker_order"})
    bbb = bbb.merge(xi, on=["match_id", "non_striker_id"], how="left")

    # ---- per-ball accounting
    et = bbb.extras_type
    bbb["is_legal"] = ~et.isin(C.ILLEGAL_EXTRAS)
    bbb["is_wide"] = et.eq("wide").fillna(False)
    bbb["faced"] = ~bbb.is_wide                                   # ball counts to the batter
    bbb["team_runs"] = bbb.runs + bbb.extras1_runs + bbb.extras_2_runs
    charged = et.isin(C.BOWLER_CHARGED_EXTRAS)
    bbb["bowler_runs"] = bbb.runs + np.where(charged, bbb.extras1_runs + bbb.extras_2_runs, 0)
    bbb["bowler_wicket"] = bbb.is_wicket & bbb.dismissal_type.isin(C.BOWLER_WICKETS)
    bbb["striker_out"] = bbb.is_wicket & (bbb.dismissed_player_id == bbb.striker_id)
    bbb["is_dot_bat"] = bbb.faced & (bbb.runs == 0)
    bbb["is_dot_bowl"] = bbb.is_legal & (bbb.bowler_runs == 0)
    bbb["is_boundary"] = bbb.is_four | bbb.is_six
    bbb["phase"] = pd.cut(bbb.overid, [0, 6, 15, 20], labels=["Powerplay", "Middle", "Death"]).astype(str)
    bbb["role_bat"] = pd.cut(bbb.batting_order, [0, 2, 4, 7, 20],
                             labels=["Opener", "Top order", "Middle order", "Lower order"]).astype(str)
    return bbb, m


def run():
    raw = load_raw()
    _say("cleaning and de-duplicating")
    d, log = clean(raw)
    _say("validating")
    log = validate(d, log)
    _say("building player registry")
    reg = build_player_registry(d)
    _say("merging into the master ball-by-ball file")
    master, matches = merge_master(d)
    log["master_rows"] = int(len(master))
    log["matches"] = int(master.match_id.nunique())
    log["players"] = int(pd.unique(pd.concat([master.striker_id, master.bowler_id])).size)
    return master, matches, reg, d, log


if __name__ == "__main__":
    master, matches, reg, d, log = run()
    print(json.dumps(log, indent=2, default=str))
