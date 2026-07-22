# CHANAKYA — Build Memory (Detailed)

Complete record of the build session: what was decided, built, calibrated, fixed, and verified. This is the project bible — a fresh reader or session can reconstruct everything from here.

---

## 1. Product definition
**CHANAKYA** — AI-Powered Energy Crisis Operating System for India's crude-oil supply chain. A full-stack, live-data, real multi-agent **working prototype** (explicitly NOT a mock/demo). It is an **AI-native Mission Control platform**, not a dashboard/chatbot/analytics portal.

**Operating loop (every screen serves it):** Observe → Understand → Predict → Simulate → Decide → Execute.

**Why it exists:** India imports ~88% of crude; ~40–45% transits the Strait of Hormuz; SPR holds only ~9.5 days cover. Existing tools are reactive. CHANAKYA turns crisis response into a managed, anticipatory process.

**Spec source of truth (repo root):** `PROBLEM.MD`, `architecture.md`, `masterimplementation.md`, `chat.md`. Where docs conflicted: name = CHANAKYA (not masterimplementation's "EnergyShield AI").

## 2. Decisions locked with the user
- Name = **CHANAKYA**.
- **Full stack now** (not frontend-only).
- **Live data + real multi-agent orchestration** using **free APIs** (Groq/Gemini/DeepSeek/NVIDIA/OpenRouter for LLMs; GDELT/Open-Meteo/EIA/AlphaVantage/aisstream/OFAC for data).
- Must be a **proper functional prototype that impresses judges**, not a demo.
- Cross-cutting principle: **graceful degradation** — a missing key, downed datastore, or rate-limit must never crash the app; every data record is stamped with provenance `LIVE / CACHED / SIM(fallback)`.

## 3. Initial architecture analysis (delivered before any code)
9-point analysis produced: product understanding, architecture summary, inconsistencies (name conflict, missing spec files chat.md prescribed, data-source realism), missing technical decisions, recommended stance, folder structure, dependency graph, component hierarchy, phased implementation strategy. Key architectural call: **one authoritative domain/simulation core in Python** exposed via fast pure-compute API (no LLM in the sim path → instant UX), consumed by agents + all rooms → "never duplicate logic."

## 4. Environment (dev machine)
Node v20.20.2, pnpm 9.12.0, Python 3.12.10, Docker 28.5.1 + Compose, git 2.50.1. No `uv` (used venv+pip).

## 5. Repository layout
```
CHANAKYA/
├── README.md, MEMORY.md, PROBLEM.MD, architecture.md, masterimplementation.md, chat.md
├── .env.example  (full 10-layer API catalog) · .env (working copy)
├── docker-compose.yml  (postgres/redis/neo4j/qdrant)
├── backend/
│   ├── requirements.txt · .venv/
│   └── app/
│       ├── main.py                 FastAPI app + lifespan + CORS(regex localhost)
│       ├── core/config.py          Pydantic Settings (reads root .env, extra=ignore)
│       ├── core/logging.py         structlog
│       ├── llm/                    base.py, providers.py, router.py (fallback)
│       ├── db/manager.py           DataStores: lazy/graceful connect to 4 stores
│       ├── domain/                 entities, seed, scenarios, engine, nesi
│       ├── ingestion/              models, cache, tagging, gdelt, weather, prices,
│       │                           vessels, sanctions, service
│       ├── agents/                 base, context, roster (6 agents), decision, council
│       └── api/routes/             health, network, simulation, intelligence, council, graph
└── frontend/
    ├── package.json (dev -p 3100) · .env.local (API→8010) · tailwind.config.ts · app/globals.css
    ├── app/                        layout.tsx, page.tsx (overview), + 6 room pages
    └── src/
        ├── config/navigation.ts    ROOMS[6] + OPERATING_LOOP
        ├── lib/                     utils, severity, api, types
        ├── stores/                  useSecurityIndex, useMission
        ├── hooks/                   useSystemHealth, useNetwork, useChanakya
        └── components/              primitives, shell, intelligence, twin,
                                     simulation, council, decision, execution
```

## 6. Backend — LLM layer (`app/llm/`)
- **Provider abstraction with ordered fallback.** `router.get_llm_router()` → tries configured providers primary-first; on error/rate-limit moves to next. `complete()` + `complete_json()` (tolerant of markdown fences).
- Groq/NVIDIA/OpenRouter/DeepSeek share **one OpenAI-compatible adapter** (different base URLs); Gemini has its own adapter. Constructed lazily, never raise at import.
- `settings.configured_llm_providers` returns keyed providers, primary first. With **no key**, router.available = False → agents use grounded fallback.

## 7. Backend — datastores (`app/db/manager.py`)
`DataStores` connects Postgres (SQLAlchemy async), Redis, Neo4j, Qdrant **lazily and gracefully**; a downed store is marked unhealthy, boot still succeeds. `/api/health` reports the capability matrix.

## 8. Backend — DOMAIN CORE (`app/domain/`) — the intellectual heart
Deterministic, explainable simulation. No black boxes; every output carries assumptions.

**entities.py** — Pydantic models: CrudeGrade, Coast, InfraStatus, ShippingCorridor, Supplier, Port, Refinery, StrategicReserveSite, MarketState, DemandProfile, EnergyNetwork (with derived aggregates: refining capacity, imports, SPR coverage days, supplier HHI).

**seed.py — India's real network (baseline figures):**
- **Refineries (15, kbpd nameplate):** Jamnagar 1240, Vadinar 405, Mangalore(MRPL) 300, Kochi 310, Mumbai 250, Paradip 300, Visakhapatnam 300, Chennai(CPCL) 230, Panipat 300, Koyali 275, Bina 156, Mathura 168, Bathinda 230, Haldia 150, Barauni 120. Total ≈ 4734 kbpd; throughput ≈ 4484.
- **Suppliers (9, import share / corridor / short-notice spare kbpd):** Russia .36 red_sea 220 · Iraq .20 hormuz 140 · Saudi .13 hormuz 900 · UAE .09 hormuz 350 · USA .06 cape 260 · Nigeria .05 cape 90 · Kuwait .04 hormuz 120 · Brazil .04 cape 110 · Others .03 malacca 80.
- **Corridors (4, import share):** Hormuz .46 (NO maritime bypass — closure forces supplier switch), Red Sea .34 (reroute via Cape +14d +38% freight), Cape .15, Malacca .05.
- **SPR (3 sites, MMT / fill%):** Vizag 1.33/98, Mangalore 1.5/95, Padur 2.5/96. → ~7.7 days coverage.
- **Market baseline:** Brent $82, INR 83.4, diesel ₹89.6/L, petrol ₹96.7/L. Demand 4900 kbpd, 88% import dependence.

**scenarios.py — catalog (6):** Hormuz Closure (chokepoint, block .9, 21d), Red Sea Suspension (block .85, 30d, reroutes), OPEC+ Cut (2000 kbpd, 60d), Supplier Sanctions (Russia, 45d), West-Coast Cyclone (Vadinar offline, 5d), Demand Surge (+12%, 30d). Each has a **ScenarioShock** (the disruption) + **ResponseLevers** (spr_release_pct, enable_reroute, enable_spot) — separation enables counterfactuals.

**engine.py — cascade (traceable):** daily imports → gross supply gap (blocked corridors + sanctions + ports offline + OPEC) → rerouting (delayed not lost, where a bypass exists) → spare replacement (only from UNAFFECTED suppliers — Gulf spare is stuck behind a closed Hormuz) → spot (~5% cap) → SPR drawdown → residual shortfall → refinery utilisation → Brent/diesel/inflation/GDP → NESI recompute. Returns headline, assumptions[], impact_lines[].

**nesi.py — National Energy Security Index:** transparent weighted composite (weights): supply .24, shipping .16, geopolitical .14, reserve .14, diversification .12, market .10, refinery .10. Returns per-component breakdown + band (Secure/Elevated/High/Critical Exposure). Baseline ≈ **66.7 Elevated Exposure**.

**Calibration story (important):** first pass had refining < imports (under-seeded refineries) and spare so generous that residual shortfall was always 0 → counterfactual didn't differentiate. Fixed by adding 7 inland refineries, cutting supplier spare to realistic short-notice deliverable volumes, and lowering spot ceiling to 5%. Result: **Hormuz closure at SPR 0% → 810 kbpd unmet, util 77.6%, NESI 45; at 90% → gap closes, util 94.7%, NESI 50.**

## 9. Backend — LIVE INGESTION (`app/ingestion/`) — Layer 1 "eyes & ears"
Every adapter: **try live → cache (Redis + in-proc TTL) → realistic fallback**, provenance-tagged.
- **models.py** — IntelEvent, PriceQuote, WeatherObs, Vessel, SanctionSignal (+ SourceKind live/cached/fallback, SignalCategory).
- **cache.py** — async TTL cache (Redis when up, in-proc always).
- **tagging.py** — keyword→corridor/country maps + severity/confidence/risk scoring + duration estimate (the clustering/entity step BEFORE any LLM).
- **gdelt.py** — GDELT 2.0 DOC API (keyless); query energy/chokepoint terms, cluster+score into events; 10-min cache; fallback seed set. LIVE (rate-limits under rapid testing → fallback, normal use fine; observed 24 real events cached).
- **weather.py** — Open-Meteo (keyless) wind+wave at Hormuz, Bab-el-Mandeb, Vadinar, Mumbai, Mangalore, Paradip, Vizag → shipping-risk band. Confirmed LIVE.
- **prices.py** — Alpha Vantage Brent/WTI (needs key) → baseline fallback.
- **vessels.py** — synthetic tankers interpolated along corridor paths (aisstream websocket collector is the live upgrade path).
- **sanctions.py** — OpenSanctions (now needs key → gated; curated fallback otherwise; ~0ms when no key).
- **service.py** — `IntelligenceService.feed()` fuses geopolitical + weather-derived + sanctions-derived events into one risk-ranked feed + summary (threat level, severity counts, corridors flagged, provenance mix).

## 10. Backend — AGENTS + DECISION (`app/agents/`) — the competitive core
- **context.py** — `CouncilContext` bundles the scenario **simulation result** + **live intel summary**; `.brief()` renders a compact factual brief for the LLM. All agents share it → evidence cites real numbers.
- **base.py** — `AgentAssessment` (stance, observations, reasoning, recommendation, concerns, confidence, evidence, key_metrics, reasoning_mode). `BaseAgent.run()` = try LLM (if router available) else `reason()` deterministic fallback. The grounded `reason()` is the backbone even in LLM mode.
- **roster.py — 6 agents, each a distinct lens** whose grounded reasoner reflects the sim so they genuinely disagree:
  Intelligence (escalation/threat), Maritime (reroute/transit/freight; flags "no bypass"), Procurement (spare+spot vs shortfall), Reserve (conserve vs release by duration — key tension), Economic (Brent/inflation/GDP buffering), Policy (synthesis/executive).
- **decision.py — AI Decision Engine ("Chief of Staff"):** 3 lever presets (Reserve-Led 75% SPR / Diversified 30% / Measured 10%), each **RE-SIMULATED** through the engine for real projections, then scored on 4 objectives (weights): continuity .40 (residual-driven, penalises unmet gap ~3×), resilience .25, affordability .15, reserve .20 (gated — hoarding SPR while short earns no credit). Ranked; benefits/tradeoffs/steps generated per doctrine.
- **council.py** — `convene()` builds context, fans out 6 agents async, detects disagreements (e.g. Reserve-conserve vs Economic-buffer; Maritime-no-bypass vs Procurement-short), computes consensus, invokes Decision Engine.

**Verified intelligence:** Hormuz (real 720 kbpd shortfall) → recommends **Reserve-Led** (closes gap). Red Sea / Cyclone / OPEC (gap absorbed) → **Measured Conservation** (preserve reserves, same outcome). Context-correct.

**Decision-scoring bug fixed:** initial weights let "Measured" win Hormuz despite leaving 720 kbpd unmet (reserve-preservation over-weighted). Fix: continuity driven by residual ratio ×300, reserve score gated by `(1 − 2×residual_ratio)`, weights re-tuned.

## 11. Backend — API (16 routes, all 200)
`/` · `/api/health` · `/api/network` · `/api/network/nesi` · `/api/simulation/scenarios` · `/api/simulation/run` · `/api/simulation/run-custom` · `/api/intelligence/feed` · `/api/intelligence/events` · `/api/intelligence/summary` · `/api/council/convene` · `/api/graph` (+ docs/openapi).

## 12. Frontend — design system
"National Energy Crisis Command Center" = Bloomberg Terminal + Mission Control. Dark palette tokens (`tailwind.config.ts` + `app/globals.css`): void/base/panel navy-blacks, **signal** cyan (intelligence accent), **energy** amber, severity colours (nominal green / elevated yellow / high orange / critical red), glow shadows, blueprint grid, JetBrains Mono for readouts, Inter for UI. Fonts via next/font.

**Primitives (built once, reused):** Panel/PanelHeader, StatusLight (pulse), SeverityTag, ConfidenceBar, MetricReadout, SecurityIndexGauge (radial; low security = critical colour), SourceTag (LIVE/CACHED/SIM/LLM/GROUNDED).
**Shell:** CommandShell = NavRail (6 rooms) + StatusBar (brand, current room, SystemStatus indicators, LiveClock UTC/IST, NESI gauge) + NesiSync (pulls live baseline NESI into store).
**State:** `useSecurityIndex` (NESI store), `useMission` (scenarioId + levers + selectedStrategyId + activated → the cross-room pipeline).
**Data layer:** `lib/api.ts` (apiGet/apiPost, base from NEXT_PUBLIC_API_BASE_URL), `lib/types.ts` (all API types), hooks in `useChanakya.ts` (useIntelFeed 30s, useNetwork, useScenarios, useSimulation, useCouncil, useGraph).

## 13. Frontend — the six rooms (all built & verified)
1. **Intelligence** (`intelligence/IntelligenceRoom`) — threat strip, event stream (risk-ranked), evidence detail (confidence + risk bars, corridors/countries, evidence), price ticker, weather alerts.
2. **Digital Twin** (`twin/`) — tab switch **Geospatial** (Leaflet CartoDB dark, corridors weighted by share, refineries coloured by util, ports/SPR/vessels, click-inspector, aggregates strip, legend) / **Knowledge Graph** (`GraphView` React Flow, layered suppliers→corridors→ports→refineries + SPR + live event nodes threatening corridors).
3. **Council** (`council/CouncilRoom`) — header (consensus/mode), disagreements panel, 6 agent cards (icon, stance, observations, reasoning, recommendation, concerns, confidence, LLM/GROUNDED badge).
4. **Decision** (`decision/DecisionRoom`) — 3 ranked strategy cards (score, 4 objective bars, projection metrics, benefits/tradeoffs, "Send to Mission Execution" → sets store + routes).
5. **Simulation Lab** (`simulation/`) — `ScenarioControls` (scenario list + SPR slider + reroute/spot toggles → mission store) + `ImpactReadout` (headline, NESI gauge + delta, impact grid, mitigation cascade bars, assumptions). Recomputes instantly.
6. **Execution** (`execution/`) — `CrisisTimeline` (10-stage replay driven by mission state; progresses when launched) + `MissionChecklist` (steps → agency+priority+status, animates on Launch) + `BriefingPack` (Cabinet/Procurement/SPR/Advisory generated from strategy projection).

## 14. Phases (all complete, each build-verified)
0 Foundation → 1 Backend + Frontend scaffold → 2 Domain core + engine + NESI → 3 Live ingestion → 4 Council + Decision → 5 Six rooms → 6 Knowledge graph + Crisis timeline. `tsc --noEmit` clean; `next build` passes all routes; live uvicorn serves every endpoint 200.

## 15. PORTS (this machine) — why not 3000/8000
User has other Docker projects (`finance-frontend-1` on 3000, `finance-backend-1` on 8000, plus chainforge/studyvault postgres). Those shadowed CHANAKYA → "no feature works" (browser hit the finance app). **Fix: CHANAKYA runs on its own ports.**
- **Backend → 8010**, **Frontend → 3100**.
- `frontend/.env.local`: `NEXT_PUBLIC_API_BASE_URL=http://127.0.0.1:8010`, `NEXT_PUBLIC_WS_BASE_URL=ws://127.0.0.1:8010`.
- `frontend/package.json`: `"dev": "next dev -p 3100"`.
- `backend/app/main.py`: CORS `allow_origin_regex=r"https?://(localhost|127\.0\.0\.1):\d+"` (any localhost port — prevents this class of issue permanently).

## 16. How to run
```bash
# Backend (8010) — already may be running
cd /Users/samarthkapoor/projects/CHANAKYA/backend
./.venv/bin/uvicorn app.main:app --host 127.0.0.1 --port 8010 --reload
#   docs: http://localhost:8010/docs

# Frontend (3100)
cd /Users/samarthkapoor/projects/CHANAKYA/frontend
pnpm dev
#   open: http://localhost:3100   ← note 3100, not 3000

# Optional datastores
docker compose up -d
```
Restart backend after editing `.env` (settings cached at startup). If a `pnpm dev` was already running, Ctrl+C and rerun to pick up new config.

Suggested demo walk: Overview → Intelligence → Digital Twin (toggle to Knowledge Graph) → Simulation Lab (trigger **Hormuz Closure**, drag SPR slider) → Council → Decision (Send to Execution) → Execution (Launch Mission).

## 17. Data sources — full status
Complete 10-layer catalog in `.env.example`/`.env`, tagged `[WIRED]/[KEYLESS]/[PLANNED]`.
- **LIVE now (keyless, no setup):** GDELT geopolitical events, Open-Meteo weather.
- **WIRED, need a free key to go live:** Alpha Vantage (Brent/WTI), OpenSanctions, aisstream (vessels); 5 LLM providers (Groq/Gemini/NVIDIA/OpenRouter/DeepSeek).
- **PLANNED (env slot ready, adapter NOT yet built — a key alone won't flow data):**
  L1 NewsAPI, Mediastack, Event Registry, ACLED, ReliefWeb ·
  L2 AISHub, MarineTraffic, Global Fishing Watch, MarineCadastre ·
  L3 EIA, FRED, Nasdaq Data Link, PPAC ·
  L4 OpenWeather, NOAA, NASA POWER, ECMWF, IMD ·
  L5 Copernicus/Sentinel-1/2, Sentinel Hub, Google Earth Engine, NASA FIRMS, Earthdata, ISRO Bhuvan ·
  L6 Mapbox (default map is keyless CartoDB) ·
  L7 World Bank, IMF, Trading Economics, RBI ·
  L8/9 UN Comtrade ·
  L10 RAG corpus (Wikipedia/Factbook/USGS/PDFs → Qdrant).

## 18. Activate real data
1. Edit `.env`, add keys (start with **`GROQ_API_KEY`** — console.groq.com — flips 6 agents grounded→LLM, biggest visible change).
2. Restart backend.
3. Verify: `curl -s http://127.0.0.1:8010/api/health` → `"llm":{"available":true,...}`; feed `source_kind` flips to `live` on priced/sanctioned items.
Note: config.py uses `extra="ignore"`, so unknown env keys never break boot; a Settings field is added only when an adapter is wired.

## 19. Problem-statement coverage
Meets all four demands (continuous geopolitical+logistics monitoring; disruption + downstream economic modelling; executable procurement/rerouting recommendations; reactive→anticipatory) and all five illustrative builds (Geopolitical Risk Intelligence Agent, Disruption Scenario Modeller, Adaptive Procurement Orchestrator, Strategic Reserve Optimisation Agent, Supply-Chain Digital Twin). Extra data layers deepen evidence, not capability.

## 20. Open next steps (historical note)
This list described the state before the July 2026 realism upgrade. The items
implemented by that upgrade are superseded by section 21 below.

## 21. Real-time and deployment upgrade (July 2026)

- Added versioned `DomainEvent` records and explicit `LIVE / CACHED / REPLAY /
  SIMULATED / UNAVAILABLE` provenance. The former fallback label now serializes
  as simulated.
- Added PostgreSQL event/workflow/mission/audit repositories, Redis Streams with
  deduplication/retry/dead-letter handling, Neo4j idempotent ontology seeding and
  Qdrant cited evidence retrieval. Every layer still degrades gracefully.
- Added scheduled GDELT/Open-Meteo ingestion, EIA-first pricing, PPAC versioned
  snapshot, AISStream live collection with honest replay, and NASA FIRMS events.
- Replaced direct council fan-out with a checkpointed LangGraph workflow. Six
  specialists read persisted events and evidence; completed runs and draft
  missions persist across backend restarts.
- Extended the simulation to a daily horizon with usable refinery inventory,
  cargo lead time and finite SPR volume/rate constraints. Overlapping sanctions
  and corridor shocks no longer double-count the same cargo.
- Strategies now include feasibility/evidence objectives and executable cargo
  candidates: supplier, grade, compatible refineries, volume, route, ETA,
  premium, constraint, confidence and evidence.
- Added normalized event/source/workflow/mission routes, protected operator
  actions, liveness/readiness endpoints and `/api/ws/intelligence`.
- Frontend now reconnects to WebSockets with cursor deduplication and REST
  recovery, displays source truth/staleness, provides evidence links and a
  replacement cargo board, and activates persistent missions with an operator PIN.
- Added Railway/Vercel containers/configuration, managed-store TLS settings,
  deployment runbook, CI and 15 backend tests.
- Verified: backend tests pass; TypeScript passes; Next.js production build
  passes; Redis Stream receives events; PostgreSQL workflow/mission records
  survive a backend restart. Local Neo4j and Qdrant were unavailable during the
  final smoke test, and their code paths used the documented degraded fallbacks.

Current deferred work: full Sentinel/GEE computer vision, a stable automated
PPAC spreadsheet parser, broader RAG corpus governance, and load/chaos testing.
