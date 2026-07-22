import json
from groq import Groq
from backend.config import settings

# --- Anuraṇana grounding (Darshan Track C §4) --------------------------------------
# The writer used to see the image and the blocks and nothing else, so it wrote
# competent, detached captions. `ground_prompt` puts the reading, the parts that moved
# the curator, their nearest past correspondences, and their voice in front of the ask.
GROUNDING_PREAMBLE = """GROUND YOUR WRITING IN THIS PERSON'S SEEING.
Below is how this image was unconcealed, which of its parts moved this person and in
their own words, how they have felt about parts like these before, and how they write.
Treat it as evidence and as voice: write from what they noticed, not from a generic
description of the image. Never quote these notes back verbatim, and never mention this
briefing — let it show only in what you attend to and how you sound."""


def ground_prompt(prompt: str, context_pack: str = "") -> str:
    """Prepend the context pack to a prompt. An empty pack returns the prompt untouched,
    so every writing path degrades to exactly its pre-Track-C behavior. The pack goes at
    the front and the caller's ask stays at the tail — the two positions an LLM actually
    attends to."""
    if not context_pack:
        return prompt
    return f"{GROUNDING_PREAMBLE}\n\n{context_pack}\n\n---\n\n{prompt}"


class EditorLLMService:
    def __init__(self):
        # Initialize Groq client with API key from settings
        if settings.GROQ_API_KEY:
            self.client = Groq(api_key=settings.GROQ_API_KEY)
        else:
            self.client = None
            print("Warning: GROQ_API_KEY not found in settings. Editor LLM features will be disabled.")
            
        # Literary refinement model (high quality text generation)
        self.literary_model = "openai/gpt-oss-120b"
        # Vision model (image understanding). Groq retired llama-4-maverick (404); qwen3.6-27b
        # is the vision-capable replacement on the current catalogue.
        self.vision_model = "qwen/qwen3.6-27b"

    def _literary_refine(self, raw_text: str, context: str = "", style_hint: str = "evocative literary prose") -> str:
        """
        Refines raw text (typically from vision model) into rich, literary prose.
        This is the second stage of the two-stage pipeline.
        
        Args:
            raw_text: The raw text to refine (e.g., from Maverick vision output)
            context: Additional context (story blocks, user direction, etc.)
            style_hint: The style to aim for (default: evocative literary prose)
            
        Returns:
            Refined, literary text
        """
        if not self.client or not raw_text:
            return raw_text
        
        prompt = f"""You are a master literary craftsperson. Transform the following raw text into {style_hint}.

RAW TEXT (from image analysis):
{raw_text}

ADDITIONAL CONTEXT:
{context if context else "No additional context."}

REQUIREMENTS:
1. Preserve the core meaning and visual observations
2. Transform it into rich, evocative prose with:
   - Sensory imagery (sight, sound, touch, smell, taste)
   - Literary devices (metaphor, simile, personification)
   - Rhythmic sentence variation
   - Emotional resonance
3. Make it feel like a passage from a literary novel, NOT a technical description
4. Keep the length similar but make every word count
5. DO NOT add explanatory meta-text like "Here's the refined version..."

Write ONLY the refined prose, nothing else:"""

        try:
            chat_completion = self.client.chat.completions.create(
                messages=[
                    {
                        "role": "system",
                        "content": "You are a literary artist. You transform plain descriptions into evocative prose. Output only the refined text with no preamble."
                    },
                    {
                        "role": "user",
                        "content": prompt,
                    }
                ],
                model=self.literary_model,
                max_tokens=2000,
                temperature=0.85,  # Higher creativity for literary output
            )
            return chat_completion.choices[0].message.content.strip()
        except Exception as e:
            print(f"Error in literary refinement: {e}")
            return raw_text  # Fallback to raw text on error

    def generate_post_suggestion(self, text_blocks: list, suggestion_type: str, user_commentary: str = "") -> dict:
        """
        Generates suggestions (short prose or story) based on existing text blocks.
        suggestion_type: "short_prose" or "story"
        """
        if not self.client:
            return {"suggestion": "LLM service is not configured (missing GROQ_API_KEY)."}

        # Extract content from text blocks
        content_text = "\n\n".join([block.get("content", "") for block in text_blocks if block.get("content")])
        
        if not content_text.strip():
            return {"suggestion": "No text content available to generate suggestions."}

        if suggestion_type == "short_prose":
            task_instruction = "Write a short, elegant prose piece (2-3 paragraphs) that expands or refines the existing content. Focus on vivid imagery and concise storytelling."
        else:  # story
            task_instruction = "Write a longer, engaging story (4-6 paragraphs) that builds upon the existing content. Include character development, narrative arc, and compelling details."

        prompt = f"""
        You are a creative writer. Based on the following existing text blocks, generate new content.

        EXISTING TEXT BLOCKS:
        {content_text[:5000]}

        USER COMMENTARY/INSTRUCTIONS:
        {user_commentary if user_commentary else "No specific instructions provided."}

        TASK:
        {task_instruction}
        The new content should complement and enhance the existing text, not simply repeat it.

        OUTPUT FORMAT:
        Return ONLY a valid JSON object with the following structure:
        {{
            "suggestion": "Your generated content here..."
        }}
        Do not include any markdown formatting (like ```json) or extra text outside the JSON object.
        """

        try:
            chat_completion = self.client.chat.completions.create(
                messages=[
                    {
                        "role": "system",
                        "content": "You are a helpful assistant that outputs JSON."
                    },
                    {
                        "role": "user",
                        "content": prompt,
                    }
                ],
                model=self.literary_model,
                response_format={"type": "json_object"},
            )

            response_content = chat_completion.choices[0].message.content
            return json.loads(response_content)

        except Exception as e:
            print(f"Error in LLM post suggestion generation: {e}")
            return {"suggestion": "Error generating suggestion."}

    def chat_with_vision(self, image_url: str, text_blocks: list, user_message: str,
                         conversation_history: list = None, context_pack: str = "") -> dict:
        """
        Vision-enabled chat using a TWO-STAGE PIPELINE:
        Stage 1: Maverick analyzes the image and generates raw understanding
        Stage 2: GPT-OSS-120B refines the output into literary prose

        Args:
            image_url: URL of the image to analyze
            text_blocks: Existing text blocks for context
            user_message: User's chat message
            conversation_history: Previous messages in the conversation
            context_pack: Anuraṇana grounding (Track C) — the reading, the parts that
                moved this person, their taste history, their voice. Empty → unchanged.

        Returns:
            Dictionary with 'response' key containing the refined AI response
        """
        if not self.client:
            return {"response": "LLM service is not configured (missing GROQ_API_KEY)."}

        # Build context from text blocks
        if text_blocks and len(text_blocks) > 0:
            blocks_context = "\n\n".join([
                f"[{block.get('type', 'paragraph')}]: {block.get('content', '')}" 
                for block in text_blocks if block.get('content')
            ])
        else:
            blocks_context = "No written content yet."

        # Build conversation context
        conv_context = ""
        if conversation_history:
            for msg in conversation_history[-6:]:  # Last 6 messages for context
                role = "User" if msg.get("role") == "user" else "Assistant"
                conv_context += f"{role}: {msg.get('content', '')}\n"

        # ═══════════════════════════════════════════════════════════════════
        # STAGE 1: MAVERICK - Vision Understanding
        # ═══════════════════════════════════════════════════════════════════
        vision_prompt = f"""Analyze this image carefully and respond to the user's request.

EXISTING STORY CONTEXT:
{blocks_context[:2000]}

CONVERSATION SO FAR:
{conv_context}

USER REQUEST: {user_message}

Provide a detailed, helpful response that:
1. Directly addresses what the user asked
2. References specific visual elements from the image
3. Connects observations to the existing story context if relevant
4. Is substantive and informative

Respond clearly and concisely:"""
        vision_prompt = ground_prompt(vision_prompt, context_pack)

        messages = [
            {"role": "system", "content": "You are a vision-enabled assistant. Describe what you see and respond helpfully. Be direct and avoid repetition."},
            {"role": "user", "content": [
                {"type": "image_url", "image_url": {"url": image_url}},
                {"type": "text", "text": vision_prompt}
            ]}
        ]

        try:
            # Stage 1: Get raw vision understanding from Maverick
            vision_completion = self.client.chat.completions.create(
                messages=messages,
                model=self.vision_model,
                reasoning_effort="none",
                max_tokens=1500,
                temperature=0.7,
            )
            
            raw_vision_response = vision_completion.choices[0].message.content
            
            # ═══════════════════════════════════════════════════════════════════
            # STAGE 2: GPT-OSS - Literary Refinement
            # ═══════════════════════════════════════════════════════════════════
            # Determine if literary refinement is appropriate
            # (Skip for short/simple queries like "what color is X?")
            needs_literary = len(raw_vision_response) > 150 or any(
                keyword in user_message.lower() 
                for keyword in ['story', 'describe', 'write', 'narrative', 'prose', 'literary', 'tell me about', 'elaborate', 'expand']
            )
            
            if needs_literary:
                # Stage 2 is where voice is decided, so the pack must reach it too —
                # grounding only stage 1 would sand the person's voice back off.
                refined_response = self._literary_refine(
                    raw_text=raw_vision_response,
                    context=ground_prompt(
                        f"Story context: {blocks_context[:1000]}\nUser asked: {user_message}",
                        context_pack,
                    ),
                    style_hint="evocative, literary prose suitable for a visual story"
                )
                return {"response": refined_response}
            else:
                # For simple queries, return the raw response
                return {"response": raw_vision_response}

        except Exception as e:
            print(f"Error in vision chat: {e}")
            # Fallback to text-only model
            return self._fallback_text_chat(blocks_context, user_message, conv_context)

    def _fallback_text_chat(self, blocks_context: str, user_message: str, conv_context: str) -> dict:
        """Fallback to text-only chat if vision fails."""
        try:
            prompt = f"""EXISTING TEXT BLOCKS:
{blocks_context}

CONVERSATION SO FAR:
{conv_context}

USER MESSAGE: {user_message}

Please respond helpfully based on the text context provided."""

            chat_completion = self.client.chat.completions.create(
                messages=[
                    {"role": "system", "content": "You are a creative writing assistant helping with prose and storytelling."},
                    {"role": "user", "content": prompt}
                ],
                model=self.literary_model,
                max_tokens=2000,
            )

            return {"response": chat_completion.choices[0].message.content}
        except Exception as e:
            print(f"Error in fallback chat: {e}")
            return {"response": "Sorry, I encountered an error. Please try again."}

    def generate_node_expansion(self, node_text: str, image_url: str, story_context: str,
                                context_pack: str = "") -> dict:
        """
        Generates a detailed literary expansion for a specific story flow node.
        Used when user clicks on a node in the StoryFlow visualization.

        Args:
            node_text: The text of the clicked node (e.g., "The storm arrives")
            image_url: URL of the associated image
            story_context: The full story/text blocks for context
            context_pack: Anuraṇana grounding (Track C). Empty → unchanged behavior.

        Returns:
            Dictionary with 'expansion' key containing rich literary prose about this moment
        """
        if not self.client:
            return {"expansion": "LLM service is not configured."}

        # Stage 1: Vision understanding of the image focused on this moment
        vision_prompt = f"""Look at this image and focus on elements that relate to this story moment:

STORY MOMENT: "{node_text}"

FULL STORY CONTEXT:
{story_context[:3000]}

Identify and describe visual elements that connect to or illuminate this specific moment.
What in the image resonates with "{node_text}"?"""
        vision_prompt = ground_prompt(vision_prompt, context_pack)

        try:
            vision_completion = self.client.chat.completions.create(
                messages=[
                    {"role": "system", "content": "You are a visual analyst connecting image details to story moments."},
                    {"role": "user", "content": [
                        {"type": "image_url", "image_url": {"url": image_url}},
                        {"type": "text", "text": vision_prompt}
                    ]}
                ],
                model=self.vision_model,
                reasoning_effort="none",
                max_tokens=800,
                temperature=0.7,
            )
            
            visual_analysis = vision_completion.choices[0].message.content

            # Stage 2: Literary expansion using both visual analysis and story context.
            # Grounded too — the prose stage is where this person's voice is decided.
            expansion_prompt = ground_prompt("""You are a literary master expanding a story moment into rich prose.""", context_pack) + f"""

THE MOMENT: "{node_text}"

VISUAL OBSERVATIONS FROM THE IMAGE:
{visual_analysis}

STORY CONTEXT:
{story_context[:2000]}

TASK:
Write a vivid, immersive literary passage (2-3 paragraphs) that:
1. Brings this specific moment to life with sensory detail
2. Incorporates the visual elements observed in the image
3. Maintains consistency with the overall story
4. Uses literary devices (metaphor, rhythm, imagery)
5. Creates emotional resonance

Write ONLY the expansion prose, no preamble or explanation:"""

            literary_completion = self.client.chat.completions.create(
                messages=[
                    {"role": "system", "content": "You are a literary artist creating evocative prose."},
                    {"role": "user", "content": expansion_prompt}
                ],
                model=self.literary_model,
                max_tokens=1500,
                temperature=0.85,
            )
            
            return {"expansion": literary_completion.choices[0].message.content.strip()}
            
        except Exception as e:
            print(f"Error in node expansion: {e}")
            return {"expansion": f"Unable to expand this moment. Error: {str(e)}"}

    def rewrite_with_vision(self, image_url: str, block_content: str,
                            rewrite_instruction: str = "", context_pack: str = "") -> dict:
        """
        Rewrites a text block with awareness of the image content.
        Uses two-stage pipeline for literary quality.

        `context_pack` is the Anuraṇana grounding (Track C); empty → unchanged behavior.
        """
        if not self.client:
            return {"rewritten": "LLM service is not configured (missing GROQ_API_KEY)."}

        instruction = rewrite_instruction if rewrite_instruction else "Enhance and improve this text while keeping it synchronized with what's visible in the image."

        user_content = [
            {
                "type": "image_url",
                "image_url": {"url": image_url}
            },
            {
                "type": "text",
                "text": ground_prompt(f"""Look at this image carefully.

CURRENT TEXT:
{block_content}

INSTRUCTION: {instruction}

Rewrite the text to better describe, relate to, or complement what's visible in the image.
Keep the same general length but improve the quality, imagery, and connection to the visual.

OUTPUT FORMAT:
Return ONLY a valid JSON object:
{{"rewritten": "Your rewritten text here..."}}""", context_pack)
            }
        ]

        try:
            chat_completion = self.client.chat.completions.create(
                messages=[
                    {"role": "system", "content": "You are a creative rewriting assistant with vision capabilities. You output JSON."},
                    {"role": "user", "content": user_content}
                ],
                model=self.vision_model,
                reasoning_effort="none",
                max_tokens=1500,
                response_format={"type": "json_object"},
            )

            response_content = chat_completion.choices[0].message.content
            result = json.loads(response_content)
            
            # Apply literary refinement to the rewritten content
            if result.get("rewritten"):
                result["rewritten"] = self._literary_refine(
                    result["rewritten"],
                    context=f"Original: {block_content}",
                    style_hint="polished literary prose"
                )
            
            return result

        except Exception as e:
            print(f"Error in vision rewrite: {e}")
            return {"rewritten": block_content}  # Return original on error


editor_llm_service = EditorLLMService()
