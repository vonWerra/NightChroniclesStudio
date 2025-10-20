#!/usr/bin/env python3
"""Test instalace všech komponent"""

import sys
import importlib

def test_imports():
    """Testuje dostupnost všech modulů"""
    modules = [
        'anthropic',
        'dotenv',
        'yaml',
        'httpx',
        'aiofiles',
        'keyring',
        'cryptography',
        'psutil'
    ]

    print("Kontrola modulů:")
    all_ok = True

    for module in modules:
        try:
            importlib.import_module(module)
            print(f"✓ {module} - OK")
        except ImportError:
            print(f"✗ {module} - CHYBÍ")
            all_ok = False

    return all_ok

def test_config():
    """Testuje konfiguraci"""
    from dotenv import load_dotenv
    import os

    load_dotenv()

    print("\nKontrolace konfigurace:")

    api_key = os.getenv('ANTHROPIC_API_KEY')
    if api_key:
        print(f"✓ API klíč nalezen ({len(api_key)} znaků)")
    else:
        print("✗ API klíč nenalezen")
        return False

    paths = {
        'OUTPUT_PATH': os.getenv('OUTPUT_PATH'),
        'CLAUDE_OUTPUT': os.getenv('CLAUDE_OUTPUT')
    }

    for name, path in paths.items():
        if path:
            print(f"✓ {name}: {path}")
        else:
            print(f"✗ {name} nenastaven")

    return True

def test_connection():
    """Testuje připojení k API"""
    try:
        from anthropic import Anthropic
        import os
        from dotenv import load_dotenv

        load_dotenv()
        client = Anthropic(api_key=os.getenv('ANTHROPIC_API_KEY'))

        # Jednoduchý test
        response = client.messages.create(
            model="claude-opus-4-1-20250805",
            max_tokens=10,
            messages=[{"role": "user", "content": "Hi"}]
        )

        if response:
            print("\n✓ Připojení k Claude API funguje!")
            return True

    except Exception as e:
        print(f"\n✗ Chyba připojení k API: {e}")
        return False

if __name__ == "__main__":
    print("=== TEST INSTALACE ===\n")

    if not test_imports():
        print("\nNěkteré moduly chybí. Spusťte:")
        print("pip install anthropic python-dotenv pyyaml httpx aiofiles keyring cryptography psutil")
        sys.exit(1)

    if not test_config():
        print("\nKonfigurace není kompletní. Zkontrolujte .env soubor")
        sys.exit(1)

    if test_connection():
        print("\n=== INSTALACE JE KOMPLETNÍ A FUNKČNÍ ===")
    else:
        print("\nInstalace je kompletní, ale API připojení nefunguje.")
        print("Zkontrolujte API klíč a internetové připojení.")
