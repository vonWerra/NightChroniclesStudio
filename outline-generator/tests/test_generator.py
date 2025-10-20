# tests/test_generator.py
# -*- coding: utf-8 -*-
"""Unit tests for the outline generator system."""

import pytest
import asyncio
from pathlib import Path
import json
from unittest.mock import Mock, AsyncMock, patch
import tempfile

from src.config import Config, load_config
from src.models import OutlineJSON, Episode, MSPItem, EpisodeRuntime
from src.cache import CacheManager
from src.monitor import Monitor
from src.api_client import APIClient
from src.generator import OutlineGenerator


class TestConfig:
    """Test configuration module."""

    def test_config_validation(self):
        """Test configuration validation."""
        # Valid config
        config = Config(
            topic="Test Topic",
            languages=["CS", "EN"],
            episodes="auto",
            episode_minutes=60,
            episode_count_range={"min": 3, "max": 6},
            msp_per_episode=5,
            msp_max_words=15,
            description_max_sentences=4,
            series_context_sentences={"min": 1, "max": 3},
            ordering="chronological",
            tolerance_min=55,
            tolerance_max=65,
            sources={"per_episode": {"min": 3, "max": 5}, "format": "name-only"}
        )
        assert config.topic == "Test Topic"
        assert len(config.languages) == 2

    def test_invalid_tolerance(self):
        """Test that invalid tolerances raise error."""
        with pytest.raises(Exception):
            Config(
                topic="Test",
                languages=["CS"],
                episodes="auto",
                episode_minutes=60,
                episode_count_range={"min": 3, "max": 6},
                msp_per_episode=5,
                msp_max_words=15,
                description_max_sentences=4,
                series_context_sentences={"min": 1, "max": 3},
                ordering="chronological",
                tolerance_min=65,  # Min > Max
                tolerance_max=55,
                sources={"per_episode": {"min": 3, "max": 5}, "format": "name-only"}
            )

    def test_flatten_config(self):
        """Test configuration flattening."""
        config = Config(
            topic="Test Topic",
            languages=["CS"],
            episodes=5,
            episode_minutes=60,
            episode_count_range={"min": 3, "max": 6},
            msp_per_episode=5,
            msp_max_words=15,
            description_max_sentences=4,
            series_context_sentences={"min": 1, "max": 3},
            ordering="chronological",
            tolerance_min=55,
            tolerance_max=65,
            sources={"per_episode": {"min": 3, "max": 5}, "format": "name-only"}
        )

        flat = config.flatten()
        assert flat["TOPIC"] == "Test Topic"
        assert flat["EPISODES"] == "5"
        assert flat["SOURCES.PER_EPISODE.min"] == "3"


class TestModels:
    """Test data models."""

    def test_episode_runtime_validation(self):
        """Test episode runtime validation."""
        runtime = EpisodeRuntime(
            segments=["12:00", "13:30", "10:45"],
            sum_minutes=36
        )
        assert len(runtime.segments) == 3

        # Invalid format
        with pytest.raises(Exception):
            EpisodeRuntime(
                segments=["12:00", "invalid"],
                sum_minutes=20
            )

    def test_msp_item_validation(self):
        """Test MSP item validation."""
        msp = MSPItem(
            timestamp="12:30",
            text="Valid text",
            sources_segment=["Source 1", "Source 2"]
        )
        assert msp.timestamp == "12:30"

        # Invalid timestamp
        with pytest.raises(Exception):
            MSPItem(
                timestamp="invalid",
                text="Text",
                sources_segment=[]
            )

    def test_episode_source_validation(self):
        """Test that MSP sources must exist in episode sources."""
        with pytest.raises(Exception):
            Episode(
                index=1,
                title="Test Episode",
                description=["Test description"],
                msp=[
                    MSPItem(
                        timestamp="00:00",
                        text="Test",
                        sources_segment=["Unknown Source"]  # Not in sources_used
                    )
                ],
                runtime=EpisodeRuntime(segments=["12:00"], sum_minutes=12),
                viewer_takeaway="Test takeaway",
                sources_used=["Known Source"],
                confidence_note="Test note"
            )

    def test_outline_json_validation(self):
        """Test complete outline validation."""
        outline = OutlineJSON(
            language="CS",
            topic="Test Topic",
            series_title="Test Series",
            series_context=["Context sentence 1"],
            episodes=[
                Episode(
                    index=1,
                    title="Episode 1",
                    description=["Description"],
                    msp=[
                        MSPItem(
                            timestamp="00:00",
                            text="MSP text",
                            sources_segment=["Source 1"]
                        )
                    ],
                    runtime=EpisodeRuntime(segments=["10:00"], sum_minutes=10),
                    viewer_takeaway="Takeaway",
                    sources_used=["Source 1"],
                    confidence_note="Note"
                )
            ]
        )

        assert outline.get_total_runtime() == 10
        assert outline.get_total_msp_count() == 1
        assert outline.get_unique_sources() == ["Source 1"]


class TestCache:
    """Test cache manager."""

    def test_cache_set_get(self):
        """Test basic cache operations."""
        with tempfile.TemporaryDirectory() as tmpdir:
            cache = CacheManager(
                cache_dir=Path(tmpdir),
                enabled=True,
                ttl_hours=1
            )

            # Set value
            cache.set("test_key", {"data": "test_value"})

            # Get value
            result = cache.get("test_key")
            assert result == {"data": "test_value"}

            # Non-existent key
            result = cache.get("non_existent")
            assert result is None

    def test_cache_disabled(self):
        """Test that disabled cache returns None."""
        with tempfile.TemporaryDirectory() as tmpdir:
            cache = CacheManager(
                cache_dir=Path(tmpdir),
                enabled=False
            )

            cache.set("test_key", "test_value")
            result = cache.get("test_key")
            assert result is None

    def test_cache_stats(self):
        """Test cache statistics."""
        with tempfile.TemporaryDirectory() as tmpdir:
            cache = CacheManager(
                cache_dir=Path(tmpdir),
                enabled=True
            )

            cache.set("key1", "value1")
            cache.set("key2", "value2")

            stats = cache.get_stats()
            assert stats['enabled'] is True
            assert stats['total_entries'] == 2


class TestMonitor:
    """Test monitoring functionality."""

    def test_api_call_recording(self):
        """Test recording API calls."""
        monitor = Monitor(save_to_file=False)
        monitor.start()

        monitor.record_api_call(
            model="gpt-4",
            tokens=1000,
            duration=2.5,
            success=True
        )

        stats = monitor.get_stats()
        assert stats['api_calls'] == 1
        assert stats['successful_calls'] == 1
        assert stats['total_tokens'] == 1000

    def test_cache_recording(self):
        """Test cache hit/miss recording."""
        monitor = Monitor(save_to_file=False)

        monitor.record_cache_hit()
        monitor.record_cache_hit()
        monitor.record_cache_miss()

        stats = monitor.get_stats()
        assert stats['cache_hits'] == 2
        assert stats['cache_misses'] == 1
        assert stats['cache_hit_rate'] == pytest.approx(66.67, 0.1)


@pytest.mark.asyncio
class TestAPIClient:
    """Test API client."""

    async def test_api_call_with_retry(self):
        """Test API call with retry logic."""
        with patch('aiohttp.ClientSession.post') as mock_post:
            # Setup mock response
            mock_response = AsyncMock()
            mock_response.raise_for_status = Mock()
            mock_response.json = AsyncMock(return_value={
                'choices': [{
                    'message': {'content': '{"test": "response"}'}
                }],
                'usage': {'total_tokens': 100}
            })
            mock_post.return_value.__aenter__.return_value = mock_response

            client = APIClient(
                api_key="test_key",
                model="gpt-4"
            )

            result = await client.generate("test prompt")
            assert '{"test": "response"}' in result


@pytest.mark.asyncio
class TestGenerator:
    """Test outline generator."""

    async def test_generate_for_language(self):
        """Test generation for single language."""
        with tempfile.TemporaryDirectory() as tmpdir:
            config = Config(
                topic="Test Topic",
                languages=["CS"],
                episodes=2,
                episode_minutes=60,
                episode_count_range={"min": 2, "max": 4},
                msp_per_episode=3,
                msp_max_words=15,
                description_max_sentences=3,
                series_context_sentences={"min": 1, "max": 2},
                ordering="chronological",
                tolerance_min=55,
                tolerance_max=65,
                sources={"per_episode": {"min": 2, "max": 3}, "format": "name-only"},
                api_key="test_key"
            )

            template = "Test template {{TOPIC}}"

            generator = OutlineGenerator(
                config=config,
                template=template,
                output_dir=Path(tmpdir),
                use_cache=False
            )

            # Mock API response
            mock_response = {
                "language": "CS",
                "topic": "Test Topic",
                "series_title": "Test Series",
                "series_context": ["Context"],
                "episodes": []
            }

            with patch.object(generator.api_client, 'generate',
                            return_value=json.dumps(mock_response)):
                result = await generator.generate_for_language("CS")

                assert result['success'] is True
                assert result['language'] == "CS"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
