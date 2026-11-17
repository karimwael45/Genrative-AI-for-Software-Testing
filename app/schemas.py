"""Shared API contract models."""
from pydantic import BaseModel, Field

class InspectRequest(BaseModel):
    url: str = Field(min_length=1)

class AssistRequest(BaseModel):
    inspectionId: str
    elementIds: list[str] = Field(min_length=1)
    goal: str = Field(min_length=1)

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

class ModelResponse(BaseModel):
    message: str
    model: str
    inputTokens: int | None = None
    outputTokens: int | None = None
    responseTimeMs: float
    tokenCountsEstimated: bool = False
