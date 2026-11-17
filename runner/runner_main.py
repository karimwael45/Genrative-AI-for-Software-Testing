"""JSON stdin/stdout entry point. Run from the project root."""
import json
import sys
from pathlib import Path
from urllib.parse import urlsplit
import yaml
from runner.inspector import inspect_page

ROOT = Path(__file__).resolve().parents[1]

def validate_url(url):
    settings = yaml.safe_load((ROOT / "config/settings.yaml").read_text())
    parts = urlsplit(url)
    if parts.scheme not in {"http", "https"} or not parts.netloc or parts.username or parts.password:
        raise ValueError("A valid HTTP(S) demo URL is required")
    origin = f"{parts.scheme}://{parts.netloc}"
    if origin not in settings["allowed_origins"]:
        raise ValueError("URL origin is not in the configured allowlist")
    return url

def main():
    try:
        request = json.load(sys.stdin)
        result = inspect_page(validate_url(request["url"]))
    except Exception as exc:
        print(json.dumps({"error": str(exc)}))
        return 1
    print(json.dumps(result))
    return 0

if __name__ == "__main__":
    sys.exit(main())
