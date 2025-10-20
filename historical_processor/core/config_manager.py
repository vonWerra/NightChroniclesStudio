#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Config Manager - Správa konfigurace aplikace
"""

from __future__ import annotations

import os
import sys
from pathlib import Path
from typing import Any, Dict, Optional
from colorama import Fore
import yaml

class ConfigManager:
    """Správa konfigurace aplikace"""

    def __init__(self, config_path: Optional[Path] = None):
        # Výchozí umístění: <repo>/historical_processor/config.yaml
        if config_path is None:
            base = Path(__file__).resolve().parents[1]
            config_path = base / "config.yaml"
        self.config_path = Path(config_path)
        self.config: Dict[str, Any] = {}
        self._load()

    # --- Public API ---------------------------------------------------------

    def get(self, key: str, default: Any = None) -> Any:
        return self.config.get(key, default)

    def get_path(self, key: str) -> Path:
        val = self.get(key)
        if not val:
            raise KeyError(f"Chybí klíč '{key}' v configu")
        return Path(val)

    @staticmethod
    def _normalize_language(language: str) -> str:
        """
        Normalizuje kód jazyka na standardní 2písmenné ISO (např. 'CS','Czech','CZ' -> 'cs').
        """
        if not language:
            return ""
        lang = str(language).strip().lower()
        # základní aliasy
        alias = {
            "cs": "cs",
            "cz": "cs",
            "czech": "cs",
            "čeština": "cs",
            "sk": "sk",
            "slovak": "sk",
            "slovenčina": "sk",
            "en": "en",
            "eng": "en",
            "english": "en",
        }
        return alias.get(lang, lang)

    def get_voice_id(self, language: str) -> Optional[str]:
        voices = self.config.get("voice_ids", {}) or {}
        key = self._normalize_language(language)
        # zkus přesně, pak původní
        return voices.get(key) or voices.get(str(language).lower())

    def get_elevenlabs_model(self) -> Optional[str]:
        # config.yaml:
        # elevenlabs_models:
        #   default: "eleven_multilingual_v2"
        models = self.config.get("elevenlabs_models", {})
        return models.get("default")

    # v metodě get_voice_settings(...) jen přidej speed do výstupu

    def get_voice_settings(self, language: Optional[str] = None) -> Dict[str, Any]:
        vs_all = self.config.get("voice_settings", {}) or {}

        base = {
            "stability": 0.5,
            "similarity_boost": 0.5,
            "style": 0.0,
            "use_speaker_boost": True,
            "speed": 1.0,  # NOVĚ: default rychlost
        }
        def _merge_for(lang: Optional[str]) -> Dict[str, Any]:
            out = dict(base)
            out.update(vs_all.get("default", {}) or {})
            if lang:
                lang_vs = vs_all.get(str(lang).lower())
                if isinstance(lang_vs, dict):
                    out.update(lang_vs)
            # normalizace čísel
            for k in ("stability", "similarity_boost", "style", "speed"):
                if k in out and out[k] is not None:
                    try:
                        out[k] = float(out[k])
                    except Exception:
                        pass
            if "use_speaker_boost" in out:
                out["use_speaker_boost"] = bool(out["use_speaker_boost"])
            return out

        return _merge_for(language)

    # --- Interní ------------------------------------------------------------

    def _load(self) -> None:
        if not self.config_path.exists():
            print(f"{Fore.RED}Nenalezen config: {self.config_path}")
            sys.exit(1)
        try:
            with self.config_path.open("r", encoding="utf-8") as f:
                cfg = yaml.safe_load(f) or {}
        except Exception as e:
            print(f"{Fore.RED}Chyba při načítání YAML: {e}")
            sys.exit(1)

        # Podpora načtení API klíčů z env proměnných (přepíší YAML pokud existují)
        cfg["openai_api_key"] = os.getenv("OPENAI_API_KEY", cfg.get("openai_api_key"))
        cfg["elevenlabs_api_key"] = os.getenv("ELEVENLABS_API_KEY", cfg.get("elevenlabs_api_key"))

        # Centralizované výstupy – volitelné. Pokud nejsou cesty v YAML, dopočítají se z env.
        nc_root = os.getenv("NC_OUTPUTS_ROOT")
        outlines_root = os.getenv("OUTLINE_OUTPUT_ROOT") or (os.path.join(nc_root, "outline") if nc_root else None)
        narration_root = os.getenv("NARRATION_OUTPUT_ROOT") or (os.path.join(nc_root, "narration") if nc_root else None)
        tts_root = os.getenv("TTS_OUTPUT_ROOT") or (os.path.join(nc_root, "tts") if nc_root else None)
        postproc_root = os.getenv("POSTPROC_OUTPUT_ROOT") or (os.path.join(nc_root, "postprocess") if nc_root else None)

        # Pokud nejsou v YAML, nastav výchozí (bez změny existujících hodnot)
        cfg.setdefault("outlines_base", outlines_root or cfg.get("outlines_base"))
        # segments_base = zdroj segmentů (narace)
        cfg.setdefault("segments_base", narration_root or cfg.get("segments_base"))
        # output_base = výstup pro zpracované TEXTY (postprocess)
        cfg.setdefault("output_base", postproc_root or cfg.get("output_base"))
        # tts_base = výstup pro audio soubory (MP3)
        cfg.setdefault("tts_base", tts_root or cfg.get("tts_base"))
        # backup a log – centralizované pod TTS
        cfg.setdefault("backup_dir", os.path.join(tts_root, "backups") if tts_root else cfg.get("backup_dir"))
        cfg.setdefault("log_file", os.path.join(tts_root, "processing_log.json") if tts_root else cfg.get("log_file"))

        self.config = cfg
