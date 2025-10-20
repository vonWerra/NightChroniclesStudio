# python studio_gui/src/fs_index.py
from __future__ import annotations

import os
import json
import time
from pathlib import Path
from typing import Dict, List, Optional, Callable
import threading

TEXT_EXT = {'.txt', '.md', '.json'}


def discover_prompts_root() -> str:
    """Discover prompts output root following priority rules.

    Priority: PROMPTS_OUTPUT_ROOT > NC_OUTPUTS_ROOT/prompts > ./outputs/prompts
    """
    pr = os.environ.get('PROMPTS_OUTPUT_ROOT')
    if pr:
        return pr
    nc = os.environ.get('NC_OUTPUTS_ROOT')
    if nc:
        return os.path.join(nc, 'prompts')
    return os.path.join(os.getcwd(), 'outputs', 'prompts')


def discover_narration_root() -> str:
    """Discover narration output root.

    Priority: NARRATION_OUTPUT_ROOT > NC_OUTPUTS_ROOT/narration > ./outputs/narration
    """
    nr = os.environ.get('NARRATION_OUTPUT_ROOT')
    if nr:
        return nr
    nc = os.environ.get('NC_OUTPUTS_ROOT')
    if nc:
        return os.path.join(nc, 'narration')
    return os.path.join(os.getcwd(), 'outputs', 'narration')


def _safe_scandir(path: Path):
    try:
        with os.scandir(path) as it:
            for e in it:
                yield e
    except Exception:
        return


def list_topics(root: str) -> List[str]:
    p = Path(root)
    if not p.exists() or not p.is_dir():
        return []
    return sorted([e.name for e in _safe_scandir(p) if e.is_dir() and not e.name.startswith('.')])


def list_languages(topic_dir: Path, allowed: Optional[List[str]] = None) -> List[str]:
    langs = []
    for e in _safe_scandir(topic_dir):
        if e.is_dir() and (allowed is None or e.name in allowed):
            langs.append(e.name)
    return sorted(langs)


def list_episodes(lang_dir: Path) -> List[str]:
    eps = []
    for e in _safe_scandir(lang_dir):
        if e.is_dir() and e.name.lower().startswith('ep'):
            eps.append(e.name)
    return sorted(eps)


def list_prompt_files(ep_dir: Path) -> List[Dict]:
    prompts_dir = ep_dir / 'prompts'
    if not prompts_dir.exists() or not prompts_dir.is_dir():
        return []
    out = []
    for e in _safe_scandir(prompts_dir):
        if e.is_file():
            try:
                st = Path(e.path).stat()
            except Exception:
                continue
            out.append({
                'name': e.name,
                'fullpath': str(Path(e.path)),
                'mtime': st.st_mtime,
                'size': st.st_size,
            })
    # Sort by name for deterministic order
    return sorted(out, key=lambda x: x['name'])


def _read_expected_segment_count(ep_path: Path) -> int:
    meta = ep_path / 'meta' / 'episode_context.json'
    try:
        if meta.exists():
            return len(json.loads(meta.read_text(encoding='utf-8')).get('segments', []))
    except Exception:
        return 0
    return 0


def scan_prompts_root(root: Optional[str] = None, allowed_langs: Optional[List[str]] = None, stop_event: Optional[threading.Event] = None, progress_callback: Optional[Callable[[str, int, str], None]] = None) -> Dict:
    """Scan prompts root and return index with topics -> languages -> episodes -> prompts metadata.

    stop_event: threading.Event to support cancellation.
    progress_callback: callable(module:str, percent:int, message:str)
    """
    import threading
    root = root or discover_prompts_root()
    root_p = Path(root)
    index = {'root': str(root_p), 'scanned_at': time.time(), 'topics': {} }
    if not root_p.exists():
        return index
    topics = list_topics(root)
    total_topics = max(1, len(topics))
    tcount = 0
    for topic in topics:
        if stop_event and stop_event.is_set():
            if progress_callback:
                progress_callback('prompts', 0, 'cancelled')
            break
        tpath = root_p / topic
        index['topics'][topic] = {'languages': {}}
        langs = list_languages(tpath, allowed=allowed_langs)
        for lang in langs:
            if stop_event and stop_event.is_set():
                break
            lpath = tpath / lang
            index['topics'][topic]['languages'][lang] = {'episodes': {}}
            eps = list_episodes(lpath)
            for ep in eps:
                if stop_event and stop_event.is_set():
                    break
                epath = lpath / ep
                prompts = list_prompt_files(epath)
                index['topics'][topic]['languages'][lang]['episodes'][ep] = {
                    'prompts': prompts,
                    'expected_segments': _read_expected_segment_count(epath)
                }
        tcount += 1
        if progress_callback:
            pct = int((tcount / total_topics) * 50)
            progress_callback('prompts', pct, f'scanned {tcount}/{total_topics} topics')
    if progress_callback:
        progress_callback('prompts', 50, 'prompts scan done')
    return index


def scan_narration_root(root: Optional[str] = None, stop_event: Optional[threading.Event] = None, progress_callback: Optional[Callable[[str, int, str], None]] = None) -> Dict:
    """Scan narration outputs and return index with segments present per episode.

    stop_event: threading.Event to support cancellation.
    progress_callback: callable(module:str, percent:int, message:str)
    """
    import threading
    root = root or discover_narration_root()
    root_p = Path(root)
    index = {'root': str(root_p), 'scanned_at': time.time(), 'topics': {}}
    if not root_p.exists():
        return index

    topics = list_topics(root)
    total_topics = max(1, len(topics))
    tcount = 0
    for topic in topics:
        if stop_event and stop_event.is_set():
            if progress_callback:
                progress_callback('narration', 0, 'cancelled')
            break
        tpath = root_p / topic
        index['topics'][topic] = {'languages': {}}
        langs = list_languages(tpath)
        for lang in langs:
            if stop_event and stop_event.is_set():
                break
            lpath = tpath / lang
            index['topics'][topic]['languages'][lang] = {'episodes': {}}
            for ep in list_episodes(lpath):
                if stop_event and stop_event.is_set():
                    break
                epath = lpath / ep
                segs = []
                for e in _safe_scandir(epath):
                    if stop_event and stop_event.is_set():
                        break
                    if e.is_file():
                        name = e.name
                        if name.startswith('segment_') and name.lower().endswith('.txt'):
                            try:
                                st = Path(e.path).stat()
                            except Exception:
                                continue
                            segs.append({
                                'name': name,
                                'fullpath': str(Path(e.path)),
                                'mtime': st.st_mtime,
                                'size': st.st_size,
                            })
                index['topics'][topic]['languages'][lang]['episodes'][ep] = {'segments': sorted(segs, key=lambda x: x['name'])}
        tcount += 1
        if progress_callback:
            pct = 50 + int((tcount / total_topics) * 50)
            progress_callback('narration', pct, f'scanned {tcount}/{total_topics} topics')
    if progress_callback:
        progress_callback('narration', 100, 'narration scan done')
    return index


def save_index(path: str, index: Dict):
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    Path(path).write_text(json.dumps(index, ensure_ascii=False, indent=2), encoding='utf-8')


def load_index(path: str) -> Optional[Dict]:
    p = Path(path)
    if not p.exists():
        return None
    try:
        return json.loads(p.read_text(encoding='utf-8'))
    except Exception:
        return None
