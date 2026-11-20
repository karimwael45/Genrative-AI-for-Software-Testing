"""Separate headed-browser inspector."""
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlsplit

import yaml
from playwright.sync_api import Error as PlaywrightError
from playwright.sync_api import sync_playwright

from runner.locators import css_escape, rank_candidates


ROOT = Path(__file__).resolve().parents[1]

TYPE_ROLES = {
    "button": ("button", "role"),
    "link": ("a", "role"),
    "input": ("input", "textbox"),
    "textarea": ("textarea", "textbox"),
    "select": ("select", "combobox"),
    "form": ("form", "form"),
}


def _allowed_origins() -> list[str]:
    settings = yaml.safe_load((ROOT / "config/settings.yaml").read_text())
    return settings.get("allowed_origins", [])


def _check_origin(url: str) -> None:
    parts = urlsplit(url)
    if parts.scheme not in {"http", "https"} or not parts.netloc:
        raise ValueError("A valid HTTP(S) demo URL is required")
    origin = f"{parts.scheme}://{parts.netloc}"
    if origin not in _allowed_origins():
        raise ValueError("URL origin is not in the configured allowlist")


def _count_locator(page, candidate: dict) -> int:
    strategy = candidate["strategy"]
    try:
        if strategy == "role":
            locator = page.get_by_role(candidate["role"], name=candidate.get("name"))
        elif strategy == "label":
            locator = page.get_by_label(candidate["value"], exact=False)
        elif strategy == "testid":
            locator = page.get_by_test_id(candidate["value"])
        elif strategy == "id":
            locator = page.locator(f"#{css_escape(candidate['value'])}")
        else:
            locator = page.locator(candidate["value"])
        return locator.count()
    except (PlaywrightError, ValueError, TypeError):
        return 0


def _attributes(element: dict) -> dict:
    keys = (
        "id", "name", "type", "role", "href", "placeholder", "aria-label",
        "title", "data-testid", "required", "disabled", "checked",
        "readonly", "multiple",
    )
    attributes = {}
    for key in keys:
        value = element.get(key)
        if value is not None:
            if key in {"required", "disabled", "checked", "readonly", "multiple"}:
                attributes[key] = bool(value)
            else:
                attributes[key] = value
    return attributes


def inspect_page(url: str, scope: dict | None = None) -> dict:
    """Open headed Chromium and return a grounded, structured inspection."""
    _check_origin(url)
    scope = scope or {}
    requested_types = scope.get("types") or list(TYPE_ROLES)
    selector = scope.get("selector")
    started = time.perf_counter()

    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=False)
        try:
            context = browser.new_context()
            page = context.new_page()
            page.goto(url, wait_until="domcontentloaded", timeout=20_000)
            page.wait_for_timeout(250)

            final_url = page.url
            _check_origin(final_url)

            tags = []
            for element_type in requested_types:
                element_type = str(element_type).lower()
                if element_type in TYPE_ROLES:
                    tags.append(TYPE_ROLES[element_type][0])
            if not tags:
                tags = [item[0] for item in TYPE_ROLES.values()]

            base = page.locator(selector) if selector else page.locator("body")
            if base.count() == 0:
                raise ValueError(f"Scope selector matched no elements: {selector}")

            css_selectors = ", ".join(dict.fromkeys(tags))
            candidates = base.locator(css_selectors)
            elements = []

            for index in range(candidates.count()):
                locator = candidates.nth(index)
                if locator.count() == 0:
                    continue
                try:
                    if not locator.is_visible():
                        continue
                except PlaywrightError:
                    continue

                observed = locator.evaluate(
                    """element => {
                        const labelFromFor = element.id
                            ? document.querySelector(`label[for="${CSS.escape(element.id)}"]`)
                            : null;
                        const wrappingLabel = element.closest('label');
                        let label = element.getAttribute('aria-label')
                            || (labelFromFor && labelFromFor.innerText.trim())
                            || (wrappingLabel && wrappingLabel.innerText.trim())
                            || element.getAttribute('placeholder')
                            || element.getAttribute('title')
                            || element.getAttribute('alt')
                            || element.innerText?.trim()
                            || element.getAttribute('value')
                            || element.getAttribute('name')
                            || '';
                        const directText = element.tagName.toLowerCase() === 'input'
                            || element.tagName.toLowerCase() === 'textarea'
                            || element.tagName.toLowerCase() === 'select'
                            ? ''
                            : (element.innerText || '').trim();
                        const attr = name => element.getAttribute(name);
                        const booleanAttr = name => element.hasAttribute(name);
                        return {
                            tag: element.tagName.toLowerCase(), label,
                            id: attr('id'), name: attr('name'), type: attr('type'),
                            role: attr('role'), href: attr('href'),
                            placeholder: attr('placeholder'), 'aria-label': attr('aria-label'),
                            title: attr('title'), 'data-testid': attr('data-testid'),
                            required: booleanAttr('required'), disabled: booleanAttr('disabled'),
                            checked: booleanAttr('checked'), readonly: booleanAttr('readonly'),
                            multiple: booleanAttr('multiple'), text: directText
                        };
                    }"""
                )
                if not isinstance(observed, dict):
                    continue

                tag = observed["tag"]
                if tag == "input":
                    input_type = (observed.get("type") or "text").lower()
                    role = "checkbox" if input_type == "checkbox" else "radio" if input_type == "radio" else "textbox"
                elif tag == "button":
                    role = "button"
                elif tag == "a":
                    role = "link"
                elif tag == "textarea":
                    role = "textbox"
                elif tag == "select":
                    role = "combobox"
                else:
                    role = observed.get("role") or "form"

                label = observed.get("label") or observed.get("name") or tag
                label_source = "aria-label" if observed.get("aria-label") else \
                    "label[for]" if observed.get("id") and page.locator(f'label[for="{css_escape(observed["id"])}"]').count() else \
                    "wrapped-label" if tag in {"input", "select", "textarea", "button"} and locator.evaluate("e => !!e.closest('label')") else \
                    "placeholder" if observed.get("placeholder") else \
                    "title" if observed.get("title") else \
                    "text" if observed.get("text") else "tag"

                locator_candidates = []
                if observed.get("data-testid"):
                    value = observed["data-testid"]
                    candidate = {"strategy": "testid", "value": value, "matchCount": 0, "unique": False}
                    match_count = _count_locator(page, candidate)
                    candidate.update(matchCount=match_count, unique=match_count == 1)
                    locator_candidates.append(candidate)
                if observed.get("id"):
                    value = observed["id"]
                    candidate = {"strategy": "id", "value": value, "matchCount": 0, "unique": False}
                    match_count = _count_locator(page, candidate)
                    candidate.update(matchCount=match_count, unique=match_count == 1)
                    locator_candidates.append(candidate)
                if label and role != "form":
                    candidate = {
                        "strategy": "role", "value": role, "name": label,
                        "role": role, "matchCount": 0, "unique": False,
                    }
                    match_count = _count_locator(page, candidate)
                    candidate.update(matchCount=match_count, unique=match_count == 1)
                    candidate.pop("role", None)
                    locator_candidates.append(candidate)
                if label and observed.get("aria-label") is None:
                    candidate = {"strategy": "label", "value": label, "matchCount": 0, "unique": False}
                    match_count = _count_locator(page, candidate)
                    candidate.update(matchCount=match_count, unique=match_count == 1)
                    locator_candidates.append(candidate)
                if observed.get("name"):
                    css = f"{tag}[name=\"{css_escape(observed['name'])}\"]"
                    candidate = {"strategy": "css", "value": css, "matchCount": 0, "unique": False}
                    match_count = _count_locator(page, candidate)
                    candidate.update(matchCount=match_count, unique=match_count == 1)
                    locator_candidates.append(candidate)
                else:
                    css = tag
                    if observed.get("type"):
                        css += f"[type=\"{css_escape(observed['type'])}\"]"
                    candidate = {"strategy": "css", "value": css, "matchCount": 0, "unique": False}
                    match_count = _count_locator(page, candidate)
                    candidate.update(matchCount=match_count, unique=match_count == 1)
                    locator_candidates.append(candidate)

                locator_candidates = rank_candidates(locator_candidates)
                elements.append({
                    "id": f"el-{len(elements) + 1}",
                    "role": role,
                    "tag": tag,
                    "label": label,
                    "labelSource": label_source,
                    "text": observed.get("text") or "",
                    "attributes": _attributes(observed),
                    "candidateLocators": locator_candidates,
                })

            elapsed_ms = round((time.perf_counter() - started) * 1000, 1)
            return {
                "inspectionId": str(uuid.uuid4()),
                "sourceUrl": final_url,
                "inspectedAt": datetime.now(timezone.utc).isoformat(),
                "scope": {
                    "selector": selector,
                    "types": requested_types,
                },
                "inspectionTimeMs": elapsed_ms,
                "elements": elements,
            }
        finally:
            context = locals().get("context")
            if context:
                context.close()
            browser.close()


