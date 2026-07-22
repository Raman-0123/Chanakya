# CHANAKYA Architecture Diagrams

## A. Signal-to-mission sequence

```mermaid
sequenceDiagram
  participant S as Signal sources
  participant I as Ingestion service
  participant R as Risk scorer
  participant T as Digital twin/ontology
  participant X as Scenario engine
  participant C as Agent council
  participant D as Decision engine
  participant O as Operator

  S->>I: News, weather, market, AIS, sanctions, satellite
  I->>I: Normalize, deduplicate, stamp provenance
  I->>R: DomainEvent v1
  R->>T: Update corridor/supplier/entity exposure
  R->>O: Live risk feed and lead-time signal
  O->>X: Select scenario and response levers
  X->>X: Cascade supply, refinery, market and reserve impacts
  X->>C: Shared simulation context and cited evidence
  C->>D: Six specialist assessments and disagreements
  D->>D: Re-simulate and rank feasible strategies
  D->>O: Recommendation, alternatives, trade-offs, mission
  O->>D: Approve/activate with operator control
```

## B. Decision optimization loop

```mermaid
flowchart TD
  S[Scenario shock] --> L[Response levers]
  L --> E[Run deterministic engine]
  E --> G[Calculate supply gap and cascade]
  G --> P[Build feasible procurement alternatives]
  P --> C{Constraints satisfied?}
  C -- no --> F[Explain infeasibility]
  C -- yes --> O[Score continuity, resilience, affordability, reserve, feasibility, evidence]
  O --> R[Rank three strategies]
  R --> A[Operator approval]
  A --> M[Persistent mission]
  M --> Q[Monitor new signals]
  Q --> S
```

## C. Trust and provenance boundary

```mermaid
flowchart LR
  L[LIVE source] --> N[Normalized event]
  C[CACHED source] --> N
  R[REPLAY source] --> N
  S[SIMULATED source] --> N
  U[UNAVAILABLE] --> N
  N --> V[Visible provenance badge]
  N --> A[Auditable model input]
  A --> W[Recommendation with evidence]
```

## D. Deployment topology

```mermaid
flowchart LR
  B[Browser] --> V[Vercel: Next.js frontend]
  V -->|HTTPS/REST + WSS| R[Railway: FastAPI backend]
  R --> P[Supabase PostgreSQL]
  R --> U[Upstash Redis]
  R --> N[Neo4j AuraDB]
  R --> Q[Qdrant Cloud]
  R --> E[External signal APIs]
```
