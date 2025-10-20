#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Historical Episodes Processor - Main Entry Point
Hlavní vstupní bod aplikace
"""

import sys
from pathlib import Path
from colorama import init, Fore

# Přidání cesty k modulu
sys.path.insert(0, str(Path(__file__).parent))

from ui.console_ui import ConsoleUI
from core.config_manager import ConfigManager


def main():
    """Hlavní funkce aplikace"""
    try:
        # Inicializace colorama pro Windows
        init(autoreset=True)

        # Načtení konfigurace
        config = ConfigManager("config.yaml")

        # Spuštění UI
        ui = ConsoleUI(config)
        ui.run()

    except KeyboardInterrupt:
        print(f"\n\n{Fore.YELLOW}Program ukončen uživatelem.")
        sys.exit(0)
    except Exception as e:
        print(f"\n{Fore.RED}Kritická chyba při spuštění: {e}")
        import traceback
        traceback.print_exc()
        input("\nStiskněte Enter pro ukončení...")
        sys.exit(1)


if __name__ == "__main__":
    main()
