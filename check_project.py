#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Celková kontrola projektu NightChronicles Studio."""

import os
import sys
from pathlib import Path

def check_structure():
    """Kontrola základní struktury."""
    print("=" * 60)
    print("  KONTROLA STRUKTURY PROJEKTU")
    print("=" * 60)
    
    modules = {
        'studio_gui/src': 'GUI orchestrátor',
        'outline-generator': 'Generování osnov',
        'B_core': 'Generování promptů',
        'claude_generator': 'Generování narativních textů',
        'modules/narrationbuilder': 'Final assembly + post-processing'
    }
    
    print("\n1. HLAVNÍ MODULY:")
    for path, desc in modules.items():
        exists = "✓" if Path(path).is_dir() else "✗"
        print(f"   {exists} {path:<35} ({desc})")
    
    return all(Path(p).is_dir() for p in modules.keys())


def check_gui_files():
    """Kontrola GUI souborů."""
    print("\n2. GUI SOUBORY:")
    
    gui_files = [
        'studio_gui/src/main.py',
        'studio_gui/src/qprocess_runner.py',
        'studio_gui/src/process_runner.py',
        'studio_gui/src/widgets/log_pane.py',
        'studio_gui/src/utils/path_resolver.py',
        'studio_gui/src/utils/fs_helpers.py',
        'studio_gui/src/fs_index.py',
    ]
    
    for f in gui_files:
        exists = "✓" if Path(f).is_file() else "✗"
        print(f"   {exists} {f}")
    
    return all(Path(f).is_file() for f in gui_files)


def check_main_py():
    """Kontrola main.py - taby, třídy."""
    print("\n3. GUI MAIN.PY:")
    
    main_py = Path('studio_gui/src/main.py')
    if not main_py.is_file():
        print("   ✗ main.py nenalezen!")
        return False
    
    txt = main_py.read_text(encoding='utf-8')
    
    # Počet řádků
    lines = txt.split('\n')
    print(f"   ✓ Celkem řádků: {len(lines)}")
    
    # Třídy
    import re
    classes = re.findall(r'^class (\w+)', txt, re.MULTILINE)
    print(f"   ✓ Definované třídy ({len(classes)}): {', '.join(classes)}")
    
    # Tabs v MainWindow
    tabs = re.findall(r'tabs\.addTab\((\w+)', txt)
    print(f"   ✓ Taby v GUI ({len(tabs)}): {', '.join(tabs)}")
    
    # Kompilace
    try:
        compile(txt, 'main.py', 'exec')
        print("   ✓ Syntaxe OK (compile test)")
    except SyntaxError as e:
        print(f"   ✗ Syntax error: {e}")
        return False
    
    return True


def check_outputs_structure():
    """Kontrola outputs/ struktury."""
    print("\n4. OUTPUTS STRUKTURA:")
    
    outputs = Path('outputs')
    if not outputs.exists():
        print("   ! outputs/ neexistuje (vytvoří se při prvním běhu)")
        return True
    
    expected = ['outline', 'prompts', 'narration', 'final']
    for folder in expected:
        p = outputs / folder
        exists = "✓" if p.is_dir() else "○"
        print(f"   {exists} outputs/{folder}/")
    
    return True


def check_requirements():
    """Kontrola requirements souborů."""
    print("\n5. REQUIREMENTS:")
    
    req_files = [
        'requirements.txt',
        'requirements-all.txt',
        'outline-generator/requirements.txt',
        'claude_generator/requirements.txt',
    ]
    
    for f in req_files:
        exists = "✓" if Path(f).is_file() else "○"
        print(f"   {exists} {f}")
    
    return True


def check_removed_modules():
    """Kontrola, že odstraněné moduly jsou pryč."""
    print("\n6. ODSTRANĚNÉ MODULY (měly by být pryč):")
    
    removed = [
        'historical_processor',
        'test_validator_debug.py',
        'test_possessive_debug.py',
        'test_path_derive.py',
    ]
    
    for item in removed:
        p = Path(item)
        gone = "✓" if not p.exists() else "✗ STÁLE TU!"
        print(f"   {gone} {item}")
    
    return all(not Path(r).exists() for r in removed)


def check_documentation():
    """Kontrola dokumentace."""
    print("\n7. DOKUMENTACE:")
    
    docs = [
        ('README.md', 'Hlavní dokumentace'),
        ('nightchronicles_context.md', 'Projektový kontext'),
        ('REMOVED_HISTORICAL_PROCESSOR.md', 'Dokumentace odstranění'),
    ]
    
    for doc, desc in docs:
        exists = "✓" if Path(doc).is_file() else "✗"
        print(f"   {exists} {doc:<40} ({desc})")
    
    return True


def main():
    """Hlavní funkce kontroly."""
    print("\n" + "=" * 60)
    print("  🔍 NIGHTCHRONICLES STUDIO - CELKOVÁ KONTROLA")
    print("=" * 60)
    
    results = []
    
    results.append(("Struktura", check_structure()))
    results.append(("GUI soubory", check_gui_files()))
    results.append(("main.py", check_main_py()))
    results.append(("Outputs", check_outputs_structure()))
    results.append(("Requirements", check_requirements()))
    results.append(("Cleanup", check_removed_modules()))
    results.append(("Dokumentace", check_documentation()))
    
    # Souhrn
    print("\n" + "=" * 60)
    print("  📊 SOUHRN")
    print("=" * 60)
    
    for name, status in results:
        icon = "✅" if status else "❌"
        print(f"   {icon} {name}")
    
    all_ok = all(r[1] for r in results)
    
    print("\n" + "=" * 60)
    if all_ok:
        print("  ✅ VŠECHNY KONTROLY PROŠLY!")
    else:
        print("  ⚠️  NĚKTERÉ KONTROLY SELHALY")
    print("=" * 60 + "\n")
    
    return 0 if all_ok else 1


if __name__ == '__main__':
    sys.exit(main())
