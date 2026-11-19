"""Grounding checks: inputs come from saved observations, outputs cite only them."""
from __future__ import annotations

import json
import re


def resolve_elements(snapshot: dict, element_ids: list[str]) -> list[dict]:
    """Resolve selected IDs exclusively against the saved inspection."""
    known = {element["id"]: element for element in snapshot["elements"]}
    if not element_ids or any(key not in known for key in element_ids):
        raise ValueError("Select element IDs from the saved inspection")
    return [known[key] for key in dict.fromkeys(element_ids)]


def parse_model_json(text: str) -> dict:
    """Extract the JSON object from a model reply (tolerates code fences / extra prose)."""
    cleaned = text.strip()
    if cleaned.startswith("```"):
        cleaned = re.sub(r"^```[a-zA-Z]*\s*|\s*```$", "", cleaned)
    try:
        data = json.loads(cleaned)
    except json.JSONDecodeError:
        start, end = cleaned.find("{"), cleaned.rfind("}")
        if start == -1 or end <= start:
            raise ValueError("Model reply contained no JSON object")
        try:
            data = json.loads(cleaned[start:end + 1])
        except json.JSONDecodeError as exc:
            raise ValueError("Model reply contained invalid JSON") from exc
    if not isinstance(data, dict):
        raise ValueError("Model reply JSON is not an object")
    return data


def normalize_reply(data: dict) -> dict:
    """Coerce the parsed reply into the expected shape with safe types."""
    def as_str(value):
        return value.strip() if isinstance(value, str) and value.strip() else None

    def as_ids(value):
        return [str(v) for v in value] if isinstance(value, list) else []

    observations = []
    for item in data.get("observations") or []:
        if isinstance(item, dict) and item.get("elementId") is not None:
            observations.append({"elementId": str(item["elementId"]),
                                 "note": as_str(item.get("note")) or ""})
    action = data.get("nextAction") if isinstance(data.get("nextAction"), dict) else {}
    clarification = as_str(data.get("clarification"))
    if clarification and clarification.lower() in {"null", "none", "n/a"}:
        clarification = None
    return {
        "summary": as_str(data.get("summary")) or "",
        "observations": observations,
        "nextAction": {"description": as_str(action.get("description")) or "",
                       "elementIds": as_ids(action.get("elementIds"))},
        "clarification": clarification,
        "assumptions": [a.strip() for a in data.get("assumptions") or []
                        if isinstance(a, str) and a.strip()],
    }


def _id_pattern(allowed_ids: list[str]) -> re.Pattern | None:
    """Build a pattern for ID-like tokens from the shape of known IDs (e.g. 'el-12')."""
    prefixes = {m.group(1) for i in allowed_ids if (m := re.match(r"^([A-Za-z]+[-_])\d+$", i))}
    if not prefixes:
        return None
    alternation = "|".join(re.escape(p) for p in sorted(prefixes))
    return re.compile(rf"\b(?:{alternation})\d+\b")


def check_grounding(reply: dict, allowed_ids: list[str]) -> dict:
    """Flag any element ID the model cites that was not in the selected evidence.

    Checks the structured ID fields and also ID-like tokens inside free text.
    Unknown IDs are reported (never silently dropped) so the tester can see them.
    """
    allowed = set(allowed_ids)
    cited = [o["elementId"] for o in reply["observations"]] + reply["nextAction"]["elementIds"]
    pattern = _id_pattern(allowed_ids)
    if pattern:
        text = " ".join([reply["summary"], reply["nextAction"]["description"],
                         reply["clarification"] or "", *reply["assumptions"],
                         *(o["note"] for o in reply["observations"])])
        cited += pattern.findall(text)
    unknown = sorted({c for c in cited if c not in allowed})
    referenced = sorted({c for c in cited if c in allowed})
    return {"ok": not unknown, "unknownElementIds": unknown, "referencedElementIds": referenced}
