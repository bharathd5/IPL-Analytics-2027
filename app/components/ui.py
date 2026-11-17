"""UI toolkit: command bar, panels, KPI tiles, selection boards, chips, tables.

Every visual sits inside a bordered *panel* with its own header, so the page is a
strict grid of cards and nothing floats or overlaps.
"""
import html
import re
from contextlib import contextmanager

import numpy as np
import pandas as pd
import streamlit as st

from .theme import (ACCENT, ACCENT2, BG, BORDER, BORDER2, CARD, FAINT, MUTED, NEG, PANEL, POS,
                    REL_COLORS, TEXT, WARN)

E = html.escape

CSS = f"""
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&family=JetBrains+Mono:wght@500;600&display=swap');
:root {{ --acc:{ACCENT}; --acc2:{ACCENT2}; --txt:{TEXT}; --mut:{MUTED}; --bd:{BORDER}; --bd2:{BORDER2}; --card:{CARD}; --panel:{PANEL}; }}
html, body, [class*="css"], .stMarkdown, button, input, select, textarea, label {{ font-family:'Inter',system-ui,sans-serif !important; }}
.stApp {{ background: radial-gradient(1200px 600px at 75% -10%, rgba(66,216,208,0.06), transparent 60%),
                       radial-gradient(900px 500px at 10% -20%, rgba(184,243,107,0.05), transparent 60%), {BG}; }}
header[data-testid="stHeader"] {{ background: transparent; }}
.block-container {{ padding: 3.2rem 2.2rem 3rem 2.2rem; max-width: 1560px; }}
#MainMenu, footer, .stDeployButton, [data-testid="stAppDeployButton"], [data-testid="stMainMenu"],
[data-testid="stStatusWidget"] {{ display:none !important; }}
/* keep the sidebar open/close controls visible and on-brand (they live in the header toolbar) */
[data-testid="stExpandSidebarButton"], [data-testid="stSidebarCollapsedControl"], [data-testid="stSidebarCollapseButton"] {{
     visibility: visible !important; display: flex !important; opacity: 1 !important; z-index: 1000; }}
[data-testid="stExpandSidebarButton"] {{ background: rgba(17,31,50,.92) !important; border: 1px solid var(--bd2) !important;
     border-radius: 10px !important; color: var(--acc) !important; }}
[data-testid="stExpandSidebarButton"] svg, [data-testid="stSidebarCollapseButton"] svg {{ color: var(--acc) !important; fill: currentColor; }}

/* ---------- sidebar */
section[data-testid="stSidebar"] {{ background: linear-gradient(180deg,#0C1626 0%,#0A1220 100%); border-right:1px solid var(--bd); }}
section[data-testid="stSidebar"] [data-testid="stSidebarNav"] a span {{ font-size:.86rem; }}
section[data-testid="stSidebar"] [data-testid="stSidebarNavLink"] {{ border-radius:8px; margin:1px 0; }}
section[data-testid="stSidebar"] [data-testid="stSidebarNavLink"][aria-current="page"] {{ background: rgba(184,243,107,0.10); box-shadow: inset 2px 0 0 var(--acc); }}
section[data-testid="stSidebar"] [data-testid="stNavSectionHeader"] {{ color:{FAINT}; font-size:.66rem; letter-spacing:.16em; text-transform:uppercase; font-weight:700; margin-top:10px; }}
[data-testid="stLogo"] {{ height: 2.1rem; max-width: 220px; }}
.sb-status {{ border:1px solid var(--bd); background: rgba(17,31,50,.55); border-radius:12px; padding:12px 14px; margin-top:14px; font-size:.74rem; color:var(--mut); line-height:1.6; }}
.sb-status b {{ color:var(--txt); font-weight:600; }}
.dot {{ display:inline-block; width:7px; height:7px; border-radius:50%; margin-right:6px; vertical-align:middle; }}
.dot.live {{ background:{POS}; box-shadow:0 0 0 3px rgba(53,214,161,.18); animation:pulse 2.4s infinite; }}
@keyframes pulse {{ 0%{{box-shadow:0 0 0 0 rgba(53,214,161,.35)}} 70%{{box-shadow:0 0 0 7px rgba(53,214,161,0)}} 100%{{box-shadow:0 0 0 0 rgba(53,214,161,0)}} }}

/* ---------- command bar */
.cmd {{ display:flex; justify-content:space-between; align-items:flex-end; gap:24px; padding:6px 2px 16px 2px;
        border-bottom:1px solid var(--bd); margin-bottom:18px; }}
.cmd .eb {{ color:var(--acc); font-size:.68rem; font-weight:700; letter-spacing:.2em; text-transform:uppercase; }}
.cmd h1 {{ font-size:1.85rem; font-weight:800; color:var(--txt); margin:4px 0 4px 0; padding:0; letter-spacing:-.01em; line-height:1.15; }}
.cmd p {{ color:var(--mut); font-size:.9rem; margin:0; max-width:880px; line-height:1.5; }}
.cmd .chips {{ display:flex; flex-wrap:wrap; gap:6px; justify-content:flex-end; max-width:520px; }}
.chip {{ display:inline-flex; align-items:center; gap:6px; padding:4px 10px; border-radius:999px; border:1px solid var(--bd2);
         background:rgba(17,31,50,.7); color:var(--mut); font-size:.72rem; font-weight:600; white-space:nowrap; }}
.chip b {{ color:var(--txt); font-weight:700; }}
.chip.acc {{ color:var(--acc); border-color:rgba(184,243,107,.35); background:rgba(184,243,107,.07); }}
.chip.pos {{ color:{POS}; border-color:rgba(53,214,161,.35); }} .chip.warn {{ color:{WARN}; border-color:rgba(245,185,66,.35); }}
.chip.neg {{ color:{NEG}; border-color:rgba(241,108,117,.35); }}

/* ---------- panels (bordered containers keyed pnl_*) */
div[class*="st-key-pnl_"] {{ background: linear-gradient(180deg, rgba(17,31,50,.92) 0%, rgba(14,25,41,.92) 100%) !important;
     border:1px solid var(--bd) !important; border-radius:14px !important; padding: 14px 16px 10px 16px !important;
     box-shadow: 0 1px 0 rgba(255,255,255,.025) inset, 0 10px 30px rgba(0,0,0,.22); }}
div[class*="st-key-flt_"] {{ background: rgba(15,26,43,.75) !important; border:1px solid var(--bd) !important;
     border-radius:12px !important; padding: 10px 14px 2px 14px !important; }}
.ph {{ display:flex; flex-wrap:wrap; align-items:baseline; justify-content:space-between; gap:2px 12px; margin:-2px 0 8px 0;
       padding-bottom:9px; border-bottom:1px solid rgba(42,60,87,.55); }}
.ph .t {{ color:var(--txt); font-weight:700; font-size:.92rem; letter-spacing:.005em; white-space:nowrap; }}
.ph .t .ix {{ color:var(--acc); font-family:'JetBrains Mono',monospace; font-size:.72rem; margin-right:8px; font-weight:600; }}
.ph .h {{ color:{FAINT}; font-size:.74rem; margin-left:auto; text-align:right; }}
.foot {{ color:{FAINT}; font-size:.72rem; margin-top:2px; }}

/* ---------- KPI tiles */
.kpi {{ background: linear-gradient(180deg,#122138 0%,#0F1B2E 100%); border:1px solid var(--bd); border-radius:14px;
        padding:14px 16px; height:118px; position:relative; overflow:hidden; }}
.kpi::before {{ content:""; position:absolute; left:0; top:0; bottom:0; width:3px; background:var(--c,{ACCENT}); opacity:.9; }}
.kpi .l {{ color:var(--mut); font-size:.66rem; font-weight:700; letter-spacing:.14em; text-transform:uppercase; white-space:nowrap; overflow:hidden; text-overflow:ellipsis; }}
.kpi .v {{ color:var(--txt); font-size:1.7rem; font-weight:800; margin-top:6px; font-variant-numeric:tabular-nums; letter-spacing:-.01em; line-height:1.1; }}
.kpi .d {{ color:{FAINT}; font-size:.74rem; margin-top:6px; white-space:nowrap; overflow:hidden; text-overflow:ellipsis; }}
.kpi .d .up {{ color:{POS}; font-weight:700; }} .kpi .d .dn {{ color:{NEG}; font-weight:700; }}

/* ---------- selection board */
.board {{ width:100%; border-collapse:separate; border-spacing:0 4px; table-layout:fixed; }}
.board td, .board th {{ overflow:hidden; text-overflow:ellipsis; white-space:nowrap; }}
.board td {{ padding:7px 6px; font-size:.82rem; color:var(--txt); background:rgba(11,18,32,.55); border-top:1px solid rgba(42,60,87,.45); border-bottom:1px solid rgba(42,60,87,.45); }}
.board td:first-child {{ border-left:1px solid rgba(42,60,87,.45); border-radius:9px 0 0 9px; text-align:center; }}
.board td:last-child {{ border-right:1px solid rgba(42,60,87,.45); border-radius:0 9px 9px 0; }}
.board tr:hover td {{ background:rgba(184,243,107,.05); }}
.board th {{ color:{FAINT}; font-size:.6rem; letter-spacing:.08em; text-transform:uppercase; font-weight:700; text-align:left; padding:0 8px 2px 8px; }}
.rk {{ font-family:'JetBrains Mono',monospace; font-weight:600; color:var(--mut); font-size:.8rem; }}
.rk.top {{ color:#0B1220; background:var(--acc); border-radius:6px; padding:2px 6px; }}
.nm {{ font-weight:650; display:block; overflow:hidden; text-overflow:ellipsis; }} .tm {{ color:{FAINT}; font-size:.72rem; display:block; margin-top:1px; overflow:hidden; text-overflow:ellipsis; }}
.bar {{ position:relative; height:6px; border-radius:6px; background:rgba(148,163,184,.12); min-width:36px; }}
.bar > i {{ position:absolute; left:0; top:0; bottom:0; border-radius:6px; background:linear-gradient(90deg, rgba(184,243,107,.55), {ACCENT}); }}
.num {{ font-variant-numeric:tabular-nums; font-weight:700; }}
.mut {{ color:var(--mut); }}
.trend.up {{ color:{POS}; }} .trend.dn {{ color:{NEG}; }} .trend.eq {{ color:var(--mut); }}

/* ---------- insight feed */
.feed {{ display:flex; gap:10px; padding:10px 12px; border:1px solid rgba(42,60,87,.55); border-radius:10px; margin-bottom:8px; background:rgba(11,18,32,.45); }}
.feed .tag {{ flex:0 0 auto; font-size:.62rem; font-weight:800; letter-spacing:.12em; padding:3px 7px; border-radius:6px; height:fit-content; }}
.feed .tag.sig {{ background:rgba(184,243,107,.12); color:{ACCENT}; }} .feed .tag.risk {{ background:rgba(241,108,117,.12); color:{NEG}; }}
.feed .tag.info {{ background:rgba(66,216,208,.12); color:{ACCENT2}; }} .feed .tag.watch {{ background:rgba(245,185,66,.12); color:{WARN}; }}
.feed .tx {{ color:var(--txt); font-size:.84rem; line-height:1.45; }} .feed .tx b {{ color:var(--acc); font-weight:700; }}

/* ---------- profile hero */
.hero {{ display:flex; justify-content:space-between; align-items:center; gap:20px; padding:16px 18px; border-radius:14px;
         border:1px solid var(--bd); background: linear-gradient(120deg, rgba(184,243,107,.07), rgba(66,216,208,.04) 40%, rgba(17,31,50,.9) 75%); }}
.hero .n {{ font-size:1.55rem; font-weight:800; color:var(--txt); letter-spacing:-.01em; }}
.hero .m {{ color:var(--mut); font-size:.85rem; margin-top:2px; }}
.hero .big {{ text-align:right; }} .hero .big .v {{ font-size:2.4rem; font-weight:800; color:var(--acc); line-height:1; font-variant-numeric:tabular-nums; }}
.hero .big .l {{ color:var(--mut); font-size:.7rem; letter-spacing:.14em; text-transform:uppercase; font-weight:700; }}

/* ---------- XI cards */
.xi {{ display:grid; grid-template-columns: repeat(auto-fill, minmax(178px,1fr)); gap:10px; }}
.xi .p {{ border:1px solid var(--bd2); border-radius:12px; padding:10px 12px; background:rgba(11,18,32,.55); }}
.xi .p .r {{ font-size:.62rem; font-weight:800; letter-spacing:.14em; color:{FAINT}; text-transform:uppercase; }}
.xi .p .n {{ font-weight:700; color:var(--txt); margin-top:3px; font-size:.9rem; }}
.xi .p .s {{ color:var(--mut); font-size:.74rem; margin-top:2px; }}
.xi .p .g {{ font-family:'JetBrains Mono',monospace; color:var(--acc); font-weight:600; font-size:.8rem; margin-top:6px; white-space:nowrap; }}

/* ---------- gauge text, notes, tabs, inputs */
.note {{ color:var(--mut); font-size:.8rem; border:1px dashed var(--bd2); border-radius:10px; padding:9px 12px; }}
.stTabs [data-baseweb="tab-list"] {{ gap:2px; border-bottom:1px solid var(--bd); }}
.stTabs [data-baseweb="tab"] {{ height:36px; padding:0 14px; background:transparent; color:var(--mut); font-size:.82rem; font-weight:600; }}
.stTabs [aria-selected="true"] {{ color:var(--acc) !important; }}
.stTabs [data-baseweb="tab-highlight"] {{ background:var(--acc); }}
span[data-baseweb="tag"], .stMultiSelect span[class*="eo2qvtu3"] {{ background-color: rgba(184,243,107,0.12) !important;
     border:1px solid rgba(184,243,107,0.32); border-radius:6px !important; }}
span[data-baseweb="tag"] span, .stMultiSelect span[class*="eo2qvtu3"] span {{ color:{ACCENT} !important; font-weight:600; }}
div[data-testid="stDataFrame"] {{ border:1px solid var(--bd); border-radius:10px; overflow:hidden; }}
label[data-testid="stWidgetLabel"] p {{ color:var(--mut) !important; font-size:.74rem !important; font-weight:600; letter-spacing:.04em; }}
div[data-baseweb="select"] > div, div[data-baseweb="input"] > div {{ background:#0D1828 !important; border-color:var(--bd2) !important; }}
.stButton button, .stDownloadButton button {{ border-radius:9px; border:1px solid var(--bd2); background:#12223A; color:var(--txt); font-weight:600; }}
.stButton button:hover, .stDownloadButton button:hover {{ border-color:var(--acc); color:var(--acc); }}
div[data-testid="stMetric"] {{ background:rgba(11,18,32,.5); border:1px solid var(--bd); border-radius:10px; padding:10px 12px; }}
hr {{ border-color: var(--bd) !important; }}

/* ================= responsive: laptop / tablet / phone ================= */
@media (max-width: 1200px) {{
  .block-container {{ padding: 3.2rem 1.4rem 2.5rem 1.4rem; }}
  .kpi .v {{ font-size: 1.4rem; }}
  .cmd h1 {{ font-size: 1.6rem; }}
}}
@media (max-width: 900px) {{
  .cmd {{ flex-direction: column; align-items: flex-start; gap: 10px; }}
  .cmd .chips {{ justify-content: flex-start; max-width: 100%; }}
  .hero {{ flex-direction: column; align-items: flex-start; }}
  .hero .big {{ text-align: left; }}
  .kpi {{ height: auto; min-height: 100px; }}
}}
@media (max-width: 640px) {{
  .block-container {{ padding: 3.6rem 0.75rem 2rem 0.75rem; }}
  div[class*="st-key-kpis_"] [data-testid="stHorizontalBlock"] {{ flex-wrap: wrap !important; gap: .5rem !important; }}
  div[class*="st-key-kpis_"] [data-testid="stColumn"] {{ flex: 1 1 calc(50% - .5rem) !important; width: calc(50% - .5rem) !important;
       min-width: calc(50% - .5rem) !important; }}
  .kpi .l {{ font-size: .6rem; letter-spacing: .1em; }}
  .cmd h1 {{ font-size: 1.35rem; }}
  .cmd p {{ font-size: .84rem; }}
  .kpi {{ min-height: 0; padding: 12px 14px; }}
  .kpi .v {{ font-size: 1.3rem; }}
  .kpi .d {{ white-space: normal; }}
  div[class*="st-key-pnl_"] {{ padding: 10px 10px 6px 10px !important; border-radius: 12px !important; }}
  .ph {{ flex-direction: column; align-items: flex-start; }}
  .ph .h {{ margin-left: 0; text-align: left; }}
  .board {{ table-layout: auto; }}
  .board colgroup {{ display: none; }}
  .board tr > *:nth-child(5), .board tr > *:nth-child(6) {{ display: none; }}
  .board td {{ padding: 6px 4px; font-size: .78rem; }}
  .hero .n {{ font-size: 1.25rem; }} .hero .big .v {{ font-size: 1.9rem; }}
  .xi {{ grid-template-columns: repeat(auto-fill, minmax(140px,1fr)); }}
  .feed {{ flex-direction: column; gap: 6px; }}
}}
</style>
"""

_COUNTER_KEY = "_pnl_counter"


def inject_css():
    st.markdown(CSS, unsafe_allow_html=True)
    st.session_state[_COUNTER_KEY] = 0


def _key(prefix, title):
    st.session_state[_COUNTER_KEY] = st.session_state.get(_COUNTER_KEY, 0) + 1
    slug = re.sub(r"[^a-z0-9]+", "_", str(title).lower())[:30]
    return f"{prefix}_{slug}_{st.session_state[_COUNTER_KEY]}"


# ------------------------------------------------------------------ chrome
def command_bar(eyebrow, title, subtitle="", chips=()):
    chip_html = "".join(f"<span class='chip {c[1] if isinstance(c, tuple) else ''}'>"
                        f"{c[0] if isinstance(c, tuple) else c}</span>" for c in chips)
    st.markdown(f"<div class='cmd'><div><div class='eb'>{E(eyebrow)}</div><h1>{E(title)}</h1>"
                f"<p>{subtitle}</p></div><div class='chips'>{chip_html}</div></div>", unsafe_allow_html=True)


@contextmanager
def panel(title, hint="", index=None, height=None):
    kw = {"height": height} if height else {}
    c = st.container(border=True, key=_key("pnl", title), **kw)
    with c:
        ix = f"<span class='ix'>{E(index)}</span>" if index else ""
        st.markdown(f"<div class='ph'><div class='t'>{ix}{E(title)}</div><div class='h'>{hint}</div></div>",
                    unsafe_allow_html=True)
        yield c


@contextmanager
def filter_bar():
    c = st.container(border=True, key=_key("flt", "filters"))
    with c:
        yield c


def foot(text):
    st.markdown(f"<div class='foot'>{text}</div>", unsafe_allow_html=True)


def chip(text, kind=""):
    return f"<span class='chip {kind}'>{text}</span>"


def pill(text, kind=""):  # backwards-compatible alias
    return chip(E(str(text)), {"high": "pos", "medium": "warn", "low": "neg"}.get(kind, kind))


def kpi(label, value, desc="", color=ACCENT):
    st.markdown(f"<div class='kpi' style='--c:{color}'><div class='l'>{E(label)}</div><div class='v'>{value}</div>"
                f"<div class='d'>{desc}</div></div>", unsafe_allow_html=True)


def kpi_row(items):
    with st.container(key=_key("kpis", "row")):
        cols = st.columns(len(items), gap="small")
        for c, it in zip(cols, items):
            with c:
                kpi(*it)


def delta_html(x, fmt="{:+.1f}", good_up=True):
    if x is None or not np.isfinite(x):
        return ""
    cls = "up" if (x > 0) == good_up else "dn"
    if abs(x) < 1e-9:
        cls = ""
    return f"<span class='{cls}'>{fmt.format(x)}</span>"


def feed(items):
    """items: list of (tag, text) with tag in sig / risk / info / watch."""
    labels = {"sig": "SIGNAL", "risk": "RISK", "info": "INTEL", "watch": "WATCH"}
    st.markdown("".join(f"<div class='feed'><span class='tag {t}'>{labels.get(t, t.upper())}</span>"
                        f"<div class='tx'>{x}</div></div>" for t, x in items), unsafe_allow_html=True)


def note(text):
    st.markdown(f"<div class='note'>{text}</div>", unsafe_allow_html=True)


def empty(msg="No data for the current filters. Widen the selection to see results."):
    st.markdown(f"<div class='note' style='text-align:center;padding:26px'>{msg}</div>", unsafe_allow_html=True)


def hero(name, meta, value, value_label, chips=""):
    st.markdown(f"<div class='hero'><div><div class='n'>{E(name)}</div><div class='m'>{meta}</div>"
                f"<div style='margin-top:8px;display:flex;gap:6px;flex-wrap:wrap'>{chips}</div></div>"
                f"<div class='big'><div class='l'>{E(value_label)}</div><div class='v'>{value}</div></div></div>",
                unsafe_allow_html=True)


# ------------------------------------------------------------------ boards
def trend_html(form, career):
    if not (np.isfinite(form) and np.isfinite(career)):
        return "<span class='trend eq'>–</span>"
    d = 100 * (form - career)
    if d > 3:
        return f"<span class='trend up' title='2025–26 vs career'>▲{d:+.0f}</span>"
    if d < -3:
        return f"<span class='trend dn' title='2025–26 vs career'>▼{d:+.0f}</span>"
    return f"<span class='trend eq' title='2025–26 vs career'>●{d:+.0f}</span>"


def selection_board(df, kind, n=10):
    """Compact war-room leaderboard: rank, player, rating bar, key stat, form arrow, P(top10), reliability."""
    rows = []
    for _, r in df.head(n).iterrows():
        top = " top" if r["rank"] <= 3 else ""
        stat = (f"{r.p_sr:.0f} <span class='mut'>/ {r.n_sr:.0f}</span>" if kind == "bat"
                else f"{r.p_econ:.2f} <span class='mut'>/ {r.n_econ:.2f}</span>")
        rel = r.get("reliability", "Low")
        rows.append(
            f"<tr><td><span class='rk{top}'>{int(r['rank'])}</span></td>"
            f"<td><span class='nm'>{E(r['name'])}</span><span class='tm'>{E(str(r.last_team))}</span></td>"
            f"<td style='width:30%'><div style='display:flex;align-items:center;gap:8px'><div class='bar' style='flex:1'>"
            f"<i style='width:{max(0, min(100, r.rating)):.0f}%'></i></div><span class='num' style='flex:0 0 auto'>{r.rating:.1f}</span></div></td>"
            f"<td class='num' style='font-size:.78rem'>{stat}</td>"
            f"<td>{trend_html(r.get('form_pc_per_ball', np.nan), r.pc_per_ball)}</td>"
            f"<td class='num'>{100 * r.p_top10:.0f}%</td>"
            f"<td title='{rel} reliability' style='text-align:center'><span class='dot' style='background:{REL_COLORS.get(rel, NEG)};margin:0'></span></td></tr>")
    stat_h = "SR P / N" if kind == "bat" else "Econ P / N"
    cols = "<colgroup><col style='width:38px'><col style='width:29%'><col style='width:24%'><col style='width:18%'>" \
           "<col style='width:12%'><col style='width:10%'><col style='width:42px'></colgroup>"
    st.markdown(f"<div class='board-wrap'><table class='board'>{cols}<tr><th>#</th><th>Player</th><th>Rating</th><th>{stat_h}</th>"
                f"<th>Form</th><th title='Share of bootstrap draws in the top 10'>P10</th><th title='Reliability'>Rel.</th></tr>{''.join(rows)}</table></div>",
                unsafe_allow_html=True)


def xi_cards(players):
    """players: list of dicts with role, name, sub, metric."""
    cards = "".join(f"<div class='p'><div class='r'>{E(p['role'])}</div><div class='n'>{E(p['name'])}</div>"
                    f"<div class='s'>{E(p['sub'])}</div><div class='g'>{p['metric']}</div></div>" for p in players)
    st.markdown(f"<div class='xi'>{cards}</div>", unsafe_allow_html=True)


# ------------------------------------------------------------------ tables
def bat_rank_view(rb: pd.DataFrame) -> pd.DataFrame:
    return pd.DataFrame({
        "Rank": rb["rank"], "Player": rb["name"], "Team": rb["last_team"], "Rating": rb["rating"],
        "Pressure inns": rb["n_pinn"].astype(int), "Pressure balls": rb["p_balls"].astype(int),
        "Pressure SR": rb["p_sr"], "Normal SR": rb["n_sr"],
        "Impact rate (20+)": 100 * rb["impact_rate"], "Qualifying rate": 100 * rb["qual_rate"],
        "Runs above exp /100b": 100 * rb["pc_per_ball"], "Consistency": rb["score_consistency"],
        "P(top 10)": 100 * rb["p_top10"], "Reliability": rb["reliability"]})


def bowl_rank_view(rw: pd.DataFrame) -> pd.DataFrame:
    return pd.DataFrame({
        "Rank": rw["rank"], "Player": rw["name"], "Team": rw["last_team"], "Rating": rw["rating"],
        "Pressure spells": rw["n_pspells"].astype(int), "Pressure overs": rw["p_overs"],
        "Pressure econ": rw["p_econ"], "Normal econ": rw["n_econ"], "Pressure wkts": rw["p_wkts"].astype(int),
        "1+ wkt rate": 100 * rw["wicket_rate"], "2+ wkt rate": 100 * rw["impact_rate"],
        "Dot-reliable rate": 100 * rw["dot_rate"], "Consistency": rw["score_consistency"],
        "P(top 10)": 100 * rw["p_top10"], "Reliability": rw["reliability"]})


def col_config(df):
    cfg = {}
    for c in df.columns:
        if c in ("Rating", "Consistency"):
            cfg[c] = st.column_config.ProgressColumn(c, min_value=0, max_value=100, format="%.1f")
        elif c == "P(top 10)" or "rate" in c.lower():
            cfg[c] = st.column_config.NumberColumn(c, format="%.0f%%")
        elif c == "Rank":
            cfg[c] = st.column_config.NumberColumn(c, width="small")
        elif df[c].dtype.kind == "f":
            cfg[c] = st.column_config.NumberColumn(c, format="%.2f")
    return cfg


# legacy name kept for pages that still call it
def section(title, hint=""):
    st.markdown(f"<div class='ph' style='margin-top:14px'><div class='t'>{E(title)}</div><div class='h'>{hint}</div></div>",
                unsafe_allow_html=True)


def page_header(eyebrow, title, subtitle=""):
    command_bar(eyebrow, title, subtitle, default_chips())


def default_chips():
    from . import data
    S = data.summary()
    c = S.get("counts", {})
    return [(f"<span class='dot live'></span>Model <b>v1</b>", "acc"),
            f"<b>{c.get('matches', 0):,}</b> matches",
            f"<b>{c.get('deliveries', 0):,}</b> balls",
            "IPL + T20I · <b>2022–26</b>"]

