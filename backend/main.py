from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from backend.routers import posts, epics, phrases, research
from backend.routers.posts import test_connection, post_helper
from backend.services.research_agent_service import start_worker
from backend.database import post_collection
from backend.schemas.post import PaginatedPosts
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
    # Start the Research Article Agent background worker (drains the agent_runs queue)
    start_worker()

# In backend/main.py

# --- FULL IMPLEMENTATION DIRECTLY ON APP ---
@app.get("/api/v1/posts/with-text", response_model=PaginatedPosts)
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
app.include_router(posts.router, prefix="/api/v1/posts", tags=["Posts"])
app.include_router(posts.text_posts_router, prefix="/api/v1/posts", tags=["Posts Text"])
app.include_router(epics.router, prefix="/api/v1/epics", tags=["Epics"])
app.include_router(research.router, prefix="/api/v1/research", tags=["Research Agent"])
app.include_router(phrases.router)

# Health check endpoint for Render
@app.get("/health")
async def health_check():
    return {"status": "healthy", "service": "sharirasutra"}