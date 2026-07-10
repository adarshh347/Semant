"""
Epic Router - API endpoints for Epic/Novel management.
Provides REST API for epic creation, story generation, and image associations.
"""

from fastapi import APIRouter, HTTPException
from typing import Optional

from backend.schemas.epic import (
    Epic,
    EpicCreate,
    EpicUpdate,
    FullStoryGenerationRequest,
    StoryCompletionRequest,
    ImageAssociationRequest,
    VisionSuggestionRequest,
    AddVisionTextToPostRequest,
    PaginatedEpics
)
from backend.services.epic_service import epic_service
from backend.services.vision_service import vision_service
from backend.services import anuranana_service
from backend.database import post_collection
from backend.schemas.post import TextBlock
from bson.objectid import ObjectId
from datetime import datetime, timezone
import uuid


router = APIRouter()


# ==================== EPIC CRUD ENDPOINTS ====================

@router.post("/", response_model=Epic, status_code=201)
async def create_epic(epic_data: EpicCreate):
    """
    Create a new empty epic.
    """
    try:
        epic = await epic_service.create_epic(
            title=epic_data.title,
            description=epic_data.description,
            generation_mode=epic_data.generation_mode,
            source_tags=epic_data.source_tags
        )
        return epic
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error creating epic: {str(e)}")


@router.get("/", response_model=PaginatedEpics)
async def list_epics(
    page: int = 1,
    limit: int = 20,
    status: Optional[str] = None
):
    """
    List all epics with pagination.
    Optionally filter by status.
    """
    try:
        result = await epic_service.list_epics(page=page, limit=limit, status=status)
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error listing epics: {str(e)}")


@router.get("/{epic_id}", response_model=Epic)
async def get_epic(epic_id: str):
    """
    Get a specific epic by ID.
    """
    epic = await epic_service.get_epic_by_id(epic_id)
    if not epic:
        raise HTTPException(status_code=404, detail="Epic not found")
    return epic


@router.put("/{epic_id}", response_model=Epic)
async def update_epic(epic_id: str, epic_data: EpicUpdate):
    """
    Update an epic.
    """
    update_dict = epic_data.dict(exclude_unset=True)
    
    if not update_dict:
        raise HTTPException(status_code=400, detail="No update data provided")
    
    epic = await epic_service.update_epic(epic_id, update_dict)
    if not epic:
        raise HTTPException(status_code=404, detail="Epic not found or update failed")
    
    return epic


@router.delete("/{epic_id}", status_code=204)
async def delete_epic(epic_id: str):
    """
    Delete an epic.
    """
    success = await epic_service.delete_epic(epic_id)
    if not success:
        raise HTTPException(status_code=404, detail="Epic not found")
    return None


# ==================== STORY GENERATION ENDPOINTS ====================

@router.post("/generate-full", response_model=Epic, status_code=201)
async def generate_full_story(request: FullStoryGenerationRequest):
    """
    Generate a full epic story from posts.
    
    This endpoint:
    1. Aggregates text from posts (filtered by tags if provided)
    2. Generates a long-form story using LLM
    3. Segments the story into coherent blocks
    4. Creates and returns the epic
    """
    try:
        epic = await epic_service.generate_full_story(
            title=request.title,
            description=request.description,
            source_tags=request.source_tags,
            use_all_text=request.use_all_text,
            generation_prompt=request.generation_prompt,
            user_commentary=request.user_commentary
        )
        return epic
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error generating story: {str(e)}")


@router.post("/complete-story", response_model=Epic)
async def complete_story(request: StoryCompletionRequest):
    """
    Continue/complete an existing epic story.
    
    This endpoint:
    1. Retrieves the existing epic
    2. Generates a continuation using LLM
    3. Segments the continuation into blocks
    4. Appends to the epic and returns updated version
    """
    epic = await epic_service.complete_story(
        epic_id=request.epic_id,
        continuation_prompt=request.continuation_prompt,
        user_commentary=request.user_commentary
    )
    
    if not epic:
        raise HTTPException(status_code=404, detail="Epic not found")
    
    return epic


@router.post("/{epic_id}/segment-blocks", response_model=Epic)
async def re_segment_blocks(epic_id: str):
    """
    Re-segment an epic's story blocks using AI.
    Useful if you want to reorganize the blocks.
    """
    # Get epic
    epic = await epic_service.get_epic_by_id(epic_id)
    if not epic:
        raise HTTPException(status_code=404, detail="Epic not found")
    
    # Aggregate all block content
    full_story = "\n\n".join([block["content"] for block in epic["story_blocks"]])
    
    # Re-segment
    from backend.services.story_block_service import story_block_service
    new_blocks_data = await story_block_service.segment_story(full_story)
    
    # Create new blocks
    new_story_blocks = []
    for block_data in new_blocks_data:
        new_story_blocks.append({
            "block_id": f"story_block_{uuid.uuid4()}",
            "sequence_order": block_data.get("sequence_order", len(new_story_blocks) + 1),
            "content": block_data.get("content", ""),
            "associated_image_id": None,
            "image_url": None,
            "coherence_score": block_data.get("coherence_score", 0.7),
            "created_at": datetime.now(timezone.utc)
        })
    
    # Update epic
    updated_epic = await epic_service.update_epic(epic_id, {
        "story_blocks": new_story_blocks,
        "metadata.total_blocks": len(new_story_blocks),
        "metadata.total_images": 0  # Reset image associations
    })
    
    return updated_epic


# ==================== IMAGE ASSOCIATION ENDPOINTS ====================

@router.get("/{epic_id}/suggest-images/{block_id}")
async def suggest_images_for_block(epic_id: str, block_id: str, count: int = 3):
    """
    Get random image suggestions for a story block.
    Returns 3 random posts with images by default.
    """
    suggestions = await epic_service.suggest_images_for_block(epic_id, block_id, count)
    return {"suggestions": suggestions}


@router.post("/{epic_id}/associate-image", response_model=Epic)
async def associate_image(epic_id: str, request: ImageAssociationRequest):
    """
    Associate an image with a story block.
    
    This creates a bidirectional link:
    - Epic stores the image reference
    - Optionally adds block content to the post's text_blocks
    """
    epic = await epic_service.associate_image_with_block(
        epic_id=epic_id,
        block_id=request.block_id,
        image_post_id=request.image_post_id,
        sync_to_post=True  # Always sync by default
    )
    
    if not epic:
        raise HTTPException(status_code=404, detail="Epic or image not found")
    
    return epic


@router.post("/{epic_id}/randomize-images/{block_id}")
async def randomize_image_suggestions(epic_id: str, block_id: str):
    """
    Get a new set of random image suggestions.
    Useful for the "randomize" button in the UI.
    """
    suggestions = await epic_service.suggest_images_for_block(epic_id, block_id, count=3)
    return {"suggestions": suggestions}


# ==================== VISION AI ENDPOINTS ====================

@router.post("/vision/auto-recommend")
async def vision_auto_recommend(request: VisionSuggestionRequest):
    """
    Generate auto-recommended text based on image analysis.
    
    Uses vision AI to analyze the image and generate text that
    complements existing textual context, grounded in the curator's reading of
    this image and their accrued taste (Anuraṇana, Track C).
    """
    if request.suggestion_type != "auto_recommend":
        raise HTTPException(status_code=400, detail="Use suggestion_type='auto_recommend'")

    context_pack = await anuranana_service.grounding_for_image(request.image_url)
    result = await vision_service.auto_recommend_text(
        image_url=request.image_url,
        existing_text=request.existing_text,
        context_pack=context_pack,
    )
    
    if result is None:
        raise HTTPException(status_code=503, detail="Vision service unavailable")
    
    return {"suggestion": result}


@router.post("/vision/prompt-enhance")
async def vision_prompt_enhance(request: VisionSuggestionRequest):
    """
    Generate text based on image + user prompt.
    
    Uses vision AI to analyze the image and generate text
    following the user's specific prompt/direction, grounded in the curator's
    reading and taste history (Anuraṇana, Track C).
    """
    if request.suggestion_type != "prompt_enhance":
        raise HTTPException(status_code=400, detail="Use suggestion_type='prompt_enhance'")

    if not request.user_prompt:
        raise HTTPException(status_code=400, detail="user_prompt is required for prompt_enhance")

    # The ask steers retrieval — "write about the sleeve" should pull sleeve-like
    # correspondences out of the taste history, not the image's loudest part.
    context_pack = await anuranana_service.grounding_for_image(
        request.image_url, ask=request.user_prompt,
    )
    result = await vision_service.prompt_enhanced_text(
        image_url=request.image_url,
        user_prompt=request.user_prompt,
        context_pack=context_pack,
    )
    
    if result is None:
        raise HTTPException(status_code=503, detail="Vision service unavailable")
    
    return {"suggestion": result}


@router.post("/vision/add-to-post")
async def add_vision_text_to_post(request: AddVisionTextToPostRequest):
    """
    Add vision-generated text as a text_block to a post.
    
    This allows users to save vision-generated suggestions
    directly to the post.
    """
    try:
        # Create text block
        text_block = {
            "id": f"block_{uuid.uuid4()}",
            "type": request.text_type,
            "content": request.text_content,
            "color": None
        }
        
        # Update post
        result = await post_collection.update_one(
            {"_id": ObjectId(request.post_id)},
            {
                "$push": {"text_blocks": text_block},
                "$set": {"updated_at": datetime.now(timezone.utc)}
            }
        )
        
        if result.modified_count == 0:
            raise HTTPException(status_code=404, detail="Post not found")
        
        return {"success": True, "message": "Text added to post"}
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error adding text to post: {str(e)}")


# ==================== UTILITY ENDPOINTS ====================

@router.get("/{epic_id}/stats")
async def get_epic_stats(epic_id: str):
    """
    Get statistics about an epic.
    """
    epic = await epic_service.get_epic_by_id(epic_id)
    if not epic:
        raise HTTPException(status_code=404, detail="Epic not found")
    
    # Calculate stats
    total_words = sum(
        len(block["content"].split())
        for block in epic["story_blocks"]
    )
    
    blocks_with_images = sum(
        1 for block in epic["story_blocks"]
        if block.get("associated_image_id")
    )
    
    avg_coherence = sum(
        block.get("coherence_score", 0)
        for block in epic["story_blocks"]
    ) / len(epic["story_blocks"]) if epic["story_blocks"] else 0
    
    return {
        "epic_id": epic_id,
        "title": epic["title"],
        "total_blocks": len(epic["story_blocks"]),
        "total_words": total_words,
        "blocks_with_images": blocks_with_images,
        "blocks_without_images": len(epic["story_blocks"]) - blocks_with_images,
        "average_coherence_score": round(avg_coherence, 2),
        "status": epic["status"],
        "created_at": epic["created_at"],
        "updated_at": epic["updated_at"]
    }
