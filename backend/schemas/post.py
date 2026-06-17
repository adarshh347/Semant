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