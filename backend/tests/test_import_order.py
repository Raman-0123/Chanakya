import subprocess
import sys


def test_operational_package_can_be_cold_imported_first() -> None:
    result = subprocess.run(
        [sys.executable, "-c", "from app.operations import get_operational_service; get_operational_service()"],
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stderr
