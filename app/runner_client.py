"""Start the isolated runner with a bounded timeout."""
import json
import subprocess
import sys
from pathlib import Path
import yaml

ROOT = Path(__file__).resolve().parents[1]

def run_inspection(url: str) -> dict:
    settings = yaml.safe_load((ROOT / "config/settings.yaml").read_text())
    result = subprocess.run(
        [sys.executable, "-m", "runner.runner_main"],
        input=json.dumps({"url": url}), text=True, capture_output=True,
        cwd=ROOT, timeout=settings["runner_timeout_seconds"],
    )
    payload = json.loads(result.stdout)
    if result.returncode or "error" in payload:
        raise ValueError(payload.get("error", "Runner failed"))
    if len(payload.get("elements", [])) > settings["max_elements"]:
        raise ValueError("Inspection exceeds the configured element limit")
    return payload
