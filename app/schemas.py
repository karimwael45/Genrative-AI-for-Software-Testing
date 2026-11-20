"""Shared API contract models.

Field names are camelCase (final team naming). Unknown fields sent by the
runner are dropped on validation, so new fields must be added here first.
"""
from pydantic import BaseModel, Field, field_validator, model_validator

class Scope(BaseModel):
    # Optional inspection refinement: a CSS region and/or element types.
    selector: str | None = None
    types: list[str] = []

class InspectRequest(BaseModel):
    url: str = Field(min_length=1)
    scope: Scope | None = None

class AssistRequest(BaseModel):
    inspectionId: str
    elementIds: list[str] = Field(min_length=1)
    goal: str = Field(min_length=1)
    # Optional tester reply to the model's previous clarification question.
    clarificationAnswer: str | None = None

class Locator(BaseModel):
    strategy: str
    value: str
    name: str | None = None
    matchCount: int | None = Field(default=None, ge=0)
    # True when the locator matches exactly one element on the live page.
    unique: bool | None = None

    @model_validator(mode="after")
    def derive_unique(self):
        if self.unique is None and self.matchCount is not None:
            self.unique = self.matchCount == 1
        return self

class Element(BaseModel):
    id: str
    role: str
    label: str
    attributes: dict
    candidateLocators: list[Locator]
    # Optional observed details (sent by the runner when available).
    tag: str | None = None
    labelSource: str | None = None
    text: str | None = None

class Inspection(BaseModel):
    inspectionId: str | None = None
    sourceUrl: str
    inspectedAt: str | None = None
    scope: Scope | None = None
    inspectionTimeMs: float | None = None
    elements: list[Element]

    @field_validator("elements")
    @classmethod
    def unique_element_ids(cls, elements):
        ids = [element.id for element in elements]
        duplicates = sorted({i for i in ids if ids.count(i) > 1})
        if duplicates:
            raise ValueError(f"Duplicate element IDs: {', '.join(duplicates)}")
        return elements

class NextAction(BaseModel):
    description: str = ""
    elementIds: list[str] = []

class Observation(BaseModel):
    elementId: str
    note: str = ""

class Grounding(BaseModel):
    ok: bool
    unknownElementIds: list[str] = []
    referencedElementIds: list[str] = []

class ModelResponse(BaseModel):
    # Original fields (the UI renders these).
    message: str
    model: str
    inputTokens: int | None = None
    outputTokens: int | None = None
    responseTimeMs: float
    tokenCountsEstimated: bool = False
    # Optional structured fields added by the model integration (Person 3).
    provider: str | None = None
    cached: bool = False
    summary: str | None = None
    observations: list[Observation] = []
    nextAction: NextAction | None = None
    clarification: str | None = None
    assumptions: list[str] = []
    grounding: Grounding | None = None
    outputValid: bool = True
    # True when the main provider failed and a fallback (e.g. ollama, mock) answered.
    fallbackUsed: bool = False
    fallbackReason: str | None = None
    logId: int | None = None
