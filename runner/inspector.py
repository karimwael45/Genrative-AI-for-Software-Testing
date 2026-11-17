"""Separate browser worker. Exchange one JSON request and response via stdin/stdout."""
import json
import sys


def inspect_page(url: str) -> dict:
    """Return an inspection matching contracts/sample-inspection.json."""
    # TODO (Person 1): Enforce the configured demo origin, including
    # navigations and redirects. Run headed Chromium, read interactive DOM
    # elements, and build locator candidates from observed evidence.
    # Measure browser inspection time and close the browser on errors too.
    raise NotImplementedError("Implement headed Playwright inspection")


