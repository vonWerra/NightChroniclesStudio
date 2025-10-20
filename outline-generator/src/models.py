# src/models.py
# -*- coding: utf-8 -*-
"""Pydantic models for outline data structures."""

from typing import Literal, Optional, Tuple, Dict, List, ClassVar
from pydantic import BaseModel, Field, field_validator, model_validator
import re
import unicodedata


Lang = Literal["CS", "EN", "DE", "ES", "FR"]


class EpisodeRuntime(BaseModel):
    """Runtime information for an episode."""
    segments: list[str] = Field(default_factory=list, description="List of segment durations")
    sum_minutes: int = Field(description="Total runtime in minutes")

    @field_validator('segments')
    def validate_segments(cls, v):
        """Validate segment format (mm:ss)."""
        import re
        pattern = re.compile(r'^\d{1,2}:\d{2}$')
        for segment in v:
            if not pattern.match(segment):
                raise ValueError(f"Invalid segment format: {segment}. Expected mm:ss")
        return v


class MSPItem(BaseModel):
    """Main Story Point item."""
    timestamp: str = Field(description="Timestamp in mm:ss format")
    text: str = Field(description="Main story point text")
    sources_segment: list[str] = Field(
        default_factory=list,
        description="List of sources for this MSP"
    )

    @field_validator('timestamp')
    def validate_timestamp(cls, v):
        """Validate timestamp format."""
        import re
        if not re.match(r'^\d{1,2}:\d{2}$', v):
            raise ValueError(f"Invalid timestamp format: {v}. Expected mm:ss")
        return v


class Episode(BaseModel):
    """Episode model."""
    index: int = Field(ge=1, description="Episode index starting from 1")
    title: str = Field(min_length=1, max_length=200)
    description: list[str] = Field(default_factory=list)
    msp: list[MSPItem] = Field(default_factory=list, description="Main story points")
    runtime: EpisodeRuntime
    viewer_takeaway: str = Field(min_length=1)
    sources_used: list[str] = Field(default_factory=list)
    confidence_note: str = Field(default="")

    @staticmethod
    def _nfkc(s: str) -> str:
        return unicodedata.normalize("NFKC", s).replace("\u00A0", " ").strip()

    _page_tail: ClassVar[re.Pattern[str]] = re.compile(r"(?:pp?\.?)\s*(\d+)\s*[\-–—]\s*(\d+)\s*$", re.IGNORECASE)

    @classmethod
    def _split_base_and_pages(cls, s: str) -> Tuple[str, Optional[Tuple[int, int]]]:
        s = cls._nfkc(s)
        m = cls._page_tail.search(s)
        if not m:
            return s.rstrip(",; "), None
        base = cls._page_tail.sub("", s).rstrip(",; ")
        a, b = int(m.group(1)), int(m.group(2))
        if a > b:
            a, b = b, a
        return base, (a, b)

    @classmethod
    def _canon_key(cls, s: str) -> str:
        s = cls._nfkc(s)
        s = re.sub(r"\s+", " ", s).strip(",; ").lower()
        return s

    @classmethod
    def _build_available_index(cls, available: list[str]) -> Dict[str, List[Tuple[int, int]] | None]:
        def extract_multi_ranges(s: str) -> List[Tuple[int, int]]:
            m = re.search(r"[,;\s]*(?:pp?\.?)\s*(\d+\s*[\-–—]\s*\d+(?:\s*,\s*\d+\s*[\-–—]\s*\d+)*)\s*$", s, re.IGNORECASE)
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

        idx: Dict[str, List[Tuple[int, int]] | None] = {}
        for src in available:
            base, _ = cls._split_base_and_pages(src)
            key_full = cls._canon_key(base)
            key_strip = cls._canon_key(re.sub(r"\([^)]*\)", " ", base))
            ranges = extract_multi_ranges(src)
            merged = idx.get(key_full)
            if merged is None and key_full in idx:
                # already set to None (no pages) – keep None
                pass
            elif key_full in idx and merged is not None:
                merged.extend(ranges)
                idx[key_full] = merged
            else:
                idx[key_full] = (ranges or None)
            # map stripped key too
            idx[key_strip] = idx[key_full]
        return idx

    @model_validator(mode='after')
    def validate_sources(self):
        """Validate MSP sources against sources_used allowing page subranges.

        Rules:
        - Base (author/title/publisher/year) must match some item in sources_used (Unicode/whitespace normalized).
        - If the matched available item has a page interval, the MSP is allowed to specify a subrange strictly inside it.
          If MSP omits pages while available has pages, it's considered invalid.
        - If the available item has no pages, MSP MUST NOT invent pages.
        """
        available = self.sources_used or []
        if not self.msp:
            return self

        idx = self._build_available_index(available)

        for i, msp_item in enumerate(self.msp, 1):
            if not msp_item.sources_segment:
                raise ValueError(f"MSP {i} must have at least one source")

            for ref in msp_item.sources_segment:
                ref_base, ref_pages = self._split_base_and_pages(ref)
                key = self._canon_key(ref_base)
                if key not in idx:
                    raise ValueError(
                        f"MSP {i} references unknown source: {ref}. Available sources: {', '.join(available)}"
                    )
                avail_pages = idx[key]
                if avail_pages is None:
                    # Available has no pages -> ref must also have none
                    if ref_pages is not None:
                        raise ValueError(
                            f"MSP {i} must not specify pages for source without pages: {ref}. Available sources: {', '.join(available)}"
                        )
                else:
                    # Available has one or more page intervals -> ref must be a subrange inside one of them
                    if ref_pages is None:
                        raise ValueError(
                            f"MSP {i} must specify page subrange for source with pages: {ref}. Available sources: {', '.join(available)}"
                        )
                    a, b = ref_pages
                    ok = False
                    for lo, hi in avail_pages:
                        if lo <= a <= b <= hi:
                            ok = True
                            break
                    if not ok:
                        ranges_str = "; ".join([f"{lo}–{hi}" for lo, hi in avail_pages])
                        raise ValueError(
                            f"MSP {i} page range {a}–{b} outside available ranges {ranges_str} for source: {ref}. Available sources: {', '.join(available)}"
                        )

        return self

    @model_validator(mode='after')
    def validate_msp_count(self):
        """Validate MSP count if configured."""
        # This will be checked against config during generation
        return self


class OutlineJSON(BaseModel):
    """Complete outline structure."""
    language: Lang
    topic: str = Field(min_length=1, max_length=200)
    series_title: str = Field(min_length=1, max_length=200)
    series_context: list[str] = Field(
        default_factory=list,
        description="Context sentences for the series"
    )
    episodes: list[Episode] = Field(
        default_factory=list,
        min_length=1,
        max_length=50
    )

    @field_validator('series_context')
    def validate_context_not_empty(cls, v):
        """Ensure at least one context sentence."""
        if not v:
            raise ValueError("Series context must have at least one sentence")
        return v

    @model_validator(mode='after')
    def validate_episode_indices(self):
        """Validate that episode indices are sequential."""
        if not self.episodes:
            return self

        expected_indices = list(range(1, len(self.episodes) + 1))
        actual_indices = [ep.index for ep in self.episodes]

        if actual_indices != expected_indices:
            raise ValueError(
                f"Episode indices must be sequential starting from 1. "
                f"Expected {expected_indices}, got {actual_indices}"
            )

        return self

    def get_total_runtime(self) -> int:
        """Calculate total runtime across all episodes."""
        return sum(ep.runtime.sum_minutes for ep in self.episodes)

    def get_total_msp_count(self) -> int:
        """Get total count of MSPs across all episodes."""
        return sum(len(ep.msp) for ep in self.episodes)

    def get_unique_sources(self) -> list[str]:
        """Get all unique sources used across episodes."""
        sources = set()
        for ep in self.episodes:
            sources.update(ep.sources_used)
        return sorted(sources)
