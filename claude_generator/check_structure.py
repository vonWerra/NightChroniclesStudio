#!/usr/bin/env python3
"""Kontrola struktury složek"""

from pathlib import Path
import json

def check_structure():
    """Kontroluje, zda existuje správná struktura složek"""

    required_paths = {
        "Vstupní data": Path("D:/NightChronicles/B_core/outputs"),
        "Výstupní data": Path("D:/NightChronicles/Claude_vystup/outputs"),
        "Logy": Path("D:/NightChronicles/Claude_vystup/logs"),
        "Souhrny": Path("D:/NightChronicles/Claude_vystup/summaries"),
        "Projekt": Path("D:/NightChronicles/claude_generator"),
        "Cache": Path("D:/NightChronicles/claude_generator/.cache/segments"),
    }

    print("=" * 50)
    print("KONTROLA STRUKTURY SLOŽEK")
    print("=" * 50)

    all_ok = True

    for name, path in required_paths.items():
        if path.exists():
            print(f"✓ {name:15} : {path}")
        else:
            print(f"✗ {name:15} : {path} - NEEXISTUJE!")
            all_ok = False

    print("=" * 50)

    if all_ok:
        print("✓ Všechny složky existují!")
    else:
        print("✗ Některé složky chybí - vytvořte je pomocí příkazů výše")

    # Kontrola série
    print("\n" + "=" * 50)
    print("DOSTUPNÉ SÉRIE:")
    print("=" * 50)

    base_path = Path("D:/NightChronicles/B_core/outputs")
    if base_path.exists():
        series = [d for d in base_path.iterdir() if d.is_dir()]
        if series:
            for s in series:
                print(f"  • {s.name}")
                # Kontrola jazyků
                langs = [l for l in s.iterdir() if l.is_dir()]
                for lang in langs:
                    print(f"    └── {lang.name}")
                    # Kontrola epizod
                    episodes = [e for e in lang.iterdir() if e.is_dir() and e.name.startswith('ep')]
                    for ep in episodes:
                        has_prompts = (ep / 'prompts').exists()
                        has_meta = (ep / 'meta').exists()
                        status = "✓" if has_prompts and has_meta else "✗"
                        print(f"        └── {ep.name} {status}")
        else:
            print("  Žádné série nenalezeny")

    return all_ok

if __name__ == "__main__":
    check_structure()
    input("\nStiskněte Enter pro ukončení...")
