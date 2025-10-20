"""Filesystem helpers for topic/episode resolution and normalization."""
from __future__ import annotations

import unicodedata
import re
from pathlib import Path
from typing import Optional

import structlog

logger = structlog.get_logger(__name__)


def normalize_name(name: str) -> str:
    """Normalize name for case-insensitive, diacritics-insensitive comparison.

    Removes diacritics, converts to lowercase, replaces non-alphanumeric with _.
    """
    try:
        # Decompose and remove combining characters (diacritics)
        nfd = unicodedata.normalize('NFKD', name)
        ascii_str = ''.join(ch for ch in nfd if not unicodedata.combining(ch))

        # Lowercase and slug-ify
        slug = ascii_str.lower()
        slug = re.sub(r'[^a-z0-9]+', '_', slug)
        slug = re.sub(r'_+', '_', slug).strip('_')

        return slug
    except Exception as e:
        logger.warning("normalize_name failed, using fallback", name=name, error=str(e))
        return name.lower().strip()


def resolve_topic_dir(root: Path, topic_display: str) -> Path:
    """Resolve topic directory with case-insensitive matching.

    Tries exact match first, then normalized match.
    Returns path even if it doesn't exist (caller decides what to do).
    """
    exact = root / topic_display
    if exact.exists() and exact.is_dir():
        logger.debug("resolve_topic_dir: exact match", root=str(root), topic=topic_display)
        return exact

    try:
        if not root.exists():
            logger.debug("resolve_topic_dir: root doesn't exist, returning exact path", root=str(root))
            return exact

        target_normalized = normalize_name(topic_display)
        for entry in root.iterdir():
            if entry.is_dir() and normalize_name(entry.name) == target_normalized:
                logger.debug("resolve_topic_dir: normalized match",
                             root=str(root), topic=topic_display, resolved=entry.name)
                return entry
    except Exception as e:
        logger.warning("resolve_topic_dir: scan failed", root=str(root), error=str(e))

    logger.debug("resolve_topic_dir: no match, returning exact path", root=str(root), topic=topic_display)
    return exact


def find_topic_in_index(topic_display: str, index: Optional[dict]) -> Optional[str]:
    """Find best-matching topic key in a cached index.

    Tries exact match first, then normalized match.
    """
    if not index or not isinstance(index, dict):
        return None

    topics = index.get('topics', {})
    if not topics:
        return None

    # Exact match first
    if topic_display in topics:
        logger.debug("find_topic_in_index: exact match", topic=topic_display)
        return topic_display

    # Normalized match
    target = normalize_name(topic_display)
    for key in topics.keys():
        if normalize_name(key) == target:
            logger.debug("find_topic_in_index: normalized match",
                         topic=topic_display, matched_key=key)
            return key

    logger.debug("find_topic_in_index: no match", topic=topic_display)
    return None
