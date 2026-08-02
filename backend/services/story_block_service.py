"""
Story Block Service for AI-powered story segmentation.
Handles breaking down long stories into coherent blocks/paragraphs.
Follows Single Responsibility Principle - only handles story segmentation logic.
"""

import json
import re
from typing import List, Dict, Any
from groq import Groq
from backend.config import settings
from backend.schemas.epic import StoryBlock
from backend.services import role_registry


class StoryBlockService:
    """
    Service for segmenting stories into coherent blocks using AI.
    Uses LLM to intelligently divide stories based on narrative coherence.
    """

    ROLE = "story_segmenter"

    def __init__(self):
        """Initialize Groq client for story analysis."""
        if settings.GROQ_API_KEY:
            self.client = Groq(api_key=settings.GROQ_API_KEY)
        else:
            self.client = None

    @property
    def model(self):
        """ROLES-001 — the capable text-analysis model, from the `story_segmenter` role.
        None with no client, exactly as before: a service that cannot call must not name one."""
        if self.client is None:
            return None
        return role_registry.model_for(self.ROLE)


    def _is_available(self) -> bool:
        """Check if service is available."""
        return self.client is not None
    
    async def segment_story(self, story_text: str) -> List[Dict[str, Any]]:
        """
        Segment a long story into coherent blocks using AI.
        
        The AI analyzes the story for:
        - Narrative coherence
        - Thematic shifts
        - Scene changes
        - Paragraph groupings
        
        Args:
            story_text: The complete story text to segment
            
        Returns:
            List of dictionaries with 'content' and 'coherence_score'
        """
        if not self._is_available():
            print("⚠️ Story block service not available - using fallback segmentation")
            return self._fallback_segmentation(story_text)
        
        try:
            prompt = f"""Analyze the following story and segment it into coherent blocks/sections.

Each block should:
1. Represent a cohesive narrative unit (scene, theme, or idea)
2. Be 2-5 paragraphs long (roughly 150-400 words)
3. Have internal coherence and flow
4. Transition naturally to the next block

Story to segment:
{story_text}

Provide your segmentation in the following JSON format:
{{
    "blocks": [
        {{
            "sequence_order": 1,
            "content": "<the text of block 1>",
            "coherence_score": <float 0-1 indicating internal coherence>,
            "summary": "<one-sentence summary of this block>"
        }},
        {{
            "sequence_order": 2,
            "content": "<the text of block 2>",
            "coherence_score": <float 0-1>,
            "summary": "<one-sentence summary>"
        }}
    ]
}}

Important:
- Preserve ALL the original text - don't omit anything
- coherence_score should reflect how well the block holds together thematically
- Aim for 3-8 blocks depending on story length
- Each block should be substantial enough to pair with an image

Respond with ONLY the JSON, no additional text."""

            completion = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {
                        "role": "system",
                        "content": "You are an expert literary analyst specializing in narrative structure and coherence. You segment stories into meaningful, cohesive blocks."
                    },
                    {
                        "role": "user",
                        "content": prompt
                    }
                ],
                temperature=0.3,  # Lower temperature for more consistent segmentation
                max_tokens=4096,
                top_p=1,
                stream=False
            )
            
            response_text = completion.choices[0].message.content
            
            # Extract JSON from response
            json_match = re.search(r'\{.*\}', response_text, re.DOTALL)
            if json_match:
                result = json.loads(json_match.group())
                return result.get("blocks", [])
            else:
                print("⚠️ Could not parse AI segmentation response, using fallback")
                return self._fallback_segmentation(story_text)
                
        except Exception as e:
            print(f"❌ Error in AI story segmentation: {e}")
            return self._fallback_segmentation(story_text)
    
    def _fallback_segmentation(self, story_text: str) -> List[Dict[str, Any]]:
        """
        Fallback segmentation method using simple paragraph grouping.
        Used when AI service is unavailable.
        
        Args:
            story_text: The story text to segment
            
        Returns:
            List of block dictionaries
        """
        # Split by double newlines (paragraph breaks)
        paragraphs = [p.strip() for p in story_text.split('\n\n') if p.strip()]
        
        if not paragraphs:
            # If no double newlines, split by single newlines
            paragraphs = [p.strip() for p in story_text.split('\n') if p.strip()]
        
        # Group paragraphs into blocks of 2-4 paragraphs each
        blocks = []
        current_block = []
        current_word_count = 0
        target_words_per_block = 250
        
        for para in paragraphs:
            word_count = len(para.split())
            current_block.append(para)
            current_word_count += word_count
            
            # Create a new block if we've reached target size or this is the last paragraph
            if current_word_count >= target_words_per_block or para == paragraphs[-1]:
                if current_block:
                    blocks.append({
                        "sequence_order": len(blocks) + 1,
                        "content": "\n\n".join(current_block),
                        "coherence_score": 0.7,  # Default score for fallback
                        "summary": f"Block {len(blocks) + 1}"
                    })
                    current_block = []
                    current_word_count = 0
        
        # If we have remaining paragraphs, add them as a final block
        if current_block:
            blocks.append({
                "sequence_order": len(blocks) + 1,
                "content": "\n\n".join(current_block),
                "coherence_score": 0.7,
                "summary": f"Block {len(blocks) + 1}"
            })
        
        return blocks
    
    async def analyze_block_coherence(self, block_content: str) -> float:
        """
        Analyze the internal coherence of a single story block.
        
        Args:
            block_content: The text content of the block
            
        Returns:
            Coherence score between 0 and 1
        """
        if not self._is_available():
            return 0.7  # Default score
        
        try:
            prompt = f"""Analyze the following text block for narrative coherence.

Text Block:
{block_content}

Rate the coherence on a scale of 0 to 1, where:
- 1.0 = Perfectly coherent, unified theme/scene, excellent flow
- 0.7-0.9 = Good coherence, minor transitions
- 0.4-0.6 = Moderate coherence, some disjointedness
- 0.0-0.3 = Poor coherence, fragmented or disjointed

Respond with ONLY a single number between 0 and 1."""

            completion = self.client.chat.completions.create(
                model=self.model,
                messages=[{"role": "user", "content": prompt}],
                temperature=0.2,
                max_tokens=10,
                stream=False
            )
            
            response = completion.choices[0].message.content.strip()
            # Extract first number found
            match = re.search(r'0?\.\d+|[01]\.?\d*', response)
            if match:
                score = float(match.group())
                return max(0.0, min(1.0, score))  # Clamp between 0 and 1
            
            return 0.7  # Default if parsing fails
            
        except Exception as e:
            print(f"❌ Error analyzing block coherence: {e}")
            return 0.7


# Singleton instance
story_block_service = StoryBlockService()
