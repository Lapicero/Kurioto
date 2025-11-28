"""
Configuration management for Kurioto.

Handles environment variables, settings, and child profile configurations.
"""

from __future__ import annotations

import os
from enum import Enum
from functools import lru_cache
from pathlib import Path
from typing import Optional

from dotenv import load_dotenv
from pydantic import BaseModel, Field

# Load environment variables from .env file
load_dotenv()


class Environment(str, Enum):
    """Application environment."""

    DEVELOPMENT = "development"
    STAGING = "staging"
    PRODUCTION = "production"


class AgeGroup(str, Enum):
    """Child age groups for content adaptation."""

    EARLY_CHILDHOOD = "early_childhood"  # 3-5 years
    MIDDLE_CHILDHOOD = "middle_childhood"  # 6-8 years
    LATE_CHILDHOOD = "late_childhood"  # 9-12 years
    EARLY_TEEN = "early_teen"  # 13-15 years
    LATE_TEEN = "late_teen"  # 16-17 years


class ChildProfile(BaseModel):
    """
    Profile for a child user, containing age and preference information
    used for content adaptation and safety rules.
    """

    child_id: str = Field(..., description="Unique identifier for the child")
    name: str = Field(..., description="Child's display name")
    age: int = Field(..., ge=3, le=17, description="Child's age in years")
    age_group: AgeGroup = Field(..., description="Age group for content adaptation")
    interests: list[str] = Field(default_factory=list, description="Topics of interest")
    allowed_topics: list[str] = Field(
        default_factory=list, description="Explicitly allowed topics"
    )
    blocked_topics: list[str] = Field(
        default_factory=list, description="Explicitly blocked topics"
    )
    music_enabled: bool = Field(
        default=True, description="Whether music features are enabled"
    )
    max_session_minutes: int = Field(default=60, description="Maximum session duration")

    @classmethod
    def get_age_group(cls, age: int) -> AgeGroup:
        """Determine age group from age."""
        if age <= 5:
            return AgeGroup.EARLY_CHILDHOOD
        elif age <= 8:
            return AgeGroup.MIDDLE_CHILDHOOD
        elif age <= 12:
            return AgeGroup.LATE_CHILDHOOD
        elif age <= 15:
            return AgeGroup.EARLY_TEEN
        else:
            return AgeGroup.LATE_TEEN


class Settings(BaseModel):
    """
    Application settings loaded from environment variables.

    These settings control API keys, logging, and runtime behavior.
    """

    # API Keys
    google_api_key: str = Field(
        default_factory=lambda: os.getenv("GOOGLE_API_KEY", ""),
        description="Google AI / Gemini API key",
    )
    google_cloud_project: Optional[str] = Field(
        default_factory=lambda: os.getenv("GOOGLE_CLOUD_PROJECT"),
        description="Google Cloud project ID for Vertex AI",
    )

    # Runtime settings
    environment: Environment = Field(
        default_factory=lambda: Environment(os.getenv("ENVIRONMENT", "development")),
        description="Application environment",
    )
    log_level: str = Field(
        default_factory=lambda: os.getenv("LOG_LEVEL", "INFO"),
        description="Logging level",
    )

    # Agent settings
    model_name: str = Field(
        default="gemini-2.0-flash", description="Default Gemini model to use"
    )
    max_reasoning_steps: int = Field(
        default=10, description="Maximum steps in agent reasoning loop"
    )

    # Safety settings
    safety_check_enabled: bool = Field(
        default=True, description="Enable safety checks on all outputs"
    )
    strict_mode: bool = Field(
        default=True, description="Strict safety mode for younger children"
    )

    # Memory settings
    memory_enabled: bool = Field(default=True, description="Enable conversation memory")
    max_memory_entries: int = Field(
        default=100, description="Maximum memory entries to retain"
    )

    @property
    def is_development(self) -> bool:
        """Check if running in development mode."""
        return self.environment == Environment.DEVELOPMENT

    def validate_api_key(self) -> bool:
        """Validate that API key is set."""
        return bool(self.google_api_key and self.google_api_key != "your_api_key_here")


@lru_cache
def get_settings() -> Settings:
    """Get cached settings instance."""
    return Settings()


# Default child profile for demo/testing
DEFAULT_CHILD_PROFILE = ChildProfile(
    child_id="demo_child_001",
    name="Alex",
    age=8,
    age_group=AgeGroup.MIDDLE_CHILDHOOD,
    interests=["dinosaurs", "space", "animals", "music"],
    allowed_topics=["science", "nature", "art", "music", "stories"],
    blocked_topics=[],
    music_enabled=True,
    max_session_minutes=30,
)
