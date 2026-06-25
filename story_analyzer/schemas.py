"""Pydantic contracts for Story Analyzer stages."""

from __future__ import annotations

from enum import Enum
from typing import List

from pydantic import BaseModel, Field, field_validator


class BubbleType(str, Enum):
    speech = "speech"
    thought = "thought"
    sfx = "sfx"
    narration = "narration"


BUBBLE_TYPES = [t.value for t in BubbleType]


class Bubble(BaseModel):
    bubble_id: str
    bbox: List[int] = Field(..., min_length=4, max_length=4)
    raw_text: str = ""
    corrected_text: str
    type: BubbleType = BubbleType.speech
    reading_order: int | None = Field(default=None, ge=1)

    @field_validator("bbox")
    @classmethod
    def bbox_ordered(cls, v: List[int]) -> List[int]:
        x1, y1, x2, y2 = v
        if x2 < x1:
            x1, x2 = x2, x1
        if y2 < y1:
            y1, y2 = y2, y1
        return [int(x1), int(y1), int(x2), int(y2)]


class Panel2a(BaseModel):
    panel_id: str
    image_path: str
    bubbles: List[Bubble] = Field(default_factory=list)


class Stage2aDocument(BaseModel):
    project: str
    panels: List[Panel2a] = Field(default_factory=list)

    def model_dump_json_pretty(self) -> str:
        import json

        return json.dumps(
            self.model_dump(mode="json"),
            ensure_ascii=False,
            indent=2,
        ) + "\n"
