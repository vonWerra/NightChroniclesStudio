#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Console UI - Hlavní uživatelské rozhraní aplikace
"""

import os
import sys
import time
from pathlib import Path
from datetime import datetime
from typing import Optional, List, Tuple
from colorama import init, Fore, Style

from core.config_manager import ConfigManager
from core.file_manager import FileManager
from core.stats_tracker import StatsTracker
from processors.gpt_processor import GPTProcessor
from processors.elevenlabs_processor import ElevenLabsProcessor
from processors.text_processor import TextProcessor
from ui.menu_manager import MenuManager


class ConsoleUI:
    """Hlavní uživatelské rozhraní"""

    def __init__(self, config_manager: ConfigManager):
        """
        Inicializace UI

        Args:
            config_manager: Instance ConfigManager
        """
        self.config = config_manager
        self.file_manager = FileManager(config_manager)
        self.stats = StatsTracker()
        self.gpt_processor = GPTProcessor(config_manager)
        self.elevenlabs_processor = ElevenLabsProcessor(config_manager, self.file_manager)
        self.text_processor = TextProcessor()
        self.menu_manager = MenuManager()

        # Inicializace colorama
        init(autoreset=True)

    def run(self):
        """Spuštění hlavního menu"""
        while True:
            self._print_header()
            choice = self.menu_manager.show_main_menu()

            if choice == '1':
                self.process_new_segments()
            elif choice == '2':
                self.send_existing_to_elevenlabs()
            elif choice == '3':
                print(f"\n{Fore.CYAN}Program ukončen.")
                sys.exit(0)
            else:
                print(f"{Fore.RED}Neplatná volba!")
                time.sleep(1)

    def _print_header(self):
        """Zobrazí hlavičku programu"""
        self._clear_screen()
        print(f"{Fore.CYAN}{'='*60}")
        print(f"{Fore.CYAN}    Historical Episodes Processor v1.0")
        print(f"{Fore.CYAN}    Zpracování historických segmentů pro ElevenLabs")
        print(f"{Fore.CYAN}{'='*60}\n")

    def _clear_screen(self):
        """Vymaže obrazovku"""
        os.system('cls' if os.name == 'nt' else 'clear')

    def process_new_segments(self):
        """Zpracování nových segmentů - hlavní workflow"""
        try:
            self._print_header()

            # 1. Výběr tématu
            topic_name, topic_path = self._select_topic()

            # 2. Výběr jazyka
            language, lang_path = self._select_language(topic_path)

            # 3. Výběr epizody
            episode_name, episode_path = self._select_episode(lang_path)

            # 4. Výběr segmentů
            segments = self._select_segments(episode_path)

            # 5. Načtení osnovy
            outline = self.file_manager.load_outline(topic_name, language)

            # 6. Číslo epizody
            episode_num = self._get_episode_number()

            # 7. Výběr GPT modelu
            model_name = self._select_gpt_model()

            # 8. Validace výstupní cesty
            output_path = self._validate_output_path(topic_name, language, episode_num)

            # 9. Záloha segmentů
            self.file_manager.backup_segments(segments, topic_name, episode_num)

            # 10. GPT zpracování
            processed_text, gpt_cost = self.gpt_processor.process_segments(
                segments, outline, episode_num, language, model_name
            )

            # Aktualizovat statistiky
            self.stats.update_gpt_stats(len(segments), len(processed_text), gpt_cost)

            if processed_text:
                # 11. Rozdělení na části
                chunks = self.text_processor.split_for_tts(processed_text)
                self.stats.chunks_count = len(chunks)

                # 12. Uložení
                self.file_manager.save_processed_text(
                    processed_text, chunks, output_path, episode_num
                )

                # 13. ElevenLabs
                if self._confirm_elevenlabs():
                    voice_id = self._get_voice_id(language)
                    if voice_id:
                        audio_paths = self.elevenlabs_processor.generate_audio(
                            chunks, output_path, episode_num, language, voice_id
                        )

                        # Aktualizovat statistiky
                        total_chars = sum(len(chunk) for chunk in chunks)
                        elevenlabs_cost = self.elevenlabs_processor.calculate_cost(total_chars)
                        self.stats.elevenlabs_cost = elevenlabs_cost

                # 14. Uložit log
                self._save_processing_log(topic_name, language, episode_num)

                # 15. Zobrazit souhrn
                self._print_summary(output_path)

            input("\nStiskněte Enter pro návrat do menu...")

        except KeyboardInterrupt:
            self._handle_interrupt(topic_name, language, episode_num if 'episode_num' in locals() else None)
        except Exception as e:
            self._handle_error(e)

    def send_existing_to_elevenlabs(self):
        """Odeslání již zpracovaných textů do ElevenLabs"""
        self._print_header()
        print(f"{Fore.YELLOW}Odeslání existujících textů do ElevenLabs\n")

        # Získat seznam zpracovaných epizod
        episodes = self.file_manager.get_existing_episodes()

        if not episodes:
            print(f"{Fore.YELLOW}Žádné zpracované epizody nenalezeny.")
            input("Stiskněte Enter pro návrat...")
            return

        # Zobrazit seznam
        self._display_existing_episodes(episodes)

        # Vybrat epizodu
        selected = self._select_existing_episode(episodes)
        if selected:
            self._process_existing_episode(selected)

    def _select_topic(self) -> Tuple[str, Path]:
        """Výběr tématu"""
        print(f"{Fore.YELLOW}1. Výběr tématu:")

        topics = self.file_manager.get_topics()
        if not topics:
            raise ValueError("Žádná témata nenalezena")

        return self.menu_manager.select_from_list(
            topics,
            "Nalezená témata:",
            lambda t: t[0]
        )

    def _select_language(self, topic_path: Path) -> Tuple[str, Path]:
        """Výběr jazyka"""
        print(f"\n{Fore.YELLOW}2. Výběr jazyka:")

        languages = self.file_manager.get_languages(topic_path)
        if not languages:
            raise ValueError("Žádné jazyky nenalezeny")

        return self.menu_manager.select_from_list(
            languages,
            "Dostupné jazyky:",
            lambda l: l[0].upper()
        )

    def _select_episode(self, lang_path: Path) -> Tuple[str, Path]:
        """Výběr epizody"""
        print(f"\n{Fore.YELLOW}3. Výběr epizody:")

        episodes = self.file_manager.get_episodes(lang_path)
        if not episodes:
            raise ValueError("Žádné epizody nenalezeny")

        formatted_episodes = [(ep['name'], ep['path']) for ep in episodes]

        return self.menu_manager.select_from_list(
            formatted_episodes,
            "Dostupné epizody:",
            lambda e: f"{e[0]} ({self._get_segment_count(e[1])} segmentů)"
        )

    def _select_segments(self, episode_path: Path) -> List[Path]:
        """Výběr segmentů"""
        print(f"\n{Fore.YELLOW}4. Výběr segmentů:")

        segments = self.file_manager.get_segments(episode_path)
        if not segments:
            raise ValueError("Žádné segmenty nenalezeny")

        # Zobrazit segmenty s náhledem
        print(f"\nNalezené segmenty:")
        for i, seg in enumerate(segments, 1):
            content, preview = self.file_manager.read_segment(seg)
            print(f"  [{i}] {seg.name}: {preview}...")

        print(f"\n  [A] Vybrat všechny")

        return self.menu_manager.select_segments(segments)

    def _get_episode_number(self) -> str:
        """Získá číslo epizody"""
        print(f"\n{Fore.YELLOW}6. Číslo epizody:")

        while True:
            num = input("Zadejte číslo epizody (např. 001): ").strip()
            if num.isdigit() and len(num) <= 3:
                return num.zfill(3)
            print(f"{Fore.RED}Zadejte platné číslo (max. 3 číslice)!")

    def _select_gpt_model(self) -> str:
        """Výběr GPT modelu"""
        print(f"\n{Fore.YELLOW}7. Výběr GPT modelu:")

        models = [
            ('gpt-4.1', 'nejnovější, nejlepší'),
            ('gpt-4.1-mini', 'rychlejší, levnější'),
            ('gpt-4-turbo-preview', 'velký kontext'),
            ('gpt-4', 'klasický'),
            ('gpt-3.5-turbo', 'levný, méně kvalitní')
        ]

        selected = self.menu_manager.select_from_list(
            models,
            "Dostupné modely:",
            lambda m: f"{m[0]} ({m[1]})"
        )

        return selected[0]

    def _validate_output_path(self, topic: str, language: str, episode_num: str) -> Path:
        """Validace výstupní cesty"""
        output_path = self.file_manager.create_output_directory(topic, language, episode_num)

        if output_path.exists() and any(output_path.iterdir()):
            print(f"\n{Fore.YELLOW}Epizoda ep_{episode_num} už existuje!")
            choice = self.menu_manager.show_overwrite_menu()

            if choice == '1':
                # Přepsat
                import shutil
                shutil.rmtree(output_path)
                output_path.mkdir(parents=True, exist_ok=True)
            elif choice == '2':
                # Vytvořit novou verzi
                version = 2
                while (output_path.parent / f"ep_{episode_num}_v{version}").exists():
                    version += 1
                output_path = output_path.parent / f"ep_{episode_num}_v{version}"
                output_path.mkdir(parents=True, exist_ok=True)
            elif choice == '3':
                # Zadat jiné číslo
                new_num = self._get_episode_number()
                return self._validate_output_path(topic, language, new_num)
            else:
                sys.exit(0)

        return output_path

    def _confirm_elevenlabs(self) -> bool:
        """Potvrzení odeslání do ElevenLabs"""
        confirm = input(f"\n{Fore.YELLOW}Odeslat do ElevenLabs? (a/n): ").strip().lower()
        return confirm == 'a'

    def _get_voice_id(self, language: str) -> Optional[str]:
        """Získá voice ID"""
        voice_id = self.config.get_voice_id(language)

        if not voice_id:
            voice_id = self.elevenlabs_processor.get_voice_id_interactive(language)

        return voice_id

    def _save_processing_log(self, topic: str, language: str, episode_num: str):
        """Uloží log zpracování"""
        log_entry = {
            "timestamp": datetime.now().isoformat(),
            "topic": topic,
            "language": language,
            "episode": episode_num,
            "stats": self.stats.get_stats()
        }

        self.file_manager.save_log(log_entry)

    def _print_summary(self, output_path: Path):
        """Zobrazí souhrn zpracování"""
        stats = self.stats.get_stats()

        print(f"\n{Fore.GREEN}{'='*60}")
        print(f"{Fore.GREEN}✓ Zpracování dokončeno!")
        print(f"{Fore.GREEN}{'='*60}")
        print(f"Segmentů zpracováno: {stats['segments_count']}")
        print(f"Celkem znaků: {stats['total_chars']:,}")
        print(f"Částí pro ElevenLabs: {stats['chunks_count']}")
        print(f"Cena GPT: ${stats['gpt_cost']:.3f}")
        print(f"Cena ElevenLabs: ${stats['elevenlabs_cost']:.3f}")
        print(f"Uloženo do: {output_path}")
        print(f"{Fore.GREEN}{'='*60}")

    def _display_existing_episodes(self, episodes: List[dict]):
        """Zobrazí existující epizody"""
        print("Nalezené zpracované epizody:\n")

        for i, ep in enumerate(episodes, 1):
            status = "✓ Hotovo" if ep['mp3_count'] > 0 else "⚠ Bez audio"
            print(f"  [{i:2}] {ep['topic']}/{ep['language']}/{ep['episode']} "
                  f"({ep['txt_count']} částí, {ep['mp3_count']} MP3) {status}")

        print(f"\n  [0] Zpět")

    def _select_existing_episode(self, episodes: List[dict]) -> Optional[dict]:
        """Vybere existující epizodu"""
        while True:
            try:
                choice = int(input(f"\nVyberte epizodu: "))
                if choice == 0:
                    return None
                if 1 <= choice <= len(episodes):
                    return episodes[choice-1]
                print(f"{Fore.RED}Neplatná volba!")
            except ValueError:
                print(f"{Fore.RED}Zadejte číslo!")

    def _process_existing_episode(self, episode_info: dict):
        """Zpracuje existující epizodu"""
        ep_path = episode_info['path']

        # Načíst textové části
        chunks = self.file_manager.load_processed_chunks(ep_path)

        print(f"\n{Fore.CYAN}Epizoda: {episode_info['topic']}/{episode_info['language']}/{episode_info['episode']}")
        print(f"Nalezeno {len(chunks)} textových částí")

        # Získat číslo epizody
        import re
        episode_num = re.search(r'ep_(\d+)', episode_info['episode'])
        episode_num = episode_num.group(1) if episode_num else "001"

        # Získat voice ID
        voice_id = self._get_voice_id(episode_info['language'])

        if voice_id:
            # Generovat audio
            self.elevenlabs_processor.generate_audio(
                chunks, ep_path, episode_num, episode_info['language'], voice_id
            )

        input("\nStiskněte Enter pro návrat do menu...")

    def _get_segment_count(self, episode_path: Path) -> int:
        """Získá počet segmentů v epizodě"""
        narration_path = episode_path / "narration"
        if narration_path.exists():
            return len(list(narration_path.glob("*.txt")))
        return 0

    def _handle_interrupt(self, topic_name: str, language: str, episode_num: Optional[str]):
        """Zpracuje přerušení uživatelem"""
        print(f"\n\n{Fore.YELLOW}Přerušeno uživatelem.")

        if episode_num:
            save = input("Uložit rozpracované? (a/n): ").strip().lower()
            if save == 'a':
                self._save_processing_log(topic_name, language, episode_num)
                print(f"{Fore.GREEN}✓ Uloženo")

    def _handle_error(self, error: Exception):
        """Zpracuje chybu"""
        print(f"\n{Fore.RED}Chyba: {error}")
        import traceback
        traceback.print_exc()
        input("\nStiskněte Enter pro návrat...")
