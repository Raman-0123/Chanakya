"""Live data ingestion — Layer 1, the platform's eyes and ears.

Every adapter normalises a heterogeneous free source into a common schema and
follows one contract: try live → fall back to cache → fall back to a realistic
synthetic baseline, always tagging provenance. This keeps the Intelligence Room
alive even with zero API keys or a flaky network.
"""

from app.ingestion.service import IntelligenceService, get_intelligence_service

__all__ = ["IntelligenceService", "get_intelligence_service"]
