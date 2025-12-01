"""
Kurioto Agent - Main agent implementation.

This module contains the core KuriotoAgent class that orchestrates
all components: planner, tools, memory, and safety evaluator.
"""

from __future__ import annotations

from typing import Any

from kurioto.agents.orchestrator import OrchestratorAgent
from kurioto.agents.safety_agent import SafetyAgent
from kurioto.config import ChildProfile, Settings, get_settings
from kurioto.logging import TraceContext, get_logger
from kurioto.memory import MemoryManager
from kurioto.safety import SafetyAction, SafetySeverity
from kurioto.tools import (
    ImageSafetyTool,
    MusicTool,
    ParentDashboardTool,
    SearchTool,
)

logger = get_logger(__name__)


class KuriotoAgent:
    """
    Main Kurioto agent for child-safe AI interactions.

    Orchestrates multi-step reasoning with safety checks, tool usage,
    memory management, and age-appropriate response generation.

    This agent is designed to work with Google's ADK framework and
    Gemini models for production deployment.
    """

    def __init__(
        self,
        child_profile: ChildProfile,
        settings: Settings | None = None,
    ):
        """
        Initialize the Kurioto agent.

        Args:
            child_profile: Profile of the child user
            settings: Application settings (uses defaults if not provided)
        """
        self.settings = settings or get_settings()
        self.child_profile = child_profile

        # Initialize components
        self.memory = MemoryManager(
            child_id=child_profile.child_id,
            max_episodic_entries=self.settings.max_memory_entries,
        )
        # Week 2: SafetyAgent wrapping multi-layer safety + LLM semantic checks
        self.safety_agent = SafetyAgent(child_profile)

        # Week 1 addition: orchestrator for intent classification & routing
        self.orchestrator = OrchestratorAgent(child_profile)

        # Initialize tools
        self.tools = {
            "search_educational": SearchTool(),
            "play_music": MusicTool(),
            "parent_dashboard": ParentDashboardTool(),
            "analyze_image": ImageSafetyTool(),
        }

        logger.info(
            "agent_init",
            child_id=child_profile.child_id,
            child_name=child_profile.name,
            age_group=child_profile.age_group.value,
        )

    async def process_message(
        self,
        user_input: str,
        context: dict[str, Any] | None = None,
    ) -> str:
        """
        Process a user message and generate a response.

        This is the main entry point for handling child interactions.
        It performs safety checks, routes to appropriate tools,
        and generates age-appropriate responses.

        Args:
            user_input: The child's message
            context: Additional context (images, audio, etc.)

        Returns:
            Agent's response text
        """
        with TraceContext(
            operation="process_message",
            child_id=self.child_profile.child_id,
        ) as trace:
            # Store user message in memory
            self.memory.add_turn("user", user_input)
            trace.log_event("input_received", data={"length": len(user_input)})

            # Step 1: Safety check on input (pre-orchestration)
            safety_result = await self.safety_agent.pre_check(user_input)
            trace.log_safety_event(
                action=safety_result.action.value,
                reason=safety_result.reason,
                severity=safety_result.severity,
            )

            if safety_result.action == SafetyAction.BLOCK:
                response = self._get_block_response(safety_result)
                await self._log_safety_event(user_input, safety_result)
                self.memory.add_turn("assistant", response)
                return response

            if safety_result.action == SafetyAction.REDIRECT:
                response = (
                    safety_result.suggested_response or self._get_redirect_response()
                )
                await self._log_safety_event(user_input, safety_result)
                self.memory.add_turn("assistant", response)
                return response

            # If we should warn the parent but still proceed, log alert now
            if safety_result.action == SafetyAction.WARN_PARENT:
                await self._log_safety_event(user_input, safety_result)

            # Step 2: Always use orchestrator routing (heuristics if LLM unavailable)
            trace.log_reasoning_step(1, "Routing via orchestrator")
            try:
                response = await self.orchestrator.route(
                    user_input,
                    agent_core=self,
                    context={"trace": trace},
                )
            except Exception as e:  # Extremely rare; provide minimal fallback
                logger.error("orchestrator_fatal", error=str(e))
                response = self._generate_conversational_response(user_input)

            # Step 4: Safety check on output
            output_safety = await self.safety_agent.post_check(response)
            if output_safety.action != SafetyAction.ALLOW:
                trace.log_safety_event(
                    action="output_filtered",
                    reason=output_safety.reason,
                    severity=output_safety.severity,
                )
                response = self._get_safe_fallback_response()

            # Store response in memory
            self.memory.add_turn("assistant", response)

            # Log interaction for parent dashboard
            await self._log_interaction(user_input, response)

            return response

    async def _execute_plan(
        self,
        plan: dict[str, Any],
        user_input: str,
        trace: TraceContext | None,
    ) -> str:
        """Execute the planned action and generate a response."""
        action = plan.get("action")

        if action == "use_tool":
            tool_name = plan.get("tool")
            if tool_name and tool_name in self.tools:
                tool = self.tools[tool_name]

                # Build tool arguments
                tool_args = {}
                if tool_name == "search_educational":
                    tool_args["query"] = plan.get("query", user_input)
                    # Use simpler results for younger children
                    if self.child_profile.age <= 8:
                        tool_args["detail_level"] = "simple"
                elif tool_name == "play_music":
                    tool_args["mood"] = plan.get("mood", "fun")

                # Execute tool
                result = await tool.execute(**tool_args)
                if trace is not None:
                    trace.log_tool_call(
                        tool_name=tool_name,
                        inputs=tool_args,
                        outputs=result.data if result.success else None,
                        error=result.error,
                    )

                if result.success:
                    return self._format_tool_response(tool_name, result.data)
                else:
                    return self._get_error_response()

        # Conversational response (no tool needed)
        return self._generate_conversational_response(user_input)

    def _format_tool_response(self, tool_name: str, data: Any) -> str:
        """Format tool results into a child-friendly response."""
        if tool_name == "search_educational":
            content = data.get("content", "")
            related = data.get("related_topics", [])
            response = content
            if related and len(related) > 0:
                topics = ", ".join(related[:3])
                response += f" Would you like to learn more about {topics}?"
            return response

        elif tool_name == "play_music":
            return data.get("message", "Here's some music for you!")

        return str(data)

    def _generate_conversational_response(self, user_input: str) -> str:
        """
        Generate a conversational response without tools.

        In production, this would call the Gemini model with appropriate
        system prompts for age-appropriate conversation.
        """
        # TODO: These will be passed to the LLM when Gemini integration is added
        # - context: recent conversation history for coherent multi-turn dialogue
        # - guidelines: age-appropriate language rules for the system prompt
        _ = self.memory.get_conversation_context(5)  # noqa: F841
        _ = self.safety_agent.get_age_appropriate_guidelines()  # noqa: F841

        # For this mock implementation, return a friendly response
        greetings = ["hi", "hello", "hey"]
        if any(g in user_input.lower() for g in greetings):
            return f"Hi there, {self.child_profile.name}! How are you today? 😊"

        thanks = ["thank", "thanks"]
        if any(t in user_input.lower() for t in thanks):
            return "You're welcome! Is there anything else you'd like to explore?"

        # Default curious response
        return (
            "That's interesting! I'd love to help you learn more. "
            "Could you tell me a bit more about what you're curious about?"
        )

    def _get_block_response(self, safety_result) -> str:
        """Get a gentle response for blocked content."""
        return (
            "I'm not able to help with that, but I'd love to help you "
            "learn about something else! What are you curious about?"
        )

    def _get_redirect_response(self) -> str:
        """Get a redirect response for unsafe content."""
        return (
            "Let's explore something fun instead! "
            "Would you like to learn about space, dinosaurs, or animals?"
        )

    def _get_safe_fallback_response(self) -> str:
        """Get a safe fallback if output filtering triggers."""
        return (
            "Hmm, let me think of a better way to explain that! "
            "Could you ask me in a different way?"
        )

    def _get_error_response(self) -> str:
        """Get a friendly error response."""
        return "Oops! Something didn't work quite right. Let's try again!"

    async def _log_safety_event(self, user_input: str, safety_result) -> None:
        """Log a safety event to parent dashboard."""
        dashboard = self.tools["parent_dashboard"]
        await dashboard.execute(
            action="log_event",
            event_type="safety_alert",
            event_data={
                "input": user_input[:100],  # Truncate for privacy
                "action": safety_result.action.value,
                "reason": safety_result.reason,
                "severity": safety_result.severity,
            },
        )

        # Generate and log a structured parent alert when severity/action warrants
        try:
            should_alert = safety_result.action in {
                SafetyAction.BLOCK,
                SafetyAction.WARN_PARENT,
                SafetyAction.REDIRECT,
            } or safety_result.severity in {
                SafetySeverity.MEDIUM,
                SafetySeverity.HIGH,
                SafetySeverity.CRITICAL,
            }
            if should_alert:
                alert = await self.safety_agent.generate_parent_alert(
                    user_input, safety_result
                )
                await dashboard.execute(
                    action="log_event",
                    event_type="parent_alert",
                    event_data={
                        "child_id": self.child_profile.child_id,
                        "subject": alert.subject,
                        "message": alert.message,
                        "urgency": alert.urgency,
                        "follow_up_recommended": alert.follow_up_recommended,
                    },
                )
        except Exception as e:
            logger.warning("parent_alert_generation_failed", error=str(e))

        # Also log to memory for tracking
        self.memory.log_safety_event(
            event_type="blocked_request",
            description=safety_result.reason,
            severity=safety_result.severity,
            action_taken=safety_result.action.value,
        )

    async def _log_interaction(self, user_input: str, response: str) -> None:
        """Log interaction to parent dashboard."""
        dashboard = self.tools["parent_dashboard"]
        await dashboard.execute(
            action="log_event",
            event_type="interaction",
            event_data={
                "input_preview": user_input[:50],
                "response_preview": response[:50],
            },
        )

    def get_system_prompt(self) -> str:
        """
        Generate the system prompt for the LLM.

        This prompt instructs the model on how to interact with children
        based on their age group and safety requirements.
        """
        guidelines = self.safety_agent.get_age_appropriate_guidelines()
        interests = ", ".join(self.child_profile.interests) or "various topics"

        return f"""You are Kurioto, a friendly and safe AI companion for children.

You are talking with {self.child_profile.name}, who is {self.child_profile.age} years old.

IMPORTANT GUIDELINES:
{guidelines}

The child is interested in: {interests}

SAFETY RULES:
- Never discuss violence, weapons, drugs, or adult content
- Never ask for or reveal personal information
- If unsure about safety, err on the side of caution
- Always be encouraging, positive, and educational
- Keep responses concise and engaging

Remember: You are helping a child learn and explore the world safely!
"""
