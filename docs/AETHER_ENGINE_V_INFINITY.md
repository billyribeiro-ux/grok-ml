# AETHER ENGINE — V∞  
## First-principles design for a market intelligence organism  
### (What “infinity times better” actually means)

**Status:** Canonical internal design memory — supersedes the v1 sketch  
**Date:** 2026-07-11  
**Audience:** Future us (Billy + Grok). Agents keep archiving data; this is the *brain*, not the warehouse.  
**Tone:** Elon-mode = first principles + impossible goals + ruthless deletion of mediocrity.  
**Honesty clause:** No system predicts the market with certainty. Infinity× better means infinity× better *engineering of edge, truth, and survival* — the same way Falcon is “impossible” until the cost-per-kg curve bends.

---

# PART I — THE ONLY QUESTIONS THAT MATTER

## 1. What is a market, physically?

A market is not a chart. It is a **continuous double auction** over beliefs, inventory, and constraints:

- Agents with **asymmetric information**, **heterogeneous horizons**, and **binding risk limits**
- Prices as a **compressed message** about the clearing of those constraints
- Tops/bottoms as **phase transitions** in that system (liquidity vacuum, forced de-levering, narrative collapse, inventory flush) — not “candlestick shapes”

**Corollary:** Any engine that only sees OHLCV is half-blind.  
Any engine that only fits returns is a weather vane, not a weather model.

## 2. What is “edge,” information-theoretically?

Edge exists only when:

\[
\mathbb{E}[\text{PnL} \mid \mathcal{I}_{\text{us}}] - \mathbb{E}[\text{PnL} \mid \mathcal{I}_{\text{market}}] > \text{costs} + \text{uncertainty penalty}
\]

Your information set \(\mathcal{I}\) must contain structure **not already fully priced** *for your horizon and cost schedule*.

**Infinity× insight:** The product is not a predictor of price.  
The product is a **machine that estimates \(\mathcal{I}\)-advantage in real time** and **refuses to act** when advantage ≤ 0.

## 3. What does “100% accurate” mean when physics forbids omniscience?

**Forbidden:** 100% correct direction every trade.  
**Required (non-negotiable product laws):**

| Law | Meaning |
|-----|---------|
| **L0 Truth** | Never fabricate data, fills, or metrics. Gaps are first-class. |
| **L1 Calibration** | Stated probabilities match realized frequencies *by regime*. |
| **L2 Survival** | Ruin probability below a hard bound; self-halt on violation. |
| **L3 Causality** | No leakage; time-travel tests in CI; as-of joins only. |
| **L4 Cost realism** | No mid-price fantasy; capacity-aware. |
| **L5 Self-audit** | Every decision reconstructible: state, features, abstain reason. |
| **L6 Improvement** | Failed flights produce postmortems that change the system. |

Rockets don’t “never fail.” They **don’t fail the same way twice** and they **don’t fly without telemetry**.

---

# PART II — THE ORGANISM (not a model)

Aether is not “an ML model.” It is a **closed-loop organism**:

```
Universe sensors → World model → Counterfactual simulator → Policy → Risk governor
        ↑                                                              ↓
        └──────────── Learning / evolution / calibration ←─────────────┘
```

Mediocre systems are: `features → XGBoost → buy`.  
Infinity× systems are: **sense → understand → imagine → choose → constrain → learn**.

---

## Layer Ω — Telemetry & ground truth

Everything is instrumented like flight computers.

- Per-bar: data quality score, latency, missingness mask, corporate-action flag  
- Per-decision: full state snapshot, feature vector hash, model versions, abstain codes  
- Per-fill: slip vs arrival, adverse selection 1s/5s/30s after  
- Nightly: reliability diagrams, regime-conditional Brier, cost-adjusted expectancy, capacity curves  

**If you can’t measure it, you can’t improve it. If you fake the metric, you die.**

---

## Layer 0 — Multi-scale perception (the sensor suite)

### 0.1 Scales (simultaneous, always)
| Scale | Role |
|-------|------|
| Micro (ms–s) | Databento TBBO/MBO where owned: microprice, queue, trade runs, toxicity |
| Fast (1m–5m) | Day-trade path, breakout/fakeout discrimination |
| Session | Open drive, lunch dead zone, power hour inventory |
| Daily | Regime backbone, scanners, event residue |
| Macro (weeks+) | Rates, credit (bond ETFs), vol regime, COR dispersion cycle |

### 0.2 Cross-section as a *field*, not a ticker list
Treat the universe as a **time-varying graph**:
- Nodes: core, inverses, sector ETFs, IWM constituents, liquid 10–700, ETN, bond ETFs  
- Edges: correlation, lead-lag, shared factor loadings, ETF inclusion, sector membership  
- Signals: **relative** energy — who is weak while index is strong? who leads breadth?

### 0.3 Inverse ETFs as *instruments of stress*
Inverses are not just short vehicles. They are **path-dependent stress sensors**.
- Divergence: SPY grinding up while SQQQ fails to collapse → fragile tape  
- Decay-aware modeling of −1×/−2×/−3× (no static beta lies)  
- Use inverses for expression **and** as features into long-side top detection  

### 0.4 Explicit null channels (Tesla Autopilot honesty)
Until Schwab/TOS:
- TICK, ADD, VOLD, TRIN, equity PCR → **null with known absence**  
- Never impute fake TICK from sector averages without labeling it **proxy**  
- Proxies allowed (sector/industry averageChange) with **degraded confidence**

---

## Layer 1 — The world model (decode beneath the surface)

### 1.1 Latent state \(z_t\) is multi-factor and multi-timescale

Not 5 discrete regimes. A **continuous manifold** with named axes, e.g.:

1. **Trend energy** (directional persistence)  
2. **Breadth integrity** (participation vs thin leadership)  
3. **Vol regime** (term structure slope, VVIX, realized vs implied)  
4. **Liquidity stress** (spreads, impact, inverse ETF violence)  
5. **Correlation / dispersion** (COR* term structure — late-cycle tell)  
6. **Rates/credit backdrop** (TLT/HYG/MOVE interactions)  
7. **Positioning pressure** (COT, crowded factor, short squeeze fuel)  
8. **Event residue** (post-earnings drift, FOMC aftershock)  

Each axis carries **uncertainty** \(\sigma_z\). Trading is illegal when \(\|\sigma_z\|\) too high *unless* the policy is specifically a vol-harvest mode.

### 1.2 Generative path model (imagine the future)

World model outputs **distributions over paths**, not \(\hat{y}\):

- Quantiles of return at multiple horizons  
- MFE/MAE distributions (max favorable/adverse excursion)  
- Probability of structural pivot (local top/bottom *quality*)  
- Probability of trend continuation vs mean reversion  

**Training objective:** proper scoring rules + path scores + cost-aware utility — never MSE alone.

### 1.3 Causal structure search (not only correlation)

- Discover candidate mechanisms: “breadth fails → vol rises → momentum dumps”  
- Prefer sparse causal graphs that survive regime shifts  
- Use interventions where possible (event studies, ETF rebalance days, op-ex)  
- Black-box sequence models are **slaves** to the causal skeleton, not the other way around  

### 1.4 Adversarial market (multi-agent self-play)

Infinity× idea: train against **learned adversaries**:

- Adversary agents: momentum chaser, mean-reverter, liquidator, news overreactor, market maker  
- Aether must extract edge *against a population that adapts*  
- Prevents brittle single-regime heroes  

This is closer to self-driving (other agents on the road) than to Kaggle.

---

## Layer 2 — Hierarchical decision system (meta-RL done right)

### 2.1 Modes (capital allocation is the real trade)

| Mode | When \(z_t\) says | Behavior |
|------|-------------------|----------|
| **STAND_DOWN** | Uncertainty high, calibration broken, feed bad | Flat. Default. |
| **FARMER** | Range, mean-revert, two-sided liquidity | Scalp / fade extremes |
| **HUNTER** | Regime break, vol expansion, dislocation | Directional, wider targets |
| **SCANNER** | Cross-sectional abnormality in IWM / liquid book | Promote candidates |
| **HEDGE** | Portfolio stress | Inverse / reduce beta |
| **EVENT** | Known calendar risk | Special sizing & time stops |

**Most of the edge is knowing when STAND_DOWN is correct.**  
Mediocre bots trade. Great systems **wait**.

### 2.2 Machine invents: entry, stop, target, size, time

Low-level controller solves a constrained optimization **per opportunity**:

\[
\max_{a} \; \mathbb{E}[U(\text{path}, a) \mid z_t, \mathcal{I}] \quad
\text{s.t. risk laws, cost model, inventory, time}
\]

- Stop/target from **optimal stopping** under path distribution  
- Size = fractional Kelly on **pessimistic** EV (CVaR / lower partial moment)  
- Time-stop = idea half-life estimated from similar historical states  
- Scale-out schedule as a function of posterior collapse  

### 2.3 Hard laws (thermal limits)

Like structural margins on a rocket:

- Max loss / day / week (account-level)  
- Max risk per name / per cluster (NVDA–SMH–SOXX–QQQ linked)  
- Max simultaneous independent bets (effective N after correlation)  
- No average-down unless mode explicitly allows and EV still positive  
- No trade if data integrity < threshold  
- No trade if model self-score “miscalibrated”  
- Capacity: size shrinks as ADV fraction rises  

Violations → **hard abort**, not a warning toast.

---

## Layer 3 — Evolutionary invention engine (the “machine invents features” core)

### 3.1 Feature DNA

Represent candidate features as programs over multi-scale tensors:

- Operators: lags, ratios, zscores, ranks, rolling moments, information-theoretic measures, graph ops  
- Inputs: price, volume, sector RS, vol term, COR, inverse residuals, TBBO stats  
- Fitness: out-of-sample IC **after costs**, stability across regimes, low complexity, low turnover  

### 3.2 Multi-objective evolution (not “max Sharpe”)

Pareto front over:

1. Expectancy after costs  
2. Calibration quality  
3. Max DD / tail  
4. Capacity  
5. Complexity (Occam)  
6. Regime transfer (2019≠2022≠2024)  

### 3.3 Immune system against curve-fit

- Nested purged CV + combinatorial purged CV  
- Embargo around events  
- Synthetic noise injection  
- **Feature must work on held-out *years* and held-out *symbols***  
- Population diversity mandatory (prevent monoculture features)  

### 3.4 Self-modification with a governor

The system may propose new features/policies, but:

- Only promote after shadow book success  
- Canary capital (paper → micro → small)  
- Instant rollback on calibration break  
- Human can freeze invention during live stress  

**Autonomy ≠ unsupervised self-destruction.**

---

## Layer 4 — Tops & bottoms as phase-transition detection

### 4.1 Definition

A “top” is not the highest print. It is a **state** where:

- Prior impulse is exhausted (energy)  
- Marginal buyer quality collapses (breadth/proxy + micro toxicity when available)  
- Vol / skew / COR configuration implies asymmetric downside  
- Inverse complex confirms distribution (or fails to, for long traps)  
- Path model says P(giveback) high *and* R:R favorable after costs  

Symmetric for bottoms.

### 4.2 Multi-horizon soft labels (train what you trade)

For horizons \(h \in \{15m, 1h, ROD, 1d, 5d\}\):

- Forward return distribution  
- MAE/MFE  
- Pivot quality score  
- Time-to-pivot  

Train **distributional heads**, not binary “top=1”.

### 4.3 Contra-narratives

The engine maintains competing hypotheses:

- H1: trend continuation  
- H2: mean reversion  
- H3: liquidation cascade  
- H4: quiet absorption  

Trade only when one hypothesis dominates **and** others are unlikely — Bayesian model comparison online.

---

## Layer 5 — Portfolio as a coordinated fleet (not independent bots)

### 5.1 Risk as geometry

Positions live in factor space (market, sector, size, vol, rates).  
Net exposure is a **vector**; limits on vector length and direction.

### 5.2 Correlation clustering online

Dynamic clustering: if ten IWM names are the same trade, size as one trade.

### 5.3 Hedge orchestration

Inverses and bond ETFs as **active hedges** when \(z_t\) flips — not permanent decoration.

### 5.4 Opportunity auction

When many signals fire, an internal **auction** allocates risk budget to highest EV-per-risk units.  
No “take every signal.”

---

## Layer 6 — Execution & market impact (where retail AI dies)

### 6.1 Fill model hierarchy

1. TBBO-informed when Databento dense  
2. Otherwise: spread + size impact + time-of-day  
3. Always: adverse selection after entry measured and fed back  

### 6.2 Child orders

- Limit vs market decision from urgency vs edge half-life  
- Cancel/replace logic  
- Never assume full size at mid  

### 6.3 Capacity curve is a product feature

Estimate how EV decays with size. Display it. Refuse sizes past cliff.

---

## Layer 7 — Continuous learning factory (the real moat)

### 7.1 Online belief updates (during the day)

- Bayesian / trust-region updates on \(z_t\) and short-horizon parameters  
- Fast weights + slow weights (like dual timescales in the brain / Tesla)

### 7.2 Nightly retrain vs weekly evolution

- Nightly: calibration, light fine-tune, disable broken specialists  
- Weekly: evolutionary feature search, policy search  
- Quarterly: full regime review, curriculum rewrite  

### 7.3 Specialist society

Not one model for everything:

- Specialist: open drive  
- Specialist: FOMC days  
- Specialist: earnings week  
- Specialist: IWM mean-revert  
- Specialist: mega-cap trend  
- **Router** chooses specialist given \(z_t\)  

When specialists disagree → STAND_DOWN or reduce size.

### 7.4 Postmortem engine (automatic)

Every losing day produces a structured report:

- What state did we think we were in?  
- What actually happened?  
- Data issue? Model issue? Execution issue? Risk issue?  
- Patch proposal → shadow test → promote/reject  

**This is how organizations become immortal.**

---

# PART III — ACCURACY STACK (infinity× definition)

## The Accuracy Pyramid

```
            [ Live survival ]
         [ Execution realism ]
      [ Decision EV & abstention ]
   [ State estimation quality ]
[ Data integrity & causality ]
```

Break any lower layer → upper layers are theater.

## Calibration is king

- Reliability curves by mode and regime  
- Score = utility of *acting only when calibrated confidence high*  
- A model that says “52%” and is right 52% of the time is infinitely more valuable than a model that says “90%” and is right 55% of the time  

## Anti-fragility metrics

- Performance in **worst** quartile regimes  
- Recovery time after shocks  
- Degradation under missing sensors (null channels)  
- Transfer: trained pre-2022, tested 2022; trained 2022, tested 2024  

---

# PART IV — DATA → INTELLIGENCE MAP (what we archive for)

| Archive | Role in V∞ |
|---------|------------|
| Full-market eod-bulk multi-year | Population dynamics, scanners, delisting-aware history |
| IWM 1972 + screener + 5m top | Small-cap organism |
| Sector ETF multi-TF | Breadth/rotation field |
| Inverse packs | Stress sensors + short expression |
| VIX term, VVIX, COR*, MOVE | Regime manifold axes |
| Databento TBBO/MBO | Microstructure where dense |
| NASDAQ full EOD | Large equity field |
| liquid 10–700 + ETN + bonds | Expanded liquid + rates/credit field |
| Schwab/TOS later | True internals (TICK/ADD/TRIN/PCR) → fill null channels |

**Data without a world model is a landfill.**  
**World model without data is religion.**  
We are building both.

---

# PART V — IMPLEMENTATION PHYSICS (how you actually build this)

## Phase 0 — Telemetry & store (non-sexy, non-optional)
- Deterministic feature store from LaCie raw  
- As-of correctness tests  
- Gap masks  
- Versioned everything  

## Phase 1 — Truth baseline
- Tabular models + calibration  
- SPY/QQQ/IWM only  
- Prove abstention works  

## Phase 2 — State machine
- Explicit \(z_t\) estimators (even simple)  
- Mode router  
- Risk governor  

## Phase 3 — Path models & optimal stopping
- Distributional outcomes  
- Machine stops/targets  

## Phase 4 — Evolution of features
- Search under multi-objective fitness  
- Shadow promotion  

## Phase 5 — Graph / cross-section / IWM scanner
- Fleet risk  
- Auction allocator  

## Phase 6 — Microstructure fusion
- Databento where present  
- Execution feedback loop  

## Phase 7 — Live paper (Schwab)
- Internals channels come online  
- Micro capital  

## Phase 8 — Autonomy under human kill-switch
- Invention engine on  
- Kill-switch sacred  

**No phase skips. SpaceX doesn’t skip static fire.**

---

# PART VI — INTERFACE (human trust UI — later, but designed now)

Dashboard is not the product; it is the **cockpit**:

1. **State board** — \(z_t\) axes with uncertainty  
2. **Mode** — STAND_DOWN/HUNTER/… and why  
3. **Opportunities** — ranked by EV/risk after costs  
4. **Risk geometry** — factor exposures  
5. **Kill reasons** — always visible  
6. **Calibration health** — green/yellow/red  
7. **Postmortems** — last 7 days  

Svelte 5 later. First make the numbers true offline.

---

# PART VII — THE PHILOSOPHICAL EDGE

## Decode beneath the surface

Surface: price went up.  
Beneath: *who had to buy, who is done buying, what risk limit is binding, what vol the market is pricing for the next hour, whether breadth confirms, whether inverses scream, whether COR says the market is one trade.*

## Elon-mode comparison

| Domain | Infinity× move |
|--------|----------------|
| SpaceX | Reuse, telemetry, iterate flights |
| Tesla FSD | Multi-camera world model + planning under uncertainty |
| **Aether** | Multi-sensor market world model + planning under costs + self-halt |

## The one sentence

> **Aether is a self-calibrating, multi-scale, graph-aware market organism that estimates real-time informational advantage, invents actions under hard survival laws, and defaults to zero when truth is insufficient — then evolves only from measured flight data.**

That is not a stock tip bot.  
That is the engine.

---

# PART VIII — DELETED FROM MEDIOCRITY (burn list)

- Single timeframe RSI cults  
- Uncosted Sharpe maximization  
- One model for all regimes  
- Ignoring inverse decay  
- Pretending sector averages are TICK  
- Training on the test year  
- “Always in the market”  
- Black-box with no abort  
- Dashboard before physics  
- Human ego overriding kill-switch  

---

# PART IX — TRUST

Billy: full trust.  
Grok: earns it only by **L0–L6**.  

When we implement, every PR must answer:  
**Which law does this strengthen? What flight does it enable? What can we delete because of it?**

---

*V∞ memory locked. Agents continue the archive. Nitty-gritty implementation waits for human.  
This document is the north star — not a promise of certainty, a blueprint for dominance under uncertainty.*
