import json, subprocess, sys, tempfile
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]

def test_rls_passes_on_dev_config():
    r = subprocess.run([sys.executable, str(ROOT/"scripts"/"validate_rls.py"),
                        "--config", str(ROOT/"workspaces"/"dev.json")], capture_output=True)
    assert r.returncode == 0, r.stderr

def test_rls_fails_when_missing():
    cfg = {"datasets": [{"name": "X", "id": "1", "rls_roles": []}]}
    with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False) as f:
        json.dump(cfg, f); path = f.name
    r = subprocess.run([sys.executable, str(ROOT/"scripts"/"validate_rls.py"), "--config", path])
    assert r.returncode != 0
