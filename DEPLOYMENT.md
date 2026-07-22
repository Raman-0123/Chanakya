# Deployment Runbook

## Managed services

Create one project/database in each service before deploying:

1. Supabase PostgreSQL. Convert the supplied URI to SQLAlchemy form:
   `postgresql+asyncpg://USER:PASSWORD@HOST:PORT/DATABASE`.
2. Upstash Redis. Use the TLS Redis URI, normally
   `rediss://default:PASSWORD@HOST:PORT`; do not use the REST URL because the
   stream consumer relies on blocking `XREADGROUP`.
3. Neo4j AuraDB. Use its `neo4j+s://...` URI and generated credentials.
4. Qdrant Cloud. Record the HTTPS cluster URL and API key.

Use the nearest available regions to reduce cross-service latency. Never commit
credentials; enter them in Railway/Vercel secret settings.

## Railway backend

Deploy the repository root. `railway.json` builds `backend/Dockerfile` and checks
`/api/livez`. Configure:

```text
ENVIRONMENT=production
PROCESS_ROLE=all
FRONTEND_ORIGIN=https://YOUR-PROJECT.vercel.app
ALLOWED_ORIGINS=https://YOUR-CUSTOM-DOMAIN
OPERATOR_PIN=A-LONG-RANDOM-DEMO-PIN
DATABASE_URL=postgresql+asyncpg://...
REDIS_URL=rediss://...
NEO4J_URI=neo4j+s://...
NEO4J_USER=neo4j
NEO4J_PASSWORD=...
QDRANT_URL=https://...
QDRANT_API_KEY=...
EVENT_POLL_SECONDS=300
```

Add whichever source/LLM credentials are available:

```text
GROQ_API_KEY=...
EIA_API_KEY=...
ALPHA_VANTAGE_API_KEY=...
AISSTREAM_API_KEY=...
OPENSANCTIONS_API_KEY=...
NASA_FIRMS_MAP_KEY=...
```

Railway supplies `PORT`; the container listens on it. Keep one Uvicorn worker
when `PROCESS_ROLE=all` so the in-process scheduler and WebSocket hub are not
duplicated. For later scaling, deploy separate `PROCESS_ROLE=api` and
`PROCESS_ROLE=worker` services.

The application initializes idempotent PostgreSQL tables, Neo4j constraints and
the Qdrant evidence corpus at startup. Manual commands are also available:

```bash
cd backend
python scripts/migrate.py
python scripts/seed_rag.py
```

## Vercel frontend

Import the same repository, set the Root Directory to `frontend`, and configure:

```text
NEXT_PUBLIC_API_BASE_URL=https://YOUR-RAILWAY-SERVICE.up.railway.app
NEXT_PUBLIC_WS_BASE_URL=wss://YOUR-RAILWAY-SERVICE.up.railway.app
```

Redeploy after setting variables. The browser connects directly to FastAPI for
WebSockets; Vercel is not used as a WebSocket proxy.

## Acceptance checks

1. `GET /api/livez` returns `alive` and `/api/readyz` reports all four stores.
2. `/api/sources/status` distinguishes live, cached, replay, simulated and unavailable sources.
3. The shell's Stream indicator becomes `live`.
4. Run the Hormuz scenario, convene the council and confirm six assessments,
   three strategies, a workflow ID, mission ID and feasible cargo rows.
5. Reload the backend and retrieve the same workflow and mission IDs.
6. Activate the mission using the configured operator PIN and confirm its status becomes `active`.
7. Temporarily remove one optional source key and verify the app degrades visibly without failing.

Free managed tiers can pause or rate-limit. Wake all services before judging and
perform this acceptance pass immediately before the presentation.
