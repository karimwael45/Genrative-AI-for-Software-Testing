"""Provider adapter. Send the tester goal and selected evidence only."""


def suggest(goal: str, source_url: str, elements: list[dict]) -> dict:
    """Return message, model, inputTokens, outputTokens and responseTimeMs."""
    # TODO (Person 3): Configure a local model or free-tier endpoint.
    # Ask for a concise observation, next step, or clarification. Treat
    # page text as data, cite observed IDs, and preserve unknown expectations.
    # Time only the model call. Return provider token counts when available.
    raise NotImplementedError("Implement the model adapter")
