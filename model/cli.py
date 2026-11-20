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


def read_json(path) -> object:
    """Read JSON written by any tool. 'utf-8-sig' accepts the BOM that Windows
    PowerShell adds when output is redirected with '>'."""
    return json.loads(Path(path).read_text(encoding="utf-8-sig"))


def append_log(path, record: dict) -> None:
    """Append one call record to a JSON list file (created if missing)."""
    path = Path(path)
    log = read_json(path) if path.exists() else []
    if not isinstance(log, list):
        raise ValueError(f"{path} is not a JSON list of call records. Move or delete it, "
                         "then run again so a fresh log is created.")
    log.append(record)
    path.write_text(json.dumps(log, indent=2, ensure_ascii=False), encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--inspection", default=str(ROOT / "contracts/sample-inspection.json"))
    parser.add_argument("--goal", required=True)
    parser.add_argument("--ids", nargs="+", required=True, help="selected element IDs")
    parser.add_argument("--answer", help="answer to a previous clarification question")
    parser.add_argument("--save", help="append the call record to this JSON file")
    parser.add_argument("--provider", choices=["groq", "gemini", "ollama", "mock"],
                        help="use only this provider, with no fallbacks (to test one provider)")
    parser.add_argument("--allow-mock", action="store_true",
                        help="allow --save with a mock reply (never use for evidence)")
    args = parser.parse_args()

    snapshot = read_json(args.inspection)
    try:
        elements = resolve_elements(snapshot, args.ids)
        result = suggest(args.goal, snapshot["sourceUrl"], elements, args.answer, provider=args.provider)
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
    if result.get("fallbackUsed"):
        print(f"FALLBACK USED  : {result['fallbackReason']}")

    if args.save:
        if result["provider"] == "mock" and not args.allow_mock:
            print("Error: not saving a MOCK reply as a usage record (it is not real model evidence). "
                  "Fix the provider (key / Ollama running) or pass --allow-mock for a scratch file.",
                  file=sys.stderr)
            return 1
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
        try:
            append_log(args.save, record)
        except ValueError as exc:
            print(f"Error: {exc}", file=sys.stderr)
            return 1
        print(f"\nSaved to {args.save}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
