# BaseModel is the foundational Pydantic class that all pydantic schemas inherit from
from pydantic import BaseModel, Field
from typing import Optional,Dict, List
from datetime import datetime
import uuid

# a schema for bounding box coordinates
class BoundingBox(BaseModel):
    x: int
    y: int
    width: int
    height: int

class TextBlock(BaseModel):
    id: str = Field(default_factory=lambda: f"block_{uuid.uuid4()}")
    type: str  # e.g., 'h1', 'paragraph', 'quote'
    content: str
    color: Optional[str] = None

class EpicRef(BaseModel):
    epic_id: str
    title: str

class Highlight(BaseModel):
    id: str = Field(default_factory=lambda: f"hl_{uuid.uuid4()}")
    text: str  # The underlined/highlighted text
    block_id: Optional[str] = None  # Which text block it came from
    created_at: Optional[datetime] = None

# main schema for post object, used for response
class Post(BaseModel):
    id: str
    photo_url: str
    photo_public_id: str
    updated_at: Optional[datetime] = None
    text_blocks:List[TextBlock] = []
    bounding_box_tags : Optional[dict[str, BoundingBox]] = None
    general_tags : Optional[List[str]] = None
    associated_epics: Optional[List[EpicRef]] = []
    highlights: Optional[List[Highlight]] = []  # NEW: Underlined text collection
    source_url: Optional[str] = None  # page the image was saved from
    instagram_handle: Optional[str] = None  # account the image came from (Darpan link)
    source_account: Optional[dict] = None  # light snapshot of that account at save time
    local_context: Optional[dict] = None  # microscopic per-image context (Aletheia + commentary)
    region_annotations: Optional[List[dict]] = None  # detected parts + user prioritisation/notes

class PostUpdate(BaseModel):
    text_blocks: Optional[List[TextBlock]] = None
    bounding_box_tags: Optional[dict[str, BoundingBox]] = None
    general_tags: Optional[List[str]] = None
    highlights: Optional[List[Highlight]] = None  # NEW: Can update highlights

class PaginatedPosts(BaseModel):
    posts: List[Post]
    total_pages: int
    current_page: int

class StoryGenerationRequest(BaseModel):
    tag: str
    plot_suggestion: str
    user_commentary: str

class AddTagRequest(BaseModel):
    tag: str

class AddTagAndStoryRequest(BaseModel):
    tag: str
    story: str

class StoryFlowRequest(BaseModel):
    story: str
    detail_level: Optional[str] = "med"  # "small", "med", "big"

class PostSuggestionRequest(BaseModel):
    text_blocks: List[TextBlock]
    suggestion_type: str  # "short_prose" or "story"
    user_commentary: Optional[str] = ""

class ChatMessage(BaseModel):
    role: str  # "user" or "assistant"
    content: str

class VisionChatRequest(BaseModel):
    image_url: str
    text_blocks: Optional[List[TextBlock]] = []
    user_message: str
    conversation_history: Optional[List[ChatMessage]] = []

class VisionRewriteRequest(BaseModel):
    image_url: str
    block_content: str
    rewrite_instruction: Optional[str] = ""

class NodeExpansionRequest(BaseModel):
    node_text: str
    image_url: str
    story_context: str

class UrlUploadRequest(BaseModel):
    image_url: str
    source_url: Optional[str] = None  # page the image was saved from
    general_tags: Optional[List[str]] = []
    instagram_handle: Optional[str] = None  # account the image came from (if on Instagram)
    source_account: Optional[dict] = None  # light snapshot {display_name, avatar_url}

class RegionAnnotationsRequest(BaseModel):
    """The curator's prioritised regions + per-part 'how it affects me' notes."""
    regions: List[dict] = []
    feed_to_persona: bool = True


class RegionDetectRequest(BaseModel):
    """Steer the Sūkṣma (fine-anatomy) pipeline. `mode` picks the subdivision
    vocabulary; `lens` is the curator's free-text intention ('focus on the fabric
    folds', 'the hands'); `coarse_only` skips the semantic decomposition stage."""
    mode: Optional[str] = "general"        # general | garment | body | texture | material | composition
    lens: Optional[str] = ""               # free-text intention prompt (always optional)
    coarse_only: Optional[bool] = False    # if True, return only the YOLO anchors (fast)


class LocalContextRequest(BaseModel):
    """Microscopic context the curator attaches to one image: their own
    unconcealment commentary, optionally alongside an Aletheia reading. Feeds the
    specific image and (optionally) rolls up into that account's persona."""
    commentary: Optional[str] = ""
    aletheia: Optional[dict] = None  # the Aletheia reading {lenses, concealed, uncertainty}
    feed_to_persona: bool = True


class BrainstormAnswer(BaseModel):
    question: str
    choice: str

class BrainstormRequest(BaseModel):
    image_url: str
    source_url: Optional[str] = None
    answers: Optional[List[BrainstormAnswer]] = None  # prior viewer choices, to refine the reading