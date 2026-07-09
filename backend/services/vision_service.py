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
from backend.services import lens_registry


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


    async def brainstorm_image(
        self,
        image_url: str,
        answers: Optional[list] = None,
        context: Optional[Dict[str, Any]] = None,
        depth: str = "deep",
    ) -> Optional[Dict[str, Any]]:
        """
        "Aletheia" interpretive DIALOGUE: unconceal an image through lenses **the
        image's own context selects** (Track C §2), and pose clickable multiple-choice
        questions that hand the looking back to the viewer. The viewer's answers
        (passed in `answers`) reshape the next reading — a back-and-forth that
        deepens the interpretation each round.

        Args:
            image_url: image URL or base64 data URL of the image to interpret
            answers: optional list of prior {"question": str, "choice": str} the
                     viewer has already chosen, to sharpen this round.
            context: optional {domain, parts[], attributes[], regions[], persona_lenses[],
                     lens_hint} — from Track B's router/detections and the curator's
                     persona. Absent or empty → the general three lenses (today's read).
            depth: "deep" (creator: all fired lenses, evidence, forks) or "hook"
                   (audience: one distilled lens + one fork, hard token cap).

        Returns:
            Normalized dict {lenses:[{name,reading,intensity,evidence,region_ids}],
            tension, questions:[{prompt,options}], concealed, uncertainty, domain,
            lens_provenance}, or None.
        """
        if not self._is_available():
            print("⚠️ Vision service not available - GROQ_API_KEY not set")
            return None

        ctx = context or {}
        regions = ctx.get("regions") or []
        lens_names, provenance = lens_registry.select_lenses(
            domain=ctx.get("domain"),
            parts=ctx.get("parts"),
            attributes=ctx.get("attributes"),
            persona_lenses=ctx.get("persona_lenses"),
            lens_hint=ctx.get("lens_hint", ""),
            depth=depth,
            # Absent an explicit strength, assume a cold start: no prior. A caller that
            # has measured the corpus passes the ramped value.
            prior_strength=float(ctx.get("prior_strength", 0.0)),
        )
        prompt = ALETHEIA_PROMPT.format(
            context_header=lens_registry.render_context_header(
                domain=ctx.get("domain"), parts=ctx.get("parts"),
                attributes=ctx.get("attributes"), regions=regions,
            ),
            lens_block=lens_registry.render_lens_block(lens_names),
            n_questions="exactly 1" if depth == "hook" else "1–3",
        )
        if depth == "hook":
            prompt += ALETHEIA_HOOK_SUFFIX

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

        # Back-loaded reminder. The region_ids rule sits mid-prompt, where models attend
        # worst ("lost in the middle") — and the deep read, with more lenses to produce,
        # reliably dropped the citations while the single-lens hook kept them. Restating
        # the requirement at the tail, next to the ask, is what makes it stick.
        closing = "\n\nUnconceal this image. Return only the JSON."
        if regions:
            closing = ("\n\nUnconceal this image. Every lens must cite 1–3 `region_ids` "
                       "copied exactly from the PART IDS list. Return only the JSON.")

        try:
            completion = self.client.chat.completions.create(
                model=self.vision_model,
                messages=[
                    {
                        "role": "user",
                        "content": [
                            {"type": "text", "text": prompt + feedback + closing},
                            {"type": "image_url", "image_url": {"url": image_url}},
                        ],
                    }
                ],
                temperature=0.65,
                max_tokens=320 if depth == "hook" else 1100,
                top_p=1,
                stream=False,
            )
            raw = completion.choices[0].message.content
            reading = self._parse_aletheia(
                raw, valid_region_ids={str(r.get("id")) for r in regions if r.get("id")}
            )
            if reading is not None:
                reading["domain"] = ctx.get("domain") or ""
                reading["lens_provenance"] = provenance
            return reading
        except Exception as e:
            print(f"❌ Error in brainstorm analysis: {e}")
            return None

    def _parse_aletheia(
        self, raw: Optional[str], valid_region_ids: Optional[set] = None
    ) -> Optional[Dict[str, Any]]:
        """Extract and normalize the Aletheia JSON from a model response.

        `evidence`/`region_ids`/`tension` are Track C §3 additions and parse null-safely:
        a model that omits them yields exactly the old shape. Cited region ids are
        intersected with the ids actually on the post, so a hallucinated part can never
        reach the UI's lens↔region highlight.
        """
        if not raw:
            return None
        try:
            # Strip code fences and pull out the first JSON object
            cleaned = re.sub(r"^```(?:json)?|```$", "", raw.strip(), flags=re.MULTILINE).strip()
            match = re.search(r"\{.*\}", cleaned, re.DOTALL)
            if not match:
                return None
            data = json.loads(match.group())

            # Normalize lenses: {name, reading, intensity:int 0-100, evidence, region_ids}
            lenses = []
            for lens in (data.get("lenses") or [])[:5]:
                try:
                    intensity = int(round(float(lens.get("intensity", 0))))
                except (TypeError, ValueError):
                    intensity = 0
                cited = [str(r).strip() for r in (lens.get("region_ids") or []) if str(r).strip()]
                if valid_region_ids is not None:
                    cited = [r for r in cited if r in valid_region_ids]
                lenses.append({
                    "name": str(lens.get("name", "")).strip(),
                    "reading": str(lens.get("reading", "")).strip(),
                    "intensity": max(0, min(100, intensity)),
                    "evidence": str(lens.get("evidence", "")).strip(),
                    "region_ids": cited[:6],
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
                "tension": str(data.get("tension", "")).strip(),
                "questions": questions,
                "concealed": str(data.get("concealed", "")).strip(),
                "uncertainty": str(data.get("uncertainty", "")).strip(),
            }
        except Exception as e:
            print(f"❌ Error parsing Aletheia JSON: {e}")
            return None


    async def detect_regions(self, image_url: str) -> list:
        """
        Dissect the image into its salient parts ("anatomy") using the vision model
        as a detector. Returns a list of regions, each with a label, category, a
        NORMALIZED bounding box (x, y, w, h in 0..1, top-left origin) and a short
        description. Coordinates are model-estimated (no dedicated detector), so they
        are approximate but good enough for clickable overlays.
        """
        if not self._is_available():
            print("⚠️ Vision service not available - GROQ_API_KEY not set")
            return []
        try:
            completion = self.client.chat.completions.create(
                model=self.vision_model,
                messages=[
                    {
                        "role": "user",
                        "content": [
                            {"type": "text", "text": DETECT_PROMPT},
                            {"type": "image_url", "image_url": {"url": image_url}},
                        ],
                    }
                ],
                temperature=0.2,
                max_tokens=1200,
                top_p=1,
                stream=False,
            )
            return self._parse_regions(completion.choices[0].message.content)
        except Exception as e:
            print(f"❌ Error in region detection: {e}")
            return []

    def _parse_regions(self, raw: Optional[str]) -> list:
        """Extract + normalize the detected-regions JSON from a model response."""
        if not raw:
            return []
        try:
            cleaned = re.sub(r"^```(?:json)?|```$", "", raw.strip(), flags=re.MULTILINE).strip()
            match = re.search(r"\{.*\}", cleaned, re.DOTALL)
            if not match:
                return []
            data = json.loads(match.group())
            out = []
            for i, r in enumerate((data.get("regions") or [])[:10]):
                box = r.get("box") or {}

                def clamp01(v):
                    try:
                        return max(0.0, min(1.0, float(v)))
                    except (TypeError, ValueError):
                        return 0.0

                x, y = clamp01(box.get("x")), clamp01(box.get("y"))
                w, h = clamp01(box.get("w")), clamp01(box.get("h"))
                if w <= 0.01 or h <= 0.01:
                    continue
                # keep the box inside the frame
                w = min(w, 1.0 - x)
                h = min(h, 1.0 - y)
                label = str(r.get("label", "")).strip() or "region"
                out.append({
                    "id": f"region_{i}",
                    "actor": "auto",
                    "detector": "vision",
                    "label": label,
                    "category": str(r.get("category", "")).strip(),
                    "box": {"x": round(x, 4), "y": round(y, 4), "w": round(w, 4), "h": round(h, 4)},
                    "description": str(r.get("description", "")).strip(),
                })
            return out
        except Exception as e:
            print(f"❌ Error parsing regions JSON: {e}")
            return []


    async def decompose_regions(
        self,
        image_url: str,
        anchors: Optional[list] = None,
        lens: str = "",
        mode: str = "general",
        max_regions: int = 16,
    ) -> list:
        """
        SŪKṢMA — the *fine* anatomy stage. Where YOLO gives coarse anchors (a whole
        "person", a whole "object"), this uses the vision model to dissect each anchor
        SEMANTICALLY into its sub-parts: individual garments, sub-sections of a garment
        (collar, cuff, hem, sleeve, placket), body parts, materials, textures, edges.

        - `anchors`: the coarse YOLO regions (label + normalized box) used as guidance,
          so the model subdivides *within* what is actually there instead of inventing.
        - `mode`: chooses the subdivision vocabulary (garment / body / texture / ...).
        - `lens`: the curator's free-text intention ("the way the fabric folds at the
          waist", "the hands"). Always optional — `general` mode works without it.

        Returns a flat list of fine sub-regions, each with a normalized box, a parent
        anchor label, a category and a description. (Boxes are model-estimated.)
        """
        if not self._is_available():
            print("⚠️ Vision service not available - GROQ_API_KEY not set")
            return []

        # Tell the model what the coarse pass already found, so it stays grounded.
        anchor_hint = ""
        if anchors:
            lines = []
            for a in anchors[:8]:
                b = a.get("box") or {}
                try:
                    lines.append(
                        f'- {a.get("label", "region")} at box '
                        f'x={round(float(b.get("x", 0)), 2)}, y={round(float(b.get("y", 0)), 2)}, '
                        f'w={round(float(b.get("w", 0)), 2)}, h={round(float(b.get("h", 0)), 2)}'
                    )
                except (TypeError, ValueError):
                    continue
            if lines:
                anchor_hint = (
                    "\n\nThe coarse pass already located these whole objects (normalized "
                    "boxes). Subdivide INSIDE these — your sub-parts' boxes must sit within "
                    "the relevant parent box, and name the parent in \"parent\":\n"
                    + "\n".join(lines)
                )

        focus = MODE_FOCUS.get((mode or "general").lower(), MODE_FOCUS["general"])
        lens_hint = ""
        if (lens or "").strip():
            lens_hint = (
                f"\n\nThe curator's INTENTION for this dissection: \"{lens.strip()}\". "
                "Bias the parts you surface and how you describe them toward this intention, "
                "but still return the structurally important parts too."
            )

        prompt = SOOKSHMA_PROMPT.replace("{focus}", focus) + anchor_hint + lens_hint + \
            "\n\nDissect this image now. Return only the JSON."

        try:
            completion = self.client.chat.completions.create(
                model=self.vision_model,
                messages=[
                    {
                        "role": "user",
                        "content": [
                            {"type": "text", "text": prompt},
                            {"type": "image_url", "image_url": {"url": image_url}},
                        ],
                    }
                ],
                temperature=0.25,
                max_tokens=1800,
                top_p=1,
                stream=False,
            )
            return self._parse_subregions(completion.choices[0].message.content, max_regions)
        except Exception as e:
            print(f"❌ Error in fine decomposition: {e}")
            return []

    def _parse_subregions(self, raw: Optional[str], max_regions: int = 16) -> list:
        """Extract + normalize the fine sub-region JSON from a model response."""
        if not raw:
            return []
        try:
            cleaned = re.sub(r"^```(?:json)?|```$", "", raw.strip(), flags=re.MULTILINE).strip()
            match = re.search(r"\{.*\}", cleaned, re.DOTALL)
            if not match:
                return []
            data = json.loads(match.group())

            def clamp01(v):
                try:
                    return max(0.0, min(1.0, float(v)))
                except (TypeError, ValueError):
                    return 0.0

            out = []
            for i, r in enumerate((data.get("parts") or data.get("regions") or [])[:max_regions]):
                box = r.get("box") or {}
                x, y = clamp01(box.get("x")), clamp01(box.get("y"))
                w, h = clamp01(box.get("w")), clamp01(box.get("h"))
                if w <= 0.01 or h <= 0.01:
                    continue
                w = min(w, 1.0 - x)
                h = min(h, 1.0 - y)
                label = str(r.get("label", "")).strip() or "part"
                out.append({
                    "id": f"fine_{i}",
                    "actor": "auto",
                    "detector": "vision",
                    "label": label,
                    "category": str(r.get("category", "")).strip() or "part",
                    # transient: used by the router's _match_parent to resolve parent_id,
                    # then popped before persisting (parent_label is dropped from Region).
                    "parent_label": str(r.get("parent", "")).strip(),
                    "material": str(r.get("material", "")).strip(),
                    "box": {"x": round(x, 4), "y": round(y, 4), "w": round(w, 4), "h": round(h, 4)},
                    "description": str(r.get("description", "")).strip(),
                    "depth": 1,
                })
            return out
        except Exception as e:
            print(f"❌ Error parsing sub-regions JSON: {e}")
            return []


# --- Region/"anatomy" detection prompt ---
DETECT_PROMPT = """You are a precise visual detector. Dissect this image into its salient PARTS —
its anatomy. Detect the distinct, meaningful regions: for a person that means body
parts and worn/held things (face, eyes, hands, hair, garment, jewellery, posture);
for any image, the principal objects, figures, and notable zones (light source,
horizon, foreground object, background element, text).

For EACH region give:
- "label": 1-3 words naming the part/object
- "category": one of person-part | figure | object | garment | environment | light | text | other
- "box": a bounding box as {"x","y","w","h"} in NORMALIZED coordinates 0..1, with the
  ORIGIN at the TOP-LEFT, x/y = the box's top-left corner, w/h = its width/height.
- "description": one short phrase on what it is / how it reads.

Detect 4 to 8 regions, the ones that actually carry the image. Boxes must lie inside
the frame (x+w ≤ 1, y+h ≤ 1) and not all overlap. Be as accurate with the boxes as you can.

Return STRICT JSON only:
{"regions": [{"label":"...","category":"...","box":{"x":0.0,"y":0.0,"w":0.0,"h":0.0},"description":"..."}]}"""


# --- Aletheia interpretive prompt (image brainstorm dialogue) ---
# Track C §2/§3: the lens set is no longer hard-coded. `{lens_block}` is filled from
# the domain→lens registry and `{context_header}` from what the detectors actually
# found, so the reading is *specific to this image* rather than generically three-lensed.
ALETHEIA_PROMPT = """You are Aletheia, an interpretive companion inside Semant. A person scrolling a
feed has paused on an image. Your task is NOT to caption it (what is depicted)
but to help them UNCONCEAL it — to make perceptible how the image appears and
works on them, and what it withholds. (Heidegger: truth as unconcealment.)

This is a DIALOGUE. You offer a reading, then pose a few multiple-choice questions
that hand the looking back to the viewer. Their clicks sharpen your next reading,
so the image is unconcealed together, round by round.

{context_header}

Rules:
- Look closely at the ACTUAL image. Never invent details you cannot see.
- Plain, sensuous, specific language. No art-jargon padding. Keep it short.
- Each lens is a distinct voice and may disagree with the others.
- Disclose your uncertainty rather than bluffing (the "earth that resists").
- GROUND EACH LENS IN THE IMAGE: give an "evidence" phrase naming what you actually
  see that licenses the claim, and cite in "region_ids" the parts it rests on. Every
  lens carries 1–3 ids, copied EXACTLY from the PART IDS list above (the bare id, e.g.
  "seg_0" — never the label, never a name you invented). Return [] only when the list
  above is empty. Do not put ids inside "evidence"; they belong in "region_ids".
  A claim you cannot ground, don't make.
- Questions are perceptual/interpretive, never a factual quiz. Each offers a real
  FORK in how to see — 2 to 4 short options (a few words each). There is no
  "correct" option; each opens a different reading.

Produce:
1. LENSES — use EXACTLY these, in this order:
{lens_block}
   Each lens: 1–2 sentences of "reading", an "intensity" 0–100 (how strongly this
   lens speaks for this image) for the UI bars, an "evidence" phrase, and "region_ids".
2. TENSION — one line naming where the lenses disagree (that friction is the reading's
   real content). Empty string if they genuinely converge.
3. QUESTIONS ({n_questions}): each a short prompt + 2–4 short options, inviting the viewer
   to choose how to see (e.g. "What pulls your eye first?", "What is this image's
   weather?"). These drive the back-and-forth.
4. CONCEALED — one line on what lies outside the frame / what the image withholds.

Return strict JSON only:
{{
  "lenses": [{{"name": "...", "reading": "...", "intensity": 0, "evidence": "...", "region_ids": ["..."]}}],
  "tension": "...",
  "questions": [{{"prompt": "...", "options": ["...", "..."]}}],
  "concealed": "...",
  "uncertainty": "..."
}}"""

# The feed-hook render (§5): same engine, one distilled lens and one fork. The scroll
# pause is worth a sentence, not an essay — and a hard token cap keeps it cheap at
# audience scale.
ALETHEIA_HOOK_SUFFIX = """

RENDER MODE: FEED HOOK. The viewer has paused mid-scroll — you have one breath.
Give ONE lens, its reading distilled to 1–2 sentences, and exactly ONE question
(the single most perceptually alive fork). Keep "concealed" to a short clause.
Everything else stays as specified."""


# --- Sūkṣma: fine semantic decomposition vocabularies (one per mode) ---
MODE_FOCUS = {
    "general": (
        "Surface the most meaningful FINE parts of whatever is present: for a person, "
        "the individual garments AND their sub-sections (collar, lapel, placket, cuff, "
        "sleeve, hem, waistband, pocket, neckline, fold, seam), plus salient body parts "
        "(face, eyes, mouth, hair, neck, hands, fingers) and anything worn or held "
        "(jewellery, bag, glasses). For objects/scenes, their constituent surfaces, "
        "edges, and zones."
    ),
    "garment": (
        "Dissect CLOTHING exhaustively. Name each separate garment (shirt, jacket, "
        "trouser, sari, dupatta, scarf, shoe) AND decompose each into its sub-sections: "
        "collar, lapel, placket, button row, cuff, sleeve (upper/fore), shoulder seam, "
        "yoke, hem, waistband, pleat, drape, fold, pocket, neckline, fastening. Treat the "
        "garment as having its own anatomy."
    ),
    "body": (
        "Dissect the BODY / figure: head, face, eyes, brow, mouth, jaw, hair, neck, "
        "shoulders, chest, arms, elbows, wrists, hands, fingers, waist, hips, legs, feet, "
        "and the POSTURE/gesture lines. Note gaze direction and where weight rests."
    ),
    "texture": (
        "Read the image as a field of TEXTURES and surface qualities: the weave/grain of "
        "each fabric, knit vs woven, sheen vs matte, wrinkle and fold patterns, skin "
        "texture, hair strands, roughness, smoothness, transparency. Each region is a "
        "distinct textural patch and how it catches light."
    ),
    "material": (
        "Read the image by MATERIAL: cotton, silk, denim, wool, leather, metal, glass, "
        "skin, stone, wood, plastic, paper. For each region name the likely material and "
        "fill \"material\", and describe how that material behaves (drapes, reflects, "
        "creases, weighs)."
    ),
    "composition": (
        "Dissect by COMPOSITION: foreground / midground / background planes, the light "
        "source and the shadow it casts, leading lines, negative space, the focal point, "
        "framing edges, and the colour blocks that structure the frame."
    ),
}


SOOKSHMA_PROMPT = """You are Sūkṣma (सूक्ष्म, 'the subtle/fine'), the deep-anatomy reader inside Semant.
A coarse detector has already found the WHOLE objects. Your job is the opposite of
coarse: do NOT return a region for 'the whole person' or 'the whole object'. Go FINE.
Dissect what is present into its constituent SUB-PARTS, the way an anatomist or a
tailor would — many small, specific, non-overlapping parts.

{focus}

For EACH fine part return:
- "label": 1-3 words naming the specific part ("left cuff", "shirt collar", "knuckles",
  "hair parting", "sleeve fold"). Be specific; never just "person" or "clothing".
- "parent": which whole object this part belongs to ("person", "jacket", "background"),
  matching the coarse anchors when given.
- "category": one of garment | garment-detail | body-part | hair | skin | accessory |
  texture | material | edge | light | plane | object | other.
- "material": the likely material if recognizable (cotton, silk, denim, skin, metal…),
  else "".
- "box": a TIGHT bounding box {"x","y","w","h"} in NORMALIZED 0..1 coords, ORIGIN
  TOP-LEFT (x/y = top-left corner, w/h = size). The box must hug just THIS part and lie
  inside its parent's box. Small parts have small boxes — a cuff is not the whole arm.
- "description": one vivid, specific phrase — what it is and how it reads/feels/affects.

Return 6 to 14 fine parts, the ones that genuinely carry the image. Make the boxes
distinct (not all stacked on the same spot) and accurate. Resist the pull toward a few
big generic regions — the whole point is the fine grain.

Return STRICT JSON only:
{"parts": [{"label":"...","parent":"...","category":"...","material":"...","box":{"x":0.0,"y":0.0,"w":0.0,"h":0.0},"description":"..."}]}"""


# Singleton instance
vision_service = VisionService()
