#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Formatters - Formátovací funkce
"""

import re
from datetime import datetime
from typing import Optional


class Formatters:
    """Formátovací funkce"""

    @staticmethod
    def format_episode_number(number: str) -> str:
        """
        Formátuje číslo epizody

        Args:
            number: Číslo epizody

        Returns:
            Formátované číslo (3 číslice)
        """
        return number.zfill(3)

    @staticmethod
    def format_file_size(bytes: int) -> str:
        """
        Formátuje velikost souboru

        Args:
            bytes: Velikost v bytech

        Returns:
            Formátovaná velikost
        """
        for unit in ['B', 'KB', 'MB', 'GB']:
            if bytes < 1024.0:
                return f"{bytes:.2f} {unit}"
            bytes /= 1024.0
        return f"{bytes:.2f} TB"

    @staticmethod
    def format_duration(seconds: float) -> str:
        """
        Formátuje dobu trvání

        Args:
            seconds: Počet sekund

        Returns:
            Formátovaná doba
        """
        hours = int(seconds // 3600)
        minutes = int((seconds % 3600) // 60)
        secs = int(seconds % 60)

        if hours > 0:
            return f"{hours}h {minutes}m {secs}s"
        elif minutes > 0:
            return f"{minutes}m {secs}s"
        else:
            return f"{secs}s"

    @staticmethod
    def format_cost(amount: float) -> str:
        """
        Formátuje cenu

        Args:
            amount: Částka

        Returns:
            Formátovaná cena
        """
        return f"${amount:.3f}"

    @staticmethod
    def format_number(number: int) -> str:
        """
        Formátuje velké číslo s oddělovači tisíců

        Args:
            number: Číslo

        Returns:
            Formátované číslo
        """
        return f"{number:,}"

    @staticmethod
    def format_timestamp(dt: Optional[datetime] = None) -> str:
        """
        Formátuje časové razítko

        Args:
            dt: Datetime objekt (výchozí: teď)

        Returns:
            Formátované časové razítko
        """
        if dt is None:
            dt = datetime.now()
        return dt.strftime("%Y-%m-%d %H:%M:%S")

    @staticmethod
    def format_date(dt: Optional[datetime] = None) -> str:
        """
        Formátuje datum

        Args:
            dt: Datetime objekt (výchozí: dnes)

        Returns:
            Formátované datum
        """
        if dt is None:
            dt = datetime.now()
        return dt.strftime("%Y-%m-%d")

    @staticmethod
    def format_percentage(value: float, total: float) -> str:
        """
        Formátuje procento

        Args:
            value: Hodnota
            total: Celkem

        Returns:
            Formátované procento
        """
        if total == 0:
            return "0.0%"
        percentage = (value / total) * 100
        return f"{percentage:.1f}%"

    @staticmethod
    def format_language_name(code: str) -> str:
        """
        Formátuje název jazyka

        Args:
            code: Kód jazyka

        Returns:
            Plný název jazyka
        """
        languages = {
            'cs': 'Čeština',
            'en': 'English',
            'de': 'Deutsch',
            'es': 'Español',
            'fr': 'Français',
            'sk': 'Slovenčina'
        }
        return languages.get(code.lower(), code.upper())

    @staticmethod
    def format_topic_name(topic: str) -> str:
        """
        Formátuje název tématu

        Args:
            topic: Název tématu

        Returns:
            Formátovaný název
        """
        # Nahradit podtržítka mezerami a kapitalizovat
        formatted = topic.replace('_', ' ')
        return formatted.title()

    @staticmethod
    def sanitize_filename(filename: str) -> str:
        """
        Očistí název souboru od neplatných znaků

        Args:
            filename: Název souboru

        Returns:
            Očištěný název
        """
        # Odstranit neplatné znaky
        invalid_chars = '<>:"/\\|?*'
        for char in invalid_chars:
            filename = filename.replace(char, '_')

        # Omezit délku
        if len(filename) > 255:
            filename = filename[:255]

        return filename

    @staticmethod
    def truncate_text(text: str, max_length: int, suffix: str = "...") -> str:
        """
        Zkrátí text na maximální délku

        Args:
            text: Text k zkrácení
            max_length: Maximální délka
            suffix: Přípona (výchozí: "...")

        Returns:
            Zkrácený text
        """
        if len(text) <= max_length:
            return text

        return text[:max_length - len(suffix)] + suffix
