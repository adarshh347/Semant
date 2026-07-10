# BaseModel is the foundational Pydantic class that all pydantic schemas inherit from
from pydantic import BaseModel, Field, ConfigDict
from typing import Optional,Dict, List
from datetime import datetime
import uuid

# a schema for bounding box coordinates
# DEPRECATED (Darshan Track A): pixel bounding boxes are retired in favour of the
# normalized `Region`/`RegionBox` model below. `bounding_box_tags` is kept read-only
# (emits {}) for one release; no new writes. 0 rows in prod — no backfill.
class BoundingBox(BaseModel):
    x: int
    y: int
    width: int
    height: int


# --- Darshan unified region model (Track A) ------------------------------------
# One region model for both auto-detected segments and creator/audience marks.
# `region_annotations` (List[Region]) is the single source of truth; the six
# catalog keys (category, label, prioritised, weight, user_note, material) are
# preserved verbatim so anatomy_catalog_service needs zero query change.
class RegionBox(BaseModel):
    x: float
    y: float
    w: float
    h: float


class Region(BaseModel):
    # Strict/typed, but permissive to unknown keys so Track B/C can evolve producer
    # shapes (new attributes, embeddings) without a schema war.
    model_config = ConfigDict(extra="allow")

    id: str = Field(default_factory=lambda: f"reg_{uuid.uuid4()}")
    # provenance (two-sided): who marked it, and — when auto — which detector.
    actor: str = "auto"                              # auto | creator | audience
    # yolo (COCO) | segformer_clothes (Phase 2a garment segmenter) | fashionpedia
    # (Phase 2b, fine parts + attributes) | sam2 | vision (LLM). Records which model
    # actually produced the region — precedence and dedup depend on telling them apart.
    detector: Optional[str] = None
    # geometry (normalized 0..1, top-left origin) — unifies manual + auto, survives resize.
    box: RegionBox
    polygon: Optional[List[List[float]]] = None      # normalized, seg only
    confidence: Optional[float] = None               # auto only
    # semantics (catalog-critical keys kept verbatim).
    label: str = ""                                  # catalog key
    category: str = "other"                          # catalog key
    material: str = ""                               # catalog key
    description: str = ""
    # fashion graph (Fashionpedia) — additive, null-safe (populated in Track B).
    part: Optional[str] = None
    attributes: List[str] = []
    # taste vector (FashionCLIP) — pointer only; the vector lives out-of-row in the
    # region_embeddings sidecar collection keyed by embedding_id (Track B fills it).
    embedding_id: Optional[str] = None
    # hierarchy.
    depth: int = 0                                   # 0 anchor/whole · 1 fine part
    parent_id: Optional[str] = None                  # replaces the dropped parent_label
    # curator meaning (catalog-critical).
    prioritised: bool = False                        # catalog key
    weight: int = 0                                  # catalog key (summed iff prioritised)
    user_note: str = ""                              # catalog key
    # cross-surface link (optional; wired later by Lane 2 / Track D).
    block_id: Optional[str] = None

# --- Source group (Darshan · feature-source-groups Phase 1) ------------------------
# The thread that ties sibling images together. A reel is a *sequence* of frames; a
# carousel (Phase 2) a *set* of slides. Ungrouped, "Split → Save" turns a reel into
# orphan Posts with no memory of which frames are neighbours or in what order — which
# is exactly the context the reading and the taste graph need. `t_ms` is a richer
# proximity axis than the index alone: two frames 200ms apart are near-duplicates.
class SourceGroup(BaseModel):
    # permissive to unknown keys so Phase 2/3 producers (carousel, video) can add
    # fields without a schema war — same posture as Region.
    model_config = ConfigDict(extra="allow")

    group_id: Optional[str] = None          # shared uuid across all siblings; null for a lone single
    group_type: str = "single"              # reel | carousel | video | post | single
    sequence_index: Optional[int] = None    # position within the group (capture/slide order); null for single
    sequence_total: Optional[int] = None    # total in the group, if known
    t_ms: Optional[int] = None              # video-frame timestamp (ms into the source video)


class TextBlock(BaseModel):
    id: str = Field(default_factory=lambda: f"block_{uuid.uuid4()}")
    type: str  # e.g., 'h1', 'paragraph', 'quote'
    content: str
    color: Optional[str] = None
    # Provenance: who wrote it. The frontend has stamped this since the slash-command
    # lane, but the field was missing here — so Pydantic dropped it on every save and
    # a sutradhar block came back from the server indistinguishable from a human one.
    origin: str = "human"           # human | sutradhar

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
    instagram_handles: Optional[List[str]] = None  # ALL authors (collab posts); first = primary
    source_account: Optional[dict] = None  # light snapshot of that account at save time
    local_context: Optional[dict] = None  # microscopic per-image context (Aletheia + commentary)
    region_annotations: Optional[List[Region]] = None  # unified regions: auto segments + curator/audience marks
    domain: Optional[dict] = None  # FashionCLIP domain router first-cut {label, score, is_fashion} (Track B/C)
    aletheia_cache: Optional[dict] = None  # cached feed-hook reading, computed once per image (Track C §5)
    source_group: Optional[SourceGroup] = None  # sibling thread: reel frames / carousel slides (Phase 1)

class PostUpdate(BaseModel):
    # bounding_box_tags removed (Track A): the manual pixel-rect write path is retired.
    text_blocks: Optional[List[TextBlock]] = None
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
    instagram_handles: Optional[List[str]] = None  # all authors on a collab post
    source_account: Optional[dict] = None  # light snapshot {display_name, avatar_url}
    source_group: Optional[SourceGroup] = None  # sibling thread stamped by the extension at split time

class RegionAnnotationsRequest(BaseModel):
    """The curator's prioritised regions + per-part 'how it affects me' notes.
    Validated against the unified Region model (also the manual-mark save target)."""
    regions: List[Region] = []
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


class AletheiaReadRequest(BaseModel):
    """Two readings, one engine (Track C §5). `deep` is the creator's reading — every
    fired lens with its evidence, region links, tension and 1–3 forks. `hook` is the
    audience's: one distilled lens and one perceptual fork, for the pause in the scroll.
    Hook readings are cached per image, so the same image is read once for all viewers."""
    depth: Optional[str] = "deep"           # deep | hook
    lens: Optional[str] = ""                # free-text intention; can pin a lens
    answers: Optional[List[BrainstormAnswer]] = None  # prior forks chosen, to refine
    refresh: Optional[bool] = False         # bypass the hook cache