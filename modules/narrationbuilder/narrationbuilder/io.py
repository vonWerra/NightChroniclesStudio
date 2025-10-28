from __future__ import annotations

import os
from pathlib import Path
from typing import List, Tuple

from .config import EpisodeConfig, EpisodeMeta, FactsConstraints, Segment, DEFAULT_STYLE, DEFAULT_LEN, DEFAULT_SENT


def load_segments(base_segments_dir: Path, episode_id: str) -> List[Segment]:
    """Load segment_01..05.txt from narration outputs for given episode.

    base_segments_dir: typically outputs/narration/<topic>/<lang>/epXX
    """
    segs: List[Segment] = []
    for i in range(1, 6):
        name = f"segment_{i:02d}.txt"
        p = base_segments_dir / name
        if not p.exists():
            # missing segments are allowed; continue
            continue
        text = p.read_text(encoding='utf-8', errors='replace').strip()
        segs.append(Segment(name=name.removesuffix('.txt'), text=text))
    return segs


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
