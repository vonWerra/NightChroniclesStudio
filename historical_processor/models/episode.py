#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Episode Model - Datový model epizody
"""

from dataclasses import dataclass
from pathlib import Path
from typing import List, Optional
from datetime import datetime


@dataclass
class Episode:
    """Model epizody"""

    topic: str
    language: str
    episode_number: str
    path: Path
    segments: List[Path]
    outline: Optional[str] = None
    processed_text: Optional[str] = None
    chunks: Optional[List[str]] = None
    audio_paths: Optional[List[Path]] = None
    created_at: datetime = None
    processed_at: Optional[datetime] = None

    def __post_init__(self):
        """Inicializace po vytvoření"""
        if self.created_at is None:
            self.created_at = datetime.now()

    @property
    def is_processed(self) -> bool:
        """Zkontroluje, zda je epizoda zpracovaná"""
        return self.processed_text is not None

    @property
    def has_audio(self) -> bool:
        """Zkontroluje, zda má epizoda audio"""
        return self.audio_paths is not None and len(self.audio_paths) > 0

    @property
    def segment_count(self) -> int:
        """Počet segmentů"""
        return len(self.segments)

    @property
    def chunk_count(self) -> int:
        """Počet částí"""
        return len(self.chunks) if self.chunks else 0

    @property
    def audio_count(self) -> int:
        """Počet audio souborů"""
        return len(self.audio_paths) if self.audio_paths else 0

    @property
    def total_chars(self) -> int:
        """Celkový počet znaků"""
        if self.processed_text:
            return len(self.processed_text)
        return sum(len(seg.read_text()) for seg in self.segments)

    def to_dict(self) -> dict:
        """Převede na dictionary"""
        return {
            'topic': self.topic,
            'language': self.language,
            'episode_number': self.episode_number,
            'path': str(self.path),
            'segment_count': self.segment_count,
            'chunk_count': self.chunk_count,
            'audio_count': self.audio_count,
            'total_chars': self.total_chars,
            'is_processed': self.is_processed,
            'has_audio': self.has_audio,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'processed_at': self.processed_at.isoformat() if self.processed_at else None
        }
