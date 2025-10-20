from pathlib import Path
import re
p = Path('studio_gui/src/main.py')
if not p.exists():
    print('main.py not found at', p)
else:
    txt = p.read_text(encoding='utf-8')
    print('main.py path:', p.resolve())
    found = 'def preview_selected' in txt
    print('contains "def preview_selected":', found)
    if found:
        # print snippet around definition
        m = re.search(r"def preview_selected\s*\(.*?\):", txt)
        if m:
            start = m.start()
            snippet = txt[start:start+400]
            print('\n--- snippet ---')
            print(snippet)
    # Also show whether PostProcessTab class exists
    print('contains class PostProcessTab:', 'class PostProcessTab' in txt)
