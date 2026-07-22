# CHANAKYA — Complete Mermaid Architecture Pack

These diagrams describe the implemented prototype and its planned production topology. They can be copied into Mermaid Live Editor, GitHub Markdown, Notion, or documentation tooling that supports Mermaid.

## 1. System context diagram

```mermaid
flowchart TB
    GOV[Ministry / National Crisis Authority]
    REFINER[Refiner / Procurement Operator]
    LOGISTICS[Logistics and Shipping Operator]
    POLICY[Policy and Executive User]

    CHANAKYA((CHANAKYA<br/>Energy Crisis Operating System))

    NEWS[GDELT / geopolitical news]
    WEATHER[Open-Meteo weather and marine data]
    MARKET[EIA / Alpha Vantage market data]
    AIS[AISStream or replay vessel tracks]
    SANCTIONS[OpenSanctions / curated sanctions data]
    SATELLITE[NASA FIRMS / satellite detection hooks]

    GOV -->|investigate, approve, activate| CHANAKYA
    REFINER -->|procurement and refinery constraints| CHANAKYA
    LOGISTICS -->|route and port decisions| CHANAKYA
    POLICY -->|scenario and policy levers| CHANAKYA

    NEWS --> CHANAKYA
    WEATHER --> CHANAKYA
    MARKET --> CHANAKYA
    AIS --> CHANAKYA
    SANCTIONS --> CHANAKYA
    SATELLITE --> CHANAKYA

    CHANAKYA -->|risk brief, scenarios, alternatives, missions| GOV
    CHANAKYA -->|feasible cargo recommendations| REFINER
    CHANAKYA -->|corridor and vessel intelligence| LOGISTICS
    CHANAKYA -->|executive strategy and trade-offs| POLICY
```

## 2. User roles and OOSE use-case diagram

Mermaid does not have a universal native UML use-case renderer, so this flowchart expresses the same OOSE structure: actors, system boundary, use cases, and include relationships.

```mermaid
flowchart LR
    subgraph ACTORS[External actors]
        A1[Government crisis operator]
        A2[Procurement officer]
        A3[Maritime logistics analyst]
        A4[Strategic reserve policymaker]
        A5[Executive decision-maker]
        A6[Data / platform administrator]
    end

    subgraph SYSTEM[CHANAKYA system boundary]
        UC1((Monitor intelligence))
        UC2((Inspect digital twin))
        UC3((Score corridor risk))
        UC4((Run disruption scenario))
        UC5((Convene six-agent council))
        UC6((Rank response strategies))
        UC7((Review procurement alternatives))
        UC8((Approve and activate mission))
        UC9((Generate briefing pack))
        UC10((Monitor execution))
        UC11((Review source health))
        UC12((Refresh sources))
    end

    A1 --> UC1
    A1 --> UC2
    A1 --> UC4
    A1 --> UC5
    A1 --> UC6
    A1 --> UC8
    A1 --> UC10

    A2 --> UC7
    A2 --> UC8
    A3 --> UC2
    A3 --> UC3
    A3 --> UC7
    A4 --> UC4
    A4 --> UC6
    A5 --> UC6
    A5 --> UC8
    A5 --> UC9
    A6 --> UC11
    A6 --> UC12

    UC4 -. includes .-> UC3
    UC5 -. includes .-> UC4
    UC6 -. includes .-> UC5
    UC6 -. includes .-> UC7
    UC8 -. includes .-> UC9
    UC8 -. includes .-> UC10
```

## 3. OOSE domain/object interaction diagram

```mermaid
classDiagram
    class Operator {
        +id: string
        +role: string
        +reviewScenario()
        +approveMission()
    }

    class IntelligenceEvent {
        +id: string
        +category: SignalCategory
        +severity: string
        +confidence: float
        +provenance: SourceKind
        +publishedAt: datetime
    }

    class EnergyNetwork {
        +suppliers: Supplier[]
        +corridors: ShippingCorridor[]
        +ports: Port[]
        +refineries: Refinery[]
        +reserves: ReserveSite[]
        +sprCoverageDays(): float
        +supplierHHI(): float
    }

    class ScenarioSpec {
        +id: string
        +name: string
        +category: ScenarioCategory
        +shock: ScenarioShock
        +defaultLevers: ResponseLevers
    }

    class SimulationResult {
        +supplyGapKbpd: float
        +residualShortfallKbpd: float
        +refineryUtilizationPct: float
        +brentChangePct: float
        +sprReleaseKbpd: float
        +nesiAfter: float
        +assumptions: Assumption[]
    }

    class AgentAssessment {
        +agentId: string
        +stance: string
        +observations: string[]
        +recommendation: string
        +confidence: float
        +evidence: Evidence[]
    }

    class StrategyOption {
        +id: string
        +title: string
        +projection: StrategyProjection
        +scores: ScoreBreakdown
        +rank: int
        +feasible: bool
        +procurementAlternatives: ProcurementAlternative[]
    }

    class Mission {
        +id: string
        +status: string
        +scenarioId: string
        +strategyId: string
        +activate()
    }

    Operator --> ScenarioSpec : creates / selects
    IntelligenceEvent --> EnergyNetwork : updates exposure
    EnergyNetwork --> ScenarioSpec : provides baseline
    ScenarioSpec --> SimulationResult : runs through engine
    SimulationResult --> AgentAssessment : shared council context
    AgentAssessment --> StrategyOption : informs ranking
    StrategyOption --> Mission : becomes approved mission
    Operator --> Mission : approves and monitors
```

## 4. High-level layered architecture

```mermaid
flowchart TB
    subgraph EXPERIENCE[Experience layer]
        UI[Next.js 14 Mission Control]
        MAP[Leaflet geospatial map]
        GRAPH[React Flow knowledge graph]
        WS[WebSocket live bridge]
        REST[REST command and recovery API]
    end

    subgraph API[Application layer]
        FASTAPI[FastAPI application]
        ROUTES[Health, intelligence, network, simulation, council, missions, ontology]
        AUTH[Operator PIN protection]
    end

    subgraph INTELLIGENCE[Intelligence layer]
        INGEST[Ingestion adapters]
        NORMALIZE[DomainEvent v1 normalizer]
        RISK[Risk scoring and lead-time analysis]
        RAG[RAG evidence retrieval]
    end

    subgraph DECISION[Decision layer]
        TWIN[Energy network digital twin]
        ENGINE[Deterministic cascade simulation]
        AGENTS[LangGraph six-agent council]
        OPT[Procurement and strategy optimizer]
        NESI[National Energy Security Index]
    end

    subgraph DATA[Data and persistence layer]
        PG[(PostgreSQL)]
        REDIS[(Redis)]
        NEO[(Neo4j)]
        QDRANT[(Qdrant)]
    end

    UI --> MAP
    UI --> GRAPH
    UI --> WS
    UI --> REST
    WS --> FASTAPI
    REST --> FASTAPI
    FASTAPI --> ROUTES
    ROUTES --> AUTH
    ROUTES --> RISK
    ROUTES --> ENGINE
    ROUTES --> AGENTS
    INGEST --> NORMALIZE --> RISK
    NORMALIZE --> REDIS
    NORMALIZE --> PG
    RISK --> TWIN
    RAG --> AGENTS
    TWIN --> ENGINE --> AGENTS --> OPT
    ENGINE --> NESI
    OPT --> PG
    AGENTS --> PG
    TWIN --> NEO
    RAG --> QDRANT
```

## 5. Detailed runtime/component diagram

```mermaid
flowchart LR
    subgraph ADAPTERS[Ingestion adapters]
        GDELT[GDELT adapter]
        METEO[Weather adapter]
        PRICES[Price adapter]
        VESSELS[Vessel adapter]
        SANC[Sanctions adapter]
        FIRMS[FIRMS adapter]
    end

    subgraph PIPELINE[Event pipeline]
        SERVICE[IntelligenceService]
        TAG[Entity and corridor tagging]
        DEDUP[Deduplication]
        CACHE[TTL cache]
        STREAM[Redis Streams]
        RETRY[Retry and dead-letter handling]
    end

    subgraph CORE[Domain core]
        ENT[Typed domain entities]
        SEED[Baseline Indian energy network]
        SCENARIOS[Scenario catalog]
        CASCADE[Cascade engine]
        LOGISTICS[Logistics realism]
        ASSUMPTIONS[Assumption self-audit]
        NESI[NESI calculator]
    end

    subgraph AGENT_LAYER[Agent and decision layer]
        CONTEXT[Council context builder]
        SIX[Six specialist agents]
        LANGGRAPH[Checkpointed LangGraph workflow]
        DECISION[Chief-of-staff decision engine]
        PROCUREMENT[Procurement alternative builder]
    end

    subgraph REPOSITORIES[Persistence]
        REPOS[RepositoryHub]
        POSTGRES[(PostgreSQL)]
        NEO4J[(Neo4j)]
        Q[(Qdrant)]
    end

    GDELT --> SERVICE
    METEO --> SERVICE
    PRICES --> SERVICE
    VESSELS --> SERVICE
    SANC --> SERVICE
    FIRMS --> SERVICE
    SERVICE --> TAG --> DEDUP --> CACHE --> STREAM
    STREAM --> RETRY
    DEDUP --> ENT
    ENT --> CORE
    SEED --> ENT
    SCENARIOS --> CASCADE
    ENT --> CASCADE
    CASCADE --> LOGISTICS
    CASCADE --> NESI
    CASCADE --> CONTEXT
    ASSUMPTIONS --> CASCADE
    CONTEXT --> LANGGRAPH --> SIX
    SIX --> DECISION
    DECISION --> PROCUREMENT
    PROCUREMENT --> LOGISTICS
    DECISION --> REPOS
    LANGGRAPH --> REPOS
    REPOS --> POSTGRES
    ENT --> NEO4J
    Q --> CONTEXT
```

## 6. Deployment diagram

```mermaid
flowchart TB
    subgraph USER_DEVICE[Operator device]
        BROWSER[Browser]
    end

    subgraph VERCEL[Vercel]
        NEXT[Next.js frontend]
        STATIC[Static assets and route shell]
    end

    subgraph RAILWAY[Railway]
        API[FastAPI API process]
        WORKER[Ingestion / worker process]
        SOCKET[WebSocket hub]
    end

    subgraph MANAGED[Managed data services]
        SUPA[(Supabase PostgreSQL)]
        UPSTASH[(Upstash Redis)]
        AURA[(Neo4j AuraDB)]
        CLOUDQ[(Qdrant Cloud)]
    end

    subgraph EXTERNAL[External APIs]
        SOURCES[News, weather, market, AIS, sanctions, satellite]
        LLM[Optional LLM providers]
    end

    BROWSER -->|HTTPS| NEXT
    BROWSER -->|HTTPS REST| API
    BROWSER -->|WSS| SOCKET
    NEXT --> STATIC
    API --> SUPA
    API --> UPSTASH
    API --> AURA
    API --> CLOUDQ
    WORKER --> UPSTASH
    WORKER --> SOURCES
    API --> LLM
    SOCKET --> API
```

## 7. Data-flow diagram

```mermaid
flowchart LR
    S1[News signal]
    S2[Weather signal]
    S3[Market signal]
    S4[Vessel signal]
    S5[Sanctions signal]
    S6[Satellite signal]

    N[Normalize into DomainEvent v1]
    P[Stamp provenance and freshness]
    F[Fuse events, prices, weather, vessels and detections]
    RS[Compute corridor/supplier risk]
    KG[Update ontology and digital twin]
    SIM[Run scenario cascade]
    ALT[Generate feasible alternatives]
    COUNCIL[Six-agent assessment]
    RANK[Rank strategies]
    MISSION[Persist mission and briefing]
    OP[Operator action]

    S1 --> N
    S2 --> N
    S3 --> N
    S4 --> N
    S5 --> N
    S6 --> N
    N --> P --> F
    F --> RS
    F --> KG
    RS --> SIM
    KG --> SIM
    SIM --> ALT --> COUNCIL --> RANK --> MISSION --> OP
    OP -->|new lever or approval| SIM
```

## 8. Signal-to-recommendation sequence diagram

```mermaid
sequenceDiagram
    autonumber
    participant Source as External source
    participant Adapter as Ingestion adapter
    participant Event as DomainEvent pipeline
    participant Risk as Risk scorer
    participant Twin as Digital twin
    participant Sim as Scenario engine
    participant Council as Six-agent council
    participant Decision as Decision engine
    participant UI as Mission Control
    participant Operator as Operator

    Source->>Adapter: Publish observation
    Adapter->>Event: Normalize observation
    Event->>Event: Deduplicate and stamp provenance
    Event->>Risk: Feed normalized event
    Risk->>Twin: Update corridor/entity exposure
    Risk-->>UI: Risk probability, confidence, lead time
    Operator->>UI: Select scenario and response levers
    UI->>Sim: POST /api/simulation/run
    Sim->>Twin: Read baseline network
    Sim->>Sim: Calculate gap, reroute, spot, SPR, macro cascade
    Sim-->>UI: Simulation result and assumptions
    Operator->>UI: Convene council
    UI->>Council: POST /api/council/convene
    Council->>Sim: Reuse scenario context
    Council->>Council: Run six specialist assessments
    Council->>Decision: Pass assessments and evidence
    Decision->>Decision: Re-simulate and rank strategies
    Decision-->>UI: Strategies, alternatives, trade-offs
    Operator->>UI: Send strategy to execution
    UI->>Decision: Create / activate mission
    Decision-->>UI: Mission, checklist, briefing pack, audit record
```

## 9. Scenario simulation activity diagram

```mermaid
flowchart TD
    START([Operator opens Scenario Lab]) --> SELECT[Select catalog or custom scenario]
    SELECT --> SHOCK[Define disruption shock]
    SHOCK --> LEVERS[Set SPR, reroute and spot levers]
    LEVERS --> VALIDATE{Valid inputs?}
    VALIDATE -- no --> ERROR[Show validation error]
    ERROR --> LEVERS
    VALIDATE -- yes --> BASELINE[Load immutable energy network baseline]
    BASELINE --> SUPPLY[Calculate affected supply]
    SUPPLY --> ROUTE{Fallback corridor available?}
    ROUTE -- yes --> REROUTE[Apply transit delay and freight premium]
    ROUTE -- no --> REPLACE[Require supplier replacement]
    REROUTE --> REPLACE
    REPLACE --> CAPACITY[Apply grade, port, tanker and spare-capacity constraints]
    CAPACITY --> SPOT[Apply limited spot procurement]
    SPOT --> RESERVE[Apply finite SPR drawdown]
    RESERVE --> IMPACT[Calculate refinery, price and economic impacts]
    IMPACT --> NESI[Recompute NESI]
    NESI --> ASSUMPTIONS[Attach explicit assumptions and self-audit]
    ASSUMPTIONS --> RESULT[Render impact readout]
    RESULT --> END([Operator compares or convenes council])
```

## 10. Mission lifecycle/state diagram

```mermaid
stateDiagram-v2
    [*] --> Draft
    Draft: Scenario selected
    Draft: Response levers editable

    Draft --> Simulated: Scenario run completed
    Simulated: Cascade and assumptions available

    Simulated --> CouncilRunning: Council convened
    CouncilRunning: Six agents assess shared context

    CouncilRunning --> Recommended: Strategies ranked
    Recommended: Recommended strategy selected

    Recommended --> PendingApproval: Sent to Mission Execution
    PendingApproval: Operator review required

    PendingApproval --> Active: Operator PIN accepted
    PendingApproval --> Rejected: Operator rejects strategy
    Rejected --> Draft: Revise scenario or levers

    Active --> Monitoring: Execution checklist launched
    Monitoring: New signals can trigger reassessment

    Monitoring --> Replanned: Risk or supply state changes
    Replanned --> CouncilRunning: Re-convene council
    Monitoring --> Completed: Mission outcome recorded
    Completed --> [*]
```

## 11. Entity relationship/data model diagram

```mermaid
erDiagram
    SUPPLIER ||--o{ SHIPPING_CORRIDOR : uses
    SHIPPING_CORRIDOR ||--o{ PORT : reaches
    PORT ||--o{ REFINERY : supplies
    REFINERY ||--o{ STRATEGIC_RESERVE : coordinates_with
    SUPPLIER ||--o{ PROCUREMENT_ALTERNATIVE : offers
    REFINERY ||--o{ PROCUREMENT_ALTERNATIVE : compatible_with
    SHIPPING_CORRIDOR ||--o{ INTELLIGENCE_EVENT : affected_by
    SUPPLIER ||--o{ INTELLIGENCE_EVENT : associated_with
    SCENARIO ||--o{ SIMULATION_RUN : produces
    SIMULATION_RUN ||--o{ AGENT_ASSESSMENT : informs
    AGENT_ASSESSMENT ||--o{ STRATEGY_OPTION : influences
    STRATEGY_OPTION ||--o{ MISSION : selected_for
    MISSION ||--o{ EXECUTION_STEP : contains
    INTELLIGENCE_EVENT ||--o{ EVIDENCE_CITATION : supports
    STRATEGY_OPTION ||--o{ EVIDENCE_CITATION : supported_by

    SUPPLIER {
        string id PK
        string country
        float import_share
        string crude_grade
        float reliability
        float spare_capacity_kbpd
        boolean sanctioned
    }
    SHIPPING_CORRIDOR {
        string id PK
        string name
        string chokepoint
        float import_share
        float base_transit_days
        float reroute_added_days
        float reroute_cost_premium_pct
    }
    PORT {
        string id PK
        string name
        string coast
        float crude_capacity_kbpd
        string status
    }
    REFINERY {
        string id PK
        string name
        string operator
        float nameplate_kbpd
        float throughput_kbpd
        string preferred_grade
        float inventory_days
    }
    STRATEGIC_RESERVE {
        string id PK
        string name
        float capacity_mmt
        float fill_pct
    }
    INTELLIGENCE_EVENT {
        string id PK
        string category
        string severity
        float risk_score
        float confidence
        string provenance
        datetime published_at
    }
    SCENARIO {
        string id PK
        string name
        string category
        int duration_days
        float block_fraction
        float market_shock_base
    }
    SIMULATION_RUN {
        string id PK
        string scenario_id FK
        float residual_shortfall_kbpd
        float nesi_after
        datetime created_at
    }
    AGENT_ASSESSMENT {
        string id PK
        string agent_id
        string stance
        float confidence
        string reasoning_mode
    }
    STRATEGY_OPTION {
        string id PK
        string title
        int rank
        float score
        boolean feasible
    }
    PROCUREMENT_ALTERNATIVE {
        string id PK
        string supplier_id FK
        float volume_kbpd
        int eta_days
        float landed_premium_usd_bbl
        string tanker_status
        boolean feasible
    }
    MISSION {
        string id PK
        string scenario_id FK
        string strategy_id FK
        string status
        datetime activated_at
    }
    EXECUTION_STEP {
        string id PK
        string mission_id FK
        string owner
        string priority
        string status
    }
    EVIDENCE_CITATION {
        string id PK
        string source
        string title
        float confidence
        string category
    }
```

## 12. Knowledge graph topology

```mermaid
flowchart LR
    SUP[Supplier country]
    COR[Shipping corridor]
    CHK[Chokepoint]
    VES[Vessel]
    PORT[Port]
    REF[Refinery]
    RES[Strategic reserve]
    EVT[Risk event]
    SAN[Sanctions signal]
    PRICE[Market signal]

    SUP -->|ships through| COR
    COR -->|contains| CHK
    VES -->|transits| COR
    COR -->|arrives at| PORT
    PORT -->|feeds| REF
    REF -->|protected by| RES
    EVT -->|threatens| COR
    EVT -->|raises risk for| SUP
    SAN -->|constrains| SUP
    PRICE -->|changes cost of| SUP
    EVT -->|propagates to| PORT
    PORT -->|constrains| REF
    REF -->|changes| RES
```

## 13. Security, trust, and provenance diagram

```mermaid
flowchart TB
    SOURCE[External observation] --> ADAPTER[Adapter]
    ADAPTER --> NORMALIZE[DomainEvent v1]
    NORMALIZE --> PROV{Provenance}

    PROV --> LIVE[LIVE]
    PROV --> CACHED[CACHED]
    PROV --> REPLAY[REPLAY]
    PROV --> SIMULATED[SIMULATED]
    PROV --> UNAVAILABLE[UNAVAILABLE]

    LIVE --> EVIDENCE[Evidence record]
    CACHED --> EVIDENCE
    REPLAY --> EVIDENCE
    SIMULATED --> EVIDENCE
    UNAVAILABLE --> EVIDENCE

    EVIDENCE --> RISK[Risk score]
    EVIDENCE --> COUNCIL[Agent context]
    RISK --> RECOMMENDATION[Recommendation]
    COUNCIL --> RECOMMENDATION
    RECOMMENDATION --> REVIEW[Human review]
    REVIEW --> PIN{Operator PIN}
    PIN -- accepted --> AUDIT[Persist mission and audit trail]
    PIN -- rejected --> REVISE[Revise or discard]
```

## 14. Optimization and objective scoring diagram

```mermaid
flowchart TD
    INPUT[Scenario + network + response levers]
    INPUT --> CONSTRAINTS[Physical and policy constraints]
    CONSTRAINTS --> C1[Supplier spare capacity]
    CONSTRAINTS --> C2[Crude grade compatibility]
    CONSTRAINTS --> C3[Port receiving capacity]
    CONSTRAINTS --> C4[Tanker and charter delay]
    CONSTRAINTS --> C5[Sanctions and corridor status]
    CONSTRAINTS --> C6[Finite SPR volume]

    INPUT --> OBJECTIVE[Multi-objective score]
    OBJECTIVE --> O1[Continuity]
    OBJECTIVE --> O2[Resilience / NESI]
    OBJECTIVE --> O3[Affordability]
    OBJECTIVE --> O4[Reserve preservation]
    OBJECTIVE --> O5[Procurement feasibility]
    OBJECTIVE --> O6[Evidence confidence]

    C1 --> FEASIBLE[Feasible strategy set]
    C2 --> FEASIBLE
    C3 --> FEASIBLE
    C4 --> FEASIBLE
    C5 --> FEASIBLE
    C6 --> FEASIBLE
    FEASIBLE --> RESIM[Re-simulate each candidate]
    O1 --> RESIM
    O2 --> RESIM
    O3 --> RESIM
    O4 --> RESIM
    O5 --> RESIM
    O6 --> RESIM
    RESIM --> RANK[Rank Reserve-Led, Diversified, Measured]
    RANK --> DECISION[Explain recommendation and trade-offs]
```

## 15. API/service interaction diagram

```mermaid
flowchart LR
    CLIENT[Next.js client]
    HEALTH[/api/health and /api/readyz/]
    INTEL[/api/intelligence/*/]
    NETWORK[/api/network and /api/graph/]
    SIM[/api/simulation/*/]
    COUNCIL[/api/council/convene/]
    WORKFLOW[/api/workflows/{run_id}/]
    MISSIONS[/api/missions/*/]
    SOURCES[/api/sources/status/]
    SOCKET[(WS /api/ws/intelligence)]

    CLIENT --> HEALTH
    CLIENT --> INTEL
    CLIENT --> NETWORK
    CLIENT --> SIM
    CLIENT --> COUNCIL
    CLIENT --> WORKFLOW
    CLIENT --> MISSIONS
    CLIENT --> SOURCES
    CLIENT <--> SOCKET

    INTEL --> INGEST[IntelligenceService]
    NETWORK --> TWIN[EnergyNetwork]
    SIM --> ENGINE[SimulationEngine]
    COUNCIL --> LANG[LangGraph Council]
    WORKFLOW --> REPO[RepositoryHub]
    MISSIONS --> REPO
    SOURCES --> STATUS[Source status registry]
```

## 16. Demo workflow diagram

```mermaid
flowchart LR
    A[Open CHANAKYA] --> B[Intelligence room]
    B --> C[Inspect Hormuz risk and evidence]
    C --> D[Digital Twin map / graph]
    D --> E[Scenario Lab: Hormuz closure]
    E --> F[Adjust SPR release]
    F --> G[View cascade and assumptions]
    G --> H[Convene six-agent council]
    H --> I[Compare three strategies]
    I --> J[Review feasible procurement alternatives]
    J --> K[Send to Mission Execution]
    K --> L[Activate mission]
    L --> M[Monitor timeline and briefing]
```
