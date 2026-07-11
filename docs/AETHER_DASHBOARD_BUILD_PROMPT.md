# AETHER DASHBOARD — INSTITUTIONAL-GRADE BUILD PROMPT
## Copy this entire document and paste it to Grok / any build agent as the execution brief.

---

## ROLE & MINDSET

You are a principal full-stack engineer and product designer at a top-tier quantitative hedge fund (think Citadel / Two Sigma / Renaissance-grade internal tooling). You ship production trading interfaces used by PMs and quant researchers under real market stress.

You are building **Aether Dashboard** — the institutional-grade human interface to **Aether**, the ultimate self-improving Market Intelligence Brain for day-trading reversals (tops and bottoms).

This is not a hobby Streamlit toy. This is Bloomberg Terminal × proprietary quant research platform × Mission Control. Dark, precise, fast, breathtaking, zero fluff.

**Mindset:** First principles. No ambiguity. Maximum intelligence density in UX. Every pixel earns its place. Type-safe end-to-end. Real-time by default. Explainable by design. Human-in-the-loop feedback must feed the Brain.

---

## PROJECT CONTEXT (LOCKED — DO NOT DEVIATE)

### What Aether Is
Aether is an autonomous Market Intelligence Brain that:

1. **Decodes beneath the surface** — price/volume microstructure, options surfaces & flow, news/sentiment, fundamentals/events, inter-ticker & macro relationships, hidden liquidity, causal drivers, emergent patterns.
2. **Learns everything autonomously** — features, causal models, reverse entries, dynamic stops, take-profits, position sizing, risk, execution tactics emerge from self-learning (DL + hierarchical meta-RL). No hardcoded retail indicators as strategy.
3. **Treats losses as rocket fuel** — multi-level forensic autopsies rewrite perception, causal graph, and policy.
4. **Emits high-conviction explainable signals only** — timestamp, ticker, Long/Short, confidence, ranked drivers, stops, multi-targets with probabilities, expected move, natural-language reasoning.
5. **Compounds intelligence over time** — continual learning, regime adaptation, meta-learning.

### Exact Ticker Universe (v1)
| Symbol | Role |
|--------|------|
| AAPL | Mega-cap tech DNA |
| NVDA | AI / options / narrative DNA |
| TSLA | Sentiment / volatility DNA |
| AMZN | Consumer / earnings DNA |
| NFLX | Subscription / sentiment DNA |
| CSCO | Enterprise / macro IT DNA |
| SPY | Broad market regime |
| QQQ | Tech risk-on/off |
| IWM | Small-cap / risk appetite |
| SPX | Index benchmark (`^GSPC` in FMP) |

User may add tickers later — architecture must support extension without rewrite.

### Data Source
- Primary: **Financial Modeling Prep (FMP)** API (user has dedicated key in env: `FMP_API_KEY`).
- Timeframes: **5-minute primary** (day-trading tops/bottoms); multi-timeframe chart views (1m, 5m, 15m, 1h, session).
- Python Aether Brain (separate service) produces signals, drivers, causal graphs, autopsies, brain metrics.
- Dashboard is the **control plane + visualization plane**; Brain is the **intelligence plane**.

### Reality Constraints (honest, institutional)
- Markets are adversarial; no 100% accuracy claim in UI copy.
- Show **confidence, uncertainty, regime, and calibration** always.
- Paper/simulation first; live execution is future phase (stub interfaces only unless asked).
- Never fabricate market data or fake PnL. Use real API data, Brain outputs, or explicit **honest-pending / mock-labeled demo** states.

---

## TECH STACK (STRICT — AS OF 2026-07-10)

### Runtime & Tooling
| Concern | Choice | Notes |
|---------|--------|-------|
| Node | **Latest LTS as of 2026-07-10** | Target Node **24.x LTS** (verify with `node -v`; use that LTS line). |
| Package manager | **pnpm** (latest stable) | Never npm/yarn for install scripts. |
| Language | **TypeScript strict mode** | `"strict": true`, `noUncheckedIndexedAccess: true`, `exactOptionalPropertyTypes: true` preferred. |
| Frontend framework | **Svelte 5 + SvelteKit** (latest) | **Svelte 5 runes only** (`$state`, `$derived`, `$effect`, `$props`, `$bindable`). No legacy Svelte 4 store patterns for new code except where adapters needed. |
| Icons | **phosphor-svelte** | Import `*Icon`-suffixed names only (e.g. `ArrowUpIcon`, `ChartLineIcon`). Never bare names that shadow DOM globals. Package is `phosphor-svelte`, NOT `@phosphor-icons/*`. |
| CSS | **Tailwind CSS v4** (latest as of date) + custom design tokens | Institutional dark design system. |
| Charts | **lightweight-charts** (TradingView Lightweight Charts) | Primary for OHLC candlesticks, markers, price lines. Secondary: custom SVG/Canvas for heatmaps/causal graphs if needed. |
| Validation | **Zod** (latest) | All API boundaries, env, forms. |
| Server data | **SvelteKit remote functions / load + TanStack Query (Svelte)** | Prefer SvelteKit-native patterns; use TanStack Query where client cache/refetch semantics win. |
| Dates | **date-fns** or **Temporal** if stable in ecosystem | Consistent UTC + exchange-local display (US equities ET). |
| Real-time | **Native WebSockets** first (SvelteKit-compatible); Socket.IO only if clearly superior | Connect to Aether Brain WS + optional market quote stream. |
| HTTP client | `fetch` + typed wrappers | No axios unless justified. |
| Testing | **Vitest** + **Playwright** | Unit + e2e smoke for dashboard shell. |
| Linting/format | **ESLint** + **Prettier** + `svelte-check` | CI-ready. |
| Docs tooling | Use **Svelte MCP** when editing any `.svelte` / `.svelte.ts`: list-sections → get-documentation → write → **svelte-autofixer** as final gate on every modified Svelte file. |

### Backend for Dashboard (Svelte ecosystem best-in-class)
- **SvelteKit server routes** (`+server.ts`) as BFF (Backend-for-Frontend).
- **Node adapter** (`@sveltejs/adapter-node`) for long-lived WS + production deploy (Railway/Fly-ready).
- Optional companion: thin **Python FastAPI/uvicorn** already exists for Aether Brain — Dashboard BFF proxies it.
- Env management: `$env/static/private` / `$env/dynamic/private`; never expose FMP key or Brain secrets to client.
- Secrets: `.env` with `FMP_API_KEY`, `AETHER_BRAIN_URL`, `AETHER_WS_URL`, `PUBLIC_APP_NAME=Aether`.

### Non-stack rules
- pnpm workspaces allowed if monorepo later; **start single app**: `apps/aether-dashboard` or repo root `aether-dashboard`.
- No TradingView widget embed (user rejected TradingView dependency). Charts are **first-party** via Lightweight Charts.
- No `window.confirm` / `alert` / `prompt` — use styled dialog primitives.
- Every `<img>` gets width+height or aspect-ratio (no CLS).
- Money/PnL display: format carefully; store cents as integers in types if any money math appears.

---

## DESIGN SYSTEM — “INSTITUTIONAL BLACK”

### Visual Identity
- **Theme:** Dark-only v1 (light mode later optional).
- **Base:** Near-black backgrounds (`#05070A`–`#0B0F14`), elevated surfaces `#11161D` / `#161C25`.
- **Borders:** Subtle 1px `rgba(255,255,255,0.06–0.10)`.
- **Text:** Primary `#E8EEF7`, secondary `#8B97A8`, muted `#5C6778`.
- **Accents:**
  - Long / positive: institutional green `#00C805` / `#12B981`
  - Short / negative: precision red `#FF3B30` / `#F43F5E`
  - Neutral / info: electric blue `#3B82F6` / cyan `#22D3EE`
  - Warning / regime risk: amber `#F59E0B`
  - Confidence high: emerald; mid: amber; low: slate
- **Typography:** Inter or Geist for UI; tabular nums (`font-variant-numeric: tabular-nums`) everywhere for prices/PnL/time.
- **Effects:** Restrained glassmorphism on floating panels only; hairline grids; micro-motion (150–250ms) — no candy animations.
- **Density:** Bloomberg-dense but readable; compact tables; 8px spacing scale.
- **Layout:** Desktop-first (1440–1920+), usable down to 1280; mobile is secondary (read-only signal list + simplified chart).

### UX Principles
1. **Signal latency visibility** — show data age / last tick / last Brain heartbeat.
2. **Explainability first** — every signal has “Why?” expandable.
3. **No fake completeness** — empty/pending/error states are honest and beautiful.
4. **Keyboard-first power user** — `/` command palette, `1–0` ticker hotkeys, `j/k` signal navigate.
5. **Auditability** — every action (feedback, simulation run) is logged client-side and sent to Brain API.

---

## INFORMATION ARCHITECTURE

### Global Shell
```
┌──────────────────────────────────────────────────────────────────────────┐
│ Top Bar: Aether mark | Environment (SIM/PAPER/LIVE) | Clock ET | Heartbeat │
│          Search/Command Palette | Alerts | Brain health | User/Settings    │
├────────────┬─────────────────────────────────────────┬───────────────────┤
│            │                                         │                   │
│  Ticker    │         MAIN STAGE (routed)             │  Context Rail     │
│  Universe  │  Chart | Causal | Autopsy | Simulation  │  Live Signals     │
│  Sidebar   │                                         │  Drivers          │
│            │                                         │  Brain Status     │
│            │                                         │  Feedback         │
├────────────┴─────────────────────────────────────────┴───────────────────┤
│ Bottom Status: Regime | Learning velocity | Open risk | WS status | FPS  │
└──────────────────────────────────────────────────────────────────────────┘
```

### Routes (SvelteKit)
| Route | Purpose |
|-------|---------|
| `/` | Mission Control (default dashboard) |
| `/ticker/[symbol]` | Deep dive for one ticker |
| `/signals` | Full signal blotter (filterable) |
| `/signals/[id]` | Single signal + autopsy |
| `/causal/[symbol]` | Full-screen causal graph |
| `/simulation` | Replay playground |
| `/brain` | Brain health, learning metrics, model versions |
| `/history` | Historical performance & calibration |
| `/settings` | Thresholds display (read-only from Brain), API health, theme density |

### Ticker Sidebar (always available on main layouts)
For each of: AAPL, NVDA, TSLA, AMZN, NFLX, CSCO, SPY, QQQ, IWM, SPX:
- Symbol + last price + % change (color coded)
- Mini sparkline (session)
- Current **regime** badge (e.g. Risk-On / Chop / High-Vol)
- **P(top)** / **P(bottom)** or unified reverse probability
- Active signal indicator (dot)
- Click → select as focused ticker (updates chart + context rail)

---

## CORE FEATURES (COMPLETE SPEC — IMPLEMENT ALL)

### 1. Main Chart Stage (Mission-Critical)
**Library:** `lightweight-charts`

**Must support:**
- Candlestick series (OHLC) + volume histogram
- Multi-timeframe switcher: `1m | 5m | 15m | 1H | D` (data from BFF/FMP/Brain cache)
- Crosshair with OHLC readout + time (ET)
- Session markers (RTH open/close)
- **Signal overlays:**
  - Long entry markers (up arrow / green)
  - Short entry markers (down arrow / red)
  - Confidence badge near marker
- **Dynamic risk geometry:**
  - Stop price line (dashed red)
  - Target 1..N lines (dashed green) with probability labels
  - Optional entry price line
- **Brain attention heatmap** (layer toggle):
  - Semi-transparent bands or bar coloring by attention weight over time
  - Toggle: Off / Attention / Volume Profile
- **Volume profile** (session or visible range) — side histogram or overlay
- Fit content, brush/time scale navigation, watermark “AETHER · SIM”
- Loading skeleton; error retry; “stale data” banner if feed lag > threshold
- ResizeObserver-safe; no layout thrash

**Chart toolbar:** timeframe, indicators toggles (only Brain-derived overlays — not classic TA suite as strategy), screenshot, pop-out (optional).

### 2. Live Signals Panel
Real-time table / virtualized list:

| Column | Detail |
|--------|--------|
| Timestamp | ISO + relative (“2m ago”), always ET display option |
| Ticker | Chip with color |
| Direction | LONG / SHORT with icon |
| Confidence | 0–100, color scale + thin bar |
| Primary Drivers | Top 3 ranked, % contribution |
| Entry | Suggested entry price |
| Stop | Dynamic stop |
| Targets | T1, T2, … with probs |
| Expected Move | % or $ |
| Status | NEW / ACTIVE / HIT_T1 / STOPPED / EXPIRED / CANCELLED |
| Actions | Open autopsy, thumbs up/down, expand why |

**Behaviors:**
- WebSocket push prepends new rows with subtle flash
- Click row → focus ticker + jump chart to signal time + open detail drawer
- Filters: ticker, direction, min confidence, status, date range
- Sort: time, confidence
- Export CSV (client-side) optional
- Empty state: “No high-conviction reversals — Brain scanning…”

### 3. Driver Breakdown
When a signal or ticker is selected:
- **Horizontal stacked bar** or **radial / sunburst** of driver contributions
- Categories (extensible): Options Flow, Sentiment/News, Technical/Microstructure, Macro/Inter-market, Fundamentals/Events, Unexplained/Residual
- Hover → exact % + short description from Brain
- Time scrubber: how driver mix evolved into the signal
- “Unexplained residual” always shown (honesty)

### 4. Causal Graph View
Interactive graph of Brain’s current causal understanding for selected ticker:
- Nodes: variables (price, gamma, sentiment, SPX, QQQ, news shock, liquidity, …)
- Edges: learned causal strength/direction (signed weight)
- Layout: force-directed or hierarchical (dagre-like)
- Click node → inspector (definition, current value, uncertainty)
- Toggle: “Session graph” vs “Long-horizon semantic graph”
- Highlight path that dominated the latest signal
- Performance: virtualize / simplify beyond N nodes; don’t freeze UI

### 5. Trade Autopsy / History
For every closed or aged signal:
- Entry thesis (NL reasoning from Brain)
- Realized path: MFE, MAE, hit stop/target?, time-in-trade
- PnL (paper), R-multiple
- **What Brain got right / wrong**
- Loss autopsy depth: missed drivers, wrong causal attribution, regime mis-ID, timing error
- Learning insights: “Weights updated: options +0.04, news −0.02” (from Brain API if available; else honest pending)
- Filterable blotter + detail page

### 6. Simulation Playground
- Select date range + tickers subset
- Replay speed: 1x, 5x, 20x, step-through
- “Run Aether with current Brain weights” on historical window
- Equity curve, drawdown, win rate, calibration plot (confidence vs hit rate)
- Side-by-side: signals vs price
- Snapshot comparison of two Brain versions (if API supports)
- Clear labeling: **SIMULATION — NOT LIVE**

### 7. Brain Status
Live metrics strip + `/brain` page:
- Heartbeat / last inference time
- Learning velocity (updates/day, replay buffer size)
- Regime detection global + per ticker
- Confidence trend (rolling calibration)
- Model version / git SHA / weights hash
- Active experiment flags
- Alert when confidence in world-model drops (regime shock)
- Queue depth / inference latency p50/p95

### 8. Feedback System (Human → Brain)
On any signal:
- Thumbs up / Thumbs down
- Structured tags: `false_top`, `false_bottom`, `early`, `late`, `missed_order_flow`, `missed_news`, `good_driver_mix`, `bad_stop`, `bad_target`
- Free-text comment (NL)
- Submit → `POST /api/feedback` → Brain training pipeline (privileged samples)
- Optimistic UI + server confirm; never swallow errors
- Show “Feedback received — queued for learning”

### 9. Command Palette & Power Features
- `Cmd/Ctrl+K` or `/`: jump ticker, open signal, toggle layers, run sim
- Hotkeys documented in `?` modal
- Alert toasts for new high-confidence signals (confidence ≥ threshold)
- Optional sound toggle (off by default)

### 10. Settings & Ops
- Display density, timezone (ET default), default timeframe
- Min confidence display filter (UI only — Brain threshold separate)
- Connection endpoints status
- Feature flags
- About / version

---

## REAL-TIME & DATA CONTRACTS

### WebSocket Channels (BFF ↔ Client)
Define typed events (Zod-validated):

```ts
// Conceptual — implement exactly with Zod schemas in src/lib/types/
type WsEvent =
  | { type: 'heartbeat'; ts: string; brain: 'ok' | 'degraded' | 'down' }
  | { type: 'quote'; symbol: string; price: number; changePct: number; ts: string }
  | { type: 'bar'; symbol: string; tf: Timeframe; bar: OhlcvBar }
  | { type: 'signal'; signal: AetherSignal }
  | { type: 'signal_update'; id: string; patch: Partial<AetherSignal> }
  | { type: 'drivers'; symbol: string; drivers: DriverContribution[] }
  | { type: 'regime'; symbol: string; regime: RegimeState }
  | { type: 'brain_metrics'; metrics: BrainMetrics }
  | { type: 'autopsy'; autopsy: TradeAutopsy };
```

### Core Types (must exist in `src/lib/types/`)
- `TickerSymbol` = union of the 10 tickers
- `AetherSignal`: id, ts, symbol, direction `'LONG' | 'SHORT'`, confidence 0–100, drivers[], entry, stop, targets[{price, probability}], expectedMove, reasoning, status, regimeContext
- `DriverContribution`: key, label, weight 0–1, explanation
- `OhlcvBar`: ts, open, high, low, close, volume
- `RegimeState`: label, confidence, since
- `TradeAutopsy`: signalId, outcome, pnl, mfe, mae, insights[], weightDeltas[]
- `BrainMetrics`: learningVelocity, calibration, bufferSize, modelVersion, latencyMs
- `FeedbackPayload`: signalId, rating, tags[], comment?

### REST BFF Endpoints (SvelteKit `+server.ts`)
| Method | Path | Purpose |
|--------|------|---------|
| GET | `/api/health` | App + Brain + FMP health |
| GET | `/api/tickers` | Universe + snapshot quotes/regimes |
| GET | `/api/bars/[symbol]?tf=&from=&to=` | OHLCV for chart |
| GET | `/api/signals?…` | Filtered history |
| GET | `/api/signals/[id]` | Detail |
| GET | `/api/drivers/[symbol]` | Latest driver mix |
| GET | `/api/causal/[symbol]` | Causal graph JSON |
| GET | `/api/autopsies` | Autopsy list |
| GET | `/api/brain/metrics` | Brain status |
| POST | `/api/feedback` | Human feedback → Brain |
| POST | `/api/simulation/run` | Start replay job |
| GET | `/api/simulation/[jobId]` | Simulation status/results |
| GET | `/api/ws-token` or upgrade path | WS auth if needed |

BFF **proxies** Python Aether Brain (`AETHER_BRAIN_URL`). Until Brain exists, BFF may serve **explicit mock fixtures** under `src/lib/server/mocks/` with header `X-Aether-Data: mock` and UI badge **DEMO DATA** — never silent fake as real.

### Python Brain Integration (document in README)
Expected Brain service contracts (OpenAPI later):
- `GET /v1/signals`
- `GET /v1/causal/{symbol}`
- `GET /v1/metrics`
- `POST /v1/feedback`
- `WS /v1/stream`
Dashboard must not block on missing Brain — degrade gracefully with banners.

---

## APPLICATION STRUCTURE (CREATE EXACTLY)

```
aether-dashboard/
├── package.json
├── pnpm-lock.yaml
├── svelte.config.js
├── vite.config.ts
├── tsconfig.json          # strict: true
├── tailwind.config.ts     # or CSS-first Tailwind v4 setup
├── playwright.config.ts
├── vitest.config.ts
├── .env.example
├── .gitignore
├── README.md
├── docs/
│   ├── ARCHITECTURE.md
│   ├── DATA_CONTRACTS.md
│   └── DESIGN_SYSTEM.md
├── static/
│   └── favicon.svg
└── src/
    ├── app.html
    ├── app.css              # design tokens + Tailwind
    ├── app.d.ts
    ├── hooks.server.ts      # security headers, request id
    ├── lib/
    │   ├── components/
    │   │   ├── layout/
    │   │   │   ├── AppShell.svelte
    │   │   │   ├── TopBar.svelte
    │   │   │   ├── TickerSidebar.svelte
    │   │   │   ├── ContextRail.svelte
    │   │   │   └── BottomStatus.svelte
    │   │   ├── chart/
    │   │   │   ├── AetherChart.svelte
    │   │   │   ├── ChartToolbar.svelte
    │   │   │   └── chart-overlays.ts
    │   │   ├── signals/
    │   │   │   ├── SignalsTable.svelte
    │   │   │   ├── SignalRow.svelte
    │   │   │   ├── SignalDetailDrawer.svelte
    │   │   │   └── ConfidenceBadge.svelte
    │   │   ├── drivers/
    │   │   │   ├── DriverBreakdown.svelte
    │   │   │   └── DriverHeatmap.svelte
    │   │   ├── causal/
    │   │   │   └── CausalGraph.svelte
    │   │   ├── autopsy/
    │   │   │   ├── AutopsyList.svelte
    │   │   │   └── AutopsyDetail.svelte
    │   │   ├── simulation/
    │   │   │   └── SimulationPlayground.svelte
    │   │   ├── brain/
    │   │   │   └── BrainStatusPanel.svelte
    │   │   ├── feedback/
    │   │   │   └── FeedbackForm.svelte
    │   │   ├── ui/          # primitives: Button, Badge, Dialog, Toast, Skeleton, Tabs…
    │   │   └── command/
    │   │       └── CommandPalette.svelte
    │   ├── server/
    │   │   ├── brain-client.ts
    │   │   ├── fmp-client.ts   # only server-side
    │   │   ├── mocks/
    │   │   └── env.ts
    │   ├── state/
    │   │   ├── dashboard.svelte.ts   # runes-based app state
    │   │   ├── ws.svelte.ts
    │   │   └── selection.svelte.ts
    │   ├── types/
    │   │   ├── signal.ts
    │   │   ├── market.ts
    │   │   ├── brain.ts
    │   │   └── ws.ts
    │   ├── utils/
    │   │   ├── format.ts
    │   │   ├── time.ts
    │   │   └── color-scale.ts
    │   └── index.ts
    └── routes/
        ├── +layout.svelte
        ├── +layout.ts
        ├── +page.svelte              # Mission Control
        ├── ticker/[symbol]/+page.svelte
        ├── signals/
        │   ├── +page.svelte
        │   └── [id]/+page.svelte
        ├── causal/[symbol]/+page.svelte
        ├── simulation/+page.svelte
        ├── brain/+page.svelte
        ├── history/+page.svelte
        ├── settings/+page.svelte
        └── api/
            ├── health/+server.ts
            ├── tickers/+server.ts
            ├── bars/[symbol]/+server.ts
            ├── signals/+server.ts
            ├── signals/[id]/+server.ts
            ├── drivers/[symbol]/+server.ts
            ├── causal/[symbol]/+server.ts
            ├── autopsies/+server.ts
            ├── brain/metrics/+server.ts
            ├── feedback/+server.ts
            └── simulation/
                ├── run/+server.ts
                └── [jobId]/+server.ts
```

---

## IMPLEMENTATION PHASES (EXECUTE IN ORDER)

### Phase 0 — Scaffold
1. Create SvelteKit app with TypeScript via pnpm.
2. Enable strict TS, Tailwind, phosphor-svelte, lightweight-charts, zod, date-fns, vitest, playwright.
3. Adapter-node, env example, README.
4. Design tokens + AppShell dark layout with placeholder panels.
5. Prove `pnpm dev`, `pnpm check`, `pnpm test` work.

### Phase 1 — Design System & Shell
- TopBar, TickerSidebar (10 tickers), ContextRail, BottomStatus
- Routing skeleton
- Command palette stub
- Loading/error/empty primitives

### Phase 2 — Types, BFF, Mocks
- Full Zod schemas
- Mock Brain + OHLCV fixtures for all 10 tickers (labeled DEMO)
- Health endpoint
- Client state (runes) for selected ticker, signals, connection status

### Phase 3 — Chart + Signals
- AetherChart fully working with overlays
- Signals table + detail drawer
- WS client with reconnect/backoff + heartbeat

### Phase 4 — Drivers, Causal, Autopsy
- DriverBreakdown
- CausalGraph
- Autopsy views

### Phase 5 — Simulation + Brain Status + Feedback
- Simulation playground
- Brain metrics
- Feedback → API

### Phase 6 — Polish & Hardening
- Keyboard shortcuts, a11y, performance pass
- Playwright smoke tests
- Docs: ARCHITECTURE, DATA_CONTRACTS, DESIGN_SYSTEM
- Integration notes for Python Brain

**After each phase:** summarize what shipped, how to run, known gaps. Wait for user approval before next phase **only if user requested gated delivery**; otherwise complete full vertical slice of Mission Control first.

---

## QUALITY BAR (DEFINITION OF DONE)

- [ ] TypeScript strict: `pnpm check` / `svelte-check` clean
- [ ] Every modified `.svelte` file passed through **Svelte MCP svelte-autofixer** until clean
- [ ] No fabricated “live” data without DEMO badge
- [ ] Real-time path works with mock WS producer in dev
- [ ] Chart remains 60fps-feel on desktop with signal overlays
- [ ] All 10 tickers visible and selectable
- [ ] Signal shows: time, ticker, long/short, confidence, drivers, stop, targets
- [ ] Feedback posts successfully to BFF
- [ ] Institutional visual quality (dense, dark, precise)
- [ ] README: setup, env, scripts, Brain integration
- [ ] Accessible focus states; reduced-motion respected where possible

---

## SETUP COMMANDS (EXPECTED)

```bash
# Node LTS 24.x, pnpm latest
pnpm create svelte@latest aether-dashboard
# Choose: Skeleton project, TypeScript, ESLint, Prettier, Playwright, Vitest
cd aether-dashboard
pnpm install
pnpm add -D tailwindcss @tailwindcss/vite
pnpm add phosphor-svelte lightweight-charts zod date-fns
# TanStack Query svelte adapter if used:
# pnpm add @tanstack/svelte-query
pnpm add -D @sveltejs/adapter-node
```

Document exact versions resolved at install time in README.

---

## SECURITY & SAFETY

- FMP key and Brain credentials **server-only**
- CSP headers in `hooks.server.ts`
- Validate all WS and REST payloads with Zod; drop invalid
- Rate-limit feedback POST
- No eval; no inline unchecked HTML from Brain without sanitization
- SIM/PAPER/LIVE banner always visible for environment

---

## WHAT NOT TO BUILD (YET)

- Full Python Aether training stack (separate project)
- Live broker execution / order entry
- Classic 50-indicator TA kitchen sink
- Mobile-first redesign
- Light theme (unless trivial token swap)
- Claiming guaranteed profitability in UI copy

---

## FIRST RESPONSE FORMAT

1. Confirm understanding of Aether + this dashboard scope in ≤15 lines.
2. Create the project scaffold and design system shell.
3. Implement Mission Control layout + mock data path for all 10 tickers.
4. Implement AetherChart + Live Signals + DriverBreakdown as first vertical slice.
5. Provide run instructions (`pnpm install`, `.env.example`, `pnpm dev`).
6. List next components in priority order.

**Begin building the Aether Dashboard now. Institutional grade. No shortcuts. No room for interpretation.**

---

## APPENDIX A — SIGNAL CARD EXAMPLE (UI COPY)

```
2026-07-10 14:35:00 ET | NVDA | LONG | Conf 78%
Drivers: Options gamma unwind 42% · Sentiment inflection 31% · Microstructure exhaustion 27%
Entry 138.20 · Stop 135.80 · T1 142.00 (65%) · T2 145.50 (38%)
Why: Brain detects confluence of gamma flip + sentiment velocity + session liquidity vacuum fill.
Regime: Tech risk-on · High vol
[▲ Good] [▼ Bad] [Tags] [Autopsy]
```

## APPENDIX B — RELATIONSHIP TO AETHER BRAIN

Dashboard is the eyes, hands, and notebook.
Brain is the perception, causal world model, hierarchical meta-RL decision core, and self-evolution engine.
This UI must make the Brain’s invisible decoding **visible, auditable, and improvable** by the human supervisor.

## APPENDIX C — TICKER DNA HINTS (FOR EMPTY STATES / EDUCATION UI ONLY)

Not hardcoded strategy — optional educational tooltips:
- TSLA: news/sentiment & vol explosions
- NVDA: options + AI narrative + sector beta
- SPX/SPY: institutional risk regime
- QQQ vs IWM: risk-on/off rotation context

---

END OF PROMPT — EXECUTE FULLY.
