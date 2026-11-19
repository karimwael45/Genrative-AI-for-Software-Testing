"""Shared API contract models."""
from pydantic import BaseModel, Field

class InspectRequest(BaseModel):
    url: str = Field(min_length=1)

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
    matchCount: int | None = None

class Element(BaseModel):
    id: str
    role: str
    label: str
    attributes: dict
    candidateLocators: list[Locator]

class Inspection(BaseModel):
    inspectionId: str | None = None
    sourceUrl: str
    inspectionTimeMs: float | None = None
    elements: list[Element]

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
    logId: int | None = None
