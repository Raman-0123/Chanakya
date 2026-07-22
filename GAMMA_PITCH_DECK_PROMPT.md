# Gamma prompt — CHANAKYA 10-page investor/judges pitch deck

Copy everything below into Gamma. Replace `[LIVE_DEMO_URL]` only when the actual deployment URL is available.

```text
Create exactly a 10-page professional hackathon pitch deck for CHANAKYA — AI-Powered Energy Crisis Operating System for India's crude-oil supply chain.

This is a serious product pitch for judges evaluating Innovation (25%), Business Impact (25%), Technical Excellence (20%), Scalability (15%), and User Experience (15%). It must feel like a government-grade mission-control product, not a generic AI presentation, consulting template, or startup pitch full of abstract claims.

CORE THESIS
India's energy vulnerability is structural: high crude-import dependence, concentrated maritime chokepoints, limited strategic reserve cover, and fragmented decision-making. CHANAKYA turns a weak signal into an auditable national response: Observe → Understand → Predict → Simulate → Decide → Execute.

PRODUCT TRUTH
CHANAKYA is a working full-stack prototype. The product has a FastAPI backend, Next.js mission-control frontend, deterministic scenario engine, geospatial digital twin, six-agent LangGraph council, procurement optimizer, persistent missions, WebSocket/REST updates, and provenance-aware ingestion. Do not call it a chatbot, dashboard, or generic analytics platform.

IMPORTANT DATA-HONESTY RULE
Clearly distinguish public context facts, explicit model assumptions, prototype outputs, and future production integrations. Use labels such as LIVE, CACHED, REPLAY, SIMULATED, and UNAVAILABLE wherever relevant. Never invent real-time metrics, customer logos, government endorsement, deployed URLs, or benchmark results. If a metric is shown as a prototype output, label it “illustrative prototype run” or “model output.” Use `[LIVE_DEMO_URL]` as a small footer on the final page, not a made-up URL.

DESIGN SYSTEM
- 16:9 widescreen, exactly 10 pages, sparse but information-dense.
- Dark navy/near-black mission-control background with electric cyan intelligence accents, amber energy accents, and restrained red for critical risk.
- Typography: modern sans-serif for narrative, monospace for telemetry and numbers.
- Visual language: geospatial map, supply-chain routes, chokepoints, refinery nodes, agent council, scenario cascade, strategy comparison, execution timeline.
- Use high-quality editorial visuals: satellite/ocean texture, Indian coastline and tanker lanes, refinery night lights, secure operations room. Images must support the argument and must never contain illegible fake UI text.
- Prefer real diagrams, maps, and annotated system visuals over decorative stock photos.
- Keep body copy short. Use one memorable headline and 3–5 evidence blocks per page.
- Do not use cheesy robot illustrations, generic neural-network backgrounds, random smiling business people, or a standard “problem/solution/market/team” template.

PAGE 1 — THE OPERATING SYSTEM FOR ENERGY RESILIENCE
Headline: “When a chokepoint moves, India needs a decision—not a delayed report.”
Subheadline: “CHANAKYA continuously connects geopolitical signals to supply impact, feasible procurement, reserve policy, and mission execution.”
Visual: cinematic dark satellite-style view of the Arabian Sea, Strait of Hormuz, Red Sea, and India with glowing routes converging on Indian refineries. Add a small CHANAKYA wordmark and the loop: Observe → Understand → Predict → Simulate → Decide → Execute.
Footer: “AI-Driven Energy Supply Chain Resilience | Prototype pitch”.

PAGE 2 — THE VULNERABILITY IS STRUCTURAL
Headline: “India’s crude supply chain is exposed before the crisis reaches the refinery.”
Show three large, visually dominant facts from the supplied challenge context: approximately 88% crude import dependence; approximately 40–45% of imports transiting the Strait of Hormuz; approximately 9.5 days of strategic reserve cover. Add the context that geopolitical and maritime incidents can reprice crude and force spot procurement.
Visual: a clean annotated map of India’s import corridors with Hormuz highlighted, plus a small reserve-cover countdown motif.
Narrative: Traditional planning tools are periodic and route-centric. They do not model geopolitical impact in real time or coordinate refiners, logistics, procurement, and reserves.
Small disclaimer: “Context figures supplied in challenge brief; verify final external citations before submission.”

PAGE 3 — THE DECISION GAP
Headline: “The missing layer is not more data. It is connected operational intelligence.”
Create a before/after visual.
Before: news feed → spreadsheet → separate logistics view → manual scenario analysis → delayed executive decision.
After: one evidence-linked loop from signal to corridor risk to cascade simulation to procurement alternative to approved mission.
Show the four questions CHANAKYA answers: What is happening? Why does it matter? What happens next? What should we do now?
Avoid generic AI language. Emphasize response time, explainability, and cross-functional coordination.

PAGE 4 — CHANAKYA PRODUCT EXPERIENCE
Headline: “One crisis. Six operational rooms. One shared truth.”
Use a polished product storyboard or six-panel interface composition showing:
1. Global Intelligence — ranked events, evidence, prices, weather, sanctions.
2. National Energy Digital Twin — map and knowledge graph of suppliers, corridors, ports, refineries, reserves, vessels.
3. Intelligence Council — six specialist assessments, confidence, evidence, disagreements.
4. Decision Center — three ranked strategies and objective scores.
5. Scenario Lab — change the shock, SPR drawdown, reroute, and spot levers.
6. Mission Execution — checklist, timeline, cabinet/procurement/SPR briefing packs.
Use small labels “prototype UI” and “source provenance visible.” Do not make it look like a consumer app.

PAGE 5 — TECHNICAL ARCHITECTURE
Headline: “A provenance-aware intelligence pipeline feeds a deterministic decision core.”
Draw a clean left-to-right architecture diagram with labeled layers:
Signal sources: GDELT news, Open-Meteo weather/marine, EIA/Alpha Vantage prices, AISStream or honest replay, OpenSanctions/curated fallback, NASA FIRMS hooks.
Ingestion: adapters → normalization → DomainEvent v1 → deduplication, caching, retries, dead-letter handling.
Knowledge and state: PostgreSQL audit/workflows/missions; Redis streams/cache; Neo4j ontology; Qdrant cited evidence.
Reasoning: risk scorer → digital twin → deterministic scenario engine → LangGraph six-agent council → decision/procurement optimizer.
Experience: Next.js 14 mission control via REST and WebSocket with reconnect/recovery.
Technology labels and official platform links in small text: FastAPI https://fastapi.tiangolo.com/ ; Next.js https://nextjs.org/ ; LangGraph https://langchain-ai.github.io/langgraph/ ; PostgreSQL https://www.postgresql.org/ ; Redis https://redis.io/ ; Neo4j https://neo4j.com/ ; Qdrant https://qdrant.tech/ ; Leaflet https://leafletjs.com/ ; Vercel https://vercel.com/ ; Railway https://railway.app/ .
Do not imply every source is live in the current environment; show the provenance contract.

PAGE 6 — THE DIGITAL TWIN AND GEOSPATIAL INTELLIGENCE
Headline: “CHANAKYA understands the network, not just the headline.”
Visual: dark India-centered map with suppliers, corridors/chokepoints, ports, refineries, SPR sites, tanker positions, and risk events. Add a small relationship-graph inset.
Explain that the twin represents wellhead/supplier → corridor → port → refinery → reserve and distribution dependencies. Clicking a node exposes status, capacity, grade, inventory, dependencies, current risk, alternatives, and historical/evidence context.
Call out geospatial evidence depth: corridor paths, chokepoints, vessel tracks, refinery utilization, ports, strategic reserves, event locations, and satellite detection hooks.

PAGE 7 — FROM SHOCK TO CASCADE TO OPTIONS
Headline: “A scenario is not a story. It is a testable set of constraints.”
Show a cascade diagram for “Hormuz Closure” as an illustrative prototype scenario:
chokepoint block → affected supplier volume → reroute availability or no-bypass constraint → spare capacity and spot replacement → finite SPR drawdown → refinery run rate → Brent/diesel/economic impact → NESI.
Show the response levers: SPR release %, enable reroute, enable spot.
Show that model assumptions are explicit and self-audited through `/api/simulation/assumptions`.
Use a side note: “Prototype model output; not a forecast or policy directive.”

PAGE 8 — MULTI-AGENT COUNCIL + OPTIMIZATION
Headline: “Six perspectives challenge one another before a strategy is recommended.”
Show six agents around a central Decision Engine: Intelligence, Maritime Logistics, Procurement, Strategic Reserve, Economic Impact, Policy Advisor.
For each, one short role label. Show disagreement as a feature: reserve conservation vs immediate drawdown; maritime no-bypass constraint vs procurement urgency.
Then show the three re-simulated strategy doctrines: Reserve-Led Stabilization, Market Diversification, Measured Conservation.
Scoring dimensions: continuity, resilience, affordability, reserve health, feasibility, evidence confidence.
Emphasize: recommendations include implementation steps, trade-offs, confidence, evidence chain, and feasible procurement alternatives—not just a generated paragraph.

PAGE 9 — EXECUTABILITY, TRUST, AND SCALE
Headline: “The recommendation is only valuable if an operator can act on it.”
Show an example procurement card/table with fields: supplier, crude grade, compatible refineries, volume kbpd, route, ETA, port congestion, charter delay, tanker status, war-risk premium, landed premium, feasibility, confidence, evidence.
Show the trust architecture: operator approval and PIN-protected mission activation; persisted workflow and mission audit; live/cached/replay/simulated labels; graceful degradation when a source or datastore is unavailable.
Scalability path: hackathon single service → separate API/worker roles → managed Postgres/Redis/Neo4j/Qdrant → source adapters and role-based government/refiner deployments.
Map judging criteria to proof: innovation = agentic decision loop; impact = faster coordinated response; technical = deterministic core + multi-agent reasoning; scalability = modular adapters/stores; UX = mission rooms.

PAGE 10 — THE ASK / DEMO / CLOSING
Headline: “Move from reactive crisis response to anticipatory energy security.”
Show the live demo path as a 7-step horizontal timeline: Intelligence → Digital Twin → Hormuz scenario → adjust SPR → convene council → compare strategies → activate mission.
Include a concise “Why CHANAKYA wins” block: earlier signal, explicit cascade, feasible options, accountable decision, persistent execution.
Include links exactly as provided, without inventing URLs:
Local demo: http://localhost:3100 (replace with actual deployed URL if available)
API/OpenAPI: http://localhost:8010/docs
Source status: http://localhost:8010/api/sources/status
Small closing line: “Built as a working prototype for India’s energy resilience challenge.”
Add a tiny footer: “Prototype outputs are decision support; external context citations and deployment URL to be finalized before submission.”

FINAL QUALITY RULES
1. Exactly 10 pages—no appendix pages.
2. Every page must contain at least one concrete system artifact: map, architecture, flow, metric, interface, scenario, strategy, or execution timeline.
3. Do not fabricate customer traction, accuracy percentages, response-time SLAs, government partnerships, or citations.
4. Keep the product name CHANAKYA consistently; do not use EnergyShield AI.
5. Use “National Energy Security Index (NESI)” consistently and explain that it is a transparent prototype composite score.
6. Use “illustrative prototype output” beside computed figures.
7. Render all diagrams cleanly with readable labels; if a diagram becomes crowded, simplify the text rather than shrinking it.
8. End with a credible, operationally specific product story, not a generic AI future statement.
```
