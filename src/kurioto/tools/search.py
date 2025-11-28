"""
Search tool for educational content.

Provides child-safe educational search functionality, returning
age-appropriate information from a curated knowledge base.
"""

from __future__ import annotations

from typing import Any

from kurioto.logging import get_logger
from kurioto.tools.base import BaseTool, ToolResult

logger = get_logger(__name__)


# Mock educational knowledge base
# In production, this would connect to a real search API or vector DB
EDUCATIONAL_CORPUS = {
    "dinosaurs": {
        "simple": "Dinosaurs were amazing animals that lived millions of years ago! Some were as big as buildings, and some were as small as chickens.",
        "detailed": "Dinosaurs were a diverse group of reptiles that dominated Earth for over 160 million years during the Mesozoic Era. They ranged from the massive Argentinosaurus (over 30 meters long) to the tiny Microraptor (less than 1 meter).",
        "topics": ["T-Rex", "Triceratops", "fossils", "extinction", "paleontology"],
    },
    "space": {
        "simple": "Space is everything beyond Earth! It has stars, planets, and moons. Our planet Earth is like a tiny blue marble floating in space.",
        "detailed": "Space, or outer space, is the vast expanse that exists beyond Earth's atmosphere. It contains galaxies, stars, planets, moons, asteroids, and more. Our solar system is just one of billions in the Milky Way galaxy.",
        "topics": ["planets", "stars", "moon", "astronauts", "rockets", "solar system"],
    },
    "animals": {
        "simple": "Animals are living things that can move around! They come in all shapes and sizes - from tiny ants to huge whales.",
        "detailed": "Animals are multicellular organisms that form the biological kingdom Animalia. They are characterized by their ability to move, respond to their environment, and consume other organisms for energy.",
        "topics": ["mammals", "reptiles", "birds", "fish", "insects", "habitats"],
    },
    "weather": {
        "simple": "Weather is what's happening outside! Sometimes it's sunny, sometimes it rains, and sometimes it snows. The sun, air, and water work together to make weather.",
        "detailed": "Weather describes the state of the atmosphere at a specific place and time, including temperature, humidity, precipitation, wind, and cloud cover. It's driven by solar energy heating Earth unevenly.",
        "topics": ["rain", "snow", "clouds", "thunder", "seasons", "climate"],
    },
    "plants": {
        "simple": "Plants are living things that make their own food using sunlight! They give us oxygen to breathe and food to eat.",
        "detailed": "Plants are photosynthetic organisms that convert sunlight, water, and carbon dioxide into glucose and oxygen. They form the foundation of most ecosystems and are essential for life on Earth.",
        "topics": ["flowers", "trees", "photosynthesis", "seeds", "gardens", "forests"],
    },
    "autumn leaves": {
        "simple": "Trees drop their leaves in autumn to rest for winter, kind of like bedtime for plants! When spring comes, they wake up and grow new leaves.",
        "detailed": "In autumn, deciduous trees stop producing chlorophyll (the green pigment) as days get shorter. This reveals yellow and orange pigments that were hidden, and some trees also produce red pigments. Trees drop their leaves to conserve water and energy during winter.",
        "topics": ["seasons", "trees", "chlorophyll", "winter"],
    },
}


class SearchTool(BaseTool):
    """
    Educational search tool for child-safe information retrieval.

    Searches a curated knowledge base and returns age-appropriate
    information based on the child's profile.
    """

    @property
    def name(self) -> str:
        return "search_educational"

    @property
    def description(self) -> str:
        return (
            "Search for educational information on a topic. "
            "Returns child-friendly explanations about science, nature, "
            "animals, space, and other educational topics."
        )

    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "The topic or question to search for",
                },
                "detail_level": {
                    "type": "string",
                    "enum": ["simple", "detailed"],
                    "description": "Level of detail in the response",
                    "default": "simple",
                },
            },
            "required": ["query"],
        }

    async def execute(
        self,
        query: str,
        detail_level: str = "simple",
    ) -> ToolResult:
        """
        Search for educational content on the given topic.

        Args:
            query: The search query
            detail_level: "simple" or "detailed"

        Returns:
            ToolResult with educational content
        """
        logger.info("search_execute", query=query, detail_level=detail_level)

        query_lower = query.lower()

        # Search for matching topics
        for topic, content in EDUCATIONAL_CORPUS.items():
            if topic in query_lower or any(
                t in query_lower for t in content.get("topics", [])
            ):
                result_text = content.get(detail_level, content.get("simple", ""))

                return ToolResult(
                    success=True,
                    data={
                        "topic": topic,
                        "content": result_text,
                        "related_topics": content.get("topics", []),
                    },
                    metadata={
                        "source": "educational_corpus",
                        "detail_level": detail_level,
                    },
                )

        # No direct match found
        return ToolResult(
            success=True,
            data={
                "topic": query,
                "content": f"I don't have specific information about '{query}' in my knowledge base, but I'd love to help you learn about it! Could you tell me more about what you'd like to know?",
                "related_topics": [],
            },
            metadata={"source": "fallback", "detail_level": detail_level},
        )
