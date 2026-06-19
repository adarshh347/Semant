"""
Vision Service for Groq Vision API Integration
Handles image analysis and text generation using Groq's vision models.
Follows Single Responsibility Principle - only handles vision-related tasks.
"""

import json
import re
from typing import Optional, Dict, Any
from groq import Groq
from backend.config import settings


class VisionService:
    """
    Service for interacting with Groq Vision API.
    Provides image analysis and text generation capabilities.
    """
    
    def __init__(self):
        """Initialize Groq client with API key from settings."""
        if settings.GROQ_API_KEY:
            self.client = Groq(api_key=settings.GROQ_API_KEY)
            # Using llama-3.2-90b-vision-preview for better quality
            # Can switch to llama-3.2-11b-vision-preview for faster responses
            self.vision_model = "meta-llama/llama-4-scout-17b-16e-instruct"
        else:
            self.client = None
            self.vision_model = None
    
    def _is_available(self) -> bool:
        """Check if vision service is available."""
        return self.client is not None
    
    async def analyze_image(self, image_url: str, prompt: str) -> Optional[str]:
        """
        Analyze an image using Groq Vision API.
        
        Args:
            image_url: URL of the image to analyze
            prompt: The prompt/question to ask about the image
            
        Returns:
            Analysis result as string, or None if service unavailable
        """
        if not self._is_available():
            print("⚠️ Vision service not available - GROQ_API_KEY not set")
            return None
        
        try:
            completion = self.client.chat.completions.create(
                model=self.vision_model,
                messages=[
                    {
                        "role": "user",
                        "content": [
                            {
                                "type": "text",
                                "text": prompt
                            },
                            {
                                "type": "image_url",
                                "image_url": {
                                    "url": image_url
                                }
                            }
                        ]
                    }
                ],
                temperature=0.7,
                max_tokens=1024,
                top_p=1,
                stream=False
            )
            
            return completion.choices[0].message.content
            
        except Exception as e:
            print(f"❌ Error in vision analysis: {e}")
            return None
    
    async def auto_recommend_text(
        self, 
        image_url: str, 
        existing_text: Optional[str] = None
    ) -> Optional[str]:
        """
        Generate auto-recommended text based on image analysis and existing text.
        
        This mode analyzes the image and creates text that complements
        existing textual information.
        
        Args:
            image_url: URL of the image to analyze
            existing_text: Existing text content for context
            
        Returns:
            Generated text recommendation, or None if service unavailable
        """
        if not self._is_available():
            return None
        
        # Build context-aware prompt
        if existing_text:
            prompt = f"""Analyze this image and generate a descriptive, narrative text that complements the following existing context:

Existing Context:
{existing_text}

Requirements:
1. Describe what you see in the image in vivid, literary detail
2. Connect your description to the existing context naturally
3. Write in a flowing, narrative style (2-4 paragraphs)
4. Focus on visual elements, atmosphere, and mood
5. Make it feel like part of a larger story or essay

Generate the text:"""
        else:
            prompt = """Analyze this image and generate a rich, descriptive narrative text about what you see.

Requirements:
1. Describe the image in vivid, literary detail
2. Write in a flowing, narrative style (2-4 paragraphs)
3. Focus on visual elements, atmosphere, mood, and implied story
4. Make it engaging and evocative
5. Use sensory language and literary devices

Generate the text:"""
        
        return await self.analyze_image(image_url, prompt)
    
    async def prompt_enhanced_text(
        self, 
        image_url: str, 
        user_prompt: str
    ) -> Optional[str]:
        """
        Generate text based on image analysis enhanced by user prompt.
        
        This mode uses the user's specific prompt/direction combined
        with image analysis.
        
        Args:
            image_url: URL of the image to analyze
            user_prompt: User's specific prompt or direction
            
        Returns:
            Generated text based on prompt and image, or None if service unavailable
        """
        if not self._is_available():
            return None
        
        enhanced_prompt = f"""Analyze this image and generate text based on the following user direction:

User Direction:
{user_prompt}

Requirements:
1. Carefully observe all details in the image
2. Follow the user's direction/prompt closely
3. Write in a flowing, narrative style (2-4 paragraphs)
4. Incorporate visual details from the image naturally
5. Make the text vivid and engaging

Generate the text:"""
        
        return await self.analyze_image(image_url, enhanced_prompt)
    
    async def suggest_story_connection(
        self, 
        image_url: str, 
        story_block_content: str
    ) -> Optional[Dict[str, Any]]:
        """
        Analyze how well an image fits with a story block.
        
        Provides a coherence score and explanation for image-text pairing.
        
        Args:
            image_url: URL of the image
            story_block_content: Content of the story block
            
        Returns:
            Dictionary with coherence_score (0-1) and explanation
        """
        if not self._is_available():
            return {"coherence_score": 0.5, "explanation": "Vision service unavailable"}
        
        prompt = f"""Analyze this image in relation to the following story text:

Story Text:
{story_block_content}

Evaluate how well the image matches or complements the story text.

Provide your analysis in the following JSON format:
{{
    "coherence_score": <float between 0 and 1>,
    "explanation": "<brief explanation of the match>",
    "visual_elements": ["<key visual element 1>", "<key visual element 2>", ...],
    "thematic_connections": ["<connection 1>", "<connection 2>", ...]
}}

Respond with ONLY the JSON, no additional text."""
        
        try:
            result = await self.analyze_image(image_url, prompt)
            if result:
                # Try to parse JSON from the response
                # Sometimes LLMs add extra text, so we extract JSON
                json_match = re.search(r'\{.*\}', result, re.DOTALL)
                if json_match:
                    return json.loads(json_match.group())
                else:
                    # Fallback if JSON parsing fails
                    return {
                        "coherence_score": 0.5,
                        "explanation": result[:200],
                        "visual_elements": [],
                        "thematic_connections": []
                    }
            return None
        except Exception as e:
            print(f"❌ Error in story connection analysis: {e}")
            return {
                "coherence_score": 0.5,
                "explanation": f"Analysis error: {str(e)}",
                "visual_elements": [],
                "thematic_connections": []
            }
    
    async def generate_image_subtitle(self, image_url: str) -> str:
        """
        Generate a short, evocative subtitle for an image.
        Used for epic story blocks to create captions/subtitles.
        
        Args:
            image_url: URL of the image
            
        Returns:
            Short subtitle (1-2 sentences)
        """
        if not self._is_available():
            return ""
        
        prompt = """Analyze this image and create a SHORT, evocative subtitle or caption.

Requirements:
1. Keep it to 1-2 sentences maximum
2. Make it poetic and atmospheric
3. Capture the essence or mood of the image
4. Use vivid, sensory language
5. It should work as a subtitle for a story chapter

Generate ONLY the subtitle, no additional text or explanation:"""
        
        try:
            result = await self.analyze_image(image_url, prompt)
            if result:
                # Clean up the result (remove quotes, extra whitespace)
                subtitle = result.strip().strip('"').strip("'")
                return subtitle
            return ""
        except Exception as e:
            print(f"❌ Error generating subtitle: {e}")
            return ""


    async def brainstorm_image(self, image_url: str, answers: Optional[list] = None) -> Optional[Dict[str, Any]]:
        """
        "Aletheia" interpretive DIALOGUE: unconceal an image through three lenses
        (Phenomenological, Semiotic, Atmospheric), and pose clickable multiple-choice
        questions that hand the looking back to the viewer. The viewer's answers
        (passed in `answers`) reshape the next reading — a back-and-forth that
        deepens the interpretation each round.

        Args:
            image_url: image URL or base64 data URL of the image to interpret
            answers: optional list of prior {"question": str, "choice": str} the
                     viewer has already chosen, to sharpen this round.

        Returns:
            Normalized dict {lenses:[{name,reading,intensity}],
            questions:[{prompt,options}], concealed, uncertainty}, or None.
        """
        if not self._is_available():
            print("⚠️ Vision service not available - GROQ_API_KEY not set")
            return None

        # Fold any prior answers into the prompt so the reading responds to them.
        feedback = ""
        if answers:
            lines = "\n".join(
                f'- Asked: "{a.get("question", "")}" → They chose: "{a.get("choice", "")}"'
                for a in answers if a
            )
            if lines:
                feedback = (
                    "\n\nThe viewer has been in dialogue with you and chose:\n"
                    f"{lines}\n\nLet these choices genuinely reshape the lenses (shift "
                    "intensities, change emphasis), then ask FEWER, deeper questions. "
                    "If the image now feels settled, return an empty \"questions\" list."
                )

        try:
            completion = self.client.chat.completions.create(
                model=self.vision_model,
                messages=[
                    {
                        "role": "user",
                        "content": [
                            {"type": "text", "text": ALETHEIA_PROMPT + feedback + "\n\nUnconceal this image. Return only the JSON."},
                            {"type": "image_url", "image_url": {"url": image_url}},
                        ],
                    }
                ],
                temperature=0.65,
                max_tokens=1100,
                top_p=1,
                stream=False,
            )
            raw = completion.choices[0].message.content
            return self._parse_aletheia(raw)
        except Exception as e:
            print(f"❌ Error in brainstorm analysis: {e}")
            return None

    def _parse_aletheia(self, raw: Optional[str]) -> Optional[Dict[str, Any]]:
        """Extract and normalize the Aletheia JSON from a model response."""
        if not raw:
            return None
        try:
            # Strip code fences and pull out the first JSON object
            cleaned = re.sub(r"^```(?:json)?|```$", "", raw.strip(), flags=re.MULTILINE).strip()
            match = re.search(r"\{.*\}", cleaned, re.DOTALL)
            if not match:
                return None
            data = json.loads(match.group())

            # Normalize lenses: list of {name, reading, intensity:int 0-100}
            lenses = []
            for lens in (data.get("lenses") or [])[:5]:
                try:
                    intensity = int(round(float(lens.get("intensity", 0))))
                except (TypeError, ValueError):
                    intensity = 0
                lenses.append({
                    "name": str(lens.get("name", "")).strip(),
                    "reading": str(lens.get("reading", "")).strip(),
                    "intensity": max(0, min(100, intensity)),
                })

            # Normalize questions: list of {prompt, options:[str]} (1-4 options each)
            questions = []
            for q in (data.get("questions") or [])[:3]:
                opts = [str(o).strip() for o in (q.get("options") or []) if str(o).strip()][:4]
                prompt = str(q.get("prompt", "")).strip()
                if prompt and opts:
                    questions.append({"prompt": prompt, "options": opts})

            return {
                "lenses": lenses,
                "questions": questions,
                "concealed": str(data.get("concealed", "")).strip(),
                "uncertainty": str(data.get("uncertainty", "")).strip(),
            }
        except Exception as e:
            print(f"❌ Error parsing Aletheia JSON: {e}")
            return None


# --- Aletheia interpretive prompt (image brainstorm dialogue) ---
ALETHEIA_PROMPT = """You are Aletheia, an interpretive companion inside Semant. A person scrolling a
feed has paused on an image. Your task is NOT to caption it (what is depicted)
but to help them UNCONCEAL it — to make perceptible how the image appears and
works on them, and what it withholds. (Heidegger: truth as unconcealment.)

This is a DIALOGUE. You offer a reading, then pose a few multiple-choice questions
that hand the looking back to the viewer. Their clicks sharpen your next reading,
so the image is unconcealed together, round by round.

Rules:
- Look closely at the ACTUAL image. Never invent details you cannot see.
- Plain, sensuous, specific language. No art-jargon padding. Keep it short.
- Each lens is a distinct voice and may disagree with the others.
- Disclose your uncertainty rather than bluffing (the "earth that resists").
- Questions are perceptual/interpretive, never a factual quiz. Each offers a real
  FORK in how to see — 2 to 4 short options (a few words each). There is no
  "correct" option; each opens a different reading.

Produce:
1. LENSES (3):
   - Phenomenological — how it meets a lived body: weight, texture, temperature,
     movement, where the eye is pulled.
   - Semiotic — its denotation vs connotation; what it culturally signifies.
   - Atmospheric — the mood/Stimmung it radiates, the emotional temperature.
   Each lens: 1–2 sentences + an "intensity" 0–100 (how strongly this lens
   speaks for this image) for the UI bars.
2. QUESTIONS (1–3): each a short prompt + 2–4 short options, inviting the viewer
   to choose how to see (e.g. "What pulls your eye first?", "What is this image's
   weather?"). These drive the back-and-forth.
3. CONCEALED — one line on what lies outside the frame / what the image withholds.

Return strict JSON only:
{
  "lenses": [{"name": "...", "reading": "...", "intensity": 0}],
  "questions": [{"prompt": "...", "options": ["...", "..."]}],
  "concealed": "...",
  "uncertainty": "..."
}"""


# Singleton instance
vision_service = VisionService()
