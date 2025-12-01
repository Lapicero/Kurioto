"""Week 1 OrchestratorAgent implementation.

Responsible for:
- Classifying child input into high-level intent categories
- Routing to existing KuriotoAgent internal methods / tools

Design goals (Week 1):
- Non-invasive: falls back to legacy keyword routing if LLM unavailable
- Safe: never bypasses existing safety checks in `KuriotoAgent`
- Simple: minimal dependencies and no breaking API changes
"""

from __future__ import annotations

import json
import os
from typing import Any

from google import genai

from kurioto.agents.base import BaseAgent, Intent
from kurioto.config import ChildProfile
from kurioto.logging import get_logger
from kurioto.safety.base import SafetyAction, SafetyResult, SafetySeverity

logger = get_logger(__name__)

_INTENT_SYSTEM_INSTRUCTIONS = (
    "You classify a child's message for an educational, playful AI companion. "
    "Return ONLY a JSON object without code fences. Categories: \n"
    "educational: factual / curiosity / learning questions\n"
    "conversational: greetings, feelings, casual talk\n"
    "action: explicit request to play music, start activity, do something\n"
    "safety_concern: dangerous, self-harm, adult, violence, highly inappropriate\n"
    "unknown: anything else or unclear\n\n"
    "Fields: type, confidence (0-1), reasoning (short)."
)


class OrchestratorAgent(BaseAgent):
    def __init__(self, child_profile: ChildProfile):
        super().__init__(child_profile)
        self._client = None
        self._model_name = self.settings.model_name
        self._available = False
        self._force_llm = str(os.getenv("KURIOTO_FORCE_LLM", "")).lower() in (
            "1",
            "true",
            "yes",
            "on",
        )
        self._last_intent: Intent | None = None
        self._last_llm_used: bool = False
        self._init_client()

    def _init_client(self) -> None:
        if genai is None:
            logger.warning(
                "orchestrator_llm_unavailable", reason="google-genai not installed"
            )
            return
        api_key = self.settings.google_api_key
        if not api_key:
            logger.warning("orchestrator_no_api_key")
            return
        try:
            self._client = genai.Client(api_key=api_key)
            self._available = True
            logger.info(
                "orchestrator_client_ready",
                model=self._model_name,
                force_llm=self._force_llm,
            )
        except Exception as e:  # pragma: no cover
            logger.error("orchestrator_client_error", error=str(e))

    @property
    def is_available(self) -> bool:
        return self._available

    async def classify_intent(self, user_input: str) -> Intent:
        """Classify intent using Gemini when available; fallback heuristics otherwise."""
        # Validate and truncate input to prevent API issues
        validated_input = self._validate_and_truncate_input(user_input)
        if not validated_input:
            # Empty input, return conversational with low confidence
            return Intent(
                type="conversational",
                confidence=0.1,
                reasoning="empty or invalid input",
            )

        if not self.is_available:
            if self._force_llm:
                logger.error(
                    "orchestrator_force_llm_unavailable",
                    message="FORCE_LLM enabled but LLM client unavailable",
                )
                raise RuntimeError("FORCE_LLM enabled but LLM client unavailable")
            intent = self._heuristic_intent(validated_input)
            self._last_intent = intent
            self._last_llm_used = False
            logger.info(
                "orchestrator_intent",
                type=intent.type,
                confidence=intent.confidence,
                llm_used=False,
                available=False,
            )
            return intent

        prompt = (
            f"{_INTENT_SYSTEM_INSTRUCTIONS}\nMessage: {json.dumps(validated_input)}"
        )
        try:
            response = await self._generate_json(prompt, self._client, self._model_name)
            intent_type = response.get("type", "unknown")
            confidence = float(response.get("confidence", 0.0))
            reasoning = response.get("reasoning")
            # Basic validation
            if intent_type not in {
                "educational",
                "conversational",
                "action",
                "safety_concern",
                "unknown",
            }:
                if self._force_llm:
                    raise ValueError("Invalid intent_type from LLM in FORCE_LLM mode")
                intent = self._heuristic_intent(validated_input)
                self._last_intent = intent
                self._last_llm_used = False
                logger.info(
                    "orchestrator_intent",
                    type=intent.type,
                    confidence=intent.confidence,
                    llm_used=False,
                    available=self._available,
                )
                return intent
            intent = Intent(
                type=intent_type, confidence=confidence, reasoning=reasoning
            )
            self._last_intent = intent
            self._last_llm_used = True
            logger.info(
                "orchestrator_intent",
                type=intent.type,
                confidence=intent.confidence,
                llm_used=True,
                available=self._available,
            )
            return intent
        except Exception as e:
            if self._force_llm:
                logger.error("orchestrator_intent_error", error=str(e), force_llm=True)
                raise
            logger.warning("orchestrator_intent_fallback", error=str(e))
            intent = self._heuristic_intent(validated_input)
            self._last_intent = intent
            self._last_llm_used = False
            logger.info(
                "orchestrator_intent",
                type=intent.type,
                confidence=intent.confidence,
                llm_used=False,
                available=self._available,
            )
            return intent

    def _heuristic_intent(self, user_input: str) -> Intent:
        text = user_input.lower()
        educational_keywords = [
            "why",
            "what",
            "how",
            "when",
            "where",
            "who",
            "tell me",
            "explain",
        ]
        action_keywords = ["play", "music", "song", "game"]
        safety_keywords = ["hurt", "kill", "weapon", "bomb", "gun", "drugs"]

        if any(k in text for k in safety_keywords):
            return Intent(
                type="safety_concern",
                confidence=0.9,
                reasoning="matched safety keyword",
            )
        if any(k in text for k in action_keywords):
            return Intent(
                type="action", confidence=0.7, reasoning="matched action keyword"
            )
        if any(k in text for k in educational_keywords):
            return Intent(
                type="educational",
                confidence=0.6,
                reasoning="matched educational keyword",
            )
        greetings = ["hi", "hello", "hey"]
        if any(g == text.strip() or text.startswith(g) for g in greetings):
            return Intent(
                type="conversational", confidence=0.5, reasoning="greeting detected"
            )
        return Intent(
            type="conversational", confidence=0.3, reasoning="default fallback"
        )

    async def route(
        self,
        user_input: str,
        agent_core: Any,
        context: dict[str, Any] | None = None,
    ) -> str:
        """Route the input based on classified intent.

        Parameters:
            user_input: raw child message
            agent_core: reference to existing `KuriotoAgent` instance for method reuse
            context: optional context dict
        """
        intent = await self.classify_intent(user_input)
        logger.debug(
            "orchestrator_intent", type=intent.type, confidence=intent.confidence
        )
        # Emit trace event with orchestrator status if trace provided
        trace = context.get("trace") if context else None
        if trace is not None:
            trace.log_event(
                "orchestrator_intent",
                data={
                    "type": intent.type,
                    "confidence": intent.confidence,
                    "reasoning": intent.reasoning,
                    "llm_used": self._last_llm_used,
                    "available": self._available,
                    "force_llm": self._force_llm,
                },
            )

        if intent.type == "safety_concern":
            return agent_core._get_block_response(
                SafetyResult(
                    action=SafetyAction.BLOCK,
                    reason="Potential unsafe content detected",
                    severity=SafetySeverity.HIGH,
                )
            )
        if intent.type == "educational":
            # Reuse existing planner logic for educational queries
            plan = {
                "action": "use_tool",
                "tool": "search_educational",
                "query": user_input,
            }
            return await agent_core._execute_plan(plan, user_input, trace)  # type: ignore[arg-type]
        if intent.type == "action":
            # Simplified: treat as music request for week 1
            plan = {"action": "use_tool", "tool": "play_music", "mood": "fun"}
            return await agent_core._execute_plan(plan, user_input, trace)  # type: ignore[arg-type]
        # Conversational or unknown
        return agent_core._generate_conversational_response(user_input)
