"""Live operational-state fusion for the signal -> decision control loop."""

from app.operations.models import OperationalSnapshot


def get_operational_service():
    # Lazy import keeps pure domain/logistics modules free of an ingestion cycle.
    from app.operations.service import get_operational_service as _get
    return _get()


__all__ = ["OperationalSnapshot", "get_operational_service"]
