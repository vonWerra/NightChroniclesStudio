# -*- coding: utf-8 -*-
from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import List, Set


META_PHRASES = {
    "CS": [
        "v této části", "v této kapitole", "v následující části", "nyní se podíváme", "tato sekce",
        "v této epizodě", "v následující epizodě", "v příští části",
    ],
    "EN": [
        "in this section", "in the following section", "now we will look", "this section",
        "in this episode", "in the next episode", "we will see", "we will explore", "let us examine",
    ],
    "DE": [
        "in diesem abschnitt", "im folgenden abschnitt", "nun betrachten wir", "diese sektion",
        "in dieser episode", "in der nächsten episode",
    ],
    "ES": [
        "en esta sección", "en la siguiente sección", "ahora veremos", "esta sección",
        "en este episodio", "en el próximo episodio",
    ],
    "FR": [
        "dans cette section", "dans la section suivante", "nous allons maintenant", "cette section",
        "dans cet épisode", "dans le prochain épisode",
    ],
}

POSSESSIVE_PATTERNS = {
    "CS": [
        r'\bnáš(eho|emu|ím|em|e|i|ich|imi)?\b',  # náš + all cases
        r'\bnaš(eho|emu|ím|em|e|í|ích|ím|imi)?\b',  # naš + all cases
    ],
    "EN": [
        r'\bour\b', r'\bours\b', r'\bmy\b', r'\bmine\b'
    ],
    "DE": [
        r'\bunser(e|em|er|es|en)?\b'
    ],
    "ES": [
        r'\bnuestro(s)?\b', r'\bnuestra(s)?\b'
    ],
    "FR": [
        r'\bnotre\b', r'\bnos\b', r'\bmon\b', r'\bma\b', r'\bmes\b'
    ],
}


@dataclass
class ValidationResult:
    ok: bool
    reasons: List[str]


class TransitionQualityValidator:
    """Validate that a transition is smooth, logical, and non-meta.

    Rules:
    - 1–2 sentences
    - avoid meta phrases (per language)
    - include at least one anchor (if anchors exist in prev/next): year/entity/keyword overlap
    - avoid copying long spans from prev/next (>50% token overlap)
    - no possessive pronouns
    - sentences should be 14-28 words
    """

    SENT_SPLIT = re.compile(r"(?<=[.!?])\s+")
    YEAR_RE = re.compile(r"\b(1\d{3}|20\d{2})\b")

    def __init__(self, language: str):
        self.lang = language.upper()
        self.meta_phrases = [p.lower() for p in META_PHRASES.get(self.lang, META_PHRASES["EN"])]
        self.possessive_patterns = POSSESSIVE_PATTERNS.get(self.lang, POSSESSIVE_PATTERNS["EN"])

    def validate(self, prev: str, next_: str, transition: str) -> ValidationResult:
        reasons: List[str] = []

        # 1) sentence count 1–2
        sentences = self._split_sentences(transition)
        if len(sentences) == 0:
            reasons.append("empty_transition")
        if len(sentences) > 2:
            reasons.append("too_many_sentences")

        low = transition.strip().lower()
        # 2) meta phrases
        if any(p in low for p in self.meta_phrases):
            reasons.append("contains_meta_phrase")

        # 3) anchors
        anchors_prev = self._anchors(prev)
        anchors_next = self._anchors(next_)
        anchors_any = anchors_prev | anchors_next
        if anchors_any:
            if not self._contains_any_anchor(low, anchors_any):
                reasons.append("missing_anchor")

        # 4) duplication check (Jaccard overlap > 0.5 with prev or next)
        toks_tr = self._tokens(low)
        if toks_tr:
            for ctx in (prev, next_):
                j = self._jaccard(toks_tr, self._tokens(ctx.lower()))
                if j > 0.5:
                    reasons.append("too_similar_to_context")
                    break

        # 🆕 5) Check for possessive pronouns
        for pattern in self.possessive_patterns:
            if re.search(pattern, transition, flags=re.IGNORECASE):
                reasons.append("contains_possessive_pronoun")
                break

        # 🆕 6) Check sentence length (14-28 words per sentence)
        for i, sent in enumerate(sentences, 1):
            word_count = len(sent.split())
            if word_count < 14:
                reasons.append(f"sentence_{i}_too_short_{word_count}_words")
            elif word_count > 28:
                reasons.append(f"sentence_{i}_too_long_{word_count}_words")

        return ValidationResult(ok=len(reasons) == 0, reasons=reasons)

    # --- helpers ---
    def _split_sentences(self, text: str) -> List[str]:
        parts = re.split(r"(?<=[.!?])\s+", text.strip())
        return [p for p in parts if p]

    def _tokens(self, text: str) -> Set[str]:
        # simplified tokenization without \p unicode classes
        return {t for t in re.findall(r"[A-Za-zÀ-ÖØ-öø-ÿĀ-žḀ-ỿ0-9]+", text) if t}

    def _anchors(self, text: str) -> Set[str]:
        s = set()
        # years
        s.update(self.YEAR_RE.findall(text))
        # capitalized words (simple heuristic, ignore beginning of sentence effects)
        for m in re.finditer(r"\b[A-ZÁČĎÉĚÍŇÓŘŠŤÚŮÝŽ][a-záčďéěíňóřšťúůýž]+\b", text):
            s.add(m.group(0))
        return s

    def _contains_any_anchor(self, low_text: str, anchors: Set[str]) -> bool:
        for a in anchors:
            if a.lower() in low_text:
                return True
        return False

    def _jaccard(self, a: Set[str], b: Set[str]) -> float:
        if not a or not b:
            return 0.0
        inter = len(a & b)
        union = len(a | b)
        return inter / max(1, union)


class SegmentQualityValidator:
    """Validate full segment narration for style and length compliance."""

    def __init__(self, language: str):
        self.lang = language.upper()
        self.possessive_patterns = POSSESSIVE_PATTERNS.get(self.lang, POSSESSIVE_PATTERNS["EN"])
        self.meta_phrases = [p.lower() for p in META_PHRASES.get(self.lang, META_PHRASES["EN"])]

    def validate(self, text: str, max_sentence_words: int = 30) -> ValidationResult:
        reasons: List[str] = []

        # 1) Check for possessive pronouns
        for pattern in self.possessive_patterns:
            if re.search(pattern, text, flags=re.IGNORECASE):
                reasons.append("contains_possessive_pronoun")
                break

        # 2) Check sentence length
        sentences = re.split(r"(?<=[.!?])\s+", text.strip())
        for i, sent in enumerate(sentences, 1):
            word_count = len(sent.split())
            if word_count > max_sentence_words:
                reasons.append(f"sentence_{i}_exceeds_{word_count}_words")

        # 3) Check for meta-narrative phrases
        low = text.lower()
        for phrase in self.meta_phrases:
            if phrase in low:
                reasons.append(f"contains_meta_phrase_{phrase.replace(' ', '_')}")

        return ValidationResult(ok=len(reasons) == 0, reasons=reasons)
