"""
Main SafetyEvaluator that integrates the multi-layer safety system.

This module provides backwards-compatible interface while using
the new multi-layer safety architecture internally.
"""

from __future__ import annotations

from typing import Any

from kurioto.config import AgeGroup, ChildProfile
from kurioto.logging import get_logger
from kurioto.safety.base import (
    SafetyAction,
    SafetyCategory,
    SafetyResult,
    SafetySeverity,
)
from kurioto.safety.multi_layer import MultiLayerResult, MultiLayerSafetyEvaluator

logger = get_logger(__name__)


class SafetyEvaluator:
    """
    Main safety evaluator with multi-layer architecture.

    This class provides a high-level interface for safety evaluation
    while internally using multiple specialized classifiers:

    1. Regex blocklist (fast first pass)
    2. Perspective API (toxicity detection)
    3. Gemini (semantic analysis)
    4. Human review queue (edge cases)

    For backwards compatibility, the interface matches the original
    SafetyEvaluator while providing enhanced safety coverage.
    """

    def __init__(
        self,
        child_profile: ChildProfile,
        use_gemini: bool = True,
        use_perspective: bool = True,
        use_mock_perspective: bool = False,
    ):
        """
        Initialize the safety evaluator.

        Args:
            child_profile: Profile of the child user
            use_gemini: Enable Gemini classifier (requires API key)
            use_perspective: Enable Perspective API (requires API key)
            use_mock_perspective: Use mock Perspective for testing
        """
        self.profile = child_profile

        # Initialize the multi-layer evaluator
        self._multi_layer = MultiLayerSafetyEvaluator(
            child_profile=child_profile,
            use_gemini=use_gemini,
            use_perspective=use_perspective,
            use_mock_perspective=use_mock_perspective,
        )

        logger.info(
            "safety_evaluator_init",
            child_id=child_profile.child_id,
            age_group=child_profile.age_group.value,
            multi_layer=True,
        )

    def evaluate_input(self, user_input: str) -> SafetyResult:
        """
        Evaluate user input for safety concerns.

        This is the synchronous interface for backwards compatibility.
        Internally runs the async multi-layer evaluation.
        """
        import asyncio

        try:
            loop = asyncio.get_running_loop()
            # Already in an async context, create a new thread
            import concurrent.futures

            with concurrent.futures.ThreadPoolExecutor() as executor:
                future = executor.submit(
                    asyncio.run, self._multi_layer.evaluate(user_input)
                )
                result = future.result()
        except RuntimeError:
            # No event loop running, safe to use asyncio.run
            result = asyncio.run(self._multi_layer.evaluate(user_input))

        return result.to_safety_result()

    async def evaluate_input_async(self, user_input: str) -> SafetyResult:
        """
        Async version of evaluate_input.

        Use this when already in an async context for better performance.
        """
        result = await self._multi_layer.evaluate(user_input)
        return result.to_safety_result()

    def evaluate_output(self, response: str) -> SafetyResult:
        """
        Evaluate agent output for safety before sending to child.

        Synchronous interface for backwards compatibility.
        """
        import asyncio

        try:
            loop = asyncio.get_running_loop()
            # Already in an async context, create a new thread
            import concurrent.futures

            with concurrent.futures.ThreadPoolExecutor() as executor:
                future = executor.submit(
                    asyncio.run, self._multi_layer.evaluate_output(response)
                )
                result = future.result()
        except RuntimeError:
            # No event loop running, safe to use asyncio.run
            result = asyncio.run(self._multi_layer.evaluate_output(response))

        return result.to_safety_result()

    async def evaluate_output_async(self, response: str) -> SafetyResult:
        """
        Async version of evaluate_output.
        """
        result = await self._multi_layer.evaluate_output(response)
        return result.to_safety_result()

    def get_age_appropriate_guidelines(self) -> str:
        """Get guidelines for the LLM based on child's age group."""
        return self._multi_layer.get_age_appropriate_guidelines()

    async def get_detailed_evaluation(
        self, text: str, is_output: bool = False
    ) -> MultiLayerResult:
        """
        Get detailed multi-layer evaluation result.

        Use this when you need access to individual classifier results
        and full evaluation metadata.

        Args:
            text: The text to evaluate
            is_output: If True, evaluate as agent output

        Returns:
            MultiLayerResult with full evaluation details
        """
        if is_output:
            return await self._multi_layer.evaluate_output(text)
        return await self._multi_layer.evaluate(text)


# Legacy function for backwards compatibility
def create_safety_evaluator(
    child_profile: ChildProfile,
    **kwargs,
) -> SafetyEvaluator:
    """Create a safety evaluator with default settings."""
    return SafetyEvaluator(child_profile, **kwargs)
