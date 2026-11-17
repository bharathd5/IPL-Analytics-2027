import pandas as pd
import plotly.express as px
import streamlit as st

from components import data, ui
from components.theme import SEQ, style
from src import config as C

S = data.summary()
cnt = S.get("counts", {})
dq = S.get("data_quality", {})

ui.page_header("Documentation", "Methodology",
               "Everything on this page is read from the same configuration the pipeline runs on "
               "(<code>src/config.py</code>), so the documentation cannot drift from the implementation.")

ui.section("0 · Pipeline at a glance")
st.markdown("""
| Stage | Module | What it does |
|---|---|---|
| 1 | `data_prep.py` | Load six CSVs, trim text, drop exact and key duplicates, drop super-over balls, flag sensor-error speeds, validate, merge into one **master ball-by-ball file** |
| 2 | `state.py` | Rebuild the match state **before every delivery**: legal balls used, balls remaining, wickets, target, runs required, RRR, CRR, last-12-ball run rate, wickets in last 18 balls, partnership, set/new batter, non-striker |
| 3 | `models.py` | Empirical **resource table** (expected runs to come for every balls-left × wickets-lost state) and a cross-fitted **win-probability** model |
| 4 | `pressure.py` | Separate **Batting** and **Bowling Pressure Indices** (0–100), knockout and DLS stakes, dead-game dampener, holdout validation |
| 5 | `expected.py` | Pre-match form and cross-fitted **expected runs / dismissal / wicket** per ball → Pressure Contribution |
| 6 | `metrics.py` | Innings & spell tables, **consistency rules**, baselines, team standout, WPA, knockout impact, shrinkage, composite rating |
| 7 | `pipeline.py` | Eligibility, **bootstrap** intervals, **sensitivity** scenarios, feature tables, outputs |
| 8 | `app/` | This dashboard — reads outputs only |
""")

ui.section("1 · Data preparation")
c1, c2, c3, c4 = st.columns(4)
c1.metric("Raw deliveries", f"{dq.get('bbb_rows_raw', 0):,}")
c2.metric("Super-over balls removed", f"{dq.get('bbb_super_over_balls_removed', 0)}")
c3.metric("Speeds set missing (≤0 or >170 kph)", f"{dq.get('bbb_bowl_speed_set_missing', 0):,}")
c4.metric("Playing-XI duplicates removed", f"{dq.get('xi_player_duplicates_removed', 0)}")
with st.expander("Ball accounting rules"):
    st.markdown(f"""
- **Legal ball** — every delivery except extras of type {sorted(C.ILLEGAL_EXTRAS)} (wides and no-balls; `other` behaves as a no-ball: 1 extra plus bat runs).
- **Ball faced by the batter** — every delivery except wides.
- **Team runs** = `runs + extras1_runs + extras_2_runs`. **Bowler runs** = bat runs + wide/no-ball extras (byes and leg-byes are not charged).
- **Bowler wicket** — dismissal types {sorted(C.BOWLER_WICKETS)}; run-outs, retirements and obstruction are team wickets only.
- **Target** = `revised_target` when present (DLS), otherwise first-innings total + 1. **Scheduled balls** come from `first_inn_revised_overs` / `second_inn_revised_overs` (stored in balls) or 120.
- **Balls remaining** = scheduled balls − legal balls already bowled. This is the owner's `120 − ((overid−1)×6 + over_ball_num)`, with wides and no-balls removed and DLS overs applied.
- **Season** = calendar year of the match; **competition type** = IPL / T20I / T20 (Emerging).
- Validation found 0 orphan balls, 0 name conflicts and 0 wicket/type mismatches. One over has 7 legal balls (umpire miscount) and is kept as recorded.
""")

ui.section("2 · Pressure definition")
st.markdown("""
Pressure is **dynamic and context-aware**: it is recomputed before every delivery from the state of the game, so a batter can be
under pressure for six balls and free of it for the next ten (owner rule 4.2). Following **Paper 2 (Bhattacharjee & Lemmer)**,
pressure is measured **separately for each side** because the same ball means different things to the batter and to the bowler.
""")
st.latex(r"PI^{bat}_{raw} = \Big(\sum_k w_k\,c_k\Big)\times \text{stakes}\times \text{dead-game factor},\qquad PI = 100\times \text{percentile rank}(PI_{raw})")
a, b = st.columns(2)
with a:
    st.markdown("**Batting Pressure Index components** (each scaled to [0, 1])")
    st.dataframe(pd.DataFrame({
        "Component": list(C.BAT_PI_WEIGHTS),
        "Weight": list(C.BAT_PI_WEIGHTS.values()),
        "Definition": [
            "Chase: Φ(z), z = (runs required − expected runs from remaining resources) / sd.  1st inns: Φ(−z_par), z_par = (projected − par) / sd",
            "Chase: (RRR − 6)/8.  1st inns (after 2 overs): (par run rate − CRR)/3",
            "Wickets lost / 7",
            "1 − balls remaining / scheduled balls",
            "max(death overs 16–20, powerplay with 2+ wickets down, 2+ wickets in last 18 balls)",
            "Closeness = 1 − |2·WP − 1|, × √(innings progress)",
            "0.5·new batter (<8 balls faced) + 0.5·tail-ender (order ≥ 8) at the non-striker's end"]}),
        hide_index=True, width="stretch")
with b:
    st.markdown("**Bowling Pressure Index components**")
    st.dataframe(pd.DataFrame({
        "Component": list(C.BOWL_PI_WEIGHTS),
        "Weight": list(C.BOWL_PI_WEIGHTS.values()),
        "Definition": [
            "Chase: Φ(−z), i.e. the batting side is ahead of what its resources require.  1st inns: Φ(z_par), batting side above par",
            "Opposition run rate over the previous 12 deliveries: (RR12 − 6)/8",
            "Batting side's wickets in hand / 10 (harder to bowl out)",
            "1 − balls remaining / scheduled balls",
            "Death overs = 1, powerplay = 0.5, middle = 0",
            "Closeness = 1 − |2·WP − 1|, × √(innings progress)",
            "max(partnership runs / 60, partnership balls / 36), an established stand that must be broken"]}),
        hide_index=True, width="stretch")
st.markdown(f"""
- **Stakes multiplier (macro indicators):** knockout ×{C.STAKES['knockout']}, Super 4 ×{C.STAKES['super4']}, DLS-revised match ×{C.STAKES['dls']}
  (rain-curtailed games force a change of pacing).
- **Dead-game dampener:** when the batting side's win probability is below {C.DEAD_GAME_WP:.0%} or above {1 - C.DEAD_GAME_WP:.0%}, the raw index is multiplied by {C.DEAD_GAME_FACTOR}.
  Needing 80 off 12 is not "pressure" in any useful sense.
- **Scale & levels:** the raw score becomes a 0–100 percentile across all deliveries. Low < 34 ≤ Moderate < 67 ≤ High < 90 ≤ Extreme.
- **Pressure ball:** index ≥ **{C.PRESSURE_THRESHOLD}** (top tercile), **or** any ball of a **knockout match** (Final, Qualifier, Eliminator, Semi-final). That is owner rule 4.1.
  Tested at {C.SENSITIVITY_THRESHOLDS} and with the knockout rule switched off.
- The weights are design choices informed by Papers 1–3 and the owner's brief: resource-adjusted difficulty carries the largest weight, as the brief specifies.
  Because the final index is a percentile, only the *ordering* of balls matters, and the sensitivity checks show the rankings barely move when the cut-off changes.
""")

with st.expander("Resource table: the DLS-style engine behind 'difficulty' (Papers 1 & 3)"):
    st.markdown("""Built from this dataset, not the official DLS table. For every first-innings state of an uninterrupted 20-over
innings we record the runs still to come and fit a **monotone gradient-boosting** model (more balls left → more runs; more wickets
lost → fewer runs), with competition type and season as covariates (IPL scoring rose sharply from 2024). A second model fits the
spread. Run value of a wicket at any state = E[runs | balls, w] − E[runs | balls, w+1].""")
    rt = data.load("resource_table")
    if len(rt):
        ipl = st.radio("Competition", ["IPL", "T20I"], horizontal=True)
        t = rt[rt.is_ipl == (1 if ipl == "IPL" else 0)].pivot_table(index="wkts_before", columns="balls_rem", values="expected_runs")
        fig = px.imshow(t, color_continuous_scale=SEQ, aspect="auto", labels=dict(x="Balls remaining", y="Wickets lost", color="Exp. runs"))
        st.plotly_chart(style(fig, 360), width="stretch")

with st.expander("Win probability (used for closeness and WPA)"):
    wp = S.get("win_probability_model", {})
    st.markdown(f"""Two gradient-boosting classifiers with monotone constraints. Chase features: runs required, balls left, wickets lost,
RRR, chase-difficulty z, competition. First innings: score, balls left, wickets, projected total, par gap, competition, season.
**Cross-fitted** over {C.N_FOLDS} folds grouped by match, so no ball is scored by a model that saw its own match.
Holdout-fold AUC: chase **{wp.get('innings_2', {}).get('auc', 0):.3f}**, first innings **{wp.get('innings_1', {}).get('auc', 0):.3f}**.
WP after a ball = WP before the next ball. At the innings break it equals 1 − the chasing side's starting WP; after the final ball it equals the result.
No-result matches carry zero WPA.""")

ui.section("3 · Expected performance and Pressure Contribution (Paper 5)")
st.latex(r"\text{Batter PC} = \sum_{\text{pressure balls}} \big[(r - \hat r) - RV_w\,(d - \hat d)\big] \qquad "
         r"\text{Bowler PC} = \sum_{\text{pressure balls}} \big[(\hat r - r) + RV_w\,(w - \hat w)\big]")
st.markdown("""
- **r̂, d̂** come from cross-fitted gradient-boosting models: the runs and dismissal probability a *comparable* batter would produce from that exact
  state (innings, over, balls left, wickets, RRR, par gap, pressure index, competition, season, opposition tier) **and role cohort**
  (batting position, as Paper 5 recommends), against that bowler type and that bowler's **pre-match form** (career-to-date economy and wicket rate, shrunk).
- **ŵ, r̂ for bowlers** additionally adjust for **batter quality**: the striker's pre-match strike rate, shrunk to the league mean (Paper 7).
- **RV_w** is the run value of a wicket at that state, taken from the resource table. Getting out at 3/40 after 12 overs costs more than at 7/180 after 19.
- **Clutch score (Paper 3):** the same per-ball contribution over *all* balls, weighted by (index/100)², reported per 100 balls. A run in a hard chase counts more than one in an easy chase.
- **Current form:** contribution recomputed for 2025–26 only. It is shown in profiles and used as the tie-breaker.
""")

ui.section("4 · Consistency under pressure: the key ranking context")
a, b = st.columns(2)
with a:
    st.markdown(f"""**Batters** (pressure balls only)
- *Pressure innings*: ≥ {C.BAT_MIN_PRESSURE_BALLS_INNINGS} pressure balls faced, or dismissed on a pressure ball.
- *Impact innings*: ≥ **{C.BAT_IMPACT_RUNS} pressure runs**.
- *Qualifying innings*: ≥ {C.BAT_QUAL_RUNS_SR[0]} pressure runs at SR ≥ **{C.BAT_QUAL_RUNS_SR[1]}**, **or**
  ≥ {C.BAT_QUAL_RUNS_SITUATION} pressure runs at a strike rate above the situation's required SR (chase: RRR/6 ×100; 1st innings: expected run rate for the state).
- Impact Rate and Qualifying Rate are knockout-weighted (knockout innings count ×{C.KNOCKOUT_INNINGS_WEIGHT}).
- Stability = 1 / (1 + CV of pressure runs across pressure innings).
- **Consistency = 0.4·z(Impact) + 0.4·z(Qualifying) + 0.2·z(Stability)**.""")
with b:
    st.markdown(f"""**Bowlers** (pressure balls only)
- *Pressure spell*: ≥ {C.BOWL_MIN_PRESSURE_BALLS_SPELL} legal pressure balls in the match, or a pressure wicket.
- *Wicket spell*: ≥ 1 pressure wicket. *Impact spell*: ≥ **{C.BOWL_IMPACT_WKTS}** pressure wickets.
- *Dot-reliable spell*: pressure dot% ≥ **{C.DOT_THRESHOLD:.0%}** (tested at {', '.join(f'{d:.0%}' for d in C.SENSITIVITY_DOT)}).
- *Qualifying spell*: a wicket spell **or** a dot-reliable spell.
- Stability = 1 / (1 + sd of spell pressure economy ÷ pool pressure economy). Dividing by the bowler's own mean would flatter expensive bowlers.
- **Consistency = 0.25·Wicket + 0.15·Impact + 0.20·Dot + 0.20·Qualifying + 0.20·Stability** (z-scores).""")
st.markdown("A single big knock or one five-wicket spell moves these *rates* very little. Repeating it is what scores.")

ui.section("5 · Rating construction")
st.dataframe(pd.DataFrame({
    "Component": ["Consistency", "Contribution vs expected", "Delta vs own baseline", "Win Probability Added",
                  "Team-relative standout", "Knockout impact"],
    "Weight": [C.BAT_WEIGHTS[k] for k in ["consistency", "contribution", "delta", "wpa", "standout", "knockout"]],
    "Batters": ["Impact, qualifying, stability (above)",
                "½ PC per pressure ball + ½ clutch score",
                "Mean z of: (pressure − normal) runs-above-expected per ball; pressure SR − normal SR; normal − pressure dismissal rate",
                "Σ WPA on pressure balls per pressure innings",
                "Own pressure SR − team-mates' pressure SR in the same innings, weighted by balls",
                "Runs above expected and WPA per knockout innings, shrunk toward 0"],
    "Bowlers": ["Wicket, impact, dot-reliable, qualifying, stability",
                "½ runs saved per pressure ball (incl. wicket value) + ½ clutch score",
                "Mean z of: contextual delta; normal − pressure economy; pressure − normal dot%; pressure − normal wickets/ball",
                "−Σ WPA (batting side) on pressure balls per pressure spell",
                "Team-mates' pressure economy − own, same match",
                "Runs saved and WPA per knockout match, shrunk toward 0"]}),
    hide_index=True, width="stretch")
st.latex(r"x^{shrunk} = \frac{n\,x + m\,\mu}{n+m},\qquad s_k = 100\,\Phi(z_k),\qquad \text{Rating} = \sum_k W_k\, s_k")
st.markdown(f"""
- **Bayesian shrinkage (Paper 8):** rates over innings use m = {C.PRIOR_INNINGS} innings, per-ball rates m = {C.PRIOR_BALLS} balls, knockout m = {C.PRIOR_KO} matches.
  μ is the eligible-pool mean. A player with few pressure innings is pulled toward average.
- Each component is z-scored across the eligible pool and mapped to 0–100 with the normal CDF, then weighted. 50 = pool average.
- **Why not average × strike rate (Paper 9):** that product over-rewards high-SR cameos and is distorted by not-outs.
  Runs above expected and dismissal-rate deltas avoid both problems, and a few balls at a huge SR are tamed by shrinkage.
- **IPL vs T20I fairness:** expected values condition on competition type, season and opposition tier (associate / A sides).
  Every comparison is therefore against the same context, and each player is also compared with his own baseline.
""")

ui.section("6 · Eligibility")
st.markdown(f"""
| Rule | Batters | Bowlers |
|---|---|---|
| Minimum pressure innings / spells | {C.BAT_MIN_PRESSURE_INNINGS} | {C.BOWL_MIN_PRESSURE_SPELLS} |
| Minimum pressure balls | {C.BAT_MIN_PRESSURE_BALLS} | {C.BOWL_MIN_PRESSURE_BALLS} |
| Played in {C.ACTIVE_YEAR} | required for pressure rankings & Pressure Player Explorer | same |
| Pakistan players (team ids {sorted(C.EXCLUDED_NATIONAL_TEAM_IDS)}) | excluded | excluded |
| Result | **{cnt.get('eligible_batters', '—')} batters** | **{cnt.get('eligible_bowlers', '—')} bowlers** |

Players who last played in 2025 or earlier remain in the **Overall Player Explorer** (owner rule 4).
{cnt.get('excluded_pakistan_players', '—')} Pakistan players are excluded from rankings; the overall explorer can show them with a toggle.
""")

ui.section("7 · Validation & reliability")
st.markdown(f"""
- **Index validation (Paper 4):** train 2022–24, holdout 2025–26. Outcomes are compared by pressure level, the index is correlated with
  per-ball win-probability swing, and its information is tested *beyond RRR alone* (holdout AUC for dismissals, boundaries and high-leverage balls).
  As a match-level check, mean chase pressure in overs 11–20 is used to classify the result. See *Model Reliability*.
- **Bootstrap:** {S.get('n_bootstrap', C.N_BOOTSTRAP)} draws resample each player's own innings/spells. Outputs: 90% rating interval, rank range, P(top 10).
  **Reliability label**: *High* = P(top 10) ≥ 50% **and** never worse than 15th in any sensitivity scenario. *Medium* = P(top 10) ≥ 25% or worst scenario rank ≤ 20. *Low* = otherwise.
- **Sensitivity:** {len(C.WEIGHT_SCENARIOS) - 1} weight sets, pressure thresholds {C.SENSITIVITY_THRESHOLDS}, knockout rule on/off, dot threshold {C.SENSITIVITY_DOT},
  DLS matches excluded, IPL-only and T20I-only. Each reports Spearman correlation and top-10 overlap with the base ranking.
""")

ui.section("8 · Owner ideas → implementation")
st.dataframe(pd.DataFrame({
    "Idea": ["1 Match experience", "2 Previous situation & performance", "3 Match-ups", "4 In-match lines/lengths & previous over",
             "5 Current form (batter & bowler)", "6 After continuous wickets / vs high run rate", "7 Non-striker context",
             "8 Lengths a batter hits / gets out to", "F1 Venue & zone strengths", "F2 Wicket clustering by stage",
             "F2.1 Recovery after quick wickets", "F3 Innings split", "Macro: stage & DLS", "Micro: RRR, CRR, wickets, balls, death, PP recovery"],
    "Where": ["Pre-match balls faced/bowled feed form shrinkage; matches shown in profiles",
              "Pre-match career form used as opponent quality in expected models",
              "Match-Up Analysis page (head-to-head overall and on pressure balls)",
              "Over-sequence table: bounce-back economy after a 12+ over; wicket deliveries by type",
              "Pre-match form features in expected models; 2025–26 form window as tie-breaker",
              "Batting index 'stage' (2+ wkts in 18 balls, PP collapse); bowling index 'momentum' (last-12-ball RR)",
              "Batting index 'partnership' (tail-ender non-striker, new batter)",
              "Match-Up page + profile delivery-type charts, pressure vs normal",
              "bat_zones / bowl_zones: venue country, delivery style, pace/spin, line, stroke",
              "wickets table → profile 'Wicket clusters' (phase × dismissal × pressure)",
              "bat_zones 'collapse' and 'delivery_after_collapse'",
              "bat_zones / bowl_zones 'innings' and 'match_type' (knockout)",
              "Stakes multiplier, DLS targets/overs, knockout full-match rule",
              "Pressure index components (see section 2)"]}), hide_index=True, width="stretch")

ui.section("9 · Literature")
st.markdown("""
1. Mallawa Arachchi, Manage & Scariano (2024). *A Pressure Index for the Team Batting Second in T20I Cricket.* JSA 10(1). Continuous, resource-based index.
2. Bhattacharjee & Lemmer (2016). *Quantifying the pressure on the teams batting or bowling in the second innings…* IJSSC. Separate batting/bowling pressure, partnerships.
3. Thomson, Perera & Swartz (2021). *Contextual batting and bowling in limited overs cricket.* SASJ 55(1). Clutch batting/bowling, resource tables.
4. Bhattacharjee & Talukdar (2020). *Predicting outcome of matches using pressure index: evidence from T20.* CSSC 49(11). Train/holdout validation.
5. Davis, Perera & Swartz (2015). *Player evaluation in Twenty20 cricket.* JSA 1. Expected run differential, role cohorts, career vs form.
6. Irvine & Kennedy (2017). *Performance indicators that most significantly affect international T20.* IJPAS 17(3). Dots, wickets, run rate.
7. Jamil et al. (2023). *Factors impacting death-phase batting and bowling in ODI cricket.* IJPAS 23(2). Length, line, batter quality, wickets in hand.
8. Chathurangi et al. (2025). *Impact ranking methodologies in limited-overs cricket: a systematic review.* IJSSC 20(3). Composite, Bayesian, multi-criteria ranking.
9. Bhattacharjee, Saikia & Das (2025). *Redefining a format-specific batting performance measure.* JORS 76(11). Pitfalls of average × SR.
10. Ramanan et al. (2026). *Match analysis trends in limited overs professional cricket: a systematic review.* IJSSC. Research gap.
""")

ui.section("10 · Limitations")
st.markdown("""
- **Weights are judgement-based.** They follow the brief and are stress-tested, not learned. The sensitivity page shows how much they matter.
- **Samples are small.** A regular player has 15–60 pressure innings over five seasons. Intervals are wide and ranks 5–15 are often statistically tied (see P(top 10)).
- **Knockouts are rare** (31 matches), so the knockout component is heavily shrunk.
- **Line/length is coarse.** `delivery_style` (yorker, bouncer, full toss, swing, spin type) and on/off side stand in for true pitch-map length and line.
- **Fielding, captaincy and match-ups chosen by captains** are not modelled. Bowlers used mainly at the death meet more pressure balls by role,
  which the expected models adjust for (phase and over are features) but cannot remove entirely.
- **Associate-nation T20Is** are adjusted through an opposition-tier feature, not a full opponent-strength model.
- **First-innings pressure** depends on a par score, which is less certain than a chase target. Win-probability AUC is lower there.
""")

ui.section("11 · IPL 2027 auction module (Rajasthan Royals)")
st.markdown("""
- **Status data:** retention-day lists of 17 Nov 2026 (owner summary reconciled with CricTracker, Outlook India, India TV, SportsCafe and
  CricketAddictor), stored with sources in `src/ipl2027_data.py`. Disagreements are flagged as *disputed*, not resolved.
- **RR squad profile:** the 19 retained players' career pressure records. Phase coverage = the squad's pooled runs above expected (batting)
  and runs saved incl. wicket value (bowling) per 100 pressure balls in the powerplay, middle and death overs.
- **Needs:** each phase's weight is proportional to how far RR's contribution in that phase sits below its best phase.
- **Targets:** released players (plus a separate wildcard watch list of ranked internationals with no IPL squad).
  **RR fit = 0.6 × pressure quality + 0.4 × phase fit**. Pressure quality is the ranked rating when available, otherwise a provisional score
  from shrunk contribution. Phase fit is the need-weighted, sample-shrunk phase contribution. Players inactive in 2026 lose 5 points;
  wildcards lose 3 for registration and adaptation risk.
- **6-slot plan:** confirmed releases only, at most 3 overseas, with role quotas (2 death/new-ball seamers, 1 bowler, 1 finisher, 1 batter,
  1 best remaining fit). Disputed or doubtful players appear as conditional upgrades. Prices are not modelled.
- Rebuild with `python -m src.auction` (also run at the end of the pipeline).
""")
