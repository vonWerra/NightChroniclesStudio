#!/usr/bin/env python3
r"""
Generate per-episode prompts for Claude from osnova.json files.

Interaktivní výběr tématu a jazyka z D:\NightChronicles\Osnova\output\
Výstup do D:\NightChronicles\B_core\outputs\

Exit codes:
 0 OK | 2 bad inputs | 3 schema validation failed | 4 prompt generation error | 5 unexpected error
"""
from __future__ import annotations

import argparse
import json
import math
import os
import re
import shutil
import sys
import unicodedata
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Tuple

import logging
import structlog

try:
    from jsonschema import validate
    from jsonschema.exceptions import ValidationError
except ImportError as e:
    print("ERROR: jsonschema is required. Install with: pip install jsonschema", file=sys.stderr)
    sys.exit(2)

# Logging setup

def setup_logging(verbosity: int) -> None:
    level = logging.WARNING
    if verbosity == 1:
        level = logging.INFO
    elif verbosity >= 2:
        level = logging.DEBUG
    logging.basicConfig(level=level, format="%(message)s")
    structlog.configure(
        processors=[
            structlog.processors.add_log_level,
            structlog.processors.TimeStamper(fmt="iso"),
            structlog.dev.ConsoleRenderer()
        ],
        wrapper_class=structlog.make_filtering_bound_logger(level),
        logger_factory=structlog.PrintLoggerFactory(),
    )

logger = structlog.get_logger()

# Kořenové cesty – konfigurovatelné přes environment variables
# Default BASE_DIR = repo root (parent of this file's parent)
BASE_DIR = Path(__file__).resolve().parents[1]
NC_OUTPUTS_ROOT = os.environ.get("NC_OUTPUTS_ROOT")  # např. ../outputs
OUTLINE_OUTPUT_ROOT = os.environ.get("OUTLINE_OUTPUT_ROOT")  # např. ../outputs/outline
PROMPTS_OUTPUT_ROOT = os.environ.get("PROMPTS_OUTPUT_ROOT")  # např. ../outputs/prompts

# Vstupní osnova (centrálně z outputs/outline, s fallbackem na původní umístění)
if OUTLINE_OUTPUT_ROOT:
    OSNOVA_DIR = Path(OUTLINE_OUTPUT_ROOT)
elif NC_OUTPUTS_ROOT:
    OSNOVA_DIR = Path(NC_OUTPUTS_ROOT) / "outline"
else:
    OSNOVA_DIR = BASE_DIR / "outline-generator" / "output"

# Lokální kořen B_core pro konfiguraci a šablony (neměníme)
B_CORE_DIR = BASE_DIR / "B_core"
CONFIG_DIR = B_CORE_DIR / "config"
TEMPLATES_DIR = B_CORE_DIR / "templates"

# Výstupy promptů (centrálně do outputs/prompts s fallbackem)
if PROMPTS_OUTPUT_ROOT:
    OUTPUTS_DIR = Path(PROMPTS_OUTPUT_ROOT)
elif NC_OUTPUTS_ROOT:
    OUTPUTS_DIR = Path(NC_OUTPUTS_ROOT) / "prompts"
else:
    OUTPUTS_DIR = B_CORE_DIR / "outputs"

# ---------------------------
# Utilities
# ---------------------------

def die(code: int, msg: str) -> None:
    logger.error(msg)
    sys.exit(code)


def slugify(s: str) -> str:
    """Převede text na ASCII bez diakritiky."""
    s_norm = unicodedata.normalize("NFKD", s)
    s_ascii = s_norm.encode("ascii", "ignore").decode("ascii")
    s_ascii = s_ascii.lower()
    s_ascii = re.sub(r"[^a-z0-9]+", "_", s_ascii)
    s_ascii = re.sub(r"_+", "_", s_ascii).strip("_")
    return s_ascii or "topic"


def parse_mm_ss(mmss: str) -> int:
    """Return seconds from a string like '12:30' or '13:00'."""
    m = re.fullmatch(r"(\d+):(\d{2})", mmss.strip())
    if not m:
        raise ValueError(f"Invalid mm:ss duration: {mmss!r}")
    minutes = int(m.group(1))
    seconds = int(m.group(2))
    if seconds >= 60:
        raise ValueError(f"Invalid seconds in duration: {mmss!r}")
    return minutes * 60 + seconds


def round_half_up(x: float) -> int:
    return int(math.floor(x + 0.5))


def minutes_round_half_up_from_mmss(mmss: str) -> int:
    total_sec = parse_mm_ss(mmss)
    return round_half_up(total_sec / 60.0)


def round_word_target(minutes_target: int, wpm: int) -> int:
    return round_half_up(minutes_target * wpm * 0.9)


def load_json(path: Path) -> Any:
    try:
        with path.open("r", encoding="utf-8") as f:
            return json.load(f)
    except Exception as e:
        die(2, f"Failed to read JSON {path}: {e}")


def load_text(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8")
    except Exception as e:
        die(2, f"Failed to read text {path}: {e}")


def write_text(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8", newline="\n")


def write_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def copy_into(dst_dir: Path, *files: Path) -> None:
    dst_dir.mkdir(parents=True, exist_ok=True)
    for src in files:
        if not src or not src.exists():
            continue
        shutil.copy2(src, dst_dir / src.name)


def extract_msp_label(msp: Any) -> str:
    """
    Safely extract MSP label from various osnova.json formats.

    Supports:
    - str: "Napoleon's rise to power"
    - dict with "text": {"text": "Napoleon...", "sources_segment": [...]}
    - dict with "label": {"label": "Napoleon...", "sources_segment": [...]}
    - dict with "msp": {"msp": "Napoleon...", "sources_segment": [...]}
    - dict with "msp_label": {"msp_label": "Napoleon...", "sources_segment": [...]}

    Returns:
        Extracted label string, or empty string if not found.
    """
    # If MSP is already a string, return it directly
    if isinstance(msp, str):
        return msp.strip()

    # If MSP is a dict, try various common key names
    if isinstance(msp, dict):
        for key in ["text", "label", "msp_label", "msp"]:
            val = msp.get(key, "")
            if val and isinstance(val, str):
                return val.strip()
        # If dict has no recognized keys, log warning and return empty
        logger.warning(
            "MSP dict has no recognized label keys (expected: text, label, msp_label, or msp)",
            msp_keys=list(msp.keys()),
            msp_value=str(msp)[:100]
        )
        return ""

    # Fallback for other types (should not happen in valid osnova.json)
    if msp is None or msp == "":
        return ""

    logger.warning(
        "Unexpected MSP type, attempting string conversion",
        msp_type=type(msp).__name__,
        msp_value=str(msp)[:100]
    )
    return str(msp).strip()


# ---------------------------
# Interaktivní výběr
# ---------------------------

def list_topics() -> List[Path]:
    if not OSNOVA_DIR.exists():
        die(2, f"Osnova directory not found: {OSNOVA_DIR}")
    return [d for d in OSNOVA_DIR.iterdir() if d.is_dir()]


def select_topic(prefer_name: Optional[str] = None) -> Tuple[str, Path]:
    """Vybere téma – nejdřív dle preferovaného názvu, jinak interaktivně."""
    topics = list_topics()
    if not topics:
        die(2, f"No topics found in {OSNOVA_DIR}")

    if prefer_name:
        # case-insensitive match on folder name
        for d in topics:
            if d.name.lower() == prefer_name.lower():
                return d.name, d
        # fallback: substring match
        for d in topics:
            if prefer_name.lower() in d.name.lower():
                return d.name, d
        logger.warning("Topic not found; falling back to interactive selection", topic=prefer_name, root=str(OSNOVA_DIR))

    print("\nDostupná témata:")
    print("-" * 40)
    for i, topic_dir in enumerate(topics, 1):
        print(f"{i}. {topic_dir.name}")

    while True:
        try:
            choice = input(f"\nVyberte číslo tématu (1-{len(topics)}): ").strip()
            idx = int(choice) - 1
            if 0 <= idx < len(topics):
                selected = topics[idx]
                return selected.name, selected
        except (ValueError, IndexError):
            pass
        print("Neplatná volba, zkuste znovu.")


def select_language(topic_dir: Path, prefer_lang: Optional[str] = None) -> str:
    """Vybere jazyk z dostupných složek; umožní předvolbu prefer_lang."""
    languages: List[str] = []
    for lang in ["CS", "EN", "DE", "FR", "ES"]:
        lang_dir = topic_dir / lang
        if lang_dir.exists() and (lang_dir / "osnova.json").exists():
            languages.append(lang)

    if not languages:
        die(2, f"No language folders with osnova.json found in {topic_dir}")

    if prefer_lang:
        u = prefer_lang.upper()
        if u in languages:
            return u
        print(f"WARNING: language '{prefer_lang}' not available for topic {topic_dir.name}. Available: {', '.join(languages)}")

    if len(languages) == 1:
        print(f"\nDostupný pouze jazyk: {languages[0]}")
        return languages[0]

    print("\nDostupné jazyky:")
    print("-" * 40)
    for i, lang in enumerate(languages, 1):
        print(f"{i}. {lang}")

    while True:
        try:
            choice = input(f"\nVyberte číslo jazyka (1-{len(languages)}): ").strip()
            idx = int(choice) - 1
            if 0 <= idx < len(languages):
                return languages[idx]
        except (ValueError, IndexError):
            pass
        print("Neplatná volba, zkuste znovu.")


# ---------------------------
# Core logic
# ---------------------------

def build_episode_context(
    series_title: str,
    episodes_total: int,
    episode: Dict[str, Any],
    idx: int,
    params: Dict[str, Any],
) -> Dict[str, Any]:
    """Vytvoří episode_context.json z dat epizody."""

    # Extract fields
    ep_title = episode.get("title", f"Episode {idx}")
    ep_desc_list = episode.get("description", []) or []
    if isinstance(ep_desc_list, list):
        ep_desc = " ".join([x.strip() for x in ep_desc_list[:2] if isinstance(x, str)])
    else:
        ep_desc = str(ep_desc_list)

    # Segments
    msp_list: List[Dict[str, Any]] = episode.get("msp", [])
    runtime = episode.get("runtime", {})
    seg_times: List[str] = runtime.get("segments", []) or []

    if len(seg_times) != len(msp_list):
        raise ValueError(
            f"Episode {idx}: runtime.segments count {len(seg_times)} != MSP count {len(msp_list)}"
        )

    wpm = int(params.get("wpm", 145))

    segments: List[Dict[str, Any]] = []
    for i, (msp, dur) in enumerate(zip(msp_list, seg_times), start=1):
        minutes_target = minutes_round_half_up_from_mmss(dur)
        word_target = round_word_target(minutes_target, wpm)

        # Use robust MSP label extraction (supports multiple formats)
        label = extract_msp_label(msp)
        if not label:
            raise ValueError(
                f"Episode {idx} segment {i}: missing MSP label. "
                f"MSP format: {type(msp).__name__}, content: {str(msp)[:100]}"
            )

        # Extract sources (handle both dict and string MSP formats)
        if isinstance(msp, dict):
            src_seg = msp.get("sources_segment") or []
        else:
            # If MSP is just a string, sources must come from episode level
            src_seg = []

        if not (isinstance(src_seg, list) and src_seg):
            logger.warning(
                "Segment missing sources_segment, will use episode-level sources",
                episode=idx,
                segment=i,
                msp_label=label
            )
            # Fallback: use episode-level sources if segment has none
            src_seg = episode.get("sources_used", []) or []
        segments.append({
            "segment_index": i,
            "msp_label": label,
            "minutes_target": minutes_target,
            "word_target": word_target,
            "sources_segment": src_seg,
        })

    # Episode-level sources
    seen = set()
    ep_sources: List[str] = []
    for seg in segments:
        for s in seg["sources_segment"]:
            if s not in seen:
                seen.add(s)
                ep_sources.append(s)

    ctx = {
        "series_title": series_title,
        "episodes_total": episodes_total,
        "episode_number": idx,
        "episode_title": ep_title,
        "episode_description": ep_desc,
        "viewer_takeaway": episode.get("viewer_takeaway", ""),
        "sources": ep_sources or episode.get("sources_used", []),
        "confidence_note": episode.get("confidence_note", ""),
        "segments": segments,
        "segments_total": len(segments),
    }

    return ctx


def validate_against_schema(instance: Dict[str, Any], schema: Dict[str, Any]) -> None:
    try:
        validate(instance=instance, schema=schema)
    except ValidationError as ve:
        raise ve


def replace_placeholders(template: str, mapping: Dict[str, str]) -> str:
    def repl(m: re.Match[str]) -> str:
        key = m.group(1)
        return str(mapping.get(key, m.group(0)))
    return re.sub(r"\{([A-Z0-9_]+)\}", repl, template)


# ---------------------------
# Prompt generation
# ---------------------------

def generate_prompts_for_episode(
    episode_dir: Path,
    ctx: Dict[str, Any],
    params: Dict[str, Any],
    segment_prompt_tmpl: str,
    fix_template_tmpl: str,
    fusion_prompt_tmpl: str,
    selected_lang: str,
) -> None:
    """Generuje prompty pro jednu epizodu."""

    prompts_dir = episode_dir / "prompts"
    prompts_dir.mkdir(parents=True, exist_ok=True)

    # Použijeme vybraný jazyk
    lang = selected_lang.lower()
    numbers_style = params.get("numbers_style", "digits_for_years")
    tol_pct = int(params.get("word_tolerance_percent", 3))

    segs_total = ctx.get("segments_total", len(ctx["segments"]))

    for seg in ctx["segments"]:
        idx = seg["segment_index"]
        pad = f"{idx:02d}"
        mapping = {
            "LANG": str(lang),
            "NUMBERS_STYLE": str(numbers_style),
            "SERIES_TITLE": str(ctx["series_title"]),
            "TOTAL_EPISODES": str(ctx["episodes_total"]),
            "EPISODE_NUMBER": str(ctx["episode_number"]),
            "EPISODE_TITLE": str(ctx["episode_title"]),
            "EPISODE_DESCRIPTION": str(ctx["episode_description"]),
            "SEGMENT_INDEX": str(idx),
            "SEGMENTS_TOTAL": str(segs_total),
            "MSP_LABEL": str(seg["msp_label"]),
            "MINUTES_TARGET": str(seg["minutes_target"]),
            "WORD_TARGET": str(seg["word_target"]),
            "WORD_TOLERANCE_PERCENT": str(tol_pct),
            "SOURCES_SEGMENT": ", ".join(seg["sources_segment"]),
        }
        exec_text = replace_placeholders(segment_prompt_tmpl, mapping)

        fix_map = {
            "WORD_TARGET": str(seg["word_target"]),
            "WORD_TOLERANCE_PERCENT": str(tol_pct),
        }
        fix_text = replace_placeholders(fix_template_tmpl, fix_map)

        write_text(prompts_dir / f"msp_{pad}_execution.txt", exec_text)
        write_text(prompts_dir / f"msp_{pad}_fix_template.txt", fix_text)

    # Fusion instructions
    fusion_map = {
        "EPISODE_NUMBER": str(ctx["episode_number"]),
        "SERIES_TITLE": str(ctx["series_title"]),
        "LANG": str(lang),
    }
    fusion_text = replace_placeholders(fusion_prompt_tmpl, fusion_map)
    write_text(prompts_dir / "fusion_instructions.txt", fusion_text)


# ---------------------------
# Main flow
# ---------------------------

def main() -> int:
    parser = argparse.ArgumentParser(description="Generate prompts from osnova.json")
    parser.add_argument("--topic", help="Topic folder name (case-insensitive). If omitted, interactive selection.")
    parser.add_argument("--language", choices=["CS", "EN", "DE", "ES", "FR"], help="Language code. If omitted, interactive selection.")
    parser.add_argument("--yes", "-y", action="store_true", help="Overwrite existing output without asking")
    parser.add_argument("--outline-root", help="Override input outline root (defaults to env OUTLINE_OUTPUT_ROOT or NC_OUTPUTS_ROOT/outline)")
    parser.add_argument("--prompts-root", help="Override output prompts root (defaults to env PROMPTS_OUTPUT_ROOT or NC_OUTPUTS_ROOT/prompts)")
    parser.add_argument("-v", "--verbose", action="count", default=0, help="Increase verbosity (-v INFO, -vv DEBUG)")
    args = parser.parse_args()

    setup_logging(args.verbose)

    logger.info("GENERATE PROMPTS - Night Chronicles")

    # Allow CLI overrides for roots
    global OSNOVA_DIR, OUTPUTS_DIR
    if args.outline_root:
        OSNOVA_DIR = Path(args.outline_root)
    if args.prompts_root:
        OUTPUTS_DIR = Path(args.prompts_root)

    # 1. Výběr tématu
    topic_name, topic_dir = select_topic(args.topic)
    logger.info("Selected topic", topic=topic_name)

    # 2. Výběr jazyka
    selected_lang = select_language(topic_dir, args.language)
    logger.info("Selected language", language=selected_lang)

    # 3. Cesty k souborům
    osnova_path = topic_dir / selected_lang / "osnova.json"

    # Univerzální soubory
    params_path = CONFIG_DIR / "params.json"
    handoff_path = CONFIG_DIR / "handoff_phrases.json"
    schema_path = CONFIG_DIR / "episode_context.schema.json"

    # Šablony
    segment_prompt_path = TEMPLATES_DIR / "segment_prompt.txt"
    fix_template_path = TEMPLATES_DIR / "fix_template.txt"
    fusion_prompt_path = TEMPLATES_DIR / "fusion_prompt.txt"

    # 4. Kontrola existence souborů
    required_files = [
        osnova_path,
        params_path,
        handoff_path,
        segment_prompt_path,
        fix_template_path,
        fusion_prompt_path
    ]

    for file_path in required_files:
        if not file_path.exists():
            die(2, f"Required file not found: {file_path}")

    # Schema je volitelné
    has_schema = schema_path.exists()
    if not has_schema:
        print("WARNING: schema file not found, skipping validation")

    # 5. Načtení dat
    print("\nNačítání souborů...")
    osnova = load_json(osnova_path)
    params = load_json(params_path)
    handoff_phrases = load_json(handoff_path)
    segment_prompt_tmpl = load_text(segment_prompt_path)
    fix_template_tmpl = load_text(fix_template_path)
    fusion_prompt_tmpl = load_text(fusion_prompt_path)

    if has_schema:
        schema = load_json(schema_path)

    # 6. Extract series info
    series_title = (
        osnova.get("series_title") or
        osnova.get("series_title_cs") or
        osnova.get("topic") or
        "Series"
    )

    episodes = osnova.get("episodes") or []
    if not isinstance(episodes, list) or not episodes:
        die(2, "osnova.json: 'episodes' must be a non-empty array")

    episodes_total = len(episodes)

    # 7. Výstupní složka
    # Prefer exact outline topic directory name to keep outputs consistent across modules
    # Fallback: keep slug for backward compatibility if needed elsewhere in metadata
    topic_slug = slugify(topic_name)
    topic_dir_name = topic_dir.name  # exact name from outline root
    output_root = OUTPUTS_DIR / topic_dir_name / selected_lang

    if output_root.exists():
        if args.yes:
            try:
                shutil.rmtree(output_root)
            except Exception as e:
                die(4, f"Failed to remove existing output: {output_root} - {e}")
        else:
            response = input(f"\nVýstup již existuje: {output_root}\nPřepsat? (y/n): ").strip().lower()
            if response == 'y':
                try:
                    shutil.rmtree(output_root)
                except Exception as e:
                    die(4, f"Failed to remove existing output: {output_root} - {e}")
            else:
                print("Operace zrušena.")
                return 0

    # 8. Zpracování epizod
    logger.info("Processing episodes", count=episodes_total, topic=topic_name, language=selected_lang)

    for ep_idx in range(1, episodes_total + 1):
        ep = episodes[ep_idx - 1]
        ep_code = f"ep{ep_idx:02d}"
        ep_dir = output_root / ep_code
        meta_dir = ep_dir / "meta"

        logger.info("Episode", index=ep_idx, title=str(ep.get('title', 'Untitled')))

        # Build episode context
        try:
            ctx = build_episode_context(series_title, episodes_total, ep, ep_idx, params)
            ctx["series_slug"] = topic_slug
            ctx["episode_code"] = ep_code
        except Exception as e:
            die(2, f"Failed to transform episode {ep_idx}: {e}")

        # Validate if schema exists
        if has_schema:
            try:
                validate_against_schema(ctx, schema)
            except ValidationError as ve:
                die(3, f"episode_context.json invalid for episode {ep_idx}: {ve.message}")

        # Write episode_context.json
        meta_dir.mkdir(parents=True, exist_ok=True)
        write_json(meta_dir / "episode_context.json", ctx)

        # Copy meta files (bez canon.json)
        copy_into(meta_dir, params_path, handoff_path, fusion_prompt_path)

        # Generate prompts
        try:
            generate_prompts_for_episode(
                episode_dir=ep_dir,
                ctx=ctx,
                params=params,
                segment_prompt_tmpl=segment_prompt_tmpl,
                fix_template_tmpl=fix_template_tmpl,
                fusion_prompt_tmpl=fusion_prompt_tmpl,
                selected_lang=selected_lang,
            )
        except Exception as e:
            die(4, f"Prompt generation failed for episode {ep_idx}: {e}")

    logger.info("DONE", topic=topic_name, language=selected_lang, output=str(output_root))

    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        print("\nPřerušeno uživatelem.", file=sys.stderr)
        sys.exit(5)
    except Exception as e:
        print(f"\nNeočekávaná chyba: {e}", file=sys.stderr)
        sys.exit(5)
