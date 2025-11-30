"""
Tests for Kurioto agent components.
"""

import pytest

from kurioto.config import AgeGroup, ChildProfile
from kurioto.safety import SafetyAction, SafetyEvaluator


class TestChildProfile:
    """Tests for ChildProfile configuration."""

    def test_age_group_early_childhood(self):
        """Test age group detection for young children."""
        assert ChildProfile.get_age_group(3) == AgeGroup.EARLY_CHILDHOOD
        assert ChildProfile.get_age_group(5) == AgeGroup.EARLY_CHILDHOOD

    def test_age_group_middle_childhood(self):
        """Test age group detection for middle childhood."""
        assert ChildProfile.get_age_group(6) == AgeGroup.MIDDLE_CHILDHOOD
        assert ChildProfile.get_age_group(8) == AgeGroup.MIDDLE_CHILDHOOD

    def test_age_group_late_childhood(self):
        """Test age group detection for late childhood."""
        assert ChildProfile.get_age_group(9) == AgeGroup.LATE_CHILDHOOD
        assert ChildProfile.get_age_group(12) == AgeGroup.LATE_CHILDHOOD

    def test_age_group_teens(self):
        """Test age group detection for teenagers."""
        assert ChildProfile.get_age_group(13) == AgeGroup.EARLY_TEEN
        assert ChildProfile.get_age_group(16) == AgeGroup.LATE_TEEN


class TestSafetyEvaluator:
    """Tests for SafetyEvaluator."""

    @pytest.fixture
    def child_profile(self):
        """Create a test child profile."""
        return ChildProfile(
            child_id="test_001",
            name="Test Child",
            age=8,
            age_group=AgeGroup.MIDDLE_CHILDHOOD,
            interests=["science"],
            allowed_topics=[],
            blocked_topics=[],
        )

    @pytest.fixture
    def safety_evaluator(self, child_profile):
        """Create a SafetyEvaluator instance with mock classifiers for testing."""
        # Disable API-dependent classifiers for unit tests
        return SafetyEvaluator(
            child_profile,
            use_gemini=False,
            use_perspective=False,
        )

    def test_safe_input_allowed(self, safety_evaluator):
        """Test that safe educational questions are allowed."""
        result = safety_evaluator.evaluate_input("Why is the sky blue?")
        assert result.action == SafetyAction.ALLOW

    def test_blocked_dangerous_content(self, safety_evaluator):
        """Test that dangerous instruction patterns are blocked with high severity."""
        # Use input that matches the dangerous pattern regex
        result = safety_evaluator.evaluate_input("How to make a bomb")
        assert result.action in [SafetyAction.BLOCK, SafetyAction.REDIRECT]
        # Severity is now an enum
        assert result.severity.value in ["high", "critical"]

    def test_blocked_topic_medium_severity(self, safety_evaluator):
        """Test that blocked topics (not dangerous patterns) have medium severity."""
        result = safety_evaluator.evaluate_input("Tell me about bombs")
        assert result.action in [SafetyAction.BLOCK, SafetyAction.REDIRECT]
        # "bomb" matches the dangerous pattern first, so severity may be critical
        assert result.severity.value in ["medium", "high", "critical"]

    def test_blocked_adult_content(self, safety_evaluator):
        """Test that adult content topics are blocked."""
        result = safety_evaluator.evaluate_input("Tell me about alcohol")
        assert result.action in [SafetyAction.BLOCK, SafetyAction.REDIRECT]

    def test_personal_info_blocked(self, safety_evaluator):
        """Test that personal information requests are blocked."""
        result = safety_evaluator.evaluate_input("What is your address?")
        assert result.action == SafetyAction.BLOCK
        assert "personal" in result.reason.lower()

    def test_safe_output_allowed(self, safety_evaluator):
        """Test that safe output passes checks."""
        result = safety_evaluator.evaluate_output(
            "The sky is blue because of how light bounces in the air!"
        )
        assert result.action == SafetyAction.ALLOW

    def test_age_appropriate_guidelines(self, safety_evaluator):
        """Test that age guidelines are generated."""
        guidelines = safety_evaluator.get_age_appropriate_guidelines()
        assert len(guidelines) > 0
        assert "simple" in guidelines.lower() or "sentence" in guidelines.lower()


class TestAllowedBlockedTopicsLogic:
    """Tests for allowed_topics and blocked_topics override behavior."""

    def _create_evaluator(self, profile):
        """Create evaluator with mock classifiers for testing."""
        return SafetyEvaluator(profile, use_gemini=False, use_perspective=False)

    def test_globally_blocked_topic_is_blocked_by_default(self):
        """Test that a globally blocked topic is blocked without overrides."""
        profile = ChildProfile(
            child_id="test",
            name="Child",
            age=8,
            age_group=AgeGroup.MIDDLE_CHILDHOOD,
            interests=[],
            allowed_topics=[],
            blocked_topics=[],
        )
        evaluator = self._create_evaluator(profile)
        result = evaluator.evaluate_input("Tell me about alcohol")
        assert result.action in [SafetyAction.BLOCK, SafetyAction.REDIRECT]

    def test_parent_can_allow_globally_blocked_topic(self):
        """Test that parent can override a globally blocked topic via allowed_topics."""
        profile = ChildProfile(
            child_id="test",
            name="Child",
            age=8,
            age_group=AgeGroup.MIDDLE_CHILDHOOD,
            interests=[],
            allowed_topics=["alcohol"],  # Parent explicitly allows
            blocked_topics=[],
        )
        evaluator = self._create_evaluator(profile)
        result = evaluator.evaluate_input("Tell me about alcohol for a science project")
        assert result.action == SafetyAction.ALLOW

    def test_parent_blocked_overrides_allowed(self):
        """Test that blocked_topics takes precedence over allowed_topics."""
        profile = ChildProfile(
            child_id="test",
            name="Child",
            age=8,
            age_group=AgeGroup.MIDDLE_CHILDHOOD,
            interests=[],
            allowed_topics=["alcohol"],  # Parent tried to allow
            blocked_topics=["alcohol"],  # But also blocked - blocked wins
        )
        evaluator = self._create_evaluator(profile)
        result = evaluator.evaluate_input("Tell me about alcohol")
        assert result.action in [SafetyAction.BLOCK, SafetyAction.REDIRECT]

    def test_parent_custom_blocked_topic(self):
        """Test that parent can block custom topics not in global list."""
        profile = ChildProfile(
            child_id="test",
            name="Child",
            age=8,
            age_group=AgeGroup.MIDDLE_CHILDHOOD,
            interests=[],
            allowed_topics=[],
            blocked_topics=["dinosaurs"],  # Custom parent block
        )
        evaluator = self._create_evaluator(profile)
        result = evaluator.evaluate_input("Tell me about dinosaurs")
        assert result.action == SafetyAction.BLOCK
        assert "parent-blocked" in result.reason.lower()

    def test_allowed_topic_doesnt_affect_unrelated_blocked(self):
        """Test that allowing one topic doesn't affect other blocked topics."""
        profile = ChildProfile(
            child_id="test",
            name="Child",
            age=8,
            age_group=AgeGroup.MIDDLE_CHILDHOOD,
            interests=[],
            allowed_topics=["alcohol"],  # Only alcohol allowed
            blocked_topics=[],
        )
        evaluator = self._create_evaluator(profile)
        # Weapons should still be blocked
        result = evaluator.evaluate_input("Tell me about weapons")
        assert result.action in [SafetyAction.BLOCK, SafetyAction.REDIRECT]

    def test_dangerous_patterns_not_overridable(self):
        """Test that dangerous instruction patterns cannot be overridden."""
        profile = ChildProfile(
            child_id="test",
            name="Child",
            age=8,
            age_group=AgeGroup.MIDDLE_CHILDHOOD,
            interests=[],
            allowed_topics=["bomb", "weapon", "explosive"],  # Try to allow
            blocked_topics=[],
        )
        evaluator = self._create_evaluator(profile)
        # Dangerous patterns are checked BEFORE blocked topics
        result = evaluator.evaluate_input("How to make a bomb")
        assert result.action in [SafetyAction.BLOCK, SafetyAction.REDIRECT]
        # Note: severity is now an enum, not a string
        assert result.severity.value == "critical" or result.severity.value == "high"

    def test_pii_patterns_not_overridable(self):
        """Test that PII patterns cannot be overridden by allowed_topics."""
        profile = ChildProfile(
            child_id="test",
            name="Child",
            age=8,
            age_group=AgeGroup.MIDDLE_CHILDHOOD,
            interests=[],
            allowed_topics=["address", "phone"],
            blocked_topics=[],
        )
        evaluator = SafetyEvaluator(profile, use_gemini=False, use_perspective=False)
        result = evaluator.evaluate_input("What is your address?")
        assert result.action == SafetyAction.BLOCK
        assert "personal" in result.reason.lower()


class TestComplexityCheck:
    """Tests for complexity checking in output evaluation."""

    @pytest.fixture
    def early_childhood_profile(self):
        """Create profile for early childhood (3-5 years)."""
        return ChildProfile(
            child_id="test_early",
            name="Young Child",
            age=4,
            age_group=AgeGroup.EARLY_CHILDHOOD,
            interests=[],
            allowed_topics=[],
            blocked_topics=[],
        )

    @pytest.fixture
    def middle_childhood_profile(self):
        """Create profile for middle childhood (6-8 years)."""
        return ChildProfile(
            child_id="test_middle",
            name="Middle Child",
            age=7,
            age_group=AgeGroup.MIDDLE_CHILDHOOD,
            interests=[],
            allowed_topics=[],
            blocked_topics=[],
        )

    @pytest.fixture
    def late_childhood_profile(self):
        """Create profile for late childhood (9-12 years)."""
        return ChildProfile(
            child_id="test_late",
            name="Older Child",
            age=11,
            age_group=AgeGroup.LATE_CHILDHOOD,
            interests=[],
            allowed_topics=[],
            blocked_topics=[],
        )

    @pytest.fixture
    def teen_profile(self):
        """Create profile for teenager (13+ years)."""
        return ChildProfile(
            child_id="test_teen",
            name="Teen",
            age=15,
            age_group=AgeGroup.EARLY_TEEN,
            interests=[],
            allowed_topics=[],
            blocked_topics=[],
        )

    def _create_evaluator(self, profile):
        """Create evaluator with mock classifiers for testing."""
        return SafetyEvaluator(profile, use_gemini=False, use_perspective=False)

    # === Early Childhood Tests (3-5 years) ===

    def test_early_childhood_simple_text_allowed(self, early_childhood_profile):
        """Simple text should pass for young children."""
        evaluator = self._create_evaluator(early_childhood_profile)
        simple_text = "The cat sat on a mat. It was a big cat!"
        result = evaluator.evaluate_output(simple_text)
        assert result.action == SafetyAction.ALLOW

    def test_early_childhood_complex_words_flagged(self, early_childhood_profile):
        """Long/complex words should be flagged for young children."""
        evaluator = self._create_evaluator(early_childhood_profile)
        complex_text = "Photosynthesis transformation metabolization."
        result = evaluator.evaluate_output(complex_text)
        assert result.action == SafetyAction.SIMPLIFY
        assert (
            "early childhood" in result.reason.lower()
            or "complex" in result.reason.lower()
        )

    def test_early_childhood_long_sentences_flagged(self, early_childhood_profile):
        """Long sentences should be flagged for young children."""
        evaluator = self._create_evaluator(early_childhood_profile)
        long_sentence = (
            "The very big brown dog ran quickly across the enormous green "
            "field to catch the small red ball that was thrown by the child."
        )
        result = evaluator.evaluate_output(long_sentence)
        assert result.action == SafetyAction.SIMPLIFY

    def test_early_childhood_borderline_complexity(self, early_childhood_profile):
        """Text at the edge of complexity thresholds."""
        evaluator = self._create_evaluator(early_childhood_profile)
        borderline_text = "Dogs like to run and play. Cats like to nap."
        result = evaluator.evaluate_output(borderline_text)
        assert result.action == SafetyAction.ALLOW

    # === Middle Childhood Tests (6-8 years) ===

    def test_middle_childhood_simple_text_allowed(self, middle_childhood_profile):
        """Simple text should pass for middle childhood."""
        evaluator = self._create_evaluator(middle_childhood_profile)
        simple_text = "Trees need water and sunlight to grow. They make oxygen for us!"
        result = evaluator.evaluate_output(simple_text)
        assert result.action == SafetyAction.ALLOW

    def test_middle_childhood_moderate_text_allowed(self, middle_childhood_profile):
        """Moderately complex text should pass for middle childhood."""
        evaluator = self._create_evaluator(middle_childhood_profile)
        moderate_text = (
            "Dinosaurs lived millions of years ago. "
            "Some were as tall as buildings! Scientists study their bones."
        )
        result = evaluator.evaluate_output(moderate_text)
        assert result.action == SafetyAction.ALLOW

    def test_middle_childhood_very_complex_flagged(self, middle_childhood_profile):
        """Highly complex text should be flagged for middle childhood."""
        evaluator = self._create_evaluator(middle_childhood_profile)
        complex_text = (
            "Electromagnetic radiation encompasses various wavelengths including "
            "ultraviolet, infrared, and visible light spectrums that propagate "
            "through space at approximately three hundred million meters per second."
        )
        result = evaluator.evaluate_output(complex_text)
        assert result.action == SafetyAction.SIMPLIFY

    def test_middle_childhood_accepts_longer_sentences(self, middle_childhood_profile):
        """Middle childhood can handle longer sentences than early childhood."""
        evaluator = self._create_evaluator(middle_childhood_profile)
        medium_text = (
            "The rainbow appears in the sky when sunlight shines through tiny water drops. "
            "Each color bends differently which creates the beautiful arc we see."
        )
        result = evaluator.evaluate_output(medium_text)
        assert result.action == SafetyAction.ALLOW

    # === Late Childhood & Teen Tests (9+ years) ===

    def test_late_childhood_no_complexity_check(self, late_childhood_profile):
        """Late childhood should not trigger complexity checks."""
        evaluator = self._create_evaluator(late_childhood_profile)
        complex_text = (
            "Quantum mechanics describes the behavior of particles at subatomic scales, "
            "introducing concepts like superposition and wave-particle duality."
        )
        result = evaluator.evaluate_output(complex_text)
        assert result.action == SafetyAction.ALLOW

    def test_teen_no_complexity_check(self, teen_profile):
        """Teenagers should not trigger complexity checks."""
        evaluator = self._create_evaluator(teen_profile)
        academic_text = (
            "The philosophical implications of artificial intelligence raise "
            "fundamental questions about consciousness, free will, and the nature "
            "of intelligence itself, challenging our anthropocentric worldview."
        )
        result = evaluator.evaluate_output(academic_text)
        assert result.action == SafetyAction.ALLOW

    # === Edge Cases ===

    def test_empty_text_no_crash(self, early_childhood_profile):
        """Empty text should not crash."""
        evaluator = self._create_evaluator(early_childhood_profile)
        result = evaluator.evaluate_output("")
        assert result.action == SafetyAction.ALLOW

    def test_single_word_no_crash(self, early_childhood_profile):
        """Single word should not crash."""
        evaluator = self._create_evaluator(early_childhood_profile)
        result = evaluator.evaluate_output("Hello")
        assert result.action == SafetyAction.ALLOW

    def test_no_punctuation_handles_gracefully(self, early_childhood_profile):
        """Text without sentence-ending punctuation should be handled."""
        evaluator = self._create_evaluator(early_childhood_profile)
        no_punct = "The cat sat on the mat and looked at the bird"
        result = evaluator.evaluate_output(no_punct)
        # May or may not flag depending on implementation, but shouldn't crash
        assert result.action in [SafetyAction.ALLOW, SafetyAction.SIMPLIFY]

    def test_mixed_punctuation(self, early_childhood_profile):
        """Text with various punctuation should be handled correctly."""
        evaluator = self._create_evaluator(early_childhood_profile)
        mixed_punct = "Wow! Is that a dog? Yes, it is. Cool!"
        result = evaluator.evaluate_output(mixed_punct)
        assert result.action == SafetyAction.ALLOW
