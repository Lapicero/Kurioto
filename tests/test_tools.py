"""
Tests for Kurioto tools.
"""

import pytest

from kurioto.tools import MusicTool, SearchTool


class TestSearchTool:
    """Tests for the educational search tool."""

    @pytest.fixture
    def search_tool(self):
        """Create a SearchTool instance."""
        return SearchTool()

    @pytest.mark.asyncio
    async def test_search_dinosaurs(self, search_tool):
        """Test searching for dinosaurs."""
        result = await search_tool.execute(query="dinosaurs")
        assert result.success is True
        assert "topic" in result.data
        assert "content" in result.data
        assert len(result.data["content"]) > 0

    @pytest.mark.asyncio
    async def test_search_unknown_topic(self, search_tool):
        """Test searching for unknown topic gives fallback."""
        result = await search_tool.execute(query="quantum physics")
        assert result.success is True
        assert "fallback" in result.metadata.get("source", "")

    @pytest.mark.asyncio
    async def test_search_detail_levels(self, search_tool):
        """Test simple vs detailed responses."""
        simple = await search_tool.execute(query="space", detail_level="simple")
        detailed = await search_tool.execute(query="space", detail_level="detailed")

        assert simple.success is True
        assert detailed.success is True
        # Detailed should generally be longer
        # (though not strictly required in mock)


class TestMusicTool:
    """Tests for the music tool."""

    @pytest.fixture
    def music_tool(self):
        """Create a MusicTool instance."""
        return MusicTool()

    @pytest.mark.asyncio
    async def test_play_fun_music(self, music_tool):
        """Test playing fun music."""
        result = await music_tool.execute(mood="fun")
        assert result.success is True
        assert result.data["status"] == "playing"
        assert "song" in result.data

    @pytest.mark.asyncio
    async def test_play_calm_music(self, music_tool):
        """Test playing calm music."""
        result = await music_tool.execute(mood="calm")
        assert result.success is True
        assert result.data["playlist_mood"] == "calm"

    @pytest.mark.asyncio
    async def test_stop_music(self, music_tool):
        """Test stopping music."""
        result = await music_tool.execute(mood="fun", action="stop")
        assert result.success is True
        assert result.data["status"] == "stopped"

    @pytest.mark.asyncio
    async def test_pause_music(self, music_tool):
        """Test pausing music."""
        result = await music_tool.execute(mood="fun", action="pause")
        assert result.success is True
        assert result.data["status"] == "paused"
