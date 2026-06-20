import subprocess
import sys
from pathlib import Path


def test_dashboard_imports_when_app_directory_is_entrypoint() -> None:
    repo_root = Path(__file__).resolve().parents[1]
    script = (
        "import os, sys; "
        "os.chdir('app'); "
        "sys.path=[os.getcwd()]+[p for p in sys.path if p != '']; "
        "import dashboard"
    )

    result = subprocess.run(
        [sys.executable, "-c", script],
        cwd=repo_root,
        capture_output=True,
        text=True,
        timeout=30,
    )

    assert result.returncode == 0, result.stderr
