# -*- coding: utf-8 -*-
from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List, Optional


@dataclass
class EpisodeContext:
    series_title: str
    series_context: List[str]
    episode_title: str
    episode_description: List[str]
    episode_index: int
    total_episodes: int
    language: str  # 'CS' | 'EN' | 'DE' | 'ES' | 'FR'


@dataclass
class GeneratedText:
    text: str
    provenance: str  # 'gpt' | 'heuristic' | 'reuse'
    prompt_hash: Optional[str] = None
    meta: Optional[Dict] = None


@dataclass
class GeneratorConfig:
    model: str = "gpt-4o"
    temperature_intro: float = 0.7
    temperature_transition: float = 0.7
    max_tokens_intro: int = 500
    max_tokens_transition: int = 300


@dataclass
class FormatterConfig:
    language: str
    use_gpt_split: bool = True
    use_gpt_grammar: bool = True
    temperature_split: float = 0.3
    temperature_grammar: float = 0.2
    model: str = "gpt-4o"
    api_key: Optional[str] = None
    # typographic conventions
    use_single_ellipsis_char: bool = True  # '…' instead of '...'
    use_en_dash_for_aside: bool = True  # ' – '
    quotes_style: str = "auto"  # auto per language
    # soft mode settings
    strict_sentence_split: bool = False  # False = warn only, True = auto-split
    max_sentence_words: int = 30  # threshold for warning/splitting
