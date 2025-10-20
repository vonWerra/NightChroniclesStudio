# -*- coding: utf-8 -*-
"""
Shared narration core for NightChronicles.
Provides generators (intro/transition), formatter, cache, and validators used by PostProcess
and narration_builder to ensure identical quality and behavior.
"""
from .types import (
    GeneratedText,
    EpisodeContext,
    GeneratorConfig,
    FormatterConfig,
)
from .generator import IntroGenerator, TransitionGenerator
from .formatter import TextFormatter
from .validator import TransitionQualityValidator
from .cache import NarrationCache

__all__ = [
    "GeneratedText",
    "EpisodeContext",
    "GeneratorConfig",
    "FormatterConfig",
    "IntroGenerator",
    "TransitionGenerator",
    "TextFormatter",
    "TransitionQualityValidator",
    "NarrationCache",
]
