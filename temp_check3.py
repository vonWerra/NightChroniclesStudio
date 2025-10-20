import importlib.util, sys
spec = importlib.util.find_spec('studio_gui.src.main')
print('spec:', spec)
if spec:
    print('origin:', spec.origin)
else:
    print('spec not found')
print('\nFirst 10 sys.path entries:')
for p in sys.path[:10]:
    print(' -', p)
# Also search for any installed studio_gui package files
import pkgutil, os
matches = []
for finder, name, ispkg in pkgutil.iter_modules():
    if name == 'studio_gui':
        matches.append((finder, name, ispkg))
print('\nstudio_gui modules found via pkgutil (first 20):', len(matches))
# look for any other main.py copies in site-packages
from pathlib import Path
roots = [Path(p) for p in sys.path if p]
candidates = []
for r in roots:
    try:
        for path in r.rglob('main.py'):
            if 'studio_gui' in str(path):
                candidates.append(str(path))
    except Exception:
        pass
print('\nFound candidate main.py files (filtered by name containing "studio_gui"):', len(candidates))
for c in candidates[:20]:
    print(' -', c)
