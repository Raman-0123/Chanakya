from app.domain import build_energy_network
from app.domain.assumptions import (
    MODEL_ASSUMPTIONS,
    assumptions_report,
    check_assumptions,
)


def test_every_declared_assumption_holds_on_baseline() -> None:
    net = build_energy_network()
    checks = check_assumptions(net)
    assert checks, "no assumptions declared"
    failed = [c.id for c in checks if not c.passed]
    assert not failed, f"model-fidelity assumptions violated: {failed}"


def test_assumptions_are_fully_specified() -> None:
    # Each assumption must be explicit AND testable: statement, basis and a
    # named invariant are all required for it to count as either.
    for a in MODEL_ASSUMPTIONS:
        assert a.statement.strip(), f"{a.id} missing an explicit statement"
        assert a.basis.strip(), f"{a.id} missing its basis/value"
        assert a.test.strip(), f"{a.id} missing a testable invariant"
        assert a.category in {"calibration", "structural", "baseline"}


def test_report_summary_is_consistent() -> None:
    report = assumptions_report(build_energy_network())
    assert report["total"] == len(MODEL_ASSUMPTIONS)
    assert report["passed"] + report["failed"] == report["total"]
    assert report["all_pass"] is True
    assert report["passed"] == report["total"]
