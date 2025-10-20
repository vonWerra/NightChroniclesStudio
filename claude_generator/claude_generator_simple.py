#!/usr/bin/env python3
"""
Claude Generator - Jednoduchá funkční verze bez složitých bezpečnostních kontrol
"""

import os
import sys
import json
import time
import re
import yaml
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Optional, Tuple, Any
from dataclasses import dataclass, asdict
import logging
import traceback
from enum import Enum

# Import knihoven
try:
    from anthropic import Anthropic
    from dotenv import load_dotenv
except ImportError as e:
    print("ERROR: Nainstalujte požadované knihovny:")
    print("pip install anthropic python-dotenv pyyaml")
    print(f"Chybějící modul: {e}")
    sys.exit(1)

# Konfigurace
load_dotenv()

class GenerationStatus(Enum):
    """Stavy generování"""
    SUCCESS = "success"
    WARNING = "warning"
    FAILED = "failed"
    ERROR = "error"

@dataclass
class SegmentResult:
    """Výsledek generování segmentu"""
    segment_index: int
    attempts: List[Dict]
    final_text: str
    final_wordcount: int
    status: GenerationStatus
    validation: Optional[Dict] = None
    error_message: Optional[str] = None

@dataclass
class Config:
    """Konfigurace aplikace"""
    api_key: str = os.getenv('ANTHROPIC_API_KEY', '')
    model: str = os.getenv('CLAUDE_MODEL', 'claude-opus-4-1-20250805')
    temperature: float = float(os.getenv('CLAUDE_TEMPERATURE', '0.3'))
    max_tokens: int = int(os.getenv('CLAUDE_MAX_TOKENS', '8000'))
    max_attempts: int = int(os.getenv('MAX_ATTEMPTS', '3'))
    word_tolerance_percent: int = int(os.getenv('WORD_TOLERANCE', '3'))
    rate_limit_delay: float = float(os.getenv('RATE_LIMIT_DELAY', '1.0'))
    base_output_path: str = os.getenv('OUTPUT_PATH', 'D:/NightChronicles/B_core/outputs')
    claude_output_path: str = os.getenv('CLAUDE_OUTPUT', 'D:/NightChronicles/Claude_vystup/outputs')

    def validate(self) -> Tuple[bool, List[str]]:
        """Validace konfigurace"""
        errors = []

        if not self.api_key:
            errors.append("ANTHROPIC_API_KEY není nastaven v .env souboru")

        if self.temperature < 0 or self.temperature > 1:
            errors.append(f"Neplatná teplota: {self.temperature} (musí být 0-1)")

        if self.max_tokens < 100:
            errors.append(f"Příliš nízký max_tokens: {self.max_tokens}")

        if not Path(self.base_output_path).exists():
            errors.append(f"Základní cesta neexistuje: {self.base_output_path}")

        return len(errors) == 0, errors

class ClaudeGeneratorError(Exception):
    """Vlastní výjimka pro generátor"""
    pass

class APIError(ClaudeGeneratorError):
    """Chyba API volání"""
    pass

class ValidationError(ClaudeGeneratorError):
    """Chyba validace"""
    pass

class ClaudeGenerator:
    """Hlavní třída pro generování textů"""

    def __init__(self, config: Config):
        self.config = config
        is_valid, errors = self.config.validate()
        if not is_valid:
            raise ValidationError(f"Chyby konfigurace: {'; '.join(errors)}")

        try:
            self.client = Anthropic(api_key=self.config.api_key)
        except Exception as e:
            raise APIError(f"Nepodařilo se inicializovat Anthropic klienta: {e}")

        self.setup_logging()
        self.retry_delays = [1, 2, 4, 8]  # Exponenciální backoff

    def setup_logging(self):
        """Nastavení logování"""
        try:
            log_dir = Path(self.config.claude_output_path).parent / "logs"
            log_dir.mkdir(parents=True, exist_ok=True)

            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            log_file = log_dir / f"generation_{timestamp}.log"

            logging.basicConfig(
                level=logging.INFO,
                format='%(asctime)s - %(levelname)s - %(message)s',
                handlers=[
                    logging.FileHandler(log_file, encoding='utf-8', errors='replace'),
                    logging.StreamHandler()
                ]
            )
            self.logger = logging.getLogger(__name__)
            self.logger.info("Logování inicializováno")

        except Exception as e:
            print(f"Varování: Nepodařilo se nastavit logování: {e}")
            self.logger = logging.getLogger(__name__)
            self.logger.addHandler(logging.StreamHandler())

    def find_series(self, base_path: Path) -> List[Path]:
        """Najde všechny dostupné série včetně jazykových podsložek"""
        series: List[Path] = []

        try:
            if not base_path.exists():
                raise FileNotFoundError(f"Cesta neexistuje: {base_path}")

            for item in base_path.iterdir():
                try:
                    if not (item.is_dir() and not item.name.startswith('.')):
                        continue

                    # Epizody přímo pod kořenem série
                    if any(d.is_dir() and d.name.startswith('ep') for d in item.iterdir()):
                        series.append(item)
                        continue

                    # Jazykové podsložky obsahující epizody
                    for lang_dir in (d for d in item.iterdir() if d.is_dir() and not d.name.startswith('.')):
                        if any(e.is_dir() and e.name.startswith('ep') for e in lang_dir.iterdir()):
                            series.append(lang_dir)

                except PermissionError as e:
                    self.logger.warning(f"Nelze přistoupit k {item}: {e}")
                    continue

            return sorted(series, key=lambda p: (p.parent.name, p.name))

        except Exception as e:
            self.logger.error(f"Chyba při hledání sérií: {e}")
            return []

    def find_episodes(self, series_path: Path) -> List[Path]:
        """Najde všechny epizody v sérii"""
        episodes = []

        try:
            for item in series_path.iterdir():
                if item.is_dir() and item.name.startswith('ep'):
                    if (item / 'prompts').exists():
                        episodes.append(item)

        except Exception as e:
            self.logger.error(f"Chyba při hledání epizod v {series_path}: {e}")

        return sorted(episodes)

    def safe_input(self, prompt: str, validator=None) -> str:
        """Bezpečný vstup s validací"""
        while True:
            try:
                value = input(prompt).strip()
                if validator and not validator(value):
                    print("Neplatná hodnota, zkuste znovu.")
                    continue
                return value
            except KeyboardInterrupt:
                print("\n\nPřerušeno uživatelem")
                sys.exit(0)

    def interactive_menu(self) -> Tuple[Path, List[Path]]:
        """Interaktivní menu pro výběr série a epizod"""
        base_path = Path(self.config.base_output_path)

        # Výběr série
        series = self.find_series(base_path)
        if not series:
            raise ClaudeGeneratorError(f"Nenalezeny žádné série v {base_path}")

        print("\n=== DOSTUPNÉ SÉRIE ===")
        for i, s in enumerate(series, 1):
            label = f"{s.parent.name}/{s.name}" if s.parent != base_path else s.name
            print(f"{i}. {label}")

        def validate_series(val):
            try:
                idx = int(val) - 1
                return 0 <= idx < len(series)
            except ValueError:
                return False

        choice = self.safe_input("\nVyberte sérii (číslo): ", validate_series)
        selected_series = series[int(choice) - 1]

        # Výběr epizod
        episodes = self.find_episodes(selected_series)
        if not episodes:
            raise ClaudeGeneratorError(f"Nenalezeny žádné epizody v {selected_series}")

        print(f"\n=== EPIZODY V '{selected_series.name}' ===")
        for i, ep in enumerate(episodes, 1):
            print(f"{i}. {ep.name}")
        print(f"{len(episodes)+1}. Všechny epizody")

        def validate_episodes(val):
            if val == str(len(episodes)+1):
                return True
            try:
                indices = [int(x.strip()) for x in val.split(',')]
                return all(1 <= idx <= len(episodes) for idx in indices)
            except ValueError:
                return False

        choice = self.safe_input(
            "\nVyberte epizody (čísla oddělená čárkou, nebo číslo pro všechny): ",
            validate_episodes
        )

        if choice == str(len(episodes)+1):
            selected_episodes = episodes
        else:
            indices = [int(x.strip())-1 for x in choice.split(',')]
            selected_episodes = [episodes[idx] for idx in indices]

        return selected_series, selected_episodes

    def load_prompt(self, prompt_file: Path) -> str:
        """Načte prompt ze souboru"""
        try:
            encodings = ['utf-8', 'utf-8-sig', 'cp1250', 'windows-1250', 'iso-8859-2']

            for encoding in encodings:
                try:
                    text = prompt_file.read_text(encoding=encoding)
                    if any(c in text for c in ['a', 'e', 'i', 'o', 'u']):
                        return text
                except (UnicodeDecodeError, UnicodeError):
                    continue

            return prompt_file.read_text(encoding='utf-8', errors='replace')

        except FileNotFoundError:
            raise FileNotFoundError(f"Soubor neexistuje: {prompt_file}")

    def parse_validation(self, text: str) -> Optional[Dict]:
        """Parsuje YAML validaci z výstupu"""
        try:
            patterns = [
                (r'---VALIDATION---\n(.*?)$', re.DOTALL),
                (r'---\n(.*?)$', re.DOTALL),
            ]

            yaml_text = None
            for pattern, flags in patterns:
                match = re.search(pattern, text, flags)
                if match:
                    yaml_text = match.group(1).strip()
                    break

            if not yaml_text:
                return None

            data = yaml.safe_load(yaml_text)
            if isinstance(data, dict):
                return data

        except Exception as e:
            self.logger.warning(f"Nepodařilo se parsovat validaci: {e}")
            return None

    def extract_narration(self, text: str) -> str:
        """Extrahuje narativní text"""
        if '---' in text:
            parts = text.split('---', 1)
            return parts[0].strip()
        return text.strip()

    def count_words(self, text: str) -> int:
        """Spočítá slova v textu"""
        cleaned = ' '.join(text.split())
        return len(cleaned.split()) if cleaned else 0

    def check_requirements(self, text: str, validation: Dict, target_words: int,
                         tolerance_percent: int) -> Tuple[bool, List[str]]:
        """Kontrola požadavků na segment"""
        issues = []

        try:
            word_count = self.count_words(text)

            min_words = int(target_words * (1 - tolerance_percent/100))
            max_words = int(target_words * (1 + tolerance_percent/100))

            if word_count < min_words:
                issues.append(f"Text je příliš krátký ({word_count} slov, minimum {min_words})")
            elif word_count > max_words:
                issues.append(f"Text je příliš dlouhý ({word_count} slov, maximum {max_words})")

            if validation:
                def check_field(field_name, expected_values, error_msg):
                    value = str(validation.get(field_name, '')).lower().strip()
                    if value not in [v.lower() for v in expected_values]:
                        issues.append(error_msg)

                check_field('opening_hook_present', ['yes', 'true', '1'], "Chybí úvodní hook")
                check_field('closing_handoff_present', ['yes', 'true', '1'], "Chybí závěrečný handoff")

        except Exception as e:
            issues.append(f"Chyba validace: {str(e)}")

        return len(issues) == 0, issues

    def call_api_with_retry(self, prompt: str, attempt_num: int = 1) -> Optional[str]:
        """Volání API s retry logikou"""
        max_retries = 3

        for retry in range(max_retries):
            try:
                if retry > 0:
                    delay = self.retry_delays[min(retry, len(self.retry_delays)-1)]
                    self.logger.info(f"    Čekám {delay} sekund před dalším pokusem...")
                    time.sleep(delay)
                else:
                    time.sleep(self.config.rate_limit_delay)

                response = self.client.messages.create(
                    model=self.config.model,
                    temperature=self.config.temperature,
                    max_tokens=self.config.max_tokens,
                    messages=[{"role": "user", "content": prompt}]
                )

                if response and response.content:
                    return response.content[0].text

            except Exception as e:
                if retry == max_retries - 1:
                    raise APIError(f"API volání selhalo po {max_retries} pokusech: {e}")

        return None

    def generate_segment(self, prompt: str, fix_template: str, segment_idx: int,
                        target_words: int) -> SegmentResult:
        """Generuje jeden segment"""
        attempts = []
        best_result = None
        best_score = float('inf')

        for attempt_num in range(1, self.config.max_attempts + 1):
            self.logger.info(f"  Pokus {attempt_num}/{self.config.max_attempts}")

            try:
                if attempt_num > 1 and best_result and fix_template:
                    issues_text = "\n".join([f"- {issue}" for issue in best_result.get('issues', [])])
                    current_prompt = fix_template.replace("{ISSUE_LIST}", issues_text)
                    current_prompt = f"Previous output:\n{best_result['full_text']}\n\n{current_prompt}"
                else:
                    current_prompt = prompt

                full_text = self.call_api_with_retry(current_prompt, attempt_num)

                if not full_text:
                    raise APIError("API nevrátilo žádný text")

                narration = self.extract_narration(full_text)
                validation = self.parse_validation(full_text)
                word_count = self.count_words(narration)

                success, issues = self.check_requirements(
                    narration, validation, target_words,
                    self.config.word_tolerance_percent
                )

                score = abs(word_count - target_words)

                attempt_data = {
                    'attempt': attempt_num,
                    'wordcount': word_count,
                    'status': 'success' if success else 'failed',
                    'issues': issues
                }
                attempts.append(attempt_data)

                if score < best_score:
                    best_score = score
                    best_result = {
                        'text': narration,
                        'full_text': full_text,
                        'wordcount': word_count,
                        'validation': validation,
                        'issues': issues,
                        'success': success
                    }

                if success:
                    self.logger.info(f"    ✓ Úspěch! {word_count} slov")
                    break
                else:
                    self.logger.warning(f"    ✗ Problémy: {', '.join(issues)}")

            except Exception as e:
                self.logger.error(f"    Chyba: {e}")
                attempts.append({
                    'attempt': attempt_num,
                    'status': 'error',
                    'error': str(e)
                })

        if best_result:
            status = GenerationStatus.SUCCESS if best_result['success'] else GenerationStatus.WARNING
            return SegmentResult(
                segment_index=segment_idx,
                attempts=attempts,
                final_text=best_result['text'],
                final_wordcount=best_result['wordcount'],
                status=status,
                validation=best_result['validation']
            )
        else:
            return SegmentResult(
                segment_index=segment_idx,
                attempts=attempts,
                final_text='',
                final_wordcount=0,
                status=GenerationStatus.FAILED,
                error_message="Nepodařilo se vygenerovat žádný text"
            )

    def generate_fusion(self, segments: List[str], fusion_prompt: str) -> Optional[str]:
        """Spojí segmenty do finálního textu"""
        self.logger.info("Generování fúze segmentů...")

        try:
            segments_text = "\n\n---SEGMENT---\n\n".join(segments)
            full_prompt = f"{fusion_prompt}\n\nSEGMENTS TO FUSE:\n\n{segments_text}"

            result = self.call_api_with_retry(full_prompt)

            if result:
                self.logger.info("Fúze úspěšně dokončena")
                return result.strip()

        except Exception as e:
            self.logger.error(f"Chyba při fúzi: {e}")

        return None

    def save_with_backup(self, file_path: Path, content: str, encoding='utf-8'):
        """Uloží soubor s vytvořením zálohy"""
        try:
            if file_path.exists():
                backup_path = file_path.with_suffix(f'.bak_{datetime.now().strftime("%Y%m%d_%H%M%S")}')
                file_path.rename(backup_path)

            file_path.write_text(content, encoding=encoding)

        except Exception as e:
            self.logger.error(f"Chyba při ukládání {file_path}: {e}")
            raise

    def process_episode(self, episode_path: Path, output_base: Path) -> bool:
        """Zpracuje jednu epizodu"""
        episode_name = episode_path.name
        self.logger.info(f"\n{'='*60}")
        self.logger.info(f"Zpracovávám epizodu: {episode_name}")
        self.logger.info(f"{'='*60}")

        try:
            prompts_dir = episode_path / 'prompts'
            meta_dir = episode_path / 'meta'

            context_file = meta_dir / 'episode_context.json'
            if not context_file.exists():
                raise FileNotFoundError(f"Nenalezen episode_context.json v {meta_dir}")

            with open(context_file, 'r', encoding='utf-8') as f:
                context = json.load(f)

            if 'segments' not in context:
                raise ValidationError("episode_context.json neobsahuje 'segments'")

            series_name = episode_path.parent.parent.name
            language_name = episode_path.parent.name
            output_dir = output_base / series_name / language_name / episode_name / 'narration'
            output_dir.mkdir(parents=True, exist_ok=True)

            results = []
            successful_segments = 0

            for seg_data in context['segments']:
                seg_idx = seg_data['segment_index']
                seg_pad = f"{seg_idx:02d}"

                self.logger.info(f"\nSegment {seg_idx}/{len(context['segments'])}: {seg_data.get('msp_label', 'Bez názvu')[:50]}...")

                exec_file = prompts_dir / f"msp_{seg_pad}_execution.txt"
                fix_file = prompts_dir / f"msp_{seg_pad}_fix_template.txt"

                if not exec_file.exists():
                    self.logger.error(f"Nenalezen execution prompt pro segment {seg_idx}")
                    continue

                exec_prompt = self.load_prompt(exec_file)
                fix_template = self.load_prompt(fix_file) if fix_file.exists() else ""

                result = self.generate_segment(
                    exec_prompt, fix_template, seg_idx,
                    seg_data.get('word_target', 500)
                )
                results.append(result)

                if result.status in [GenerationStatus.SUCCESS, GenerationStatus.WARNING]:
                    successful_segments += 1

                if result.final_text:
                    segment_file = output_dir / f"segment_{seg_pad}.txt"
                    self.save_with_backup(segment_file, result.final_text)

            # Fúze segmentů
            if successful_segments >= 3:
                fusion_file = prompts_dir / 'fusion_instructions.txt'
                if fusion_file.exists():
                    fusion_prompt = self.load_prompt(fusion_file)
                    segment_texts = [r.final_text for r in results if r.final_text]

                    if len(segment_texts) >= 3:
                        fused_text = self.generate_fusion(segment_texts, fusion_prompt)
                        if fused_text:
                            fusion_output = output_dir / 'fusion_result.txt'
                            self.save_with_backup(fusion_output, fused_text)

            self.logger.info(f"\nEpizoda {episode_name} dokončena")
            self.logger.info(f"Úspěšné segmenty: {successful_segments}/{len(results)}")

            return successful_segments > 0

        except Exception as e:
            self.logger.error(f"Chyba při zpracování epizody {episode_name}: {e}")
            return False

    def run(self):
        """Hlavní běh programu"""
        print("\n=== CLAUDE NARRATION GENERATOR ===\n")

        try:
            series_path, episodes = self.interactive_menu()

            print(f"\nVybraná série: {series_path.name}")
            print(f"Vybrané epizody: {', '.join(ep.name for ep in episodes)}")

            confirm = self.safe_input("\nPokračovat? (y/n): ", lambda x: x.lower() in ['y', 'n'])
            if confirm.lower() != 'y':
                print("Zrušeno")
                return

            output_base = Path(self.config.claude_output_path)

            for i, episode in enumerate(episodes, 1):
                print(f"\n[{i}/{len(episodes)}] Zpracovávám: {episode.name}")
                self.process_episode(episode, output_base)

            print("\n=== GENEROVÁNÍ DOKONČENO ===")

        except Exception as e:
            self.logger.error(f"Kritická chyba: {e}")
            print(f"\nKRITICKÁ CHYBA: {e}")

def main():
    """Hlavní funkce"""
    try:
        config = Config()
        generator = ClaudeGenerator(config)
        generator.run()

    except KeyboardInterrupt:
        print("\n\nProgram ukončen uživatelem")
        sys.exit(0)
    except Exception as e:
        print(f"CHYBA: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
