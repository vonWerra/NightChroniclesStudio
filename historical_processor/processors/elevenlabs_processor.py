#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
ElevenLabs Processor – verze pro ElevenLabs SDK v2
- Používá klienta `ElevenLabs` a endpoint `text_to_speech.convert(...)`
- Podporuje 'voice_settings' včetně 'speed'
- Retry s exponenciálním backoffem
- Možnost výběru konkrétních chunků (selected_indices)
"""

from __future__ import annotations

import time
from typing import List, Optional, Dict
from pathlib import Path
from colorama import Fore

# ElevenLabs SDK v2
from elevenlabs.client import ElevenLabs
from elevenlabs import VoiceSettings


class ElevenLabsProcessor:
    """Zpracování TTS pomocí ElevenLabs (SDK v2)"""

    PRICE_PER_1K_CHARS = 0.30  # USD / 1000 znaků (orientačně)
    MAX_RETRIES = 3
    INITIAL_BACKOFF = 2.0

    def __init__(self, config_manager, file_manager):
        """
        Args:
            config_manager: ConfigManager (očekává metody get, get_voice_id, get_elevenlabs_model, get_voice_settings)
            file_manager: FileManager (není zde přímo využit, necháno pro konzistenci konstruktoru)
        """
        self.config = config_manager
        self.file_manager = file_manager

        api_key = self.config.get("elevenlabs_api_key")
        if not api_key:
            raise RuntimeError("Chybí elevenlabs_api_key v config.yaml")

        # v2: klient s API klíčem
        self.client = ElevenLabs(api_key=api_key)

    # --------------------------------------------------------------------- #
    # Public API
    # --------------------------------------------------------------------- #

    def generate_audio(
        self,
        chunks: List[str],
        output_path: Path,
        episode_num: str,
        language: str,
        voice_id: Optional[str] = None,
        selected_indices: Optional[List[int]] = None,
        output_format: str = "mp3_44100_128",  # např. "mp3_44100_128"
    ) -> List[Path]:
        """
        Vygeneruje audio pro vybrané textové části.

        Args:
            chunks: seznam textových částí (po splitu)
            output_path: cílová složka pro audio výstupy
            episode_num: číslo epizody (string, např. "001")
            language: jazyk (např. "cs")
            voice_id: volitelné override; jinak z configu podle jazyka
            selected_indices: 0-based indexy chunků, které generovat; None = všechny
            output_format: formát výstupu (SDK v2: "wav", "mp3_44100_128", ...)

        Returns:
            Seznam cest k vytvořeným audio souborům.
        """
        model = self._get_model()
        vs = self._get_voice_settings(language)  # dict včetně speed

        if not voice_id:
            voice_id = self.config.get_voice_id(language)

        if not voice_id:
            # Bez voices_read: jednoduchý manuální input
            voice_id = self.get_voice_id_interactive(language)
            if not voice_id:
                print(f"{Fore.RED}Voice ID není nastaveno – generování se ruší.")
                return []

        # Debug: zobrazíme, co se použije
        print(f"{Fore.BLUE}ElevenLabs model: {model}")
        print(f"{Fore.BLUE}Voice ID: {voice_id}")
        print(f"{Fore.BLUE}Voice settings: {vs}")

        output_path.mkdir(parents=True, exist_ok=True)

        indices = list(range(len(chunks))) if not selected_indices else list(selected_indices)
        produced: List[Path] = []

        for idx in indices:
            text = chunks[idx]
            # přípona podle output_format
            if output_format.startswith("mp3"):
                ext = "mp3"
            elif output_format.startswith("opus"):
                ext = "opus"
            elif output_format.startswith(("pcm", "ulaw_", "alaw_")):
                ext = "wav"   # syrový PCM stream → uložíme jako .wav
            else:
                ext = "bin"

            out_file = output_path / f"ep_{episode_num}_part_{idx+1:02d}.{ext}"

            ok = self._generate_with_retry(
                text=text,
                voice_id=voice_id,
                model=model,
                voice_settings=vs,
                out_path=out_file,
                output_format=output_format,
            )
            if ok:
                produced.append(out_file)

        return produced

    def calculate_cost(self, char_count: int) -> float:
        """Orientační cena v USD."""
        return round((char_count / 1000.0) * self.PRICE_PER_1K_CHARS, 4)

    def get_voice_id_interactive(self, language: str) -> Optional[str]:
        """
        Jednoduchý interaktivní výběr: nejdřív zkus config, jinak požádej o ruční vložení.
        Nepoužívá seznam hlasů (nevyžaduje 'voices_read' permission).
        """
        vid = self.config.get_voice_id(language)
        if vid:
            print(f"{Fore.GREEN}Používám voice_id z configu pro '{language}': {vid}")
            return vid

        print(f"{Fore.YELLOW}Pro jazyk '{language}' není v configu nastaven voice_id.")
        manual = input("Vlož voice_id (Enter = zrušit): ").strip()
        if manual:
            print(f"{Fore.GREEN}Použiji zadaný voice_id: {manual}")
            return manual
        return None

    # --------------------------------------------------------------------- #
    # Interní pomocné metody
    # --------------------------------------------------------------------- #

    def _get_model(self) -> str:
        # zkus načíst z configu; pokud chybí, použij standardní ML model
        try:
            model = self.config.get_elevenlabs_model()
        except Exception:
            model = None
        return model or "eleven_multilingual_v2"

    def _get_voice_settings(self, language: str) -> Dict[str, float | bool]:
        """
        Vrací dict s klíči: stability, similarity_boost, style, use_speaker_boost, speed.
        Hodnoty se čtou z configu (default + per-language).
        """
        raw = self.config.get_voice_settings(language) or {}
        allowed = {"stability", "similarity_boost", "style", "use_speaker_boost", "speed"}
        return {k: raw[k] for k in allowed if k in raw and raw[k] is not None}

    def _generate_with_retry(
        self,
        text: str,
        voice_id: str,
        model: str,
        voice_settings: Dict[str, float | bool],
        out_path: Path,
        output_format: str,
    ) -> bool:
        """
        Volá ElevenLabs TTS s retry. SDK v2 vrací stream chunků, které zapisujeme do souboru.
        """
        backoff = self.INITIAL_BACKOFF
        for attempt in range(1, self.MAX_RETRIES + 1):
            try:
                response = self.client.text_to_speech.convert(
                    voice_id=voice_id,
                    model_id=model,
                    text=text,
                    output_format=output_format,  # např. "wav" nebo "mp3_44100_128"
                    voice_settings=VoiceSettings(
                        stability=float(voice_settings.get("stability", 0.5)),
                        similarity_boost=float(voice_settings.get("similarity_boost", 0.5)),
                        style=float(voice_settings.get("style", 0.0)),
                        use_speaker_boost=bool(voice_settings.get("use_speaker_boost", True)),
                        speed=float(voice_settings.get("speed", 1.0)),
                    ),
                )

                with open(out_path, "wb") as f:
                    for chunk in response:
                        if chunk:
                            f.write(chunk)

                print(f"{Fore.GREEN}✓ Vygenerováno: {out_path.name}")
                return True

            except KeyboardInterrupt:
                raise

            except Exception as e:
                print(f"{Fore.RED}Pokus {attempt}/{self.MAX_RETRIES} selhal: {e}")
                if attempt == self.MAX_RETRIES:
                    print(f"{Fore.RED}✗ Přeskakuji {out_path.name}")
                    return False
                time.sleep(backoff)
                backoff *= 2
