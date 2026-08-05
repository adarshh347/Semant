from fastapi import FastAPI, Depends
from fastapi.middleware.cors import CORSMiddleware
from backend.routers import posts, epics, phrases, research, personas, anatomy, taste, manuscript, runs, atlas, corpora, writer
from backend.routers import retina
from backend.routers.posts import test_connection, post_helper
from backend.services.research_agent_service import start_worker
from backend.services.region_embedding_service import ensure_indexes
from backend.services.taste_signal_service import ensure_indexes as ensure_taste_indexes
from backend.services.vision_run_service import ensure_indexes as ensure_vision_run_indexes
from backend.database import post_collection
from backend.schemas.post import PaginatedPosts
from backend.security import require_api_key
import math

app = FastAPI(title="visual dictionary")

# for security reasons, browsers block requests between multiple addresses
# CORS(cross origin resource sharing) allows both to get connected
# Note: Using "*" to allow Chrome extension to make requests from any website
origins = [
    "http://localhost:5173",
    "https://sharirasutra.onrender.com",
    "http://localhost:3000",
    "http://localhost:5000",
    "https://sharirasutra-rae3yyibx-huih-huis-projects.vercel.app",
]


app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Allow all origins for Chrome extension
    allow_credentials=False,  # Must be False when using "*"
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["*"],
)


@app.on_event("startup")
async def startup_event():
    await test_connection()
    # Index the taste-graph sidecar (idempotent; Track C retrieval filters on post_id)
    await ensure_indexes()
    # Index the audience signal store (Track F)
    await ensure_taste_indexes()
    # Index the vision-run provenance store (CIRCULATION-SPINE-001 · P1)
    await ensure_vision_run_indexes()
    # Start the Research Article Agent background worker (drains the agent_runs queue)
    start_worker()

# In backend/main.py

# --- FULL IMPLEMENTATION DIRECTLY ON APP ---
@app.get("/api/v1/posts/with-text", response_model=PaginatedPosts, dependencies=[Depends(require_api_key)])
async def get_posts_with_text_main(page: int = 1, limit: int = 50):
    query = {
        "text_blocks": {
            "$exists": True,
            "$not": {"$size": 0}
        }
    }

    total_posts = await post_collection.count_documents(query)
    if total_posts == 0:
        return {"posts": [], "total_pages": 0, "current_page": 1}

    skip = (page - 1) * limit
    posts_cursor = post_collection.find(query).sort("updated_at", -1).skip(skip).limit(limit)

    posts_list = []
    async for post in posts_cursor:
        try:
            helper_result = post_helper(post)
            posts_list.append(helper_result)
        except Exception as e:
            print(f"Error processing post {post.get('_id')} in post_helper: {e}")

    total_pages = math.ceil(total_posts / limit)

    response_data = {
        "posts": posts_list,
        "total_pages": total_pages,
        "current_page": page
    }

    # Keep the detailed logging for now, it's helpful
    # ... (print statements) ...

    return response_data

# Include routers
app.include_router(posts.router, prefix="/api/v1/posts", tags=["Posts"], dependencies=[Depends(require_api_key)])
app.include_router(posts.text_posts_router, prefix="/api/v1/posts", tags=["Posts Text"], dependencies=[Depends(require_api_key)])
app.include_router(epics.router, prefix="/api/v1/epics", tags=["Epics"], dependencies=[Depends(require_api_key)])
app.include_router(research.router, prefix="/api/v1/research", tags=["Research Agent"], dependencies=[Depends(require_api_key)])
app.include_router(personas.router, prefix="/api/v1/personas", tags=["Darpan Personas"], dependencies=[Depends(require_api_key)])
app.include_router(anatomy.router, prefix="/api/v1/anatomy", tags=["Anatomy Catalog"], dependencies=[Depends(require_api_key)])
# Track F. The consumer surface is intentionally NOT behind the curator API key — an
# audience member pausing on an image has no key, and identity is the upsell, not the
# toll (F3). It is gated instead by explicit opt-in, an opaque subject id, and a rate
# limit. The brand tier IS keyed: aggregate taste intelligence is the paid product.
app.include_router(taste.router, prefix="/api/v1/taste", tags=["Taste Signals (audience)"])
app.include_router(taste.brand_router, prefix="/api/v1/taste/brand", tags=["Taste Intelligence (brand)"], dependencies=[Depends(require_api_key)])
app.include_router(phrases.router, dependencies=[Depends(require_api_key)])
# Writing Studio (WS-0A · the sacred manuscript) — a second app on the same kernel.
app.include_router(manuscript.router, prefix="/api/v1/manuscript", tags=["Writing Studio"], dependencies=[Depends(require_api_key)])
# Semant Writer (W1 · the executable document) — the manuscript half of the Chiasmatic
# circulation, wrapping the same kernel. It owns no canon: Accept writes THROUGH the
# manuscript service above, so the sacred manuscript keeps exactly one owner.
app.include_router(writer.router, prefix="/api/v1/writer", tags=["Semant Writer"], dependencies=[Depends(require_api_key)])
# SURFACE-002 — the corpus run surface: (a set of images + a prompt) → the whole loop, its
# production record, and (in argue mode) a drafted article. Suggestions-only, like everything it
# drives: a run never accepts a mark or writes a post.
app.include_router(runs.router, prefix="/api/v1/runs", tags=["Runs"], dependencies=[Depends(require_api_key)])
# ATLAS C1 — the multi-image writing canvas. A thin arrangement document over the existing corpus,
# ledger and Differential: it stores where each image sits and references percepts by id, never
# copying them. Writes nothing to any post.
app.include_router(atlas.router, prefix="/api/v1/atlas", tags=["Atlas"], dependencies=[Depends(require_api_key)])
# L1 — the curated corpus: a named, ordered walk an Atlas can be opened from and reopened later.
app.include_router(corpora.router, prefix="/api/v1/corpora", tags=["Corpora"], dependencies=[Depends(require_api_key)])

# Simulation Engine · Lane 3 — the retina: peripheral vision for movement. A cheap, broad
# "what is roughly near this?" over a LanceDB index derived from `region_embeddings`. Proposal
# only, and there is no write path here to misuse: it returns candidates with similarity
# scores, never relations, and grounding one into a claim is a later organ's job.
app.include_router(retina.router, prefix="/api/v1/retina", tags=["Retina"], dependencies=[Depends(require_api_key)])

# Health check endpoint for Render
@app.get("/health")
async def health_check():
    return {"status": "healthy", "service": "sharirasutra"}