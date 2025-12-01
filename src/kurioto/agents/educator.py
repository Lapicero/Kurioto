"""
Educator Agent - Socratic Tutoring

Guides children to discover answers through thoughtful questioning
rather than providing direct solutions. Grounded in parent-provided
educational materials using File Search.
"""

import asyncio
import json
from typing import Any

import structlog
from google import genai
from google.genai import types

from kurioto.agents.base import BaseAgent
from kurioto.config import AgeGroup, ChildProfile
from kurioto.education.material_manager import EducationalMaterialManager

logger = structlog.get_logger()


class EducatorAgent(BaseAgent):
    """
    Socratic tutor that guides children to discover answers themselves.

    Core Principles:
    - Socratic Method: Ask guiding questions, not provide direct answers
    - Grounded Learning: Use parent-uploaded textbooks and materials
    - Age-Appropriate: Adjust language and complexity for developmental stage
    - Safe: All content filtered through safety layers
    - Transparent: Generate summaries for parent oversight
    """

    def __init__(
        self,
        child_profile: ChildProfile,
        client: genai.Client,
        model_name: str = "gemini-2.5-flash",
    ):
        """
        Initialize educator agent.

        Args:
            child_profile: Child's profile with age, grade, interests
            client: Initialized Gemini client
            model_name: Model to use (default: gemini-2.5-flash for 1M context)
        """
        super().__init__(child_profile)
        self._client = client
        self._model_name = model_name

        # Initialize material manager for this child
        self.material_manager = EducationalMaterialManager(
            child_id=child_profile.child_id, client=client
        )

        # Initialize File Search store
        asyncio.create_task(self.material_manager.initialize_store())

    async def tutor_homework(
        self,
        question: str,
        subject: str | None = None,
        context: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """
        Guide child through homework using Socratic method.

        IMPORTANT: Does NOT provide direct answers. Asks guiding questions
        that lead the child to discover the solution themselves.

        Args:
            question: Child's question about homework
            subject: Subject area (math, science, english, etc.)
            context: Optional context with conversation history, attempts

        Returns:
            dict with:
                - response: Guiding questions and hints (NOT direct answer)
                - citations: References to textbook pages used
                - parent_summary: Learning insights for dashboard
                - session_id: For tracking conversation

        Example:
            >>> result = await educator.tutor_homework(
            ...     "How do I solve 3/4 + 1/2?",
            ...     subject="math"
            ... )
            >>> print(result["response"])
            "Great question! Let me help you figure this out.

             First, what does the denominator (bottom number) tell us?
             Can you add fractions when the denominators are different?"
        """
        context = context or {}

        # Validate and truncate input
        validated_question = self._validate_and_truncate_input(question)

        # Build Socratic prompt
        socratic_prompt = self._build_socratic_prompt(
            validated_question, subject, context
        )

        # Get File Search tool for relevant materials
        file_search_tool = self.material_manager.get_file_search_tool(
            subject=subject,
            material_type="textbook",  # Focus on textbooks for homework help
        )

        logger.info(
            "tutoring_homework",
            child_id=self.child_profile.child_id,
            subject=subject,
            question_length=len(validated_question),
        )

        # Generate Socratic response with File Search grounding
        response = await self._client.models.generate_content(
            model=self._model_name,
            contents=socratic_prompt,
            config=types.GenerateContentConfig(
                system_instruction=self._get_tutor_system_instruction(),
                tools=[file_search_tool],
                response_modalities=["TEXT"],
                temperature=0.7,  # Some creativity for engaging questions
            ),
        )

        # Extract citations from grounding metadata
        citations = self._extract_citations(response)

        # Generate parent summary
        parent_summary = await self._generate_parent_summary(
            question=validated_question,
            response=response.text,
            citations=citations,
            subject=subject,
            context=context,
        )

        result = {
            "response": response.text,
            "citations": citations,
            "parent_summary": parent_summary,
            "session_id": context.get("session_id"),
            "subject": subject,
        }

        logger.info(
            "tutoring_complete",
            child_id=self.child_profile.child_id,
            subject=subject,
            citations_count=len(citations),
            understanding_level=parent_summary.get("understanding_level"),
        )

        return result

    async def explain_concept(
        self,
        concept: str,
        subject: str | None = None,
        context: dict[str, Any] | None = None,
    ) -> str:
        """
        Explain a concept using textbook materials.

        Unlike homework tutoring, this provides explanations rather than
        pure Socratic questioning, but still age-appropriate and engaging.

        Args:
            concept: Concept to explain (e.g., "photosynthesis", "fractions")
            subject: Subject area
            context: Optional context

        Returns:
            Age-appropriate explanation grounded in textbooks
        """
        context = context or {}
        validated_concept = self._validate_and_truncate_input(concept, max_length=500)

        # Get File Search tool for textbooks
        file_search_tool = self.material_manager.get_file_search_tool(
            subject=subject, material_type="textbook"
        )

        child_age = self.child_profile.age
        prompt = f"""Explain {json.dumps(validated_concept)} to a {child_age}-year-old child.

Use the textbook materials to ground your explanation.
Use age-appropriate language and examples.
Break it down into simple, digestible pieces.
Use analogies or real-world examples when helpful.

Keep explanation under 200 words.
"""

        logger.info(
            "explaining_concept",
            child_id=self.child_profile.child_id,
            concept=validated_concept,
            subject=subject,
        )

        response = await self._client.models.generate_content(
            model=self._model_name,
            contents=prompt,
            config=types.GenerateContentConfig(
                system_instruction=self._get_tutor_system_instruction(),
                tools=[file_search_tool],
                temperature=0.8,
            ),
        )

        return response.text

    def _build_socratic_prompt(
        self, question: str, subject: str | None, context: dict[str, Any]
    ) -> str:
        """Build prompt that enforces Socratic teaching methodology."""

        age_guidelines = self._get_age_guidelines()
        conversation_history = context.get("conversation_history", [])
        has_attempted = context.get("has_attempted", False)
        child_attempt = context.get("child_attempt", "")

        child_age = self.child_profile.age
        prompt = f"""You are a patient, encouraging tutor for a {child_age}-year-old child.

**Your Role**: Guide the child to discover the answer themselves using the Socratic method.

**DO NOT**:
- Provide direct answers to homework questions
- Solve the problem for the child
- Give step-by-step solutions without child participation

**DO**:
- Ask guiding questions that lead to understanding
- Break complex problems into smaller steps
- Acknowledge effort and celebrate small wins
- Use age-appropriate language and examples
- Reference the textbook materials when helpful
- Encourage the child to try before helping more

**Age Guidelines**:
{age_guidelines}

**Child's Question**:
{json.dumps(question)}

"""

        if has_attempted and child_attempt:
            prompt += f"""
**Child's Attempt**:
{json.dumps(child_attempt)}

Review their work and guide them to the correct answer. If they're close, encourage them!
If they're stuck, ask a question that helps them see the next step.
"""
        else:
            prompt += """
**This is the first question**. Start by asking what they already know about the topic.
Encourage them to try the problem before offering hints.
"""

        if conversation_history:
            prompt += "\n**Previous conversation**:\n"
            for turn in conversation_history[-3:]:  # Last 3 turns for context
                prompt += (
                    f"Child: {turn.get('child', '')}\nYou: {turn.get('tutor', '')}\n"
                )

        prompt += """
**Your response should**:
1. Ask 1-2 guiding questions
2. Provide a small hint if needed
3. Encourage the child to think/try
4. Keep it friendly and age-appropriate

**Remember**: Do not solve the problem. Your job is to guide discovery.
"""

        return prompt

    def _get_tutor_system_instruction(self) -> str:
        """System instruction defining tutor behavior and personality."""

        emoji_guideline = self._get_emoji_guideline()

        return f"""You are Kurioto, a friendly and patient AI tutor for children.

**Core Principles**:
1. **Socratic Method**: Guide through questions, not answers
2. **Age-Appropriate**: Adjust language for {self.child_profile.age}-year-old
3. **Encouraging**: Celebrate effort and small wins
4. **Safe**: Never provide inappropriate content
5. **Grounded**: Use uploaded textbooks and educational materials

**Personality**:
- Patient and never frustrated
- Enthusiastic about learning
- Uses emojis sparingly ({emoji_guideline})
- Encouraging without being condescending

**When child is stuck**:
- Ask what they've tried
- Break problem into smaller pieces
- Provide one hint at a time
- Celebrate when they figure it out

**When child gets it wrong**:
- Acknowledge the effort
- Ask gentle questions to reveal the error
- Never say "wrong" or "incorrect" harshly
- Frame as "let's think about this together"

**When child gets it right**:
- Celebrate! 🎉
- Ask a follow-up to check understanding
- Connect to real-world examples

You are helping them learn, not doing their homework for them.
"""

    def _get_age_guidelines(self) -> str:
        """Get age-specific language and complexity guidelines."""

        age_group = self.child_profile.age_group

        guidelines = {
            AgeGroup.EARLY_CHILDHOOD: """
- Use very simple words (1-2 syllables)
- Short sentences (5-10 words)
- Concrete, visual examples
- Lots of encouragement
- Simple questions with yes/no or short answers
""",
            AgeGroup.MIDDLE_CHILDHOOD: """
- Use simple but varied vocabulary
- Moderate sentences (8-15 words)
- Relatable examples from their life
- Encourage problem-solving
- Questions that require thinking
""",
            AgeGroup.LATE_CHILDHOOD: """
- Age-appropriate vocabulary (avoid jargon)
- Can handle longer explanations
- Abstract concepts with good examples
- Encourage critical thinking
- Open-ended questions
""",
        }

        return guidelines.get(age_group, guidelines[AgeGroup.MIDDLE_CHILDHOOD])

    def _get_emoji_guideline(self) -> str:
        """Age-appropriate emoji usage."""

        age_group = self.child_profile.age_group

        if age_group == AgeGroup.EARLY_CHILDHOOD:
            return "use frequently for engagement"
        elif age_group == AgeGroup.MIDDLE_CHILDHOOD:
            return "use occasionally for encouragement"
        else:
            return "use rarely, more mature tone"

    def _extract_citations(self, response: Any) -> list[dict[str, str]]:
        """Extract citations from grounding metadata."""

        citations = []

        try:
            if hasattr(response, "candidates") and response.candidates:
                candidate = response.candidates[0]

                if (
                    hasattr(candidate, "grounding_metadata")
                    and candidate.grounding_metadata
                ):
                    grounding = candidate.grounding_metadata

                    if hasattr(grounding, "grounding_chunks"):
                        for chunk in grounding.grounding_chunks:
                            citation = {
                                "text": getattr(chunk, "text", ""),
                            }

                            # Add source information if available
                            if hasattr(chunk, "web") and chunk.web:
                                citation["source"] = "web"
                                citation["uri"] = getattr(chunk.web, "uri", "")
                            else:
                                citation["source"] = "textbook"

                            citations.append(citation)
        except Exception as e:
            logger.warning(
                "error_extracting_citations",
                error=str(e),
                child_id=self.child_profile.child_id,
            )

        return citations

    async def _generate_parent_summary(
        self,
        question: str,
        response: str,
        citations: list[dict[str, str]],
        subject: str | None,
        context: dict[str, Any],
    ) -> dict[str, Any]:
        """Generate summary for parent dashboard."""

        summary_prompt = f"""Analyze this tutoring interaction and create a parent summary.

**Child's Question**: {json.dumps(question)}
**Tutor's Response**: {json.dumps(response)}
**Subject**: {subject or 'general'}

Generate a brief summary for parents:
1. What topic was covered
2. How well the child understood (struggling/learning/mastered)
3. Any concerns or recommendations
4. Key learning outcome

Return JSON:
{{
    "topic": "specific topic (e.g., fractions, multiplication)",
    "understanding_level": "struggling|learning|mastered",
    "concern_level": "none|low|medium|high",
    "recommendation": "what parent should know or do",
    "learning_outcome": "what child practiced/learned"
}}
"""

        try:
            summary_response = await self._generate_json(
                prompt=summary_prompt, client=self._client, model_name=self._model_name
            )

            return summary_response
        except Exception as e:
            logger.error(
                "error_generating_parent_summary",
                error=str(e),
                child_id=self.child_profile.child_id,
            )

            # Return basic fallback summary
            return {
                "topic": subject or "general education",
                "understanding_level": "learning",
                "concern_level": "none",
                "recommendation": "Session completed successfully",
                "learning_outcome": "Engaged with educational content",
            }
