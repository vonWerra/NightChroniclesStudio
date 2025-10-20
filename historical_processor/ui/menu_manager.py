#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Menu Manager - Správa menu a výběrů
"""

from typing import List, Tuple, Any, Callable, Optional
from pathlib import Path
from colorama import Fore


class MenuManager:
    """Správa menu a interaktivních výběrů"""

    def show_main_menu(self) -> str:
        """
        Zobrazí hlavní menu

        Returns:
            Volba uživatele
        """
        print(f"{Fore.YELLOW}Hlavní menu:")
        print("  [1] Zpracovat nové segmenty (GPT + rozdělení)")
        print("  [2] Odeslat existující text do ElevenLabs")
        print("  [3] Ukončit")

        return input(f"\n{Fore.CYAN}Volba: ").strip()

    def show_overwrite_menu(self) -> str:
        """
        Zobrazí menu pro přepsání existující epizody

        Returns:
            Volba uživatele
        """
        print("  [1] Přepsat")
        print("  [2] Vytvořit novou verzi")
        print("  [3] Zadat jiné číslo")
        print("  [4] Zrušit")

        return input("Volba: ").strip()

    def select_from_list(self, items: List[Tuple[Any, Any]],
                        title: str,
                        formatter: Callable[[Tuple], str]) -> Tuple[Any, Any]:
        """
        Obecný výběr ze seznamu

        Args:
            items: Seznam položek (tuple)
            title: Nadpis menu
            formatter: Funkce pro formátování položek

        Returns:
            Vybraná položka
        """
        print(f"\n{title}")

        for i, item in enumerate(items, 1):
            print(f"  [{i}] {formatter(item)}")

        while True:
            try:
                choice = int(input(f"\nVyberte (1-{len(items)}): "))
                if 1 <= choice <= len(items):
                    return items[choice-1]
                print(f"{Fore.RED}Neplatná volba!")
            except ValueError:
                print(f"{Fore.RED}Zadejte číslo!")

    def select_segments(self, segments: List[Path]) -> List[Path]:
        """
        Výběr segmentů

        Args:
            segments: Seznam segmentů

        Returns:
            Seznam vybraných segmentů
        """
        while True:
            choice = input(f"\nVyberte segmenty (např. 1,3,5 nebo A pro všechny): ").strip()

            if choice.upper() == 'A':
                return segments

            try:
                indices = [int(x.strip()) for x in choice.split(',')]
                selected = []

                for idx in indices:
                    if 1 <= idx <= len(segments):
                        selected.append(segments[idx-1])
                    else:
                        print(f"{Fore.RED}Číslo {idx} není v rozsahu!")
                        selected = []
                        break

                if selected:
                    return selected

            except ValueError:
                print(f"{Fore.RED}Neplatný formát!")

    def confirm_action(self, message: str) -> bool:
        """
        Potvrzení akce

        Args:
            message: Zpráva pro uživatele

        Returns:
            True pokud uživatel potvrdí
        """
        response = input(f"{Fore.YELLOW}{message} (a/n): ").strip().lower()
        return response == 'a'

    def get_text_input(self, prompt: str, validator: Optional[Callable[[str], bool]] = None) -> str:
        """
        Získá textový vstup od uživatele

        Args:
            prompt: Výzva pro uživatele
            validator: Volitelná validační funkce

        Returns:
            Vstup od uživatele
        """
        while True:
            value = input(f"{prompt}: ").strip()

            if validator:
                if validator(value):
                    return value
                print(f"{Fore.RED}Neplatný vstup!")
            else:
                return value

    def get_number_input(self, prompt: str, min_val: int = None,
                        max_val: int = None) -> int:
        """
        Získá číselný vstup od uživatele

        Args:
            prompt: Výzva pro uživatele
            min_val: Minimální hodnota
            max_val: Maximální hodnota

        Returns:
            Číslo od uživatele
        """
        while True:
            try:
                value = int(input(f"{prompt}: "))

                if min_val is not None and value < min_val:
                    print(f"{Fore.RED}Hodnota musí být alespoň {min_val}!")
                    continue

                if max_val is not None and value > max_val:
                    print(f"{Fore.RED}Hodnota může být maximálně {max_val}!")
                    continue

                return value

            except ValueError:
                print(f"{Fore.RED}Zadejte platné číslo!")

    def display_progress(self, current: int, total: int, message: str = ""):
        """
        Zobrazí progress bar

        Args:
            current: Aktuální hodnota
            total: Celková hodnota
            message: Dodatečná zpráva
        """
        if total == 0:
            return

        percentage = (current / total) * 100
        bar_length = 40
        filled = int(bar_length * current / total)

        bar = '█' * filled + '░' * (bar_length - filled)

        print(f"\r{Fore.CYAN}[{bar}] {percentage:.1f}% {message}", end='', flush=True)

        if current >= total:
            print()  # Nový řádek na konci
