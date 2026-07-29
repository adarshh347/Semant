"""
Schemas for the Manuscript-Oriented Writing Studio (WS-0A · the sacred manuscript).

The writing studio is a second application on the same orchestration kernel as the
vision app. WS-0A stands up only the *canon*: the manuscript, its chapter/scene
hierarchy, immutable version snapshots, and export. No AI touches any of this — the
manuscript is sacred, and everything here is a plain author-owned write.

Storage model (MongoDB):
  - `manuscripts`     one doc per work. Holds metadata + the chapter hierarchy
                      (ordered chapters, each an ordered list of scene ids). The
                      hierarchy lives here so structure is a single atomic source
                      of truth; scenes never disagree about where they sit.
  - `scenes`          one doc per scene. Holds the scene body as `text_blocks`
                      (the same {id,type,content,color,origin} shape the BlockNote
                      editor round-trips) plus title + word_count.
  - `scene_versions`  immutable snapshots of a scene's blocks. A snapshot is never
                      edited or deleted by normal flows; restoring copies a snapshot
                      forward into the live scene, it does not rewrite history.

A `text_block` mirrors the frontend `blockConvert` contract and backend
`schemas/post.py:TextBlock`; `origin` marks provenance ('human' | 'sutradhar' |
'model_suggested') so the propose-never-commit discipline has somewhere to land in
later gates. In WS-0A everything the author writes is `origin: 'human'`.
"""

from typing import List, Optional
from pydantic import BaseModel, Field


# --- The block model (round-trips through the BlockNote converter) ---

class TextBlock(BaseModel):
    """One block of scene prose. `content` is HTML; `origin` carries provenance."""
    id: str
    type: str = "paragraph"            # paragraph | h1 | h2 | h3 | quote
    content: str = ""                  # HTML
    color: Optional[str] = None        # colour wash (author highlight), or None
    origin: str = "human"              # human | sutradhar | model_suggested


# --- Hierarchy ---

class ChapterOutline(BaseModel):
    """A chapter as it lives inside the manuscript doc: id, title, ordered scenes."""
    id: str
    title: str
    scene_ids: List[str] = Field(default_factory=list)


# --- Manuscript-level requests ---

class ManuscriptCreate(BaseModel):
    title: str = "Untitled manuscript"
    synopsis: Optional[str] = None


class ManuscriptUpdate(BaseModel):
    """Patch manuscript metadata. Omitted fields are left untouched."""
    title: Optional[str] = None
    synopsis: Optional[str] = None


# --- Chapter requests ---

class ChapterCreate(BaseModel):
    title: str = "Untitled chapter"


class ChapterUpdate(BaseModel):
    title: Optional[str] = None


# --- Scene requests ---

class SceneCreate(BaseModel):
    """Create a scene inside a chapter. Body starts empty unless seeded."""
    chapter_id: str
    title: str = "Untitled scene"
    blocks: Optional[List[TextBlock]] = None


class SceneUpdate(BaseModel):
    """
    The canonical scene write. Saving `blocks` overwrites the live scene body — this
    is the author committing to canon, the one place the manuscript actually changes.
    """
    title: Optional[str] = None
    blocks: Optional[List[TextBlock]] = None


# --- Structure edits ---

class ReorderRequest(BaseModel):
    """
    Replace the manuscript's whole chapter/scene ordering in one atomic write. The
    client sends the desired outline; the server validates that it references only
    known chapter + scene ids (no scene is created or destroyed by a reorder).
    """
    chapters: List[ChapterOutline]


# --- Versioning ---

class SnapshotRequest(BaseModel):
    """Freeze the scene's current blocks as an immutable version."""
    label: Optional[str] = None
