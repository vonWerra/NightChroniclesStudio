# src/config.py
# -*- coding: utf-8 -*-
"""Configuration module with Pydantic validation."""

from pathlib import Path
from typing import Literal, Optional, Callable, Any
from pydantic import BaseModel, Field, field_validator, model_validator
import json


Lang = Literal["CS", "EN", "DE", "ES", "FR"]


class EpisodeCountRange(BaseModel):
    """Range for automatic episode count determination."""
    min: int = Field(ge=1, le=50)
    max: int = Field(ge=1, le=50)

    @model_validator(mode='after')
    def validate_range(self):
        if self.min > self.max:
            raise ValueError(f"min ({self.min}) must be <= max ({self.max})")
        return self


class SeriesContextRange(BaseModel):
    """Range for series context sentences."""
    min: int = Field(ge=1, le=10)
    max: int = Field(ge=1, le=10)

    @model_validator(mode='after')
    def validate_range(self):
        if self.min > self.max:
            raise ValueError(f"min ({self.min}) must be <= max ({self.max})")
        return self


class SourcesConfig(BaseModel):
    """Configuration for sources."""
    per_episode: EpisodeCountRange
    format: Literal["name-only", "with-url", "full-citation"] = "name-only"


class FactualityRules(BaseModel):
    """Rules for factual accuracy."""
    no_dialogue: bool = True
    no_speculation: bool = True
    consensus_only: bool = True
    note_disputes_briefly: bool = True


class Markers(BaseModel):
    """Template markers for sections."""
    begin_template: str = "===BEGIN_SECTION:{LANG}==="
    end_template: str = "===END_SECTION:{LANG}==="
    bullet: str = "-"


class OutputConfig(BaseModel):
    """Output configuration."""
    mode: Literal["multi-file", "single-file"] = "multi-file"
    basename: str = "outline"
    directory: Path = Path("./output")
    filename_pattern: str = "{BASENAME}_{LANG}.txt"
    # New: Unified project structure
    use_project_structure: bool = False
    project_root: Optional[Path] = None  # e.g., D:/NightChronicles/projects


class Config(BaseModel):
    """Main configuration model with validation."""
    topic: str = Field(min_length=1, max_length=200)
    languages: list[Lang]
    episodes: str | int = "auto"  # "auto" or specific number
    episode_minutes: int = Field(ge=10, le=180)
    episode_count_range: EpisodeCountRange
    msp_per_episode: int = Field(ge=3, le=10)
    msp_max_words: int = Field(ge=5, le=50)
    description_max_sentences: int = Field(ge=1, le=10)
    series_context_sentences: SeriesContextRange
    ordering: Literal["chronological", "thematic"] = "chronological"
    tolerance_min: int = Field(ge=1)
    tolerance_max: int = Field(ge=1)
    markers: Markers = Markers()
    factuality: FactualityRules = FactualityRules()
    sources: SourcesConfig
    output: OutputConfig = OutputConfig()

    # API Configuration (loaded from env)
    api_key: Optional[str] = Field(None, exclude=True)
    model: str = "gpt-5-mini"
    temperature: float = Field(ge=0.0, le=2.0, default=0.3)
    max_tokens: int = Field(ge=100, le=10000, default=6000)

    # Progress callback for GUI integration
    progress_callback: Optional[Callable[[str, int, int], None]] = Field(None, exclude=True)

    @field_validator('episodes')
    def validate_episodes(cls, v):
        if isinstance(v, str):
            if v != "auto":
                raise ValueError("String value must be 'auto'")
        elif isinstance(v, int):
            if not 1 <= v <= 50:
                raise ValueError("Episode count must be between 1 and 50")
        return v

    @model_validator(mode='after')
    def validate_tolerances(self):
        if self.tolerance_min > self.tolerance_max:
            raise ValueError(
                f"tolerance_min ({self.tolerance_min}) must be <= "
                f"tolerance_max ({self.tolerance_max})"
            )

        # Check if tolerances make sense with episode_minutes
        if self.tolerance_max < self.episode_minutes - 10:
            raise ValueError(
                f"tolerance_max ({self.tolerance_max}) is too far from "
                f"episode_minutes ({self.episode_minutes})"
            )
        if self.tolerance_min > self.episode_minutes + 10:
            raise ValueError(
                f"tolerance_min ({self.tolerance_min}) is too far from "
                f"episode_minutes ({self.episode_minutes})"
            )
        return self

    def flatten(self) -> dict[str, str]:
        """Flatten configuration to key-value pairs for template substitution."""
        result = {}

        def _walk(prefix: str, obj: Any):
            if isinstance(obj, BaseModel):
                for key, value in obj.model_dump().items():
                    _walk(f"{prefix}.{key}" if prefix else key, value)
            elif isinstance(obj, dict):
                for key, value in obj.items():
                    _walk(f"{prefix}.{key}" if prefix else key, value)
            elif isinstance(obj, list):
                result[prefix] = str(obj)
            else:
                result[prefix] = str(obj)

        _walk("", self)

        # Add uppercase versions for compatibility
        result["TOPIC"] = self.topic
        result["LANG"] = "{LANG}"  # Will be replaced per language
        result["EPISODES"] = str(self.episodes)
        result["EPISODE_MINUTES"] = str(self.episode_minutes)
        result["MSP_PER_EPISODE"] = str(self.msp_per_episode)
        result["MSP_MAX_WORDS"] = str(self.msp_max_words)
        result["DESCRIPTION_MAX_SENTENCES"] = str(self.description_max_sentences)
        result["ORDERING"] = self.ordering
        result["TOLERANCE_MIN"] = str(self.tolerance_min)
        result["TOLERANCE_MAX"] = str(self.tolerance_max)

        # Add nested values
        result["EPISODE_COUNT_RANGE.min"] = str(self.episode_count_range.min)
        result["EPISODE_COUNT_RANGE.max"] = str(self.episode_count_range.max)
        result["SERIES_CONTEXT_SENTENCES.min"] = str(self.series_context_sentences.min)
        result["SERIES_CONTEXT_SENTENCES.max"] = str(self.series_context_sentences.max)
        result["SOURCES.PER_EPISODE.min"] = str(self.sources.per_episode.min)
        result["SOURCES.PER_EPISODE.max"] = str(self.sources.per_episode.max)
        result["SOURCES.FORMAT"] = self.sources.format

        # Markers
        result["MARKERS.BEGIN_TEMPLATE"] = self.markers.begin_template
        result["MARKERS.END_TEMPLATE"] = self.markers.end_template
        result["MARKERS.BULLET"] = self.markers.bullet

        # Factuality
        result["FACTUALITY.NO_DIALOGUE"] = str(self.factuality.no_dialogue)
        result["FACTUALITY.NO_SPECULATION"] = str(self.factuality.no_speculation)
        result["FACTUALITY.CONSENSUS_ONLY"] = str(self.factuality.consensus_only)
        result["FACTUALITY.NOTE_DISPUTES_BRIEFLY"] = str(self.factuality.note_disputes_briefly)

        return result


def load_config(path: Path) -> Config:
    """Load and validate configuration from JSON file."""
    if not path.exists():
        raise FileNotFoundError(f"Configuration file not found: {path}")

    # Explicitly force UTF-8 encoding to prevent Windows cp1250 issues
    with path.open('r', encoding='utf-8', errors='strict') as f:
        data = json.load(f)

    # Map old keys to new structure if needed
    if "LANGUAGES" in data:
        data["languages"] = data.pop("LANGUAGES")
    if "TOPIC" in data:
        data["topic"] = data.pop("TOPIC")
    if "EPISODES" in data:
        data["episodes"] = data.pop("EPISODES")
    if "EPISODE_MINUTES" in data:
        data["episode_minutes"] = data.pop("EPISODE_MINUTES")
    if "EPISODE_COUNT_RANGE" in data:
        data["episode_count_range"] = data.pop("EPISODE_COUNT_RANGE")
    if "MSP_PER_EPISODE" in data:
        data["msp_per_episode"] = data.pop("MSP_PER_EPISODE")
    if "MSP_MAX_WORDS" in data:
        data["msp_max_words"] = data.pop("MSP_MAX_WORDS")
    if "DESCRIPTION_MAX_SENTENCES" in data:
        data["description_max_sentences"] = data.pop("DESCRIPTION_MAX_SENTENCES")
    if "SERIES_CONTEXT_SENTENCES" in data:
        data["series_context_sentences"] = data.pop("SERIES_CONTEXT_SENTENCES")
    if "ORDERING" in data:
        data["ordering"] = data.pop("ORDERING")
    if "TOLERANCE_MIN" in data:
        data["tolerance_min"] = data.pop("TOLERANCE_MIN")
    if "TOLERANCE_MAX" in data:
        data["tolerance_max"] = data.pop("TOLERANCE_MAX")
    if "MARKERS" in data:
        data["markers"] = data.pop("MARKERS")
    if "FACTUALITY" in data:
        data["factuality"] = data.pop("FACTUALITY")
    if "SOURCES" in data:
        sources_data = data.pop("SOURCES")
        if "PER_EPISODE" in sources_data:
            sources_data["per_episode"] = sources_data.pop("PER_EPISODE")
        if "FORMAT" in sources_data:
            sources_data["format"] = sources_data.pop("FORMAT")
        data["sources"] = sources_data
    if "OUTPUT" in data:
        data["output"] = data.pop("OUTPUT")

    # Load API config from environment
    import os
    from dotenv import load_dotenv
    load_dotenv()

    data["api_key"] = os.getenv("OPENAI_API_KEY")
    data["model"] = os.getenv("GPT_MODEL", "gpt-5-mini")
    data["temperature"] = float(os.getenv("GPT_TEMPERATURE", "0.3"))
    data["max_tokens"] = int(os.getenv("GPT_MAX_TOKENS", "6000"))

    return Config(**data)
