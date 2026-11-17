"""Locator ranking helpers for the future Playwright inspector."""
def rank_candidates(candidates: list[dict]) -> list[dict]:
    priorities = {"testid": 0, "label": 1, "role": 2, "id": 3, "css": 4}
    return sorted(candidates, key=lambda item: (
        item.get("matchCount") != 1,
        priorities.get(item.get("strategy"), 99),
    ))
# The inspector must measure matchCount against the live page.
