import subprocess
import sys

from backend.services.perception_lab.model_lease import learned_model_lease


def test_live_process_cannot_be_displaced(tmp_path):
    path = tmp_path / "model.lease"
    code = ("from pathlib import Path\n"
            "from backend.services.perception_lab.model_lease import learned_model_lease,ModelLeaseBusy\n"
            f"try:\n  with learned_model_lease(family='depth',path=Path({str(path)!r})):\n    pass\n"
            "except ModelLeaseBusy:\n  raise SystemExit(75)\n")
    with learned_model_lease(family="colour", path=path):
        assert subprocess.run([sys.executable, "-c", code], check=False).returncode == 75
    assert subprocess.run([sys.executable, "-c", code], check=False).returncode == 0
