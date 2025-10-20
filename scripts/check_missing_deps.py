#!/usr/bin/env python3
import importlib
reqs = {
    'anthropic':'anthropic',
    'aiofiles':'aiofiles',
    'python-dotenv':'dotenv',
    'pyyaml':'yaml',
    'httpx':'httpx',
    'keyring':'keyring',
    'cryptography':'cryptography',
    'psutil':'psutil'
}
missing = []
for pkg, mod in reqs.items():
    try:
        importlib.import_module(mod)
        try:
            m = importlib.import_module(mod)
            ver = getattr(m, '__version__', None) or getattr(m, 'VERSION', None)
        except Exception:
            ver = None
        print(f"OK: {pkg} -> {mod}" + (f" (version={ver})" if ver else ""))
    except Exception as e:
        print(f"MISSING: {pkg} ({mod}) - {e}")
        missing.append(pkg)
print("\nMISSING_LIST:", missing)
