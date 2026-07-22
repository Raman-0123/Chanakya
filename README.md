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
- Neo4j ontology for suppliers, corridors, ports, refineries, reserves and
  risk events. The graph API declares when it is using its degraded in-memory fallback.
- LangGraph council with six parallel specialists, deterministic grounded mode,
  optional multi-provider LLM explanation, Qdrant evidence retrieval and persisted runs.
- Daily disruption horizon with inventory buffers, procurement lead time,
  finite SPR volume/draw constraints and actionable replacement cargo options.
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
- `POST /api/missions/{id}/activate` with `X-Operator-Pin`
- `POST /api/sources/refresh` with `X-Operator-Pin`
- `WS /api/ws/intelligence`
- `GET /api/livez` and `GET /api/readyz`

Existing network, simulation, intelligence, council and graph routes remain compatible.

## Verification

```bash
cd backend && .venv/bin/pytest -q
cd frontend && pnpm typecheck && pnpm build
```

CI runs those checks on every push and pull request. The 15-test backend suite
covers provenance/deduplication, finite SPR accounting, overlapping shocks,
procurement feasibility, LangGraph workflow creation and protected contracts.

## Deployment

The intended hackathon deployment is Vercel for the frontend and Railway Hobby
for the always-on backend, connected to Supabase PostgreSQL, Upstash Redis,
Neo4j AuraDB and Qdrant Cloud. See [DEPLOYMENT.md](DEPLOYMENT.md) for exact
variables, commands, health checks and post-deploy acceptance tests.

Product specifications:
[PROBLEM.MD](PROBLEM.MD) · [architecture.md](architecture.md) ·
[masterimplementation.md](masterimplementation.md) · [MEMORY.md](MEMORY.md)
