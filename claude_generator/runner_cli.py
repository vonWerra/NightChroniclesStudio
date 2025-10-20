# python claude_generator/runner_cli.py
"""Non-interactive runner for OptimizedClaudeGenerator.
Accepts --topic, --language, --episodes (comma-separated) and --retry-failed.
Returns exit codes aligned with Subprocess contract.
"""
from __future__ import annotations

import argparse
import sys
import json
from pathlib import Path
from typing import List, TYPE_CHECKING, Any
import logging
try:
    import structlog  # type: ignore
except Exception:
    structlog = None  # type: ignore

if TYPE_CHECKING:
    # For type-checkers only
    from claude_generator.claude_generator import Config, OptimizedClaudeGenerator, ValidationError, APIError  # type: ignore
else:
    # Runtime import with fallback to file-based loader to avoid package import issues
    try:
        from claude_generator.claude_generator import Config, OptimizedClaudeGenerator, ValidationError, APIError  # type: ignore
    except Exception:
        try:
            import importlib.util
            from pathlib import Path

            pkg_dir = Path(__file__).parent
            module_file = pkg_dir / "claude_generator.py"
            if module_file.exists():
                spec = importlib.util.spec_from_file_location("claude_generator_impl", str(module_file))
                _cg = importlib.util.module_from_spec(spec)
                spec.loader.exec_module(_cg)  # type: ignore[attr-defined]
                Config = _cg.Config
                OptimizedClaudeGenerator = _cg.OptimizedClaudeGenerator
                ValidationError = _cg.ValidationError
                APIError = _cg.APIError
            else:
                raise ImportError(f"Module file not found: {module_file}")
        except Exception as e:
            print(f"ERROR: cannot import claude_generator module: {e}", file=sys.stderr)
            sys.exit(5)

EXIT_OK = 0
EXIT_VALIDATION = 2
EXIT_API = 3
EXIT_IO = 4
EXIT_UNEXPECTED = 5


def setup_logging(verbosity: int) -> None:
    """Configure logging and structlog according to verbosity level."""
    level = logging.WARNING
    if verbosity >= 2:
        level = logging.DEBUG
    elif verbosity == 1:
        level = logging.INFO
    logging.basicConfig(level=level, format='%(message)s')
    structlog.configure(processors=[
        structlog.processors.TimeStamper(fmt='iso'),
        structlog.processors.JSONRenderer()
    ])


def _normalize_name(s: str) -> str:
    try:
        import unicodedata, re
        s2 = unicodedata.normalize('NFKD', s)
        s2 = ''.join(ch for ch in s2 if not unicodedata.combining(ch))
        s2 = s2.lower()
        s2 = re.sub(r"[^a-z0-9]+", "_", s2)
        s2 = re.sub(r"_+", "_", s2).strip('_')
        return s2
    except Exception:
        return s.strip().lower()


def _resolve_topic_dir(root: Path, topic_display: str) -> Path:
    exact = root / topic_display
    if exact.exists() and exact.is_dir():
        return exact
    target = _normalize_name(topic_display)
    try:
        for d in root.iterdir():
            if d.is_dir() and _normalize_name(d.name) == target:
                return d
    except Exception:
        pass
    return exact


def find_episode_dirs(prompts_root: Path, topic: str, lang: str) -> List[Path]:
    base = _resolve_topic_dir(prompts_root, topic) / lang
    if not base.exists() or not base.is_dir():
        return []
    eps = sorted([d for d in base.iterdir() if d.is_dir() and d.name.startswith("ep")])
    return eps


def read_expected_segments(ep_dir: Path) -> int:
    meta = ep_dir / "meta" / "episode_context.json"
    try:
        if meta.exists():
            data = json.loads(meta.read_text(encoding="utf-8"))
            return len(data.get("segments", []))
    except Exception:
        pass
    return 0


def count_generated_segments(ep_dir: Path, narration_root: Path, topic: str, lang: str) -> int:
    # Output dir no longer contains trailing 'narration'
    out_dir = _resolve_topic_dir(narration_root, topic) / lang / ep_dir.name
    if not out_dir.exists():
        return 0
    generated = 0
    try:
        for p in out_dir.iterdir():
            if p.name.startswith("segment_") and p.suffix == ".txt":
                generated += 1
    except Exception:
        return 0
    return generated


def should_retry_episode(ep_dir: Path, narration_root: Path, topic: str, lang: str) -> bool:
    expected = read_expected_segments(ep_dir)
    generated = count_generated_segments(ep_dir, narration_root, topic, lang)
    return generated < expected


def main(argv: List[str] | None = None) -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--topic", required=False)
    p.add_argument("--language", required=False)
    p.add_argument("--episodes", help="Comma-separated episode names (ep01,ep02) or omitted for all")
    p.add_argument("--prompt-file", help="Path to a single prompt file to process (absolute or relative)")
    p.add_argument("--retry-failed", action="store_true", help="Only retry episodes that are incomplete")
    p.add_argument("-v", "--verbose", action="count", default=0, help="Increase verbosity (-v, -vv)")
    args = p.parse_args(argv)

    setup_logging(args.verbose)
    logger = structlog.get_logger(__name__)

    try:
        config = Config()
    except Exception as e:
        logger.error("Configuration error", error=str(e))
        return EXIT_VALIDATION

    prompts_root = Path(config.base_output_path)
    narration_root = Path(config.claude_output_path)

    # If prompt-file is provided, process single prompt
    if args.prompt_file:
        pf = Path(args.prompt_file)
        # if relative, make relative to repo cwd
        if not pf.is_absolute():
            pf = (Path.cwd() / pf).resolve()
        try:
            gen = OptimizedClaudeGenerator(config)
        except ValidationError as e:
            logger.error("Validation error", error=str(e))
            return EXIT_VALIDATION
        except APIError as e:
            logger.error("API error", error=str(e))
            return EXIT_API
        except Exception as e:
            logger.exception("Unexpected error", error=str(e))
            return EXIT_UNEXPECTED  # pragma: no cover

        # Implement processing of single prompt file
        def process_single_prompt_file(generator: 'OptimizedClaudeGenerator', prompt_path: Path, narration_root: Path) -> bool:
            prompt_path = prompt_path.resolve()
            if not prompt_path.exists() or not prompt_path.is_file():
                logger.error("Prompt file not found", path=str(prompt_path))
                return False
            prompts_dir = prompt_path.parent
            ep_dir = prompts_dir.parent
            lang_dir = ep_dir.parent
            topic_dir = lang_dir.parent
            # parse msp index
            import re
            m = re.search(r"msp[_-]0*(\d+)", prompt_path.name, flags=re.I)
            if not m:
                logger.error("Cannot parse segment index from filename", filename=prompt_path.name)
                return False
            seg_idx = int(m.group(1))
            try:
                exec_text = prompt_path.read_text(encoding='utf-8')
            except Exception:
                exec_text = prompt_path.read_text(encoding='utf-8', errors='replace')
            fix_path = prompts_dir / f"msp_{seg_idx:02d}_fix_template.txt"
            fix_text = ""
            if fix_path.exists():
                try:
                    fix_text = fix_path.read_text(encoding='utf-8')
                except Exception:
                    fix_text = fix_path.read_text(encoding='utf-8', errors='replace')
            # read target words
            meta_file = ep_dir / 'meta' / 'episode_context.json'
            target_words = 500
            try:
                if meta_file.exists():
                    meta = json.loads(meta_file.read_text(encoding='utf-8'))
                    for s in meta.get('segments', []):
                        if int(s.get('segment_index', -1)) == seg_idx:
                            target_words = int(s.get('word_target', target_words))
                            break
            except Exception:
                pass
            # call generator
            result = generator.generate_segment(exec_text, fix_text, seg_idx, target_words)
            # Output dir no longer contains trailing 'narration'
            output_dir = narration_root / topic_dir.name / lang_dir.name / ep_dir.name
            output_dir.mkdir(parents=True, exist_ok=True)
            if result.final_text:
                out_file = output_dir / f"segment_{seg_idx:02d}.txt"
                out_file.write_text(result.final_text, encoding='utf-8')
            log = {
                'segment_index': result.segment_index,
                'status': result.status.value,
                'attempts': result.attempts,
                'error_message': result.error_message
            }
            (output_dir / f"generation_{seg_idx:02d}.json").write_text(json.dumps(log, ensure_ascii=False, indent=2), encoding='utf-8')
            return result.status in (generator.GenerationStatus.SUCCESS, generator.GenerationStatus.WARNING, generator.GenerationStatus.CACHED) if hasattr(generator, 'GenerationStatus') else (result.status.value in ('success','warning','cached'))

        ok = process_single_prompt_file(gen, pf, narration_root)
        return EXIT_OK if ok else EXIT_UNEXPECTED

    # else regular episode-mode
    if not args.topic or not args.language:
        logger.error("Missing required args", message="--topic and --language are required when not using --prompt-file")
        return EXIT_IO

    all_eps = find_episode_dirs(prompts_root, args.topic, args.language)
    if not all_eps:
        logger.error("No episodes found", path=str(prompts_root / args.topic / args.language))
        return EXIT_IO

    if args.episodes:
        wanted = [e.strip() for e in args.episodes.split(",") if e.strip()]
        eps = [d for d in all_eps if d.name in wanted]
        if not eps:
            logger.error("No matching episodes found for --episodes")
            return EXIT_IO
    else:
        eps = all_eps

    if args.retry_failed:
        filtered = [d for d in eps if should_retry_episode(d, narration_root, args.topic, args.language)]
        eps = filtered

    if not eps:
        logger.info("No episodes to process after filtering.")
        return EXIT_OK

    try:
        gen = OptimizedClaudeGenerator(config)
        results = gen.process_episodes_parallel(eps, narration_root)
    except ValidationError as e:
        logger.error("Validation error", error=str(e))
        return EXIT_VALIDATION
    except APIError as e:
        logger.error("API error", error=str(e))
        return EXIT_API
    except Exception as e:
        logger.exception("Unexpected error while processing episodes", error=str(e))
        return EXIT_UNEXPECTED

    success = all(results.get(ep.name, False) for ep in eps)
    return EXIT_OK if success else EXIT_UNEXPECTED


if __name__ == "__main__":
    rc = main()
    sys.exit(rc)
