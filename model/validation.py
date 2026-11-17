"""Resolve selected IDs exclusively against saved observations."""
def resolve_elements(snapshot: dict, element_ids: list[str]) -> list[dict]:
    known = {element["id"]: element for element in snapshot["elements"]}
    if not element_ids or any(key not in known for key in element_ids):
        raise ValueError("Select element IDs from the saved inspection")
    return [known[key] for key in dict.fromkeys(element_ids)]
# Semantic grounding of free-text model output still requires implementation.
