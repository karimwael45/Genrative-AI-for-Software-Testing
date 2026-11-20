"""Locator ranking and CSS escaping helpers for the Playwright inspector."""


def css_escape(value: str) -> str:
    """Escape a value for use in a simple CSS identifier or attribute selector."""
    return str(value).replace("\\", "\\\\").replace('"', '\\"')


def rank_candidates(candidates: list[dict]) -> list[dict]:
    # Prefer semantic locators, then stable attributes, then CSS fallbacks.
    priorities = {"role": 0, "label": 1, "testid": 2, "id": 3, "css": 4}
    return sorted(candidates, key=lambda item: (
        item.get("matchCount") != 1,
        priorities.get(item.get("strategy"), 99),
    ))
