from __future__ import annotations

import os
from pathlib import Path
from typing import List, Tuple

from .config import EpisodeConfig, EpisodeMeta, FactsConstraints, Segment, DEFAULT_STYLE, DEFAULT_LEN, DEFAULT_SENT


def load_segments(base_segments_dir: Path, episode_id: str) -> List[Segment]:
    """Load all segment_XX.txt files from narration outputs for given episode.

    Dynamically discovers all segment files (not hard-coded to 1-5).
    Tries multiple encodings for robustness.

    base_segments_dir: typically outputs/narration/<topic>/<lang>/epXX
    """
    segs: List[Segment] = []

    # Dynamically find all segment_*.txt files
    segment_files = sorted(base_segments_dir.glob('segment_*.txt'))

    if not segment_files:
        # Fallback: try numbered segments if glob returns nothing
        # (for compatibility with older structures)
        for i in range(1, 20):  # Check up to 20 segments
            name = f"segment_{i:02d}.txt"
            p = base_segments_dir / name
            if p.exists():
                segment_files.append(p)
            elif i > 5:
                # Stop if we've checked beyond 5 and found nothing
                break

    for p in segment_files:
        name = p.name.removesuffix('.txt')
        text = _read_text_robust(p)
        if text.strip():
            segs.append(Segment(name=name, text=text.strip()))

    return segs


def _read_text_robust(path: Path) -> str:
    """Read text file with multiple encoding fallbacks.

    Tries UTF-8, UTF-8-sig, CP1250, Windows-1250, ISO-8859-2, and finally replace errors.
    """
    encodings = ['utf-8', 'utf-8-sig', 'cp1250', 'windows-1250', 'iso-8859-2']

    for encoding in encodings:
        try:
            text = path.read_text(encoding=encoding)
            # Verify it's readable (contains common characters)
            if any(c in text for c in 'aeiouAEIOU \t\n'):
                return text
        except (UnicodeDecodeError, UnicodeError):
            continue

    # Final fallback: replace errors
    try:
        return path.read_text(encoding='utf-8', errors='replace')
    except Exception:
        return ""


def build_episode_config(series_title: str, episode_title: str, lang: str, segments: List[Segment],
                         style: str | None = None, length_words: str | None = None,
                         sentence_len: str | None = None) -> EpisodeConfig:
    em = EpisodeMeta(
        series_title=series_title,
        episode_title=episode_title,
        target_language=lang,
        target_style=style or DEFAULT_STYLE,
        desired_length_words=length_words or DEFAULT_LEN,
        sentence_length_target=sentence_len or DEFAULT_SENT,
    )
    fc = FactsConstraints(
        must_keep_chronology=True,
        no_fiction=True,
        no_dialogue=True,
        no_reenactment=True,
        keep_roles_explicit=True,
        unify_duplicate_events=True,
    )
    return EpisodeConfig(episode_meta=em, facts_and_constraints=fc, segments=segments)


def ensure_output_dirs(final_root: Path, topic: str, lang: str, episode_id: str) -> Path:
    out_dir = final_root / topic / lang / f"episode_{episode_id}"
    out_dir.mkdir(parents=True, exist_ok=True)
    return out_dir


def write_outputs(out_dir: Path, episode_id: str, text: str, prompt_pack: dict, metrics: dict) -> Tuple[Path, Path, Path]:
    main = out_dir / f"episode_{episode_id}_final.txt"
    main.write_text(text, encoding='utf-8')
    import json
    (out_dir / 'prompt_pack.json').write_text(json.dumps(prompt_pack, ensure_ascii=False, indent=2), encoding='utf-8')
    (out_dir / 'metrics.json').write_text(json.dumps(metrics, ensure_ascii=False, indent=2), encoding='utf-8')
    # basic status file
    (out_dir / 'status.json').write_text(json.dumps({'status': 'ok'}), encoding='utf-8')
    return main, out_dir / 'prompt_pack.json', out_dir / 'metrics.json'
