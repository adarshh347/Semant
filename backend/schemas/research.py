"""
Schemas for the Research Article Agent and Sankalpa (will-detection engine).

The agent runs as a background job: it picks a topic from the gallery + what
Sankalpa has inferred about the reader's will, gathers gallery images, and
composes a research article with images interleaved into the prose. Reader
feedback (explicit + implicit) flows back into Sankalpa, which steers the next
article.
"""

from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field


# --- Agent run requests ---

class RunAgentRequest(BaseModel):
    """Kick off a background research-article run."""
    topic: Optional[str] = None          # optional explicit topic override
    source_tags: Optional[List[str]] = None  # optional explicit tag scope
    angle: Optional[str] = None          # optional steer ("focus on the bodily")


# --- Feedback signals ---

class Signal(BaseModel):
    """
    A single feedback event. Deliberately flexible so the front end can stream
    many kinds of signal without a schema change.

    type:
      "rating"   -> payload {value: 1..5}
      "section"  -> payload {section_id, reaction: "resonates"|"not_me"|"go_deeper"}
      "mcq"      -> payload {question, choice}
      "image"    -> payload {image_id, kept: bool}
      "dwell"    -> payload {section_id, ms}
      "scroll"   -> payload {depth: 0..100}
      "linger"   -> payload {image_id, ms}
    """
    type: str
    payload: Dict[str, Any] = Field(default_factory=dict)


class FeedbackRequest(BaseModel):
    """A batch of signals the reader produced on an article."""
    signals: List[Signal] = Field(default_factory=list)
