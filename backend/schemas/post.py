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


class MarkProvenance(BaseModel):
    """The receipt on a produced mark: which run, which plan step, which producer.

    CIRCUIT-002 PROV-001 Seam 2. Seam 1 stamps `step_id` onto every suggestion at the produce
    chokepoint, and the client carries a suggestion's provenance onto the mark it mints. But it
    carried it only through an undeclared `...(fields.provenance || {})` spread, and the server
    stored `visual_marks` as bare `List[dict]` — so nothing anywhere DECLARED that `step_id` is
    part of the record. Undeclared is undefended: any future edit that replaces the spread with an
    explicit pick, or any schema that validates marks, drops it silently. That is precisely how
    `TextBlock.origin` was lost — the frontend stamped it for a whole lane while Pydantic dropped
    it on every save, because the field was not declared here.

    So this type exists to make the four provenance facts first-class and defended, not to
    restrict what a mark may carry.

    `extra="allow"` is LOAD-BEARING, not laxity. A mark's provenance also carries `planner`,
    `prompt_excerpt`, `model`, `matched` and `latency_ms`, and P4/P5/P6 keep adding to it. A
    strict model here would silently delete every undeclared one on the next PATCH — trading the
    hole this closes for a bigger one. `model` in particular is left undeclared deliberately: it
    collides with Pydantic's protected `model_` namespace, and `extra="allow"` carries it safely
    without the rename that would break the wire contract.

    Every field is Optional and defaults to None because a curator's own mark HAS no producer.
    None means "no producer said anything", which is the honest record — never a synthesized id.
    """
    model_config = ConfigDict(extra="allow")

    run_id: Optional[str] = None      # the vision_runs run that produced this
    step_id: Optional[str] = None     # PROV-001 — the plan step, the key M4's resolver joins on
    producer: Optional[str] = None    # one of PRODUCERS, or None for a curator's mark
    adapter: Optional[str] = None     # the concrete transport, e.g. 'sam2'


class Mark(BaseModel):
    """A durable visual_mark. Declares ONLY its provenance; everything else rides `extra`.

    Deliberately minimal. The mark contract (geometry, role, epistemic_status, warnings, …) lives
    in `frontend/src/differential/visualMarks.js` and is validated there by `validateMark`; the
    aim here is not to restate it — a second copy would be one more thing to drift, which is the
    same failure this seam is closing. The aim is that provenance cannot be dropped in transit.
    """
    model_config = ConfigDict(extra="allow")

    provenance: Optional[MarkProvenance] = None


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
    # When `mask_rle` is present it is the AUTHORITATIVE identity; `box`, `polygons` and
    # the legacy `polygon` are DERIVED from it by mask_geometry. Box-only/legacy regions
    # (no mask_rle) keep `box` (+ optional single `polygon`) as their own geometry.
    box: RegionBox                                   # derived bbox when mask_rle present
    polygon: Optional[List[List[float]]] = None      # legacy single ring (largest), normalized
    # ── canonical mask evidence (VISION-BUILD-001 Increment A) ──────────────────
    mask_rle: Optional[Dict] = None                  # COCO uncompressed RLE {"size":[h,w],"counts":[...]}
    polygons: Optional[List[List[List[float]]]] = None  # derived rings (outer + holes), normalized
    geometry_rev: int = 0                            # bumps on every mask-identity (re)derivation
    geometry_provenance: Optional[Dict] = None       # {kind, method, size, ...} lineage
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
    # VISION-C: the persisted multi-label, user-overridable domain profile
    # {mode, proposed{fashion,architecture,painting}, chosen[], user_overridden, reason,
    #  scheduled_passes[], router_version}. See services/domain_profiles.py.
    domain_profile: Optional[dict] = None
    # VISION-D: semantic assertions (VLM interpretation), stored SEPARATELY from geometry
    semantics: Optional[dict] = None
    aletheia_cache: Optional[dict] = None  # cached feed-hook reading, computed once per image (Track C §5)
    # Differential v1 — Grounds (visual evidence) + expression Percepts. Deliberately
    # OUTSIDE region_annotations: detect-regions wholesale-replaces that array, and the
    # region machinery (persona rollup, embeddings, catalog) iterates it.
    grounds: Optional[List[dict]] = None
    percepts: Optional[List[dict]] = None
    # CIRCUIT-001 P2E — durable visual_marks (contract v2 §7.3). Additive, PATCH-persisted
    # beside grounds/percepts; only committed/superseded marks are ever written (the client
    # filters — a suggestion never reaches here). Rides the same exclude_unset PATCH, so a
    # re-dissect that replaces region_annotations can never wipe them.
    # PROV-001 Seam 2 — typed so provenance is DECLARED and cannot be dropped in transit.
    # Mark/MarkProvenance both allow extras, so the rest of the mark contract is untouched.
    visual_marks: Optional[List[Mark]] = None
    # CIRCUIT-001 Q-C — durable visual_layers: the per-producer/role render layers' saved
    # visibility/opacity/order. Additive, PATCH-persisted like visual_marks, so a layer a curator
    # hides stays hidden across reload. Opaque dicts (`{key, visibility, opacity, order}`).
    visual_layers: Optional[List[dict]] = None

class PostUpdate(BaseModel):
    # bounding_box_tags removed (Track A): the manual pixel-rect write path is retired.
    text_blocks: Optional[List[TextBlock]] = None
    general_tags: Optional[List[str]] = None
    highlights: Optional[List[Highlight]] = None  # NEW: Can update highlights
    grounds: Optional[List[dict]] = None   # Differential v1
    percepts: Optional[List[dict]] = None  # Differential v1
    # PROV-001 Seam 2 — typed on the WRITE model too, and that is the half that matters. This is
    # the model the wholesale PATCH validates against (`update_post`), so a bare List[dict] here
    # would leave provenance undefended on exactly the path marks are persisted by.
    visual_marks: Optional[List[Mark]] = None  # CIRCUIT-001 P2E — durable marks
    visual_layers: Optional[List[dict]] = None  # CIRCUIT-001 Q-C — durable render layers
    domain_profile: Optional[dict] = None  # VISION-C domain profile
    semantics: Optional[dict] = None       # VISION-D semantic assertions

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
    # PROV-001 Seam 5 — the caller states authorship, because only the caller knows it.
    # Unlike the vision and epic routes, the text here is whatever the client had in hand: it
    # may be a curator's own paragraph or a generated one, and the server cannot tell them apart
    # from a bare string. Defaulting to "sutradhar" would be the same falsehood as the silent
    # "human" it replaces, merely inverted. So it is explicit, and defaults to `human` — the
    # conservative reading for a route whose payload a person assembled and submitted.
    origin: str = "human"           # human | sutradhar

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