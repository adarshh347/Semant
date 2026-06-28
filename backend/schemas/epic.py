from pydantic import BaseModel, Field
from typing import Optional, List
from datetime import datetime
import uuid


class StoryBlock(BaseModel):
    """
    Represents a single coherent block/paragraph of the epic story.
    """
    block_id: str = Field(default_factory=lambda: f"story_block_{uuid.uuid4()}")
    sequence_order: int
    content: str
    associated_image_id: Optional[str] = None
    image_url: Optional[str] = None
    coherence_score: Optional[float] = None
    created_at: datetime = Field(default_factory=datetime.utcnow)


class EpicMetadata(BaseModel):
    """
    Metadata about the epic generation process.
    """
    total_blocks: int = 0
    total_images: int = 0
    generation_prompt: Optional[str] = None
    user_commentary: Optional[str] = None


class Epic(BaseModel):
    """
    Main schema for Epic/Novel story.
    Represents a complete multi-block story with associated images.
    """
    id: str
    title: str
    description: Optional[str] = None
    created_at: datetime
    updated_at: datetime
    status: str = "draft"  # "draft", "completed", "archived"
    generation_mode: str  # "full_story" or "story_completion"
    source_tags: List[str] = []
    story_blocks: List[StoryBlock] = []
    metadata: EpicMetadata = Field(default_factory=EpicMetadata)


class EpicCreate(BaseModel):
    """
    Schema for creating a new epic.
    """
    title: str
    description: Optional[str] = None
    generation_mode: str = "full_story"
    source_tags: List[str] = []
    generation_prompt: Optional[str] = None
    user_commentary: Optional[str] = None


class EpicUpdate(BaseModel):
    """
    Schema for updating an existing epic.
    """
    title: Optional[str] = None
    description: Optional[str] = None
    status: Optional[str] = None
    story_blocks: Optional[List[StoryBlock]] = None


class FullStoryGenerationRequest(BaseModel):
    """
    Request schema for generating a full story from scratch.
    """
    title: str
    description: Optional[str] = None
    source_tags: Optional[List[str]] = None  # Use posts with these tags
    use_all_text: bool = True  # If True, use all text_blocks; if False, use only selected tags
    generation_prompt: str
    user_commentary: Optional[str] = None


class StoryCompletionRequest(BaseModel):
    """
    Request schema for completing an existing story.
    """
    epic_id: str
    continuation_prompt: str
    user_commentary: Optional[str] = None


class ImageAssociationRequest(BaseModel):
    """
    Request schema for associating an image with a story block.
    """
    epic_id: str
    block_id: str
    image_post_id: str


class VisionSuggestionRequest(BaseModel):
    """
    Request schema for getting vision-based text suggestions.
    """
    image_url: str
    suggestion_type: str  # "auto_recommend" or "prompt_enhance"
    existing_text: Optional[str] = None  # For auto_recommend
    user_prompt: Optional[str] = None  # For prompt_enhance


class AddVisionTextToPostRequest(BaseModel):
    """
    Request schema for adding vision-generated text to a post.
    """
    post_id: str
    text_content: str
    text_type: str = "paragraph"  # Type of text block


class PaginatedEpics(BaseModel):
    """
    Paginated response for epic listings.
    """
    epics: List[Epic]
    total_pages: int
    current_page: int
    total_count: int