# Aether — Elon-mode first-principles engine brainstorm

**Status:** Internal design memory (not a build order yet)  
**Date:** 2026-07-11  
**Context:** Human trusts this direction; data archive runs in parallel (FMP/LaCie, Databento cart, Kimi sessions).  
**Non-negotiable honesty:** Markets do not allow *certainty*. “100% accurate” is redefined below as *100% honest physics* — calibrated probabilities, no fake edge, no silent failures, perfect *accounting* of uncertainty. That is how rockets and autonomy actually win: not by claiming zero error, but by bounding error and surviving it.

---

## 0. Mission statement (first principles)

**Goal:** An autonomous market-intelligence brain that finds *regime-conditional* tops/bottoms and path edges on a defined universe (core names, inverses, sector ETFs, IWM book, liquid $10–$700, ETN/bond proxies), invents features/stops/targets/sizing, and never lies about data or risk.

**Not the goal:** A dashboard that looks smart. A backtest that curve-fits 2023. A model that prints “BUY” without a state estimate of *why the market is offering that trade*.

**Elon-mode constraint stack:**
1. Physics first (microstructure + flow + regime) before narratives.
2. Vertical integration of data → features → decision → risk → learning.
3. Delete parts until it breaks, then add back only what restores capability.
4. Iteration velocity with real feedback (live paper / sim), not slideware.
5. Human-in-the-loop for capital and kill-switch; machine invents the rest.

---

## 1. Redefine “100% accurate” so it is achievable and useful

| Claim (naive) | Claim (engineering-true) |
|---------------|---------------------------|
| Predict every top/bottom | Detect *high-posterior* reversal *states* with known false-positive rates |
| Always profitable | Positive expectancy *after* costs, with drawdown bounds and kill criteria |
| Model is right | Model is *calibrated*: P(win\|score) matches reality in out-of-sample regimes |
| Never lose | Never blow up; losses are bounded, explained, and used as training signal |
| Perfect data | Honest data + explicit gaps (TICK/TRIN via Schwab later; FMP proxies now) |

**Accuracy pillars (must all be true for a decision to fire):**
1. **Data accuracy** — no fabricated bars; timestamps, corporate actions, survivorship handled.
2. **State accuracy** — regime / breadth / vol term / correlation state is estimated with uncertainty.
3. **Decision accuracy** — action only when EV > threshold *and* uncertainty < threshold.
4. **Execution accuracy** — sim fills include spread, latency, partials; never mid-price fantasy.
5. **Self-accuracy** — continuous calibration tests; model freezes itself when miscalibrated.

---

## 2. Architecture: five stacked brains (not one giant net)

### Layer 0 — Perception (sensors)
- Multi-resolution tape: 1m / 5m / 1h / EOD (FMP + Databento TBBO/MBO where owned).
- Cross-asset: indices, VIX term, COR*, MOVE, sectors, inverses, IWM constituents, bond ETFs, commodities.
- Flow proxies: gainers/losers/actives, insider/congress (weak but real), COT, institutional snapshots.
- **Gap sensors:** explicit null channels for TICK/ADD/TRIN/PCR until Schwab/TOS.

### Layer 1 — Causal world model (not pure black box)
Learn a latent **market state** \(z_t\):
- Trend / mean-revert / volatility expansion / liquidation / quiet grind.
- Breadth confirmation vs divergence (sector/industry averageChange as FMP proxy).
- Vol term structure slope (VIX9D/VIX/VIX3M…) + VVIX + COR dispersion.
- Inverse ETF stress (SQQQ/TZA/UVXY behavior vs underlyings — path + decay aware).

World model predicts **distribution** of next path, not a single price:
- Short horizon (minutes–hours) for day trade.
- Session horizon (open→close) for swing of day.
- Multi-day for small-cap scanner (IWM book).

### Layer 2 — Hierarchical policy (meta-RL)
- **High level:** choose *mode* (hunt longs, hunt shorts via inverse, stand down, scalp mean-revert, trend follow).
- **Mid level:** choose *symbol set* from universe (core / sector / IWM scanner / liquid 10–700).
- **Low level:** entry, stop, target, size, time-stop — **invented by the machine** under constraints.

Constraints = hard laws (like thermal limits on a rocket):
- Max risk per trade / per day / per correlated cluster.
- No trade if data integrity flag.
- No trade if calibration broken.
- No averaging down without explicit policy (default: forbidden).

### Layer 3 — Meta-learning (learn to learn)
- Fast adaptation when regime shifts (2020 crash ≠ 2023 melt-up ≠ 2022 bear).
- Outer loop optimizes *objective of calibration + survival*, not raw PnL alone.
- Inner loop updates beliefs during the session (Bayesian or online gradient with tight trust region).

### Layer 4 — Truth & safety officer (always on)
- Shadow book: every signal paper-traded with honest fills.
- Kill switch: daily loss, error spikes, feed lag, LaCie/API down.
- Attribution: which features/state drove the call (even if model is deep — require probes).
- Human dashboard later (Svelte): state, EV, size, kill reasons — not pretty charts first.

---

## 3. Best-of-best ideas (ranked by leverage)

### Idea A — “Reversal is a state, not a pattern”
Tops/bottoms are **regime exits**, not RSI crosses.
- Detect *exhaustion + divergence + vol + inverse confirmation*.
- Multi-scale agreement: 1m impulse, 5m structure, daily context.
- Inverse ETFs as **stress gauges** (not just trade vehicles): when SQQQ/TZA refuse to confirm, long-side “top” calls get downgraded.

### Idea B — Machine-invented features with a physics prior
- Genetic / neural architecture search over transforms of:
  - returns, range, volume imbalance proxies, sector relative strength,
  - VIX term slopes, COR term slopes, MOVE, breadth sector A/D proxy,
  - Databento TBBO: microprice, queue imbalance, trade sign runs (where owned).
- Prior: features must be **causal-plausible** (liquidity, risk premium, positioning), not pure noise hash.
- Regularize by: stability across regimes, low turnover, cost-aware IC.

### Idea C — Stops/targets as optimal stopping, not fixed %
- For each entry belief, solve for stop/target that maximize EV under the world-model path distribution.
- Time-stop is first-class (theta of the idea dies).
- Partial scale-out when posterior of trend continuation collapses.

### Idea D — Sizing = Kelly under uncertainty, not full Kelly
- Use **fractional Kelly on lower-confidence EV** (distributional, not point).
- Cluster risk: NVDA + SMH + SOXX + SQQQ hedge awareness = one risk bucket.
- Hard cap when COR↑ and breadth narrows (dispersion dying).

### Idea E — Dual books: “Hunter” and “Farmer”
- Hunter: event/regime breaks, wider targets, lower frequency.
- Farmer: mean-revert in high-liquidity names when vol is range-bound.
- Meta-policy allocates capital between books by state \(z_t\).

### Idea F — Small-cap scanner as a separate organism
- IWM holdings (~1972) + liquid 10–700 book.
- Rank by *abnormality*: volume shock, sector-relative move, float/mcap context, gap quality.
- Only promote to tradeable when microstructure (if any) + daily context agree.
- Survivorship: use delisted lists + eod-bulk history carefully.

### Idea G — Inverse-native shorting
- Prefer liquid inverses when shorting hard-to-borrow names is painful.
- Model **decay and path dependence** of leveraged ETFs explicitly (not “−3× beta forever”).
- Pair: long core + long inverse as *hedge state* when uncertain, not as hopium.

### Idea H — Continuous calibration factory
- Nightly: reliability diagrams, Brier score by regime bucket, cost-adjusted expectancy.
- Auto-disable strategies that fail calibration for N sessions.
- Never re-enable without out-of-sample recovery — like flight software interlocks.

### Idea I — Data as a first-class product
- LaCie raw is sacred; build a **feature store** with deterministic rebuilds.
- Every feature has: source, as-of time, quality flag, gap mask.
- Training never sees future bars (strict time travel tests in CI).

### Idea J — Execution realism from day one
- Even offline: spread model from TBBO when present; else conservative BBO proxy.
- Slippage scales with size and ADV; IWM names get harsher costs.
- If edge < 2× estimated cost, signal is zero.

---

## 4. Labeling tops/bottoms (the hard problem)

Do **not** label “the” top as a single tick.

**Multi-horizon path labels:**
- Forward return distributions at 15m / 1h / rest-of-day / 1–5 sessions.
- Drawup/drawdown excursion (MFE/MAE).
- “Reversal quality”: how much of the prior impulse is given back within horizon.
- Soft labels: probability the next structural pivot is a local extreme under noise model.

**Regime-conditional labels:**
- Same pattern in low-vol grind ≠ high-vol liquidation.
- Train separate heads or conditioned towers on \(z_t\).

**Adversarial labels:**
- Synthetic microstructure noise / missing bars / delayed opens to force robustness.

---

## 5. Model stack candidates (use the simplest that works)

1. **Gradient-boosted tables** on engineered + invented features for baseline truth.
2. **Temporal models** (TCN / Transformer / SSM) on multi-scale sequences.
3. **Graph model** across sector/IWM peers (relative strength graph).
4. **World model + policy** (Dreamer-like or MuZero-ish for discrete actions: flat/long/short/inverse).
5. **Ensemble with disagreement**: trade only when models *agree on direction* and *disagree little on risk*.

Start with (1)+(5); add deep only when tables plateau *with honest costs*.

---

## 6. Training curriculum (SpaceX-style iterative flights)

| Flight | Objective |
|--------|-----------|
| F1 | Data integrity + feature store + no leakage CI |
| F2 | Calibrated direction on SPY/QQQ/IWM only |
| F3 | Add inverses; prove short-side EV after decay |
| F4 | Sector rotation confirmation layer |
| F5 | IWM scanner paper book (tiny notionals) |
| F6 | Multi-name risk clustering |
| F7 | Live paper via Schwab (when wired) |
| F8 | Micro-size live capital with hard kill |
| F9 | Meta-RL mode switching |
| F10 | Full autonomy under human kill-switch only |

Each flight has a **go/no-go checklist**. No skipping.

---

## 7. What we will *not* do (delete list)

- Optimize raw backtest PnL without costs.
- Train on shuffled days.
- Use future earnings knowledge accidentally.
- Treat leveraged ETF as static beta.
- Claim TICK/TRIN edge without the series.
- Silent `try/except` that swallows feed failures.
- “AI said so” without state dump.
- Infinite leverage mental models.

---

## 8. Integration with data we already own / are pulling

| Data | Engine use |
|------|------------|
| eod-bulk 2015/2019→2026 | Universe-wide daily brain, scanners, regime history |
| IWM 1972 + screener + 5m top | Small-cap organism |
| Sector ETF multi-TF | Rotation / confirmation |
| Inverses packs | Short expression + stress gauges |
| VIX term, VVIX, COR*, MOVE | Regime & tail state |
| Databento TBBO/MBO (partial) | Microstructure features where dense |
| liquid_10_700 + ETN + bonds (Session B) | Expanded liquid book, rates risk |
| NASDAQ full EOD | Large liquid/semi-liquid equity set |
| Schwab/TOS later | True TICK/ADD/TRIN/PCR + live |

---

## 9. Metrics that matter (scoreboard)

- **Calibration** by regime (not just accuracy).
- **Expectancy after costs** per mode.
- **Max DD / time-to-recover**.
- **Tail ratio** and worst-day PnL.
- **Turnover** and capacity (can we size up?).
- **Disagreement rate** (safety).
- **Data integrity uptime**.
- **False confidence rate** (high score, losing trades).

---

## 10. Human trust contract

Human trusts “Elon mode.” Machine earns it by:
1. Never faking data.
2. Never hiding losses in metrics.
3. Preferring no-trade to random trade.
4. Explaining state in plain language on the future dashboard.
5. Improving from every failed flight with a written postmortem.

---

## 11. Immediate next design steps (when human returns)

1. Freeze v1 **universe definitions** (files on LaCie → machine-readable manifests).
2. Spec **label math** (horizons, MFE/MAE, costs).
3. Spec **risk laws** (numbers).
4. Choose **F1 offline baseline** (tabular + calibration).
5. Wire **feature store** rebuild from LaCie raw only.
6. Defer Svelte dashboard until F2 works offline.

---

## 12. One-sentence north star

**Aether is a self-calibrating, regime-aware decision engine that only acts when its world model says the edge survives reality — microstructure, costs, and uncertainty included — and otherwise does nothing.**

---

*End of internal brainstorm memory. Agents continue data archive. No build until human resumes nitty-gritty.*
