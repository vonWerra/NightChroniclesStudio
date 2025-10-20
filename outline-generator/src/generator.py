# src/generator.py
# -*- coding: utf-8 -*-
"""Outline generator with async support and caching."""

import asyncio
import json
import re
import unicodedata
from pathlib import Path
from typing import Optional, Any, TYPE_CHECKING, Callable, Tuple, List, Dict

from src.config import Config
from src.models import OutlineJSON, Episode
from src.api_client import APIClient
from src.cache import CacheManager
from src.logger import setup_logging

# Type checking import - pouze pro IDE, ne pro runtime
if TYPE_CHECKING:
    from src.monitor import Monitor

logger = setup_logging(__name__)

# --- Unicode and citation canonicalization helpers ---
# Normalize to NFKC, replace NBSP with space, strip

def _nfkc(s: str) -> str:
    return unicodedata.normalize("NFKC", s).replace("\u00A0", " ").strip()

# Allow multiple page ranges at the end, e.g., "pp. 102–104, 110–111"
_pages_tail: re.Pattern[str] = re.compile(r"[,;\s]*(?:pp?\.?)\s*(\d+\s*[\-–—]\s*\d+(?:\s*,\s*\d+\s*[\-–—]\s*\d+)*)\s*$", re.IGNORECASE)


def _extract_page_ranges(s: str) -> List[Tuple[int, int]]:
    m = _pages_tail.search(s)
    if not m:
        return []
    tail = m.group(1)
    ranges: List[Tuple[int, int]] = []
    for a, b in re.findall(r"(\d+)\s*[\-–—]\s*(\d+)", tail):
        ia, ib = int(a), int(b)
        if ia > ib:
            ia, ib = ib, ia
        ranges.append((ia, ib))
    return ranges


def _split_base_and_pages_multi(s: str) -> tuple[str, Optional[List[Tuple[int, int]]]]:
    s = _nfkc(s)
    ranges = _extract_page_ranges(s)
    if not ranges:
        return s.rstrip(",; "), None
    base = _pages_tail.sub("", s).rstrip(",; ")
    return base, ranges


def _strip_parens(s: str) -> str:
    return re.sub(r"\([^)]*\)", " ", s)


def _canon_keys(s: str) -> List[str]:
    """Return list of canonical keys for matching: [full_base, paren_stripped]."""
    full = _canon_key(s)
    stripped = _canon_key(_strip_parens(s))
    keys = [full]
    if stripped != full:
        keys.append(stripped)
    return keys


def _canon_key(s: str) -> str:
    # Canonical key: NFKC, single spaces, strip trailing commas, lowercase
    s = _nfkc(s)
    s = re.sub(r"\s+", " ", s).strip(",; ").lower()
    return s


def _build_available_index(available: List[str]) -> Dict[str, Dict[str, Optional[List[Tuple[int, int]]]]]:
    """
    Build index: base_key -> { 'full': original_base_string (no pages), 'pages': list[(lo, hi)] | None }
    Maps both full and paren-stripped keys to the same entry. If multiple entries share the same base,
    merge page intervals.
    """
    idx: Dict[str, Dict[str, Optional[List[Tuple[int, int]]]]] = {}
    by_base: Dict[str, Dict[str, Optional[List[Tuple[int, int]]]]] = {}
    for src in available:
        base, pages = _split_base_and_pages_multi(src)
        key_full = _canon_key(base)
        key_stripped = _canon_key(_strip_parens(base))
        entry = by_base.get(key_full)
        if not entry:
            entry = {"full": base, "pages": (pages[:] if pages else None)}
            by_base[key_full] = entry
        else:
            if entry["pages"] is None:
                entry["pages"] = (pages[:] if pages else None)
            elif pages:
                entry["pages"].extend(pages)
        # Map keys to this entry
        for k in {key_full, key_stripped}:
            idx[k] = entry
    return idx


def canonicalize_msp_sources(msp_sources: List[str], available: List[str]) -> List[str]:
    """
    Map MSP sources_segment strings to exact canonical strings from available sources.
    - If available has pages: allow sub-range inside and format as ", pp. A–B" (en dash).
    - If available has multiple page intervals: clamp to an intersecting interval, or use the first interval.
    - If available has no pages: return the exact canonical base without pages.
    - Preserve diacritics from available; normalize dash/pages/whitespace from MSP refs.
    """
    idx = _build_available_index(available)
    fixed: List[str] = []
    for ref in msp_sources:
        ref_base, ref_pages = _split_base_and_pages_multi(ref)
        entry = None
        for k in _canon_keys(ref_base or ""):
            entry = idx.get(k)
            if entry:
                break
        if not entry:
            fixed.append(ref)
            continue
        av_base = entry["full"]
        av_pages = entry["pages"]
        if av_pages and ref_pages:
            # Find an interval that intersects and clamp into it
            chosen = None
            for lo, hi in av_pages:
                a, b = ref_pages[0]
                if b < lo or a > hi:
                    continue
                a2 = max(a, lo)
                b2 = min(b, hi)
                if a2 <= b2:
                    chosen = (a2, b2)
                    break
            if not chosen:
                lo, hi = av_pages[0]
                chosen = (lo, hi)
            a2, b2 = chosen
            fixed.append(f"{av_base}, pp. {a2}\u2013{b2}")
        elif av_pages and not ref_pages:
            lo, hi = av_pages[0]
            fixed.append(f"{av_base}, pp. {lo}\u2013{hi}")
        else:
            fixed.append(av_base)
    return fixed


def canonicalize_parsed_citations(parsed: dict) -> None:
    """In-place canonicalization of parsed JSON structure produced by the model.
    For each episode, remap each MSP's sources_segment entries to exact strings from sources_used.
    """
    episodes = parsed.get("episodes", [])
    if not isinstance(episodes, list):
        return
    for ep in episodes:
        if not isinstance(ep, dict):
            continue
        available = ep.get("sources_used") or []
        if not isinstance(available, list) or not available:
            continue
        msp_list = ep.get("msp") or []
        if not isinstance(msp_list, list):
            continue
        for msp in msp_list:
            if not isinstance(msp, dict):
                continue
            seg = msp.get("sources_segment") or []
            if isinstance(seg, list) and seg:
                msp["sources_segment"] = canonicalize_msp_sources(seg, available)


class OutlineGenerator:
    """Main generator class for creating outlines."""

    PLACEHOLDER_RE = re.compile(r"\{\{\s*([A-Za-z0-9_.]+)\s*\}\}")

    def __init__(
        self,
        config: Config,
        template: str,
        output_dir: Path,
        use_cache: bool = True,
        monitor: Optional['Monitor'] = None
    ):
        self.config = config
        self.template = template
        self.output_dir = output_dir
        self.use_cache = use_cache
        self.monitor = monitor

        # Initialize API client
        self.api_client = APIClient(
            api_key=config.api_key,
            model=config.model,
            temperature=config.temperature,
            max_tokens=config.max_tokens,
            monitor=monitor
        )

        # Initialize cache
        self.cache = CacheManager(
            cache_dir=output_dir / ".cache",
            enabled=use_cache,
            ttl_hours=24
        )

        # Pre-render template with config values
        self.rendered_template = self._render_template(template, config.flatten())

    def _render_template(self, template: str, values: dict[str, str]) -> str:
        """Render template with placeholder values."""
        def _sub(match: re.Match) -> str:
            key = match.group(1)
            return values.get(key, match.group(0))

        return self.PLACEHOLDER_RE.sub(_sub, template)

    def _create_prompt(self, lang_code: str) -> str:
        """Create JSON generation prompt for specific language."""
        filled = self.rendered_template.replace("{LANG}", lang_code)

        rules = (
            "You are a strict JSON generator. Return ONLY a single valid UTF-8 JSON object, "
            "with no Markdown, no comments, no trailing prose.\n\n"
            "CRITICAL REQUIREMENTS:\n"
            "- Return pure JSON that can be parsed with json.loads()\n"
            "- Use proper UTF-8 encoding for all text\n"
            "- Ensure all required fields are present\n"
            "- Follow the exact schema specified\n\n"
            "CITATION RULES:\n"
            "- Use EXACT strings from the episode's 'sources_used' array when filling each MSP 'sources_segment'.\n"
            "- If a 'sources_used' item includes a page interval, choose a subrange strictly inside it and format as: \", pp. A–B\".\n"
            "- If a 'sources_used' item has NO pages, DO NOT invent pages; use the exact source string only.\n"
            "- Preserve diacritics and punctuation exactly as shown in 'sources_used'.\n"
            "- Do NOT create, translate, or modify source strings.\n"
        )

        json_schema = f"""
OUTPUT JSON SCHEMA:
{{
  "language": "{lang_code}",
  "topic": "{self.config.topic}",
  "series_title": "string",
  "series_context": ["sentence1", "sentence2", ...],
  "episodes": [
    {{
      "index": 1,
      "title": "string",
      "description": ["sentence1", ...],  // max {self.config.description_max_sentences}
      "msp": [
        {{
          "timestamp": "mm:ss",
          "text": "string with max {self.config.msp_max_words} words",
          "sources_segment": ["source_name1", ...]
        }}
      ],  // exactly {self.config.msp_per_episode} items
      "runtime": {{
        "segments": ["mm:ss", ...],
        "sum_minutes": integer  // {self.config.tolerance_min}-{self.config.tolerance_max}
      }},
      "viewer_takeaway": "string",
      "sources_used": ["source_name1", ...],  // {self.config.sources.per_episode.min}-{self.config.sources.per_episode.max}
      "confidence_note": "string"
    }}
  ]
}}

REQUIREMENTS:
- Language MUST be "{lang_code}"
- Topic MUST be "{self.config.topic}"
- Each episode MUST have exactly {self.config.msp_per_episode} MSP items
- Runtime sum MUST be between {self.config.tolerance_min} and {self.config.tolerance_max} minutes
- Each MSP sources_segment must reference sources from sources_used
"""

        return f"{rules}\n\n{filled}\n\n{json_schema}\n\nGENERATE JSON NOW:"

    async def generate_for_language(self, lang_code: str) -> dict[str, Any]:
        """Generate outline for a specific language."""
        logger.info(f"Generating outline for {lang_code}")

        # Progress callback for GUI
        if self.config.progress_callback:
            self.config.progress_callback(f"Generating {lang_code}", 0, len(self.config.languages))

        # Check cache first
        cache_key = f"{self.config.topic}_{lang_code}_{self.config.model}"
        if self.use_cache:
            cached = self.cache.get(cache_key)
            if cached:
                logger.info(f"Using cached result for {lang_code}")
                if self.monitor:
                    self.monitor.record_cache_hit()
                return cached
            elif self.monitor:
                self.monitor.record_cache_miss()

        try:
            # Create prompt
            prompt = self._create_prompt(lang_code)

            # Call API
            raw_response = await self.api_client.generate(prompt)

            # Parse JSON
            parsed = self._parse_json_response(raw_response)

            # Canonicalize citations to match sources_used and normalize pages/diacritics
            canonicalize_parsed_citations(parsed)

            # Validate with Pydantic
            outline = OutlineJSON(**parsed)

            # Ensure correct language and topic
            if outline.language != lang_code:
                logger.warning(f"Language mismatch: expected {lang_code}, got {outline.language}")
                outline.language = lang_code

            if outline.topic != self.config.topic:
                logger.warning(f"Topic mismatch: expected {self.config.topic}, got {outline.topic}")
                outline.topic = self.config.topic

            # Save to files
            output_path = await self._save_outline(outline, lang_code)

            result = {
                "success": True,
                "language": lang_code,
                "outline": outline.model_dump(),  # Convert Pydantic to dict for JSON serialization
                "output_path": str(output_path)  # Convert Path to string
            }

            # Cache the result
            if self.use_cache:
                self.cache.set(cache_key, result)

            logger.info(f"Successfully generated outline for {lang_code}")

            # Progress callback
            if self.config.progress_callback:
                idx = self.config.languages.index(lang_code) + 1
                self.config.progress_callback(f"Completed {lang_code}", idx, len(self.config.languages))

            return result

        except Exception as e:
            logger.error(f"Failed to generate outline for {lang_code}: {e}")
            return {
                "success": False,
                "language": lang_code,
                "error": str(e)
            }

    def _parse_json_response(self, raw: str) -> dict:
        """Robustly parse JSON from LLM response."""
        # Try direct parsing
        try:
            return json.loads(raw)
        except json.JSONDecodeError:
            pass

        # Try to extract JSON object
        start = raw.find("{")
        end = raw.rfind("}")
        if start != -1 and end != -1 and end > start:
            try:
                return json.loads(raw[start:end+1])
            except json.JSONDecodeError:
                pass

        # Try to remove markdown code blocks
        cleaned = re.sub(r'^```json?\s*', '', raw)
        cleaned = re.sub(r'\s*```$', '', cleaned)
        try:
            return json.loads(cleaned)
        except json.JSONDecodeError:
            pass

        # Last resort - use LLM to fix it
        logger.warning("Failed to parse JSON, attempting repair")
        raise ValueError(f"Could not parse JSON from response")

    async def _save_outline(self, outline: OutlineJSON, lang_code: str) -> Path:
        """Save outline to JSON and TXT files."""
        # Determine output path based on config
        topic_safe = self._sanitize_filename(self.config.topic)

        if self.config.output.use_project_structure and self.config.output.project_root:
            # New unified structure: projects/{topic}/{lang}/01_outline/
            lang_dir = self.config.output.project_root / topic_safe / lang_code / "01_outline"
        else:
            # Legacy structure: output/{topic}/{lang}/
            lang_dir = self.output_dir / topic_safe / lang_code

        lang_dir.mkdir(parents=True, exist_ok=True)

        # Save JSON
        json_path = lang_dir / "osnova.json"
        json_content = json.dumps(
            outline.model_dump(),
            ensure_ascii=False,
            indent=2
        )
        json_path.write_text(json_content, encoding='utf-8')
        logger.debug(f"Saved JSON to {json_path}")

        # Save TXT
        txt_path = lang_dir / "osnova.txt"
        txt_content = self._format_as_text(outline)
        txt_path.write_text(txt_content, encoding='utf-8')
        logger.debug(f"Saved TXT to {txt_path}")

        return lang_dir

    def _sanitize_filename(self, name: str) -> str:
        """Sanitize string for use as filename."""
        # Replace problematic characters
        sanitized = re.sub(r'[\\/:*?"<>|]+', '_', name)
        # Remove leading/trailing dots and spaces
        sanitized = sanitized.strip('. ')
        # Limit length
        if len(sanitized) > 100:
            sanitized = sanitized[:100]
        return sanitized or "unnamed"

    def _format_as_text(self, outline: OutlineJSON) -> str:
        """Format outline as human-readable text."""
        lines = []

        # Title and context
        lines.append(outline.series_title)
        lines.append("")
        for sentence in outline.series_context:
            lines.append(f"- {sentence}")
        lines.append("")

        # Episodes
        for ep in outline.episodes:
            lines.append(f"Episode {ep.index}: {ep.title}")

            # Description
            for desc in ep.description:
                lines.append(f"  - {desc}")

            # MSPs
            for i, msp in enumerate(ep.msp, 1):
                lines.append(f"    - [{msp.timestamp}] {msp.text}")
                if msp.sources_segment:
                    lines.append(f"      Sources: {', '.join(msp.sources_segment)}")

            # Runtime
            segments_str = ', '.join(ep.runtime.segments)
            lines.append(f"  Runtime: {ep.runtime.sum_minutes} min ({segments_str})")

            # Takeaway
            lines.append(f"  Takeaway: {ep.viewer_takeaway}")

            # Sources
            lines.append(f"  Sources Used: {', '.join(ep.sources_used)}")
            lines.append("")

        return '\n'.join(lines)

    async def generate_all_parallel(self) -> dict[str, dict[str, Any]]:
        """Generate outlines for all languages in parallel."""
        tasks = [
            self.generate_for_language(lang)
            for lang in self.config.languages
        ]
        results = await asyncio.gather(*tasks)

        # Cleanup sessions
        await self.api_client.cleanup()

        return {
            lang: result
            for lang, result in zip(self.config.languages, results)
        }

    async def generate_all_sequential(self) -> dict[str, dict[str, Any]]:
        """Generate outlines for all languages sequentially."""
        results = {}
        for lang in self.config.languages:
            results[lang] = await self.generate_for_language(lang)

        # Cleanup sessions
        await self.api_client.cleanup()

        return results
