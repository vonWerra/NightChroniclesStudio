from __future__ import annotations

import os
from pathlib import Path
from typing import Optional

from .logging_utils import emit_evt, log_err
from .io import load_segments, build_episode_config, ensure_output_dirs, write_outputs
from .prompt import SYSTEM_PROMPT, build_user_yaml
from .llm import call_llm


def run_narration(project_root: str, topic_id: str, episode_id: str, lang: str,
                  model: str, style: str, length_words: str, sentence_len: str,
                  dry_run: bool = False) -> int:
    try:
        emit_evt({"type": "phase", "value": "loading_segments"})
        # Resolve roots
        proj = Path(project_root)
        narr_root = proj / 'outputs' / 'narration' / topic_id / lang / f'ep{episode_id}'
        final_root = proj / 'outputs' / 'final'
        if not narr_root.exists():
            log_err(f"Segments directory not found: {narr_root}")
            emit_evt({"type": "error", "code": "invalid-input", "message": "segments dir not found"})
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
        emit_evt({"type": "tokens", "prompt": res.get('prompt_tokens'), "completion": res.get('completion_tokens')})
        emit_evt({"type": "metrics", "latency_sec": res.get('latency_sec'), "provider": "openai", "model": res.get('model')})

        emit_evt({"type": "phase", "value": "writing_output"})
        out_dir = ensure_output_dirs(final_root, topic_id, lang, episode_id)
        main_path, _, _ = write_outputs(out_dir, episode_id, text, prompt_pack, {
            'latency_sec': res.get('latency_sec'),
            'prompt_tokens': res.get('prompt_tokens'),
            'completion_tokens': res.get('completion_tokens'),
            'model': res.get('model'),
        })
        emit_evt({"type": "output_path", "value": str(main_path)})
        emit_evt({"type": "done"})
        return 0
    except Exception as e:
        log_err(f"Unhandled error: {e}")
        emit_evt({"type": "error", "code": "unhandled", "message": str(e)})
        return 5
