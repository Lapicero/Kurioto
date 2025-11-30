"""
Tests for KuriotoAgent class.
"""

import pytest

from kurioto.agent import KuriotoAgent
from kurioto.config import AgeGroup, ChildProfile


class TestGenerateConversationalResponse:
    """Tests for _generate_conversational_response method."""

    @pytest.fixture
    def child_profile(self):
        """Create a test child profile."""
        return ChildProfile(
            child_id="test_001",
            name="Emma",
            age=8,
            age_group=AgeGroup.MIDDLE_CHILDHOOD,
            interests=["dinosaurs", "space"],
            allowed_topics=[],
            blocked_topics=[],
        )

    @pytest.fixture
    def agent(self, child_profile):
        """Create a test agent instance."""
        return KuriotoAgent(child_profile=child_profile)

    # Greeting tests
    def test_greeting_hi(self, agent):
        """Test response to 'hi' greeting."""
        response = agent._generate_conversational_response("hi")
        assert "Hi there" in response
        assert "Emma" in response
        assert "😊" in response

    def test_greeting_hello(self, agent):
        """Test response to 'hello' greeting."""
        response = agent._generate_conversational_response("hello")
        assert "Hi there" in response
        assert "Emma" in response

    def test_greeting_hey(self, agent):
        """Test response to 'hey' greeting."""
        response = agent._generate_conversational_response("hey")
        assert "Hi there" in response
        assert "Emma" in response

    def test_greeting_mixed_case(self, agent):
        """Test greetings are case-insensitive."""
        response = agent._generate_conversational_response("HELLO")
        assert "Hi there" in response
        assert "Emma" in response

    def test_greeting_in_sentence(self, agent):
        """Test greeting detection within a sentence."""
        response = agent._generate_conversational_response("Hi there friend!")
        assert "Hi there" in response
        assert "Emma" in response

    # Thanks tests
    def test_thanks_response(self, agent):
        """Test response to 'thanks' message."""
        response = agent._generate_conversational_response("thanks")
        assert "You're welcome" in response
        assert "anything else" in response.lower()

    def test_thank_you_response(self, agent):
        """Test response to 'thank you' message."""
        response = agent._generate_conversational_response("thank you so much!")
        assert "You're welcome" in response

    def test_thanks_mixed_case(self, agent):
        """Test thanks detection is case-insensitive."""
        response = agent._generate_conversational_response("THANKS!")
        assert "You're welcome" in response

    # Default response tests
    def test_default_response_for_unknown_input(self, agent):
        """Test default curious response for unrecognized input."""
        response = agent._generate_conversational_response("blueberry pancakes")
        assert "interesting" in response.lower() or "curious" in response.lower()
        assert "help" in response.lower() or "learn" in response.lower()

    def test_default_response_for_statement(self, agent):
        """Test default response for a simple statement."""
        response = agent._generate_conversational_response("I like cats")
        assert len(response) > 20  # Should be a meaningful response

    def test_default_response_encourages_elaboration(self, agent):
        """Test default response encourages the child to elaborate."""
        response = agent._generate_conversational_response("something random")
        assert "?" in response  # Should ask a follow-up question

    # Child name personalization tests
    def test_greeting_uses_child_name(self, agent):
        """Test that greetings include the child's name."""
        response = agent._generate_conversational_response("hi")
        assert "Emma" in response

    def test_different_child_name(self):
        """Test greeting with a different child name."""
        profile = ChildProfile(
            child_id="test_002",
            name="Lucas",
            age=6,
            age_group=AgeGroup.MIDDLE_CHILDHOOD,
            interests=[],
            allowed_topics=[],
            blocked_topics=[],
        )
        agent = KuriotoAgent(child_profile=profile)
        response = agent._generate_conversational_response("hello")
        assert "Lucas" in response

    # Priority tests (greeting takes precedence over thanks if both present)
    def test_greeting_takes_priority_over_thanks(self, agent):
        """Test that greeting response takes priority when both patterns match."""
        response = agent._generate_conversational_response("hi thanks")
        # Greetings are checked first, so should get greeting response
        assert "Hi there" in response

    # Edge cases
    def test_empty_string(self, agent):
        """Test handling of empty input string."""
        response = agent._generate_conversational_response("")
        assert len(response) > 0  # Should return default response

    def test_whitespace_only(self, agent):
        """Test handling of whitespace-only input."""
        response = agent._generate_conversational_response("   ")
        assert len(response) > 0  # Should return default response

    def test_special_characters(self, agent):
        """Test handling of input with special characters."""
        response = agent._generate_conversational_response("!@#$%^&*()")
        assert len(response) > 0  # Should return default response

    def test_very_long_input(self, agent):
        """Test handling of very long input."""
        long_input = "I really want to know " * 100
        response = agent._generate_conversational_response(long_input)
        assert len(response) > 0
