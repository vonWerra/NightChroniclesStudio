#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Diagnostický skript pro kontrolu instalace.
Spusťte: python check_installation.py
"""

import sys
import os
from pathlib import Path

def check_python_version():
    """Kontrola verze Pythonu."""
    print("1. Kontrola Python verze...")
    version = sys.version_info
    if version.major >= 3 and version.minor >= 8:
        print(f"   ✅ Python {version.major}.{version.minor}.{version.micro} - OK")
        return True
    else:
        print(f"   ❌ Python {version.major}.{version.minor} - Potřebujete Python 3.8+")
        return False

def check_required_packages():
    """Kontrola instalovaných balíčků."""
    print("\n2. Kontrola požadovaných balíčků...")

    required = {
        'aiohttp': 'pip install aiohttp',
        'pydantic': 'pip install pydantic',
        'dotenv': 'pip install python-dotenv',
        'structlog': 'pip install structlog',
        'backoff': 'pip install backoff',
        'openai': 'pip install openai'
    }

    all_ok = True
    for package, install_cmd in required.items():
        try:
            if package == 'dotenv':
                import dotenv
            else:
                __import__(package)
            print(f"   ✅ {package} - nainstalováno")
        except ImportError:
            print(f"   ❌ {package} - CHYBÍ (instalujte: {install_cmd})")
            all_ok = False

    return all_ok

def check_project_structure():
    """Kontrola struktury projektu."""
    print("\n3. Kontrola struktury projektu...")

    required_files = [
        'generate_outline.py',
        'requirements.txt',
        '.env.example',
        'src/__init__.py',
        'src/config.py',
        'src/generator.py',
        'src/api_client.py',
        'src/models.py',
        'src/cache.py',
        'src/logger.py',
        'src/monitor.py'
    ]

    required_dirs = [
        'src',
        'config',
        'templates',
        'output',
        'logs'
    ]

    all_ok = True

    # Kontrola složek
    for dir_name in required_dirs:
        if Path(dir_name).exists():
            print(f"   ✅ {dir_name}/ - existuje")
        else:
            print(f"   ❌ {dir_name}/ - CHYBÍ (vytvořte: mkdir {dir_name})")
            all_ok = False

    # Kontrola souborů
    for file_name in required_files:
        if Path(file_name).exists():
            print(f"   ✅ {file_name} - existuje")
        else:
            print(f"   ❌ {file_name} - CHYBÍ")
            all_ok = False

    return all_ok

def check_config_files():
    """Kontrola konfiguračních souborů."""
    print("\n4. Kontrola konfigurace...")

    all_ok = True

    # .env soubor
    if Path('.env').exists():
        print("   ✅ .env - existuje")
        with open('.env', 'r') as f:
            content = f.read()
            if 'OPENAI_API_KEY=' in content:
                if 'sk-' in content and 'your-api-key-here' not in content:
                    print("   ✅ OpenAI API klíč - nastaven")
                else:
                    print("   ⚠️  OpenAI API klíč - vypadá jako placeholder, nahraďte skutečným")
                    all_ok = False
            else:
                print("   ❌ OpenAI API klíč - CHYBÍ v .env")
                all_ok = False
    else:
        print("   ❌ .env - CHYBÍ (zkopírujte z .env.example)")
        all_ok = False

    # Config JSON
    config_path = Path('config/outline_config.json')
    if config_path.exists():
        print("   ✅ config/outline_config.json - existuje")
    else:
        print("   ❌ config/outline_config.json - CHYBÍ")
        all_ok = False

    # Template
    template_path = Path('templates/outline_master.txt')
    if template_path.exists():
        print("   ✅ templates/outline_master.txt - existuje")
    else:
        print("   ❌ templates/outline_master.txt - CHYBÍ")
        all_ok = False

    return all_ok

def check_imports():
    """Kontrola, zda fungují importy."""
    print("\n5. Test importů modulů...")

    try:
        from src.config import Config
        print("   ✅ Import Config - OK")
    except ImportError as e:
        print(f"   ❌ Import Config - CHYBA: {e}")
        return False

    try:
        from src.models import OutlineJSON
        print("   ✅ Import Models - OK")
    except ImportError as e:
        print(f"   ❌ Import Models - CHYBA: {e}")
        return False

    try:
        from src.generator import OutlineGenerator
        print("   ✅ Import Generator - OK")
    except ImportError as e:
        print(f"   ❌ Import Generator - CHYBA: {e}")
        return False

    return True

def main():
    """Hlavní diagnostická funkce."""
    print("="*50)
    print("DIAGNOSTIKA INSTALACE - Outline Generator")
    print("="*50)

    results = []

    # Spusť všechny kontroly
    results.append(check_python_version())
    results.append(check_required_packages())
    results.append(check_project_structure())
    results.append(check_config_files())
    results.append(check_imports())

    # Výsledek
    print("\n" + "="*50)
    if all(results):
        print("✅ VŠE JE V POŘÁDKU - můžete spustit generátor")
        print("\nDalší krok:")
        print("  python generate_outline.py --dry-run")
    else:
        print("❌ BYLY NALEZENY PROBLÉMY - opravte výše uvedené chyby")
        print("\nNápověda:")
        print("  1. Nainstalujte chybějící balíčky: pip install -r requirements.txt")
        print("  2. Vytvořte .env z .env.example a vložte API klíč")
        print("  3. Zkontrolujte, že máte všechny soubory")
    print("="*50)

if __name__ == "__main__":
    main()
