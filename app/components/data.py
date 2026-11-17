"""Cached loaders - the dashboard only READS precomputed pipeline outputs."""
import json
from pathlib import Path

import pandas as pd
import streamlit as st

OUT = Path(__file__).resolve().parents[2] / "outputs"


def available(name):
    return (OUT / name).exists()


@st.cache_data(show_spinner="Loading analytics outputs…")
def load(name: str) -> pd.DataFrame:
    path = OUT / f"{name}.parquet"
    if not path.exists():
        return pd.DataFrame()
    return pd.read_parquet(path)


@st.cache_data
def summary() -> dict:
    p = OUT / "summary.json"
    return json.loads(p.read_text(encoding="utf-8")) if p.exists() else {}


@st.cache_data
def pak_ids() -> set:
    reg = load("player_registry")
    return set(reg.loc[reg.is_pakistan, "player_id"]) if len(reg) else set()


@st.cache_data
def registry() -> pd.DataFrame:
    return load("player_registry")


def require(*names):
    """Stop the page with a clear message if an output is missing."""
    missing = [n for n in names if not available(f"{n}.parquet")]
    if missing:
        st.error("Analytical outputs not found: " + ", ".join(missing) +
                 ".  Run `python -m src.pipeline` from the project root first.")
        st.stop()


def ipl2027_chip(player_id):
    """HTML chip with the player's IPL 2027 retention-day status (and RR fit when he is an auction target)."""
    st_ = load("ipl2027_status")
    if st_.empty or player_id is None:
        return ""
    r = st_[st_.player_id == player_id]
    if r.empty:
        return "<span class='chip'>IPL 2027: <b>not in published lists</b></span>"
    r = r.iloc[0]
    if r.status == "Retained":
        txt, kind = f"IPL 2027: <b>retained · {r.team_2027}</b>", "pos"
    else:
        txt, kind = f"IPL 2027: <b>{r.availability.lower()}</b> by {r.team_2026}", "warn"
    fit = ""
    for name in ("rr_targets_bowl", "rr_targets_bat"):
        t = load(name)
        if len(t) and (t.player_id == player_id).any():
            x = t[t.player_id == player_id].iloc[0]
            fit = f"<span class='chip acc'>RR fit <b>{x.rr_fit:.1f}</b> · #{int(x.target_rank)} {'bowling' if 'bowl' in name else 'batting'} target</span>"
            break
    return f"<span class='chip {kind}'>{txt}</span>{fit}"
