#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Stats Tracker - Sledování statistik zpracování
"""

from typing import Dict, Any
from datetime import datetime


class StatsTracker:
    """Sledování statistik zpracování"""

    def __init__(self):
        """Inicializace sledování statistik"""
        self.reset()

    def reset(self):
        """Reset všech statistik"""
        self.segments_count = 0
        self.total_chars = 0
        self.chunks_count = 0
        self.gpt_cost = 0.0
        self.elevenlabs_cost = 0.0
        self.start_time = datetime.now()
        self.end_time = None

    def update_gpt_stats(self, segments: int, chars: int, cost: float):
        """
        Aktualizuje GPT statistiky

        Args:
            segments: Počet segmentů
            chars: Počet znaků
            cost: Cena zpracování
        """
        self.segments_count = segments
        self.total_chars = chars
        self.gpt_cost = cost

    def update_elevenlabs_stats(self, cost: float):
        """
        Aktualizuje ElevenLabs statistiky

        Args:
            cost: Cena generování
        """
        self.elevenlabs_cost = cost

    def set_chunks_count(self, count: int):
        """
        Nastaví počet částí

        Args:
            count: Počet částí
        """
        self.chunks_count = count

    def finish(self):
        """Označí konec zpracování"""
        self.end_time = datetime.now()

    def get_processing_time(self) -> float:
        """
        Získá čas zpracování

        Returns:
            Čas v sekundách
        """
        if self.end_time:
            delta = self.end_time - self.start_time
        else:
            delta = datetime.now() - self.start_time

        return delta.total_seconds()

    def get_total_cost(self) -> float:
        """
        Získá celkovou cenu

        Returns:
            Celková cena
        """
        return self.gpt_cost + self.elevenlabs_cost

    def get_stats(self) -> Dict[str, Any]:
        """
        Získá všechny statistiky

        Returns:
            Dictionary se statistikami
        """
        return {
            'segments_count': self.segments_count,
            'total_chars': self.total_chars,
            'chunks_count': self.chunks_count,
            'gpt_cost': self.gpt_cost,
            'elevenlabs_cost': self.elevenlabs_cost,
            'total_cost': self.get_total_cost(),
            'processing_time': self.get_processing_time(),
            'start_time': self.start_time.isoformat(),
            'end_time': self.end_time.isoformat() if self.end_time else None
        }

    def print_summary(self):
        """Vypíše souhrn statistik"""
        stats = self.get_stats()

        print("\n" + "="*50)
        print("STATISTIKY ZPRACOVÁNÍ")
        print("="*50)
        print(f"Segmentů zpracováno: {stats['segments_count']}")
        print(f"Celkem znaků: {stats['total_chars']:,}")
        print(f"Částí pro TTS: {stats['chunks_count']}")
        print(f"Čas zpracování: {stats['processing_time']:.1f} sekund")
        print("-"*50)
        print(f"Cena GPT: ${stats['gpt_cost']:.3f}")
        print(f"Cena ElevenLabs: ${stats['elevenlabs_cost']:.3f}")
        print(f"CELKEM: ${stats['total_cost']:.3f}")
        print("="*50)
