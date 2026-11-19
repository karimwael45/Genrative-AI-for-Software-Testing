"""Try the model without the web UI or the browser runner.

Examples (from the project root):
    python -m model.cli --goal "Check how invalid emails are handled" --ids el-1 el-2
    python -m model.cli --inspection evidence/inspection_output.json --goal "..." --ids el-3 \
        --save evidence/model_usage_log.json

By default it uses contracts/sample-inspection.json (synthetic data: fine for
checking the setup, but use a real inspection for submitted evidence).
"""
import argparse
import json
import platform
import sys
from datetime import datetime, timezone
from pathlib import Path

from model.model import load_model_config, suggest
from model.providers import ProviderError
from model.validation import resolve_elements

ROOT = Path(__file__).resolve().parents[1]


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--inspection", default=str(ROOT / "contracts/sample-inspection.json"))
    parser.add_argument("--goal", required=True)
    parser.add_argument("--ids", nargs="+", required=True, help="selected element IDs")
    parser.add_argument("--answer", help="answer to a previous clarification question")
    parser.add_argument("--save", help="append the call record to this JSON file")
    args = parser.parse_args()

    snapshot = json.loads(Path(args.inspection).read_text(encoding="utf-8"))
    try:
        elements = resolve_elements(snapshot, args.ids)
        result = suggest(args.goal, snapshot["sourceUrl"], elements, args.answer)
    except (ValueError, ProviderError) as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1

    print(result["message"])
    print("\n--- usage ---")
    print(f"provider/model : {result['provider']} / {result['model']}")
    est = " (estimated)" if result["tokenCountsEstimated"] else ""
    print(f"tokens in/out  : {result['inputTokens']} / {result['outputTokens']}{est}")
    print(f"model time     : {result['responseTimeMs']} ms{' (cached result)' if result['cached'] else ''}")
    print(f"grounded       : {result['grounding']['ok']} {result['grounding']['unknownElementIds'] or ''}")

    if args.save:
        cfg = load_model_config()
        record = {
            "loggedAt": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "inspectionFile": args.inspection, "sourceUrl": snapshot["sourceUrl"],
            "goal": args.goal, "elementIds": args.ids, "clarificationAnswer": args.answer,
            "setup": {"provider": result["provider"], "model": result["model"],
                      "temperature": cfg.get("temperature"), "maxOutputTokens": cfg.get("max_output_tokens"),
                      "host": f"{platform.system()} {platform.release()}, Python {platform.python_version()}"},
            **result,
        }
        path = Path(args.save)
        log = json.loads(path.read_text(encoding="utf-8")) if path.exists() else []
        log.append(record)
        path.write_text(json.dumps(log, indent=2, ensure_ascii=False), encoding="utf-8")
        print(f"\nSaved to {path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
