#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Validators - Validační funkce
"""

import re
from pathlib import Path
from typing import Optional


class Validators:
    """Validační funkce"""

    @staticmethod
    def validate_episode_number(number: str) -> bool:
        """
        Validuje číslo epizody

        Args:
            number: Číslo epizody

        Returns:
            True pokud je validní
        """
        return number.isdigit() and len(number) <= 3

    @staticmethod
    def validate_language_code(code: str) -> bool:
        """
        Validuje kód jazyka

        Args:
            code: Kód jazyka

        Returns:
            True pokud je validní
        """
        valid_codes = ['cs', 'en', 'de', 'es', 'fr', 'sk']
        return code.lower() in valid_codes

    @staticmethod
    def validate_path_exists(path: Path) -> bool:
        """
        Zkontroluje existenci cesty

        Args:
            path: Cesta k ověření

        Returns:
            True pokud existuje
        """
        return path.exists()

    @staticmethod
    def validate_voice_id(voice_id: str) -> bool:
        """
        Validuje voice ID pro ElevenLabs

        Args:
            voice_id: ID hlasu

        Returns:
            True pokud je validní
        """
        # Voice ID by mělo mít 20 znaků
        return len(voice_id) == 20

    @staticmethod
    def validate_model_name(model: str, valid_models: list) -> bool:
        """
        Validuje název modelu

        Args:
            model: Název modelu
            valid_models: Seznam platných modelů

        Returns:
            True pokud je validní
        """
        return model in valid_models

    @staticmethod
    def validate_text_length(text: str, min_length: int = 10,
                           max_length: Optional[int] = None) -> bool:
        """
        Validuje délku textu

        Args:
            text: Text k validaci
            min_length: Minimální délka
            max_length: Maximální délka (volitelné)

        Returns:
            True pokud je v rozmezí
        """
        text_len = len(text)

        if text_len < min_length:
            return False

        if max_length and text_len > max_length:
            return False

        return True

    @staticmethod
    def validate_file_extension(path: Path, extensions: list) -> bool:
        """
        Validuje příponu souboru

        Args:
            path: Cesta k souboru
            extensions: Seznam povolených přípon

        Returns:
            True pokud má povolenou příponu
        """
        return path.suffix.lower() in extensions

    @staticmethod
    def validate_float_range(value: float, min_val: float = 0.0,
                           max_val: float = 1.0) -> bool:
        """
        Validuje float v rozmezí

        Args:
            value: Hodnota k validaci
            min_val: Minimální hodnota
            max_val: Maximální hodnota

        Returns:
            True pokud je v rozmezí
        """
        return min_val <= value <= max_val

    @staticmethod
    def validate_api_key(key: str, prefix: Optional[str] = None) -> bool:
        """
        Validuje API klíč

        Args:
            key: API klíč
            prefix: Očekávaný prefix (volitelné)

        Returns:
            True pokud vypadá jako validní klíč
        """
        if not key or len(key) < 10:
            return False

        if prefix and not key.startswith(prefix):
            return False

        return True

    @staticmethod
    def validate_yaml_structure(data: dict, required_fields: list) -> tuple:
        """
        Validuje strukturu YAML dat

        Args:
            data: Dictionary k validaci
            required_fields: Seznam povinných polí

        Returns:
            Tuple (is_valid, missing_fields)
        """
        missing = []
        for field in required_fields:
            if field not in data:
                missing.append(field)

        return len(missing) == 0, missing
