"""URGENT 0b — the backup scripts actually restore.

Thin pytest wrapper around scripts/backup-smoke-test.sh so the round-trip runs
in CI. Skips where bash/python3 aren't both available (e.g. some dev boxes)."""

import shutil
import subprocess
from pathlib import Path

import pytest

_REPO_ROOT = Path(__file__).resolve().parents[3]
_SMOKE = _REPO_ROOT / "scripts" / "backup-smoke-test.sh"


@pytest.mark.skipif(
    shutil.which("bash") is None or shutil.which("python3") is None,
    reason="requires bash + python3",
)
def test_backup_restore_roundtrip():
    assert _SMOKE.is_file(), f"missing {_SMOKE}"
    result = subprocess.run(
        ["bash", str(_SMOKE)], capture_output=True, text=True, timeout=120
    )
    assert result.returncode == 0, f"stdout:\n{result.stdout}\nstderr:\n{result.stderr}"
    assert "SMOKE TEST PASSED" in result.stdout
