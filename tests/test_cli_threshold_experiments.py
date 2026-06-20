from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path


def test_cli_threshold_experiments_outputs_audit_deltas() -> None:
    completed = subprocess.run(
        [
            sys.executable,
            "-m",
            "app.cli",
            "threshold-experiments",
            "--experiments",
            "more_sensitive",
        ],
        cwd=Path(__file__).resolve().parents[1],
        capture_output=True,
        text=True,
        check=True,
    )

    payload = json.loads(completed.stdout)
    experiment = payload["experiments"][0]

    assert payload["baseline_id"] == "locked_oos_audit_baseline_v1"
    assert payload["fee_profile"] == "a_share_conservative"
    assert experiment["experiment_id"] == "more_sensitive"
    assert experiment["threshold_changes"]
    assert "baseline" in payload["report_note"]