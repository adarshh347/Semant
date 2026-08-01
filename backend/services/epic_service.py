"""
Epic Service - Business logic for Epic/Novel management.
Handles epic CRUD operations, story generation, and image associations.
Follows Single Responsibility Principle.
"""

import uuid
from datetime import datetime, timezone
from typing import List, Dict, Any, Optional
from bson.objectid import ObjectId

from backend.database import epic_collection, post_collection
from backend.schemas.epic import Epic, StoryBlock, EpicMetadata
from backend.services.llm_service import llm_service
from backend.services.story_block_service import story_block_service
from backend.services.vision_service import vision_service


class EpicService:
    """
    Service for managing epics/novels.
    Handles business logic for epic creation, updates, and associations.
    """
    
    def __init__(self):
        """Initialize the epic service."""
        pass
    
    @staticmethod
    def epic_helper(epic_doc: dict) -> dict:
        """
        Convert MongoDB epic document to API-friendly format.
        Similar to post_helper for posts.
        
        Args:
            epic_doc: Raw MongoDB document
            
        Returns:
            Formatted epic dictionary
        """
        return {
            "id": str(epic_doc["_id"]),
            "title": epic_doc.get("title", "Untitled Epic"),
            "description": epic_doc.get("description"),
            "created_at": epic_doc.get("created_at"),
            "updated_at": epic_doc.get("updated_at"),
            "status": epic_doc.get("status", "draft"),
            "generation_mode": epic_doc.get("generation_mode", "full_story"),
            "source_tags": epic_doc.get("source_tags", []),
            "story_blocks": epic_doc.get("story_blocks", []),
            "metadata": epic_doc.get("metadata", {
                "total_blocks": 0,
                "total_images": 0,
                "generation_prompt": None,
                "user_commentary": None
            })
        }
    
    async def create_epic(
        self,
        title: str,
        description: Optional[str] = None,
        generation_mode: str = "full_story",
        source_tags: List[str] = None
    ) -> dict:
        """
        Create a new empty epic.
        
        Args:
            title: Epic title
            description: Optional description
            generation_mode: "full_story" or "story_completion"
            source_tags: Tags used for generation
            
        Returns:
            Created epic document
        """
        now = datetime.now(timezone.utc)
        
        epic_doc = {
            "_id": ObjectId(),
            "title": title,
            "description": description,
            "created_at": now,
            "updated_at": now,
            "status": "draft",
            "generation_mode": generation_mode,
            "source_tags": source_tags or [],
            "story_blocks": [],
            "metadata": {
                "total_blocks": 0,
                "total_images": 0,
                "generation_prompt": None,
                "user_commentary": None
            }
        }
        
        await epic_collection.insert_one(epic_doc)
        return self.epic_helper(epic_doc)
    
    async def get_epic_by_id(self, epic_id: str) -> Optional[dict]:
        """
        Retrieve an epic by ID.
        
        Args:
            epic_id: Epic ID
            
        Returns:
            Epic document or None
        """
        try:
            epic_doc = await epic_collection.find_one({"_id": ObjectId(epic_id)})
            if epic_doc:
                return self.epic_helper(epic_doc)
            return None
        except Exception as e:
            print(f"Error fetching epic {epic_id}: {e}")
            return None
    
    async def update_epic(self, epic_id: str, update_data: dict) -> Optional[dict]:
        """
        Update an epic.
        
        Args:
            epic_id: Epic ID
            update_data: Fields to update
            
        Returns:
            Updated epic or None
        """
        try:
            update_data["updated_at"] = datetime.now(timezone.utc)
            
            result = await epic_collection.update_one(
                {"_id": ObjectId(epic_id)},
                {"$set": update_data}
            )
            
            if result.modified_count > 0:
                return await self.get_epic_by_id(epic_id)
            return None
        except Exception as e:
            print(f"Error updating epic {epic_id}: {e}")
            return None
    
    async def delete_epic(self, epic_id: str) -> bool:
        """
        Delete an epic.
        
        Args:
            epic_id: Epic ID
            
        Returns:
            True if deleted, False otherwise
        """
        try:
            result = await epic_collection.delete_one({"_id": ObjectId(epic_id)})
            return result.deleted_count > 0
        except Exception as e:
            print(f"Error deleting epic {epic_id}: {e}")
            return False
    
    async def list_epics(
        self,
        page: int = 1,
        limit: int = 20,
        status: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        List epics with pagination.
        
        Args:
            page: Page number
            limit: Items per page
            status: Filter by status (optional)
            
        Returns:
            Dictionary with epics, total_pages, current_page, total_count
        """
        query = {}
        if status:
            query["status"] = status
        
        total_count = await epic_collection.count_documents(query)
        
        if total_count == 0:
            return {
                "epics": [],
                "total_pages": 0,
                "current_page": 1,
                "total_count": 0
            }
        
        skip = (page - 1) * limit
        cursor = epic_collection.find(query).sort("updated_at", -1).skip(skip).limit(limit)
        
        epics = []
        async for epic_doc in cursor:
            epics.append(self.epic_helper(epic_doc))
        
        import math
        total_pages = math.ceil(total_count / limit)
        
        return {
            "epics": epics,
            "total_pages": total_pages,
            "current_page": page,
            "total_count": total_count
        }
    
    async def generate_full_story(
        self,
        title: str,
        description: Optional[str],
        source_tags: Optional[List[str]],
        use_all_text: bool,
        generation_prompt: str,
        user_commentary: Optional[str]
    ) -> dict:
        """
        Generate a full epic story from posts.
        
        Args:
            title: Epic title
            description: Epic description
            source_tags: Tags to filter posts
            use_all_text: Use all text_blocks or only from tagged posts
            generation_prompt: Main story direction
            user_commentary: Additional user input
            
        Returns:
            Created epic with generated story blocks
        """
        # Step 1: Aggregate text from posts
        aggregated_text = await self._aggregate_text_from_posts(source_tags, use_all_text)
        
        # Step 2: Generate epic story using LLM
        story_result = llm_service.generate_epic_story(
            aggregated_text=aggregated_text,
            generation_prompt=generation_prompt,
            user_commentary=user_commentary or "",
            source_tags=source_tags
        )
        
        story_text = story_result.get("story", "")
        title_suggestion = story_result.get("title_suggestion", title)
        themes = story_result.get("themes", [])
        
        # Step 3: Segment story into blocks
        blocks_data = await story_block_service.segment_story(story_text)
        
        # Step 4: Create story blocks
        story_blocks = []
        for block_data in blocks_data:
            story_blocks.append({
                "block_id": f"story_block_{uuid.uuid4()}",
                "sequence_order": block_data.get("sequence_order", len(story_blocks) + 1),
                "content": block_data.get("content", ""),
                "associated_image_id": None,
                "image_url": None,
                "coherence_score": block_data.get("coherence_score", 0.7),
                "created_at": datetime.now(timezone.utc)
            })
        
        # Step 5: Create epic
        epic_doc = {
            "_id": ObjectId(),
            "title": title or title_suggestion,
            "description": description,
            "created_at": datetime.now(timezone.utc),
            "updated_at": datetime.now(timezone.utc),
            "status": "draft",
            "generation_mode": "full_story",
            "source_tags": source_tags or [],
            "story_blocks": story_blocks,
            "metadata": {
                "total_blocks": len(story_blocks),
                "total_images": 0,
                "generation_prompt": generation_prompt,
                "user_commentary": user_commentary,
                "themes": themes
            }
        }
        
        await epic_collection.insert_one(epic_doc)
        return self.epic_helper(epic_doc)
    
    async def complete_story(
        self,
        epic_id: str,
        continuation_prompt: str,
        user_commentary: Optional[str]
    ) -> Optional[dict]:
        """
        Continue/complete an existing epic story.
        
        Args:
            epic_id: ID of epic to continue
            continuation_prompt: Direction for continuation
            user_commentary: Additional user input
            
        Returns:
            Updated epic with new blocks
        """
        # Get existing epic
        epic = await self.get_epic_by_id(epic_id)
        if not epic:
            return None
        
        # Aggregate existing story
        existing_story = "\n\n".join([
            block["content"] for block in epic["story_blocks"]
        ])
        
        # Generate continuation
        continuation_result = llm_service.complete_epic_story(
            existing_story=existing_story,
            continuation_prompt=continuation_prompt,
            user_commentary=user_commentary or ""
        )
        
        continuation_text = continuation_result.get("continuation", "")
        
        # Segment continuation into blocks
        new_blocks_data = await story_block_service.segment_story(continuation_text)
        
        # Create new story blocks
        current_max_order = max([b["sequence_order"] for b in epic["story_blocks"]], default=0)
        new_story_blocks = []
        
        for block_data in new_blocks_data:
            new_story_blocks.append({
                "block_id": f"story_block_{uuid.uuid4()}",
                "sequence_order": current_max_order + block_data.get("sequence_order", len(new_story_blocks) + 1),
                "content": block_data.get("content", ""),
                "associated_image_id": None,
                "image_url": None,
                "coherence_score": block_data.get("coherence_score", 0.7),
                "created_at": datetime.now(timezone.utc)
            })
        
        # Update epic
        all_blocks = epic["story_blocks"] + new_story_blocks
        update_data = {
            "story_blocks": all_blocks,
            "metadata.total_blocks": len(all_blocks),
            "updated_at": datetime.now(timezone.utc)
        }
        
        return await self.update_epic(epic_id, update_data)
    
    async def associate_image_with_block(
        self,
        epic_id: str,
        block_id: str,
        image_post_id: str,
        sync_to_post: bool = True
    ) -> Optional[dict]:
        """
        Associate an image with a story block.
        
        Args:
            epic_id: Epic ID
            block_id: Story block ID
            image_post_id: Post ID containing the image
            sync_to_post: Whether to add block content to post's text_blocks
            
        Returns:
            Updated epic
        """
        # Get epic and post
        epic = await self.get_epic_by_id(epic_id)
        if not epic:
            return None
        
        post = await post_collection.find_one({"_id": ObjectId(image_post_id)})
        if not post:
            return None
        
        # Find the block
        block_index = None
        block_content = None
        for i, block in enumerate(epic["story_blocks"]):
            if block["block_id"] == block_id:
                block_index = i
                block_content = block["content"]
                break
        
        if block_index is None:
            return None
        
        # Update block with image association
        epic["story_blocks"][block_index]["associated_image_id"] = image_post_id
        epic["story_blocks"][block_index]["image_url"] = post.get("photo_url")
        
        # Count total images
        total_images = sum(1 for b in epic["story_blocks"] if b.get("associated_image_id"))
        
        # Update epic
        update_data = {
            "story_blocks": epic["story_blocks"],
            "metadata.total_images": total_images,
            "updated_at": datetime.now(timezone.utc)
        }
        
        await epic_collection.update_one(
            {"_id": ObjectId(epic_id)},
            {"$set": update_data}
        )
        
        # Optionally sync to post
        if sync_to_post and block_content:
            await self._sync_block_to_post(image_post_id, block_content, epic_id, epic.get("title", "Untitled Epic"))
        
        return await self.get_epic_by_id(epic_id)
    
    async def suggest_images_for_block(
        self,
        epic_id: str,
        block_id: str,
        count: int = 3
    ) -> List[dict]:
        """
        Suggest random images WITHOUT text_blocks for a story block.
        Returns 3 random posts that have no text content yet.
        
        Args:
            epic_id: Epic ID
            block_id: Block ID
            count: Number of suggestions (default 3)
            
        Returns:
            List of suggested post documents with generated subtitles
        """
        import random
        
        # Get posts with images but NO text_blocks
        query = {
            "photo_url": {"$exists": True},
            "$or": [
                {"text_blocks": {"$exists": False}},
                {"text_blocks": {"$size": 0}}
            ]
        }
        
        cursor = post_collection.find(query)
        all_posts = await cursor.to_list(length=None)
        
        if not all_posts:
            return []
        
        if len(all_posts) <= count:
            selected = all_posts
        else:
            # Random selection
            selected = random.sample(all_posts, count)
        
        # Generate subtitles for each image using Vision AI
        results = []
        for post in selected:
            post_dict = self._post_helper(post)
            
            # Generate subtitle suggestion using Vision AI
            try:
                subtitle = await vision_service.generate_image_subtitle(
                    post.get("photo_url")
                )
                post_dict["suggested_subtitle"] = subtitle
            except Exception as e:
                print(f"Error generating subtitle for post {post.get('_id')}: {e}")
                post_dict["suggested_subtitle"] = ""
            
            results.append(post_dict)
        
        return results
    
    async def _aggregate_text_from_posts(
        self,
        tags: Optional[List[str]],
        use_all: bool
    ) -> str:
        """
        Aggregate text content from posts.
        
        Args:
            tags: Tags to filter by
            use_all: Use all posts or only tagged ones
            
        Returns:
            Aggregated text string
        """
        query = {}
        
        if not use_all and tags:
            query["general_tags"] = {"$in": tags}
        
        # Get posts with text_blocks
        query["text_blocks"] = {"$exists": True, "$not": {"$size": 0}}
        
        cursor = post_collection.find(query).limit(50)  # Limit to avoid overwhelming
        
        texts = []
        async for post in cursor:
            for block in post.get("text_blocks", []):
                content = block.get("content", "").strip()
                if content:
                    texts.append(content)
        
        return "\n\n".join(texts)
    
    async def _sync_block_to_post(self, post_id: str, block_content: str, epic_id: str, epic_title: str):
        """
        Add story block content to post's text_blocks and link epic.
        
        Args:
            post_id: Post ID
            block_content: Content to add
            epic_id: Epic ID
            epic_title: Epic Title
        """
        # PROV-001 Seam 5 — a synced epic block is the epic agent's prose, not the curator's.
        # `block_content` arrives from the epic's story_blocks, which story_block_service
        # segmented out of generated story text. TextBlock defaults `origin` to "human", so
        # leaving it unset made the agent's writing read back as the curator's own.
        text_block = {
            "id": f"block_{uuid.uuid4()}",
            "type": "paragraph",
            "content": block_content,
            "color": None,
            "origin": "sutradhar",
        }
        
        epic_ref = {
            "epic_id": epic_id,
            "title": epic_title
        }
        
        # Check if epic is already associated to avoid duplicates
        post = await post_collection.find_one({"_id": ObjectId(post_id)})
        associated_epics = post.get("associated_epics", [])
        
        # Add if not present
        if not any(e.get("epic_id") == epic_id for e in associated_epics):
            await post_collection.update_one(
                {"_id": ObjectId(post_id)},
                {
                    "$push": {
                        "text_blocks": text_block,
                        "associated_epics": epic_ref
                    },
                    "$set": {"updated_at": datetime.now(timezone.utc)}
                }
            )
        else:
            # Just add text block if epic already linked
            await post_collection.update_one(
                {"_id": ObjectId(post_id)},
                {
                    "$push": {"text_blocks": text_block},
                    "$set": {"updated_at": datetime.now(timezone.utc)}
                }
            )
    
    @staticmethod
    def _post_helper(post_doc: dict) -> dict:
        """Helper to format post documents."""
        return {
            "id": str(post_doc["_id"]),
            "photo_url": post_doc.get("photo_url"),
            "photo_public_id": post_doc.get("photo_public_id"),
            "general_tags": post_doc.get("general_tags", [])
        }


# Singleton instance
epic_service = EpicService()
