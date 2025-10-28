from __future__ import annotations

from dataclasses import dataclass
from typing import List, Optional


@dataclass
class Segment:
    name: str
    text: str


@dataclass
class EpisodeMeta:
    series_title: str
    episode_title: str
    target_language: str
    target_style: str
    desired_length_words: str
    sentence_length_target: str


@dataclass
class FactsConstraints:
    must_keep_chronology: bool = True
    no_fiction: bool = True
    no_dialogue: bool = True
    no_reenactment: bool = True
    keep_roles_explicit: bool = True
    unify_duplicate_events: bool = True
    allowed_narrative_tone: str = "vyprávění historie, ne učebnice, ne propaganda"


@dataclass
class EpisodeConfig:
    episode_meta: EpisodeMeta
    facts_and_constraints: FactsConstraints
    segments: List[Segment]


DEFAULT_STYLE = "historicko-dokumentární, klidné tempo, čitelné i pro laika"
DEFAULT_LEN = "1800-2200"
DEFAULT_SENT = "20-30 slov"
