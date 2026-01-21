from __future__ import annotations

import os
import re
from pathlib import Path
from typing import Optional, Dict, List, Any

from .logging_utils import emit_evt, log_err
from .io import load_segments, build_episode_config, ensure_output_dirs, write_outputs
from .prompt import SYSTEM_PROMPT, build_user_yaml
from .llm import call_llm
from .config import EpisodeConfig


def _count_words(text: str) -> int:
    """Count words in text (simple whitespace split)."""
    return len(text.split())


def _validate_output(text: str, config: EpisodeConfig, lang: str) -> Dict[str, Any]:
    """Validate final narrative output quality.

    Returns dict with:
        - word_count: int
        - quality_score: float (0.0-1.0)
        - warnings: List[str]
    """
    warnings: List[str] = []
    word_count = _count_words(text)

    # Parse target word range
    target_range = config.episode_meta.desired_length_words
    try:
        parts = target_range.split('-')
        min_words = int(parts[0].strip())
        max_words = int(parts[1].strip()) if len(parts) > 1 else min_words + 500
    except Exception:
        min_words, max_words = 1500, 2500

    # Check word count
    if word_count < min_words:
        warnings.append(f"Output too short: {word_count} words (target: {min_words}-{max_words})")
    elif word_count > max_words:
        warnings.append(f"Output too long: {word_count} words (target: {min_words}-{max_words})")

    # Check for empty paragraphs or excessive whitespace
    if '\n\n\n' in text:
        warnings.append("Contains excessive whitespace (triple newlines)")

    # Check language (simple heuristic)
    if lang.upper() == 'CS':
        # Check for Czech-specific characters
        czech_chars = set('áčďéěíňóřšťúůýžÁČĎÉĚÍŇÓŘŠŤÚŮÝŽ')
        if not any(c in text for c in czech_chars):
            warnings.append("Text may not be in Czech (no Czech diacritics found)")

    # Calculate quality score (0.0-1.0)
    score = 1.0

    # Penalize length deviations
    if word_count < min_words:
        score -= 0.3
    elif word_count > max_words:
        score -= 0.2

    # Penalize warnings
    score -= len(warnings) * 0.1
    score = max(0.0, min(1.0, score))

    return {
        'word_count': word_count,
        'quality_score': score,
        'warnings': warnings,
        'target_min': min_words,
        'target_max': max_words,
    }


def _resolve_path(env_key: str, nc_root_subdir: str, fallback_subdir: str, project_root: Path) -> Path:
    """Resolve path with precedence: specific env var > NC_OUTPUTS_ROOT > project fallback.

    Args:
        env_key: Specific environment variable (e.g., 'NARRATION_OUTPUT_ROOT')
        nc_root_subdir: Subdirectory under NC_OUTPUTS_ROOT (e.g., 'narration')
        fallback_subdir: Fallback relative to project_root (e.g., 'outputs/narration')
        project_root: Project root path
    """
    # Priority 1: Specific env variable
    specific = os.environ.get(env_key)
    if specific:
        return Path(specific)

    # Priority 2: NC_OUTPUTS_ROOT + subdirectory
    nc_root = os.environ.get('NC_OUTPUTS_ROOT')
    if nc_root:
        return Path(nc_root) / nc_root_subdir

    # Priority 3: Project-relative fallback
    return project_root / fallback_subdir


def run_narration(project_root: str, topic_id: str, episode_id: str, lang: str,
                  model: str, style: str, length_words: str, sentence_len: str,
                  dry_run: bool = False) -> int:
    try:
        emit_evt({"type": "phase", "value": "loading_segments"})
        # Resolve roots with environment variable support
        proj = Path(project_root)

        # Narration input (from claude_generator)
        narr_base = _resolve_path('NARRATION_OUTPUT_ROOT', 'narration', 'outputs/narration', proj)
        narr_root = narr_base / topic_id / lang / f'ep{episode_id}'

        # Final output
        final_root = _resolve_path('FINAL_OUTPUT_ROOT', 'final', 'outputs/final', proj)

        if not narr_root.exists():
            log_err(f"Segments directory not found: {narr_root}")
            emit_evt({"type": "error", "code": "invalid-input", "message": f"segments dir not found: {narr_root}"})
            return 2
        segs = load_segments(narr_root, episode_id)
        if not segs:
            log_err("No segments found (segment_01..05.txt)")
            emit_evt({"type": "error", "code": "invalid-input", "message": "no segments"})
            return 2

        # Series/Episode naming (simple derivation)
        series_title = topic_id.replace('-', ' ').title()
        episode_title = f"Epizoda {int(episode_id)}"
        cfg = build_episode_config(series_title, episode_title, lang, segs, style, length_words, sentence_len)
        user_yaml = build_user_yaml(cfg)
        prompt_pack = {
            'system_prompt': SYSTEM_PROMPT,
            'user_yaml': user_yaml,
            'model': model,
            'lang': lang,
            'topic_id': topic_id,
            'episode_id': episode_id,
        }
        emit_evt({"type": "phase", "value": "building_prompt"})
        if dry_run:
            out_dir = ensure_output_dirs(final_root, topic_id, lang, episode_id)
            write_outputs(out_dir, episode_id, "", prompt_pack, {"dry_run": True})
            emit_evt({"type": "done"})
            return 0

        messages = [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": user_yaml},
        ]
        emit_evt({"type": "phase", "value": "calling_llm"})
        res = None
        try:
            res = call_llm(messages, model=model)
        except Exception as e:
            # fallback to gpt-4.1 if configured model fails
            fallback = 'gpt-4.1'
            emit_evt({"type": "warn", "message": f"primary model failed: {e}; falling back to {fallback}"})
            try:
                res = call_llm(messages, model=fallback)
            except Exception as e2:
                log_err(f"Provider error: {e2}")
                emit_evt({"type": "error", "code": "provider-error", "message": str(e2)})
                return 3

        text = (res or {}).get('text', '') or ''
        if not text.strip():
            log_err("Empty response from provider")
            emit_evt({"type": "error", "code": "provider-empty", "message": "empty response"})
            return 3

        # Validate output quality
        validation_result = _validate_output(text, cfg, lang)
        if validation_result['warnings']:
            for warn in validation_result['warnings']:
                emit_evt({"type": "warn", "message": warn})

        emit_evt({"type": "validation", "word_count": validation_result['word_count'],
                  "quality_score": validation_result['quality_score']})
        emit_evt({"type": "tokens", "prompt": res.get('prompt_tokens'), "completion": res.get('completion_tokens')})
        emit_evt({"type": "metrics", "latency_sec": res.get('latency_sec'), "provider": "openai", "model": res.get('model')})

        emit_evt({"type": "phase", "value": "writing_output"})
        out_dir = ensure_output_dirs(final_root, topic_id, lang, episode_id)
        main_path, _, _ = write_outputs(out_dir, episode_id, text, prompt_pack, {
            'latency_sec': res.get('latency_sec'),
            'prompt_tokens': res.get('prompt_tokens'),
            'completion_tokens': res.get('completion_tokens'),
            'model': res.get('model'),
            'validation': validation_result,
        })
        emit_evt({"type": "output_path", "value": str(main_path)})
        emit_evt({"type": "done"})
        return 0
    except Exception as e:
        log_err(f"Unhandled error: {e}")
        emit_evt({"type": "error", "code": "unhandled", "message": str(e)})
        return 5
