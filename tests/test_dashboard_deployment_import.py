import subprocess
import sys
import types
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


def test_dashboard_refresh_removes_cached_project_submodules() -> None:
    import app.dashboard as dashboard

    sys.modules["research.dataset_registry"] = types.ModuleType("research.dataset_registry")

    dashboard._refresh_project_modules_after_deploy()

    assert "research.dataset_registry" not in sys.modules
    assert sys.modules["app.dashboard"] is dashboard
