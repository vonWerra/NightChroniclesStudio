#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
File Manager - Správa souborů a složek
"""

import os
import shutil
import json
from pathlib import Path
from typing import List, Dict, Optional, Tuple
from datetime import datetime
from colorama import Fore


class FileManager:
    """Správa souborů a složek"""

    def __init__(self, config_manager):
        """
        Inicializace správce souborů

        Args:
            config_manager: Instance ConfigManager
        """
        self.config = config_manager

    def get_topics(self) -> List[Tuple[str, Path]]:
        """
        Získá seznam dostupných témat

        Returns:
            Seznam tuple (název tématu, cesta)
        """
        base_path = self.config.get_path('segments_base')

        if not base_path.exists():
            raise FileNotFoundError(f"Cesta {base_path} neexistuje!")

        topics = []
        for topic_dir in base_path.iterdir():
            if topic_dir.is_dir():
                topics.append((topic_dir.name, topic_dir))

        return topics

    def get_languages(self, topic_path: Path) -> List[Tuple[str, Path]]:
        """
        Získá seznam jazyků pro dané téma

        Args:
            topic_path: Cesta k tématu

        Returns:
            Seznam tuple (kód jazyka, cesta)
        """
        languages = []
        for lang_dir in topic_path.iterdir():
            if lang_dir.is_dir():
                languages.append((lang_dir.name, lang_dir))

        return languages

    def get_episodes(self, lang_path: Path) -> List[Dict]:
        """
        Získá seznam epizod pro daný jazyk

        Args:
            lang_path: Cesta k jazykové složce

        Returns:
            Seznam dictionary s informacemi o epizodách
        """
        episodes = []
        for ep_dir in lang_path.iterdir():
            if ep_dir.is_dir() and ep_dir.name.startswith('ep'):
                narration_path = ep_dir / "narration"
                segment_count = 0
                if narration_path.exists():
                    segment_count = len(list(narration_path.glob("*.txt")))

                episodes.append({
                    'name': ep_dir.name,
                    'path': ep_dir,
                    'segment_count': segment_count
                })

        # Seřadit podle čísla epizody
        episodes.sort(key=lambda x: self._extract_episode_number(x['name']))
        return episodes

    def get_segments(self, episode_path: Path) -> List[Path]:
        """
        Získá seznam segmentů pro danou epizodu

        Args:
            episode_path: Cesta k epizodě

        Returns:
            Seznam cest k segmentům
        """
        narration_path = episode_path / "narration"

        if not narration_path.exists():
            raise FileNotFoundError(f"Složka 'narration' nenalezena v {episode_path}")

        segments = list(narration_path.glob("*.txt"))
        segments.sort()

        return segments

    def read_segment(self, segment_path: Path, preview_length: int = 100) -> Tuple[str, str]:
        """
        Načte segment a vrátí obsah a náhled

        Args:
            segment_path: Cesta k segmentu
            preview_length: Délka náhledu

        Returns:
            Tuple (celý obsah, náhled)
        """
        with open(segment_path, 'r', encoding='utf-8') as f:
            content = f.read()
            preview = content[:preview_length].replace('\n', ' ')

        return content, preview

    def load_outline(self, topic_name: str, language: str) -> str:
        """
        Načte osnovu pro dané téma a jazyk

        Args:
            topic_name: Název tématu
            language: Kód jazyka

        Returns:
            Text osnovy nebo prázdný řetězec
        """
        base_path = self.config.get_path('outlines_base')

        # Mapování názvů témat
        topic_mappings = {
            'vznik_ceskoslovenska': 'Vznik Československa',
            'vznik ceskoslovenska': 'Vznik Československa',
            'prvni_svetova_valka': 'První světová válka',
            'druha_svetova_valka': 'Druhá světová válka',
        }

        outline_topic = topic_mappings.get(
            topic_name.lower(),
            topic_name.replace('_', ' ').title()
        )

        outline_path = base_path / outline_topic / language.upper() / "osnova.txt"

        if outline_path.exists():
            with open(outline_path, 'r', encoding='utf-8') as f:
                return f.read()

        print(f"{Fore.YELLOW}Osnova nenalezena. Pokračuji bez osnovy...")
        return ""

    def create_output_directory(self, topic: str, language: str,
                              episode_num: str) -> Path:
        """
        Vytvoří výstupní složku

        Args:
            topic: Název tématu
            language: Kód jazyka
            episode_num: Číslo epizody

        Returns:
            Cesta k výstupní složce
        """
        # output_base = postprocess výstupy (texty)
        output_path = (self.config.get_path('output_base') /
                      topic / language / f"ep_{episode_num}")

        output_path.mkdir(parents=True, exist_ok=True)
        return output_path

    def backup_segments(self, segments: List[Path], topic: str,
                       episode: str) -> Path:
        """
        Vytvoří zálohu segmentů

        Args:
            segments: Seznam segmentů k zálohování
            topic: Název tématu
            episode: Číslo epizody

        Returns:
            Cesta k záložní složce
        """
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_path = (self.config.get_path('backup_dir') /
                      f"{topic}_{episode}_{timestamp}")
        backup_path.mkdir(parents=True, exist_ok=True)

        for seg in segments:
            shutil.copy2(seg, backup_path / seg.name)

        print(f"{Fore.GREEN}✓ Záloha vytvořena: {backup_path}")
        return backup_path

    def save_processed_text(self, text: str, chunks: List[str],
                           output_path: Path, episode_num: str):
        """
        Uloží zpracovaný text a jeho části

        Args:
            text: Kompletní zpracovaný text
            chunks: Seznam částí pro TTS
            output_path: Cesta k výstupní složce
            episode_num: Číslo epizody
        """
        # Uložit kompletní text
        full_path = output_path / f"epizoda_{episode_num}_full.txt"
        with open(full_path, 'w', encoding='utf-8') as f:
            f.write(text)
        print(f"{Fore.GREEN}✓ Kompletní text: {full_path}")

        # Uložit jednotlivé části
        for i, chunk in enumerate(chunks, 1):
            chunk_path = output_path / f"epizoda_{episode_num}_cast_{i:03d}.txt"
            with open(chunk_path, 'w', encoding='utf-8') as f:
                f.write(chunk)
            print(f"{Fore.GREEN}✓ Část {i:03d}: {chunk_path}")

    def save_audio(self, audio_data, output_path: Path,
                  episode_num: str, part_num: int):
        """
        Uloží audio soubor

        Args:
            audio_data: Audio data
            output_path: Cesta k výstupní složce
            episode_num: Číslo epizody
            part_num: Číslo části
        """
        from elevenlabs import save

        # TTS ukládáme do centrálního TTS rootu (tts_base), pokud je definován
        try:
            tts_root = self.config.get_path('tts_base')
            audio_output_dir = tts_root / output_path.relative_to(self.config.get_path('output_base'))
        except Exception:
            # fallback na původní output_path
            audio_output_dir = output_path

        audio_output_dir.mkdir(parents=True, exist_ok=True)
        audio_path = audio_output_dir / f"epizoda_{episode_num}_cast_{part_num:03d}.mp3"
        save(audio_data, str(audio_path))

        return audio_path

    def get_existing_episodes(self) -> List[Dict]:
        """
        Získá seznam již zpracovaných epizod

        Returns:
            Seznam dictionary s informacemi o epizodách
        """
        output_base = self.config.get_path('output_base')
        episodes = []

        if not output_base.exists():
            return episodes

        for topic_dir in output_base.iterdir():
            if topic_dir.is_dir():
                for lang_dir in topic_dir.iterdir():
                    if lang_dir.is_dir():
                        for ep_dir in lang_dir.iterdir():
                            if ep_dir.is_dir() and ep_dir.name.startswith('ep_'):
                                txt_files = list(ep_dir.glob("epizoda_*_cast_*.txt"))
                                mp3_files = list(ep_dir.glob("*.mp3"))

                                if txt_files:
                                    episodes.append({
                                        'path': ep_dir,
                                        'topic': topic_dir.name,
                                        'language': lang_dir.name,
                                        'episode': ep_dir.name,
                                        'txt_count': len(txt_files),
                                        'mp3_count': len(mp3_files)
                                    })

        return episodes

    def load_processed_chunks(self, episode_path: Path) -> List[str]:
        """
        Načte již zpracované textové části

        Args:
            episode_path: Cesta k epizodě

        Returns:
            Seznam textových částí
        """
        txt_files = sorted(episode_path.glob("epizoda_*_cast_*.txt"))
        chunks = []

        for txt_file in txt_files:
            with open(txt_file, 'r', encoding='utf-8') as f:
                chunks.append(f.read())

        return chunks

    def save_log(self, log_entry: Dict):
        """
        Uloží záznam do logu

        Args:
            log_entry: Dictionary s log záznamem
        """
        log_path = self.config.get_path('log_file')
        log_path.parent.mkdir(parents=True, exist_ok=True)

        # Načíst existující log
        if log_path.exists():
            with open(log_path, 'r', encoding='utf-8') as f:
                log_data = json.load(f)
        else:
            log_data = []

        # Přidat nový záznam
        log_data.append(log_entry)

        # Uložit
        with open(log_path, 'w', encoding='utf-8') as f:
            json.dump(log_data, f, ensure_ascii=False, indent=2)

    def _extract_episode_number(self, episode_name: str) -> int:
        """
        Extrahuje číslo epizody z názvu

        Args:
            episode_name: Název epizody

        Returns:
            Číslo epizody
        """
        import re
        match = re.search(r'\d+', episode_name)
        return int(match.group()) if match else 0
