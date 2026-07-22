# CHANAKYA

AI-powered energy crisis operating system for India's crude-oil supply chain.
CHANAKYA joins live geopolitical, weather, shipping, market and satellite
signals to a persistent energy-network ontology, runs deterministic disruption
simulations, convenes a six-specialist LangGraph council, and turns the selected
strategy into a persistent mission.

The operating loop is:

**Observe → Understand → Predict → Simulate → Decide → Execute**

## What actually runs

- FastAPI REST and WebSocket backend on port `8010`.
- Next.js 14 command center on port `3100`.
- Versioned `DomainEvent` contract with `live`, `cached`, `replay`, `simulated`
  and `unavailable` provenance. Generated data is never labeled live.
- Redis Streams ingestion bus with deduplication, consumer acknowledgements,
  bounded retries, dead-letter stream and a distributed scheduler lease.
- PostgreSQL event, workflow, mission and execution audit records.
- Neo4j ontology for suppliers, corridors, ports, refineries, reserves, downstream demand hubs and
  risk events. The graph API declares when it is using its degraded in-memory fallback.
- One provenance-carrying operational snapshot shared by risk scoring, geo stations,
  simulation, all six council agents and the optimizer; simulated fallback cannot auto-trigger action.
- LangGraph council with six parallel specialists, typed control proposals,
  optional multi-provider LLM reasoning/model provenance, Qdrant evidence retrieval and persisted runs.
- Constraint search across response levers, with route-specific cargo ETA, current
  tanker/port/market conditions, refinery-grade fit and late-arrival rejection.
- Daily disruption horizon with refinery run-rate projections, power/fuel stress,
  finite site-level SPR schedules and replacement-linked replenishment windows.
- Event-triggered council runs with risk/quality thresholds, cooldown and mission deduplication.
- WebSocket-first UI updates with reconnect, heartbeat, cursor deduplication and
  REST polling recovery.

## Data-source behavior

| Source | Without credentials | With credentials |
|---|---|---|
| GDELT | Keyless live; simulated baseline on outage/rate limit | Same |
| Open-Meteo | Keyless live; simulated baseline on outage | Same |
| EIA / Alpha Vantage | Simulated baseline | Live Brent/WTI observations |
| AISStream | Historical route replay labeled `REPLAY` | Live AIS positions |
| OpenSanctions | Simulated curated signals | Live API results |
| PPAC | Versioned cached baseline | Same until a stable official API exists |
| NASA FIRMS | Unavailable | Live VIIRS thermal detections |
| Qdrant corpus | In-process cited corpus search | Persistent vector retrieval |

`GET /api/sources/status` reports configuration separately from runtime health,
last success/failure, event count and current provenance.

## Local start

Requirements: Node 20+, pnpm 9+, Python 3.12+, and Docker Compose.

```bash
cp .env.example .env
cp frontend/.env.example frontend/.env.local

# Full Docker stack: PostgreSQL, Redis, Neo4j, Qdrant, backend, frontend
docker compose up --build -d

# Backend (local dev, if you are not using Docker)
cd backend
python3.12 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --host 127.0.0.1 --port 8010 --reload

# Frontend (local dev, if you are not using Docker)
cd frontend
pnpm install
pnpm dev
```

Open `http://localhost:3100`; API documentation is at
`http://localhost:8010/docs`.

The backend remains usable when optional stores are down. In production,
`/api/readyz` reports degraded until PostgreSQL, Redis, Neo4j and Qdrant are connected.

## Operational API additions

- `GET /api/events` and `GET /api/events/{id}`
- `GET /api/sources/status`
- `GET /api/workflows/{run_id}`
- `GET /api/missions/{id}`
- `GET /api/operations/snapshot` and `GET /api/operations/scenario`
- `POST /api/missions/{id}/activate` with selected `strategy_id` and `X-Operator-Pin`
- `POST /api/missions/{id}/tasks/{task_id}` for audited execution status
- `POST /api/sources/refresh` with `X-Operator-Pin`
- `WS /api/ws/intelligence`
- `GET /api/livez` and `GET /api/readyz`

Existing network, simulation, intelligence, council and graph routes remain compatible.

## Verification

```bash
cd backend && .venv/bin/pytest -q
cd frontend && pnpm typecheck && pnpm build
```

CI runs those checks on every push and pull request. The backend suite covers
provenance gating, AIS typing/geofencing, finite and site-level SPR accounting,
route-specific arrivals, agent-to-optimizer influence, downstream cascades,
LangGraph workflow creation and protected mission/task contracts.

## Deployment

The intended hackathon deployment is Vercel for the frontend and Railway Hobby
for the always-on backend, connected to Supabase PostgreSQL, Upstash Redis,
Neo4j AuraDB and Qdrant Cloud. See [DEPLOYMENT.md](DEPLOYMENT.md) for exact
variables, commands, health checks and post-deploy acceptance tests.

Product specifications:
[PROBLEM.MD](docs/PROBLEM.MD) · [architecture.md](docs/architecture.md) ·
[masterimplementation.md](docs/masterimplementation.md) · [MEMORY.md](docs/MEMORY.md)
