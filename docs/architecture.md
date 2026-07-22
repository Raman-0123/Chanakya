# CHANAKYA Architecture

Complete Mermaid diagram source pack: [docs/MERMAID_ARCHITECTURE_PACK.md](docs/MERMAID_ARCHITECTURE_PACK.md).

## Implemented runtime (July 2026)

```text
GDELT · Open-Meteo · EIA/Alpha Vantage · AISStream/Replay · Sanctions · FIRMS
                                  │
                       Normalized DomainEvent v1
                                  │
                   PostgreSQL ← Redis Streams → WebSocket
                                  │
             Fused OperationalSnapshot + geo monitoring stations
                                  │
          Risk/quality gate ──→ LangGraph six-specialist council
                                  │
       Control search + ETA-aware procurement + site-level SPR plan
                                  │
      Neo4j: supplier→route→port→refinery→distribution demand hub
                                  │
                 Next.js six-room mission-control interface
```

- PostgreSQL is the audit/system-of-record store for events, workflows and missions.
- Redis provides caching, a bounded event stream, retry/dead-letter handling and scheduler leases.
- Neo4j is the ontology source; `/api/graph` declares its in-memory degraded fallback.
- Qdrant stores a small cited official-source evidence corpus.
- Agents consume the same immutable operational snapshot and simulation context;
  their typed lever proposals are confidence-weighted into decision scoring.
- AIS positions are geofenced to monitored routes and count as tankers only when
  AIS static ship type identifies them; unknown vessels stay explicitly unknown.
- Mission activation persists the operator-selected strategy, while every agency
  task transition is PIN-gated and audit-recorded.
- WebSockets carry invalidation/events; REST remains the recovery and command interface.
- `PROCESS_ROLE=all|api|worker` supports a one-service hackathon deployment and later separation.

The original high-level design follows. Items naming paid feeds represent future
adapter possibilities, not claims that those sources are currently licensed.

## Original high-level architecture

Energy Crisis Operating System (High-Level Architecture)

flowchart LR

%% =========================
%% DATA SOURCES
%% =========================

subgraph DS["🌍 Global Intelligence Sources"]
N1[Reuters / Bloomberg News]
N2[Satellite Imagery]
N3[AIS Vessel Tracking]
N4[Oil Prices & Commodity Markets]
N5[Weather APIs]
N6[Sanctions Database]
N7[Port & Shipping Data]
N8[Government Energy Data]
end

%% =========================
%% INGESTION
%% =========================

subgraph DI["📡 Data Ingestion & Event Detection"]
A1[Streaming Pipeline]
A2[Document & News Parser]
A3[Entity Extraction]
A4[Event Detection Engine]
A5[Risk Signal Generator]
end

%% =========================
%% KNOWLEDGE LAYER
%% =========================

subgraph KG["🧠 Knowledge Graph & Data Fusion"]
K1[Entity Relationship Graph]
K2[Historical Incidents]
K3[Supplier Network]
K4[Shipping Routes]
K5[Refineries]
K6[Strategic Petroleum Reserve]
end

%% =========================
%% DIGITAL TWIN
%% =========================

subgraph DT["🌐 National Energy Digital Twin"]
D1[Ports]
D2[Pipelines]
D3[Shipping Corridors]
D4[Oil Tankers]
D5[Storage Facilities]
D6[Indian Refineries]
end

%% =========================
%% MULTI AGENT
%% =========================

subgraph MA["🤖 Multi-Agent Intelligence Council"]

M1[Intelligence Agent]

M2[Maritime Logistics Agent]

M3[Procurement Agent]

M4[Strategic Reserve Agent]

M5[Economic Impact Agent]

M6[Policy Advisor Agent]

end

%% =========================
%% DECISION ENGINE
%% =========================

subgraph DE["⚡ AI Decision Engine"]

E1[Risk Assessment]

E2[Scenario Simulator]

E3[Counterfactual Analysis]

E4[Optimization Engine]

E5[National Recommendation]

end

%% =========================
%% EXECUTION
%% =========================

subgraph EX["🎯 Mission Execution"]

X1[Government Dashboard]

X2[Cabinet Brief]

X3[Procurement Orders]

X4[SPR Release Plan]

X5[Public Advisory]

X6[Response Timeline]

end

%% FLOW

N1-->A1
N2-->A1
N3-->A1
N4-->A1
N5-->A1
N6-->A1
N7-->A1
N8-->A1

A1-->A2
A2-->A3
A3-->A4
A4-->A5

A5-->K1

K1-->K2
K1-->K3
K1-->K4
K1-->K5
K1-->K6

K1-->D1
K1-->D2
K1-->D3
K1-->D4
K1-->D5
K1-->D6

D1-->M1
D2-->M2
D3-->M2
D4-->M2
D5-->M4
D6-->M3

M1-->E1
M2-->E1
M3-->E1
M4-->E1
M5-->E1
M6-->E1

E1-->E2
E2-->E3
E3-->E4
E4-->E5

E5-->X1
E5-->X2
E5-->X3
E5-->X4
E5-->X5
E5-->X6

User Workflow (Palantir Gotham Style)

flowchart TD

A[🚨 Geopolitical Event Detected]

-->B[AI Detects Risk Signals]

B

-->C[Knowledge Graph Updates]

C

-->D[Energy Digital Twin Updates]

D

-->E[AI Agents Begin Investigation]

E

-->F[Intelligence Council Discussion]

F

-->G[Decision Engine Evaluates Options]

G

-->H[Scenario Simulation]

H

-->I[Best Strategy Selected]

I

-->J[Cabinet Approval]

J

-->K[Mission Execution]

K

-->L[Continuous Monitoring]


Multi-Agent Collaboration

flowchart LR

A[Intelligence Agent]

-->F[Decision Engine]

B[Logistics Agent]

-->F

C[Procurement Agent]

-->F

D[SPR Agent]

-->F

E[Economic Agent]

-->F

F

-->G[Policy Recommendation]

G

-->H[Mission Execution]

Scenario Simulation Engine

This is one of the strongest differentiators because it lets decision-makers explore possible futures before acting.

flowchart TD

A[Choose Crisis]

-->B{Scenario}

B

-->C[Hormuz Closed]

B

-->D[Red Sea Blocked]

B

-->E[OPEC Production Cut]

B

-->F[Supplier Sanctions]

C-->G

D-->G

E-->G

F-->G

G[Simulation Engine]

-->H[Oil Supply Impact]

H

-->I[Fuel Price Prediction]

I

-->J[GDP Impact]

J

-->K[AI Recommended Response]


AI Decision Pipeline

flowchart LR

A[Global Event]

-->

B[Risk Analysis]

-->

C[Knowledge Graph Retrieval]

-->

D[Multi-Agent Discussion]

-->

E[Optimization Engine]

-->

F[Counterfactual Simulator]

-->

G[Final National Strategy]

-->

H[Mission Execution]


Digital Twin Architecture


flowchart TD

World[Global Suppliers]

-->

Ports[Indian Ports]

-->

SPR[Strategic Petroleum Reserve]

-->

Refineries[Indian Refineries]

-->

Distribution[Fuel Distribution]

-->

Consumers[Citizens & Industries]

Weather

-->Ports

Shipping

-->Ports

News

-->World

Satellite

-->Shipping

System Architecture (Microservice View)


flowchart LR

UI[React / Next.js Mission Control]

<-->API[FastAPI Gateway]

API

-->AUTH[Authentication]

API

-->INGEST[Data Ingestion Service]

API

-->GRAPH[Knowledge Graph Service]

API

-->RAG[RAG Service]

API

-->AGENTS[Multi-Agent Orchestrator]

API

-->SIM[Scenario Simulator]

API

-->OPT[Optimization Engine]

API

-->TWIN[Digital Twin Service]

API

-->REPORT[Mission Report Generator]

INGEST

-->DB[(PostgreSQL)]

GRAPH

-->NEO[(Neo4j)]

RAG

-->VDB[(Vector Database)]

SIM

-->CACHE[(Redis)]

REPORT

-->PDF[Cabinet Brief]
