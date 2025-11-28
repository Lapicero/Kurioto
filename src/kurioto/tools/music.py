"""
Music tool for Kurioto (mock implementation).

Provides music playback functionality with child-safe content filtering.
In production, this would integrate with Spotify or similar services.
"""

from __future__ import annotations

import random
from typing import Any

from kurioto.logging import get_logger
from kurioto.tools.base import BaseTool, ToolResult

logger = get_logger(__name__)


# Mock music library - child-safe playlists
MUSIC_LIBRARY = {
    "fun": [
        {"title": "Happy Dance", "artist": "Kids Bop", "duration": "2:45"},
        {"title": "Jump Around", "artist": "Children's Favorites", "duration": "3:12"},
        {"title": "Sunny Day", "artist": "Rainbow Singers", "duration": "2:58"},
    ],
    "calm": [
        {"title": "Peaceful Dreams", "artist": "Lullaby Land", "duration": "4:15"},
        {"title": "Ocean Waves", "artist": "Nature Sounds", "duration": "5:00"},
        {"title": "Starlight", "artist": "Bedtime Beats", "duration": "3:45"},
    ],
    "learning": [
        {"title": "ABC Alphabet Song", "artist": "Learning Tunes", "duration": "2:30"},
        {"title": "Count to Ten", "artist": "Math Melodies", "duration": "2:15"},
        {
            "title": "Colors of the Rainbow",
            "artist": "Science Singers",
            "duration": "2:48",
        },
    ],
    "adventure": [
        {"title": "Pirate Ship", "artist": "Adventure Kids", "duration": "3:22"},
        {"title": "Space Explorer", "artist": "Cosmic Tunes", "duration": "3:55"},
        {"title": "Jungle Safari", "artist": "Wild Beats", "duration": "3:10"},
    ],
}


class MusicTool(BaseTool):
    """
    Music playback tool with child-safe content.

    This is a mock implementation that simulates music playback.
    In production, this would integrate with Spotify, Apple Music,
    or another music service with parental controls.
    """

    @property
    def name(self) -> str:
        return "play_music"

    @property
    def description(self) -> str:
        return (
            "Play music for the child. Can play songs by mood (fun, calm, learning, adventure) "
            "or search for specific child-friendly songs. All music is pre-approved and safe."
        )

    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "mood": {
                    "type": "string",
                    "enum": ["fun", "calm", "learning", "adventure"],
                    "description": "The mood or type of music to play",
                },
                "action": {
                    "type": "string",
                    "enum": ["play", "pause", "skip", "stop"],
                    "description": "Playback action to perform",
                    "default": "play",
                },
            },
            "required": ["mood"],
        }

    async def execute(
        self,
        mood: str = "fun",
        action: str = "play",
    ) -> ToolResult:
        """
        Execute music playback command.

        Args:
            mood: Type of music to play
            action: Playback action

        Returns:
            ToolResult with playback status
        """
        logger.info("music_execute", mood=mood, action=action)

        if action == "stop":
            return ToolResult(
                success=True,
                data={"status": "stopped", "message": "Music stopped."},
            )

        if action == "pause":
            return ToolResult(
                success=True,
                data={"status": "paused", "message": "Music paused."},
            )

        # Get playlist for mood
        playlist = MUSIC_LIBRARY.get(mood, MUSIC_LIBRARY["fun"])

        # Select a random song (in production, this would be smarter)
        song = random.choice(playlist)

        return ToolResult(
            success=True,
            data={
                "status": "playing",
                "song": song,
                "message": f"Now playing '{song['title']}' by {song['artist']}!",
                "playlist_mood": mood,
            },
            metadata={"mock": True},
        )
