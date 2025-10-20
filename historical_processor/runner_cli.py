#!/usr/bin/env python3
"""Post-process runner (non-interactive CLI)

Writes processed texts to <output_base>/<topic>/<lang>/<ep>/ and metadata JSON.
Follows subprocess contract exit codes and structured logging (simple JSON lines).
"""
from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
import os
import sys
import tempfile
import unicodedata
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple


try:
    import structlog
except Exception:  # pragma: no cover - best effort
    structlog = None

# Import helpers: allow running both as package (historical_processor.*) and as module (script).
try:
    from historical_processor.core.config_manager import ConfigManager  # type: ignore
    from historical_processor.core.file_manager import FileManager  # type: ignore
    from historical_processor.processors.text_processor import TextProcessor  # type: ignore
except Exception:
    try:
        from core.config_manager import ConfigManager  # type: ignore
        from core.file_manager import FileManager  # type: ignore
        from processors.text_processor import TextProcessor  # type: ignore
    except Exception:
        # Last resort: adjust sys.path to include this file's parent and try again
        _this_dir = Path(__file__).resolve().parent
        sys.path.insert(0, str(_this_dir))
        sys.path.insert(0, str(_this_dir.parent))
        from core.config_manager import ConfigManager  # type: ignore
        from core.file_manager import FileManager  # type: ignore
        from processors.text_processor import TextProcessor  # type: ignore

EXIT_OK = 0
EXIT_VALIDATION = 2
EXIT_API = 3
EXIT_IO = 4
EXIT_UNEXPECTED = 5

PROCESSOR_VERSION = "historical_processor_v1"


def _setup_logger():
    if structlog:
        structlog.configure(processors=[structlog.processors.JSONRenderer()])
        return structlog.get_logger()
    import logging

    log = logging.getLogger("postprocess")
    if not log.handlers:
        h = logging.StreamHandler(sys.stdout)
        f = logging.Formatter("%(message)s")
        h.setFormatter(f)
        log.addHandler(h)
        log.setLevel(logging.INFO)
    return log


LOGGER = _setup_logger()


def sha256_text(s: str) -> str:
    return hashlib.sha256(s.encode("utf-8")).hexdigest()


def load_rules(rules_path: Optional[Path]) -> Dict[str, Any]:
    if not rules_path:
        return {}
    try:
        return json.loads(rules_path.read_text(encoding="utf-8"))
    except Exception as e:
        LOGGER.error(f"failed_load_rules: {e}")
        return {}


async def process_file(
    in_path: Path,
    out_base: Path,
    rules: Dict[str, Any],
    preset: str = "default",
    dry_run: bool = False,
) -> Dict[str, Any]:
    """Process single text file and return a result dict.

    If dry_run is True, write to a temp file and return its path in 'temp_path'.
    """
    tp = TextProcessor()

    try:
        try:
            src = in_path.read_text(encoding="utf-8")
        except Exception:
            src = in_path.read_text(encoding="utf-8", errors="replace")

        # Basic processing pipeline
        processed = src

        # Preset handling (simple): minimal -> whitespace/punct fixes; default -> + abbreviations; aggressive -> + numbers->words
        if preset in ("minimal",):
            processed = tp.clean_for_gpt(processed)
        else:
            processed = tp.clean_for_gpt(processed)
            processed = tp.prepare_for_tts(processed)
            if preset == "aggressive":
                # try numbers -> words for years and small numbers
                processed = _numbers_to_words(processed)

        # Apply extra regex rules from rules
        if rules:
            processed = _apply_rules(processed, rules)

        rel = in_path
        # Determine topic/lang/ep based on expected layout: .../<topic>/<lang>/<ep>/narration/<file>
        narration_dir = in_path.parent
        ep_dir = narration_dir.parent
        lang_dir = ep_dir.parent
        topic_dir = lang_dir.parent

        topic = topic_dir.name
        lang = lang_dir.name
        ep = ep_dir.name

        # Apply shared narration_core formatter (offline) to unify punctuation/paragraphs
        try:
            from historical_processor.narration_core.formatter import TextFormatter as NCTextFormatter  # type: ignore
            from historical_processor.narration_core.types import FormatterConfig as NCFormatterConfig  # type: ignore
            fmt = NCTextFormatter(NCFormatterConfig(language=lang.upper(), use_gpt_split=False, use_gpt_grammar=False))
            processed = fmt.format(processed)
        except Exception:
            pass

        out_dir = out_base / topic / lang / ep
        out_dir.mkdir(parents=True, exist_ok=True)

        out_file = out_dir / in_path.name

        meta = {
            "source_path": str(in_path.resolve()),
            "source_sha256": sha256_text(src),
            "processor_version": PROCESSOR_VERSION,
            "preset": preset,
            "rules": rules.get("name") if isinstance(rules, dict) else None,
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "language": lang,
            "topic": topic,
            "episode": ep,
            "output_path": str(out_file.resolve()) if not dry_run else None,
        }

        if dry_run:
            # write to temp and return its path
            tf = tempfile.NamedTemporaryFile(delete=False, suffix=".txt", mode="w", encoding="utf-8")
            tf.write(processed)
            tf.flush()
            tf.close()
            meta["temp_path"] = tf.name
            LOGGER.info(json.dumps({"event": "dry_run", "temp_path": tf.name}))
            return {"ok": True, "meta": meta, "temp_path": tf.name}

        # write output
        out_file.write_text(processed, encoding="utf-8")
        meta["output_sha256"] = sha256_text(processed)

        # write metadata
        meta_path = out_file.with_suffix(out_file.suffix + ".meta.json")
        meta_path.write_text(json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8")

        LOGGER.info(json.dumps({"event": "processed", "file": str(out_file), "topic": topic, "lang": lang, "ep": ep}))
        return {"ok": True, "meta": meta}

    except PermissionError as e:
        LOGGER.error(json.dumps({"event": "error", "error": str(e)}))
        return {"ok": False, "error": str(e)}
    except Exception as e:
        LOGGER.error(json.dumps({"event": "error", "error": str(e)}))
        return {"ok": False, "error": str(e)}


def _apply_rules(text: str, rules: Dict[str, Any]) -> str:
    """Apply simple regex-based rules from a dict: {"rules": [{"pattern":"...","replacement":"...","flags":"i"}]}"""
    import re

    rl = rules.get("rules") if isinstance(rules, dict) else None
    if not rl:
        return text
    out = text
    for r in rl:
        pat = r.get("pattern")
        repl = r.get("replacement", "")
        flags = r.get("flags", "")
        f = 0
        if "i" in flags:
            f |= re.IGNORECASE
        try:
            out = re.sub(pat, repl, out, flags=f)
        except Exception as e:
            LOGGER.error(f"rule_error: {e} for pattern: {pat}")
    return out


def _numbers_to_words(text: str) -> str:
    """Try to convert years (1000-2099) into words using num2words if available, else leave unchanged."""
    import re

    try:
        from num2words import num2words  # type: ignore
    except Exception:
        return text

    def repl(m: Any) -> str:
        n = int(m.group(0))
        try:
            return num2words(n, lang="cs")
        except Exception:
            try:
                return num2words(n, lang="en")
            except Exception:
                return str(n)

    return re.sub(r"\b(1[0-9]{3}|20[0-9]{2})\b", repl, text)


async def _gather_with_concurrency(n: int, tasks: List[asyncio.Task]):
    semaphore = asyncio.Semaphore(n)

    async def sem_task(t):
        async with semaphore:
            return await t

    return await asyncio.gather(*(sem_task(t) for t in tasks))


def _collect_txt_files(input_dir: Path) -> List[Path]:
    # expect input_dir to be <...>/<ep>/narration or the narration dir itself
    if input_dir.is_file():
        return [input_dir]
    files = []
    # if path points to an ep dir, search ep_dir / 'narration'
    if (input_dir / "narration").exists():
        scan_dir = input_dir / "narration"
    elif input_dir.name == "narration":
        scan_dir = input_dir
    else:
        # maybe user pointed directly to the topic/lang/ep dir
        # try to find narration subdirs recursively
        cand = list(input_dir.rglob("narration"))
        if cand:
            scan_dir = cand[0]
        else:
            scan_dir = input_dir

    for p in sorted(scan_dir.glob("*.txt")):
        files.append(p)
    return files


def _to_slug(name: str) -> str:
    nfd = unicodedata.normalize("NFD", name)
    s = "".join(ch for ch in nfd if unicodedata.category(ch) != "Mn")
    s = s.lower().replace(" ", "_")
    return s


def _derive_episode_context_from_path(p: Path) -> Tuple[str, str, str, int]:
    ep_dir = p.parent if p.name == "narration" else p
    lang_dir = ep_dir.parent
    topic_dir = lang_dir.parent
    topic = topic_dir.name
    lang = lang_dir.name
    ep = ep_dir.name
    epi = 0
    for part in ep.replace("_", " ").split():
        if part.isdigit():
            epi = int(part)
            break
        if part.lower().startswith("ep"):
            digits = "".join(ch for ch in part if ch.isdigit())
            if digits:
                epi = int(digits)
                break
    return topic, lang, ep, epi


def _find_reuse_merged(topic: str, lang: str, ep_index: int) -> Optional[Path]:
    root_env = Path(os.environ.get("NC_OUTPUTS_ROOT", Path.cwd() / "outputs"))
    narration_root = root_env / "narration"
    if not narration_root.exists():
        return None
    slug = _to_slug(topic)
    patt = f"{slug}_{lang}_episode_{ep_index:03d}*.txt"
    cands = list(narration_root.glob(patt))
    return cands[0] if cands else None


def _sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open('rb') as f:
        for chunk in iter(lambda: f.read(8192), b''):
            h.update(chunk)
    return h.hexdigest()


def _fallback_transition(prev: str, next_: str, language: str) -> str:
    import re as _re
    year = None
    mprev = _re.search(r"\b(1\d{3}|20\d{2})\b", prev)
    mnext = _re.search(r"\b(1\d{3}|20\d{2})\b", next_)
    if mnext:
        year = mnext.group(0)
    elif mprev:
        year = mprev.group(0)
    lang = language.upper()
    if lang == 'CS':
        if year:
            return f"Následně, v roce {year}, plynule navazujeme dalším vývojem."
        return "Na tomto pozadí plynule navazujeme další částí vyprávění."
    if year:
        return f"Subsequently, in {year}, the narrative moves forward naturally."
    return "Against this backdrop, we move seamlessly to the next part of the narrative."


async def process_episode_dir(
    in_dir: Path,
    out_base: Path,
    use_gpt: bool = False,
    prefer_existing: bool = True,
    force_rebuild: bool = False,
    save_merged: bool = True,
) -> Dict[str, Any]:
    """Episode-level processing using narration_core.

    Default keeps offline behavior unless use_gpt is True. If prefer_existing, tries to reuse
    narration_builder merged output.
    """
    from historical_processor.narration_core.generator import IntroGenerator, TransitionGenerator
    from historical_processor.narration_core.formatter import TextFormatter
    from historical_processor.narration_core.types import EpisodeContext, GeneratorConfig, FormatterConfig
    from historical_processor.narration_core.validator import TransitionQualityValidator

    topic, lang, ep, ep_index = _derive_episode_context_from_path(in_dir)

    out_dir = out_base / topic / lang / ep
    out_dir.mkdir(parents=True, exist_ok=True)

    merged_path = out_dir / "episode_merged.txt"

    if prefer_existing and not force_rebuild and merged_path.exists():
        LOGGER.info(json.dumps({"event": "episode_already_present", "file": str(merged_path)}))
        return {"ok": True, "reused": str(merged_path)}

    if prefer_existing and not force_rebuild and ep_index:
        cand = _find_reuse_merged(topic, lang, ep_index)
        if cand and cand.exists():
            try:
                txt = cand.read_text(encoding="utf-8")
            except Exception:
                txt = cand.read_text(encoding="utf-8", errors="replace")
            merged_path.write_text(txt, encoding="utf-8")
            meta = {
                "event": "reused_merged",
                "source_path": str(cand.resolve()),
                "output_path": str(merged_path.resolve()),
                "topic": topic,
                "lang": lang,
                "episode": ep,
                "timestamp": datetime.utcnow().isoformat() + "Z",
            }
            (out_dir / "episode_merged.txt.meta.json").write_text(json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8")
            LOGGER.info(json.dumps({"event": "reused_merged", "file": str(merged_path)}))
            return {"ok": True, "reused": str(merged_path)}

    # read segments
    seg_files = _collect_txt_files(in_dir)
    if not seg_files:
        LOGGER.error(json.dumps({"event": "error", "error": "no_segments"}))
        return {"ok": False, "error": "no_segments"}

    seg_texts: List[str] = []
    for f in seg_files:
        try:
            seg_texts.append(f.read_text(encoding="utf-8").strip())
        except Exception:
            seg_texts.append(f.read_text(encoding="utf-8", errors="replace").strip())

    merged = " ".join(seg_texts)

    if use_gpt:
        api_key = os.environ.get("OPENAI_API_KEY")
        if not api_key:
            LOGGER.error(json.dumps({"event": "error", "error": "missing_openai_api_key"}))
            return {"ok": False, "error": "missing_openai_api_key"}
        intro_gen = IntroGenerator(api_key)
        trans_gen = TransitionGenerator(api_key)
        fmt = TextFormatter(FormatterConfig(language=lang.upper(), use_gpt_split=True, use_gpt_grammar=True, api_key=api_key))
        ctx = EpisodeContext(
            series_title=topic,
            series_context=[],
            episode_title=f"{ep}",
            episode_description=[],
            episode_index=ep_index or 1,
            total_episodes=0,
            language=lang.upper(),
        )
        intro = intro_gen.generate(ctx).text
        combined: List[str] = []
        tv = TransitionQualityValidator(language=lang.upper())
        for i, seg in enumerate(seg_texts):
            combined.append(seg)
            if i < len(seg_texts) - 1:
                attempts = 0
                last_reasons: List[str] = []
                tr_text = ""
                while attempts < 3:
                    gen = trans_gen.generate(seg_texts[i], seg_texts[i+1], language=lang.upper())
                    tr_text = gen.text
                    val = tv.validate(seg_texts[i], seg_texts[i+1], tr_text)
                    if val.ok:
                        break
                    last_reasons = val.reasons
                    attempts += 1
                    LOGGER.info(json.dumps({"event": "transition_retry", "index": i + 1, "reasons": last_reasons, "attempt": attempts}))
                if attempts >= 3 and last_reasons:
                    LOGGER.info(json.dumps({"event": "transition_fallback", "index": i + 1, "reasons": last_reasons}))
                    tr_text = _fallback_transition(seg_texts[i], seg_texts[i+1], lang)
                combined.append(tr_text)
        body = " ".join(combined)
        merged = intro.strip() + "\n\n" + body.strip()
        merged = fmt.format(merged)

    if save_merged:
        merged_path.write_text(merged, encoding="utf-8")
        meta_obj = {
            "event": "episode_merged",
            "topic": topic,
            "lang": lang,
            "episode": ep,
            "length": len(merged),
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "provenance": "gpt" if use_gpt else "offline_or_reuse_failed",
        }
        (out_dir / "episode_merged.txt.meta.json").write_text(
            json.dumps(meta_obj, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        LOGGER.info(json.dumps({"event": "episode_merged", "file": str(merged_path)}))

        # manifest.json (M3c): include all relevant files in episode dir (txt + meta.json), exclude manifest itself
        try:
            files_list: List[Dict[str, Any]] = []
            for fp in sorted(out_dir.rglob("*")):
                if fp.is_dir():
                    continue
                if fp.name == "manifest.json":
                    continue
                if not (fp.suffix.lower() in (".txt", ".json")):
                    continue
                rel = fp.relative_to(out_dir).as_posix()
                files_list.append({
                    "path": rel,
                    "sha256": _sha256_file(fp),
                    "size": fp.stat().st_size,
                })
            manifest = {
                "package_version": "1.0",
                "generated_at": datetime.utcnow().isoformat() + "Z",
                "source": {"topic": topic, "lang": lang, "episode": ep},
                "files": files_list,
            }
            (out_dir / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
            LOGGER.info(json.dumps({"event": "manifest_written", "file": str(out_dir / 'manifest.json')}))
        except Exception as e:
            LOGGER.error(json.dumps({"event": "manifest_error", "error": str(e)}))

    return {"ok": True, "merged_path": str(merged_path) if save_merged else None}


def main(argv: Optional[List[str]] = None) -> int:
    p = argparse.ArgumentParser(prog="historical_processor/runner_cli.py")
    g = p.add_mutually_exclusive_group(required=True)
    g.add_argument("--input-file", help="Single segment file to process")
    g.add_argument("--input-dir", help="Directory to scan for segments (ep dir or narration dir)")
    p.add_argument("--output-dir", help="Optional explicit output dir (overrides configured output_base)")
    p.add_argument("--preset", choices=["default", "minimal", "aggressive"], default="default")
    p.add_argument("--dry-run", action="store_true", help="Do not write outputs, write temp file and print its path")
    p.add_argument("--apply", action="store_true", help="Alias to actually write outputs (default when not --dry-run)")
    p.add_argument("--rules", help="JSON file with extra regex rules")
    p.add_argument("--concurrency", type=int, default=3, help="Concurrency for batch processing (default 3)")
    p.add_argument("--episode-mode", action="store_true", help="Process input-dir as an episode (intro/transitions/formatter)")
    p.add_argument("--use-gpt", action="store_true", help="Use OpenAI to generate intro/transitions and apply formatting")
    # prefer-existing defaults to True; allow disabling via --no-prefer-existing
    p.add_argument("--prefer-existing", dest="prefer_existing", action="store_true", default=True, help="Prefer existing narration merged output if present")
    p.add_argument("--no-prefer-existing", dest="prefer_existing", action="store_false", help="Do not reuse existing narration merged output")
    p.add_argument("--force-rebuild", action="store_true", help="Ignore cache/reuse and rebuild")
    # save-merged defaults to True; allow disabling via --no-save-merged
    p.add_argument("--save-merged", dest="save_merged", action="store_true", default=True, help="Save merged episode output file")
    p.add_argument("--no-save-merged", dest="save_merged", action="store_false", help="Do not write merged episode output file")
    p.add_argument("-v", action="count", default=0)
    args = p.parse_args(argv)

    try:
        cfg = ConfigManager()
    except Exception as e:
        print(f"Configuration error: {e}", file=sys.stderr)
        return EXIT_VALIDATION

    try:
        fm = FileManager(cfg)
    except Exception:
        print("Failed to init FileManager", file=sys.stderr)
        return EXIT_UNEXPECTED

    try:
        if args.output_dir:
            out_base = Path(args.output_dir)
        else:
            out_base = Path(cfg.get("output_base")) if cfg.get("output_base") else Path.cwd() / "outputs" / "postprocess"
        out_base.mkdir(parents=True, exist_ok=True)
    except Exception as e:
        print(f"Output dir error: {e}", file=sys.stderr)
        return EXIT_IO

    rules = load_rules(Path(args.rules)) if args.rules else {}

    files: List[Path] = []
    in_dir: Optional[Path] = None
    if args.input_file:
        f = Path(args.input_file)
        if not f.exists():
            print(f"Input file not found: {f}", file=sys.stderr)
            return EXIT_IO
        files = [f]
    else:
        in_dir = Path(args.input_dir)
        if not in_dir.exists():
            print(f"Input directory not found: {in_dir}", file=sys.stderr)
            return EXIT_IO
        # If episode-mode requested, process at episode level and return
        if args.episode_mode:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            try:
                ep_res = loop.run_until_complete(
                    process_episode_dir(
                        in_dir,
                        out_base,
                        use_gpt=args.use_gpt,
                        prefer_existing=args.prefer_existing,
                        force_rebuild=args.force_rebuild,
                        save_merged=args.save_merged,
                    )
                )
            finally:
                loop.close()
            return EXIT_OK if ep_res.get("ok") else EXIT_UNEXPECTED
        files = _collect_txt_files(in_dir)

    if not files:
        print("No input files found.", file=sys.stderr)
        return EXIT_IO

    # prepare tasks
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)

    async def _run_all():
        tasks = [asyncio.create_task(process_file(f, out_base, rules, preset=args.preset, dry_run=args.dry_run)) for f in files]
        results = await _gather_with_concurrency(args.concurrency, tasks)
        return results

    try:
        results = loop.run_until_complete(_run_all())
    finally:
        loop.close()

    success = True
    for r in results:
        if not r.get("ok"):
            success = False
            LOGGER.error(json.dumps({"event": "segment_failed", "error": r.get("error")}))

    return EXIT_OK if success else EXIT_UNEXPECTED


if __name__ == "__main__":
    rc = main()
    sys.exit(rc)
