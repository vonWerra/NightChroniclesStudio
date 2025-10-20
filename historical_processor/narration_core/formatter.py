# -*- coding: utf-8 -*-
from __future__ import annotations

import re
from typing import Dict, Optional

try:
    from num2words import num2words  # type: ignore
except Exception:  # pragma: no cover - optional
    num2words = None

from .types import FormatterConfig
from openai import OpenAI


class TextFormatter:
    def __init__(self, cfg: FormatterConfig):
        self.cfg = cfg
        self.lang = cfg.language.upper()

    # --- Public API ---
    def format(self, text: str) -> str:
        t = text
        t = self._normalize_whitespace(t)
        t = self._remove_bracketed_citations(t)
        t = self._expand_abbreviations(t)
        t = self._convert_years(t)
        t = self._convert_numbers(t)
        t = self._normalize_ellipsis(t)
        t = self._normalize_quotes_and_dashes(t)
        t = self._ensure_sentence_termination(t)
        if self.cfg.use_gpt_split or self.cfg.use_gpt_grammar:
            t = self._gpt_edit(t)
        else:
            t = self._split_long_sentences(t)
        t = self._final_cleanup(t)
        return t

    # --- Steps ---
    def _normalize_whitespace(self, text: str) -> str:
        # unify newlines and collapse multiple spaces
        t = text.replace("\r\n", "\n").replace("\r", "\n")
        t = re.sub(r"[\u200B\u200C\u200D\uFEFF]", "", t)  # remove zero width chars
        t = re.sub(r"\s+", " ", t)
        t = re.sub(r"\n\s*\n+", "\n\n", t)
        return t.strip()

    def _remove_bracketed_citations(self, text: str) -> str:
        t = re.sub(r"\([A-ZÁČĎÉĚÍŇÓŘŠŤÚŮÝŽ][a-záčďéěíňóřšťúůýž]+,?\s+\d{4}\)", "", text)
        t = re.sub(r"\[[^\]]+\]", "", t)
        t = re.sub(r"(?i)podle\s+[A-ZÁČĎÉĚÍŇÓŘŠŤÚŮÝŽ][a-záčďéěíňóřšťúůýž]+a?", "", t)
        return t

    def _expand_abbreviations(self, text: str) -> str:
        maps: Dict[str, Dict[str, str]] = {
            'CS': {
                'např.': 'například', 'tzv.': 'takzvaný', 'tj.': 'to jest', 'tzn.': 'to znamená',
                'atd.': 'a tak dále', 'apod.': 'a podobně', 'resp.': 'respektive', 'popř.': 'popřípadě',
                'cca': 'cirka', 'č.': 'číslo', 'str.': 'strana', 'odd.': 'oddíl', 'ods.': 'odstavec',
                'kpt.': 'kapitán', 'plk.': 'plukovník', 'gen.': 'generál', 'dr.': 'doktor', 'prof.': 'profesor', 'ing.': 'inženýr'
            },
            'EN': {'e.g.': 'for example', 'i.e.': 'that is', 'etc.': 'et cetera', 'vs.': 'versus', 'ca.': 'circa', 'approx.': 'approximately', 'Dr.': 'Doctor', 'Prof.': 'Professor'},
            'DE': {'z.B.': 'zum Beispiel', 'd.h.': 'das heißt', 'usw.': 'und so weiter', 'bzw.': 'beziehungsweise', 'ca.': 'circa', 'Dr.': 'Doktor', 'Prof.': 'Professor'},
            'ES': {'p.ej.': 'por ejemplo', 'etc.': 'etcétera', 'aprox.': 'aproximadamente', 'Dr.': 'Doctor', 'Prof.': 'Profesor'},
            'FR': {'p.ex.': 'par exemple', 'c.-à-d.': "c'est-à-dire", 'etc.': 'et cetera', 'env.': 'environ', 'Dr.': 'Docteur', 'Prof.': 'Professeur'},
        }
        m = maps.get(self.lang, maps['CS'])
        t = text
        for abbr, full in m.items():
            t = re.sub(rf"\b{re.escape(abbr)}\b", full, t)
        return t

    def _convert_years(self, text: str) -> str:
        if not num2words:
            return text
        def repl(m):
            y = int(m.group(0))
            try:
                out = num2words(y, lang=self._n2w_lang())
                return out.replace(" ", "").replace("-", "").replace("\u200B", "")
            except Exception:
                return m.group(0)
        return re.sub(r"\b(1\d{3}|20\d{2})\b", repl, text)

    def _convert_numbers(self, text: str) -> str:
        if not num2words:
            return text
        def repl(m):
            n = int(m.group(0))
            if 1 <= n <= 999:
                try:
                    out = num2words(n, lang=self._n2w_lang())
                    return out.replace(" ", "").replace("-", "").replace("\u200B", "")
                except Exception:
                    return m.group(0)
            return m.group(0)
        return re.sub(r"(?<!\d)\b([1-9]\d{0,2})(?!\d)", repl, text)

    def _normalize_ellipsis(self, text: str) -> str:
        t = text
        if self.cfg.use_single_ellipsis_char:
            t = t.replace("...", "…")
        # collapse multiple ellipses
        t = re.sub(r"…{2,}", "…", t)
        return t

    def _normalize_quotes_and_dashes(self, text: str) -> str:
        t = text
        # normalize dashes
        if self.cfg.use_en_dash_for_aside:
            t = re.sub(r"\s+-\s+", " – ", t)
        # basic quotes normalization (language-aware minimal)
        if self.lang in ("CS", "DE"):
            t = t.replace('"', '"')  # no-op placeholder, real mapping might be added later
        elif self.lang == "EN":
            t = t.replace('"', '"')
        elif self.lang in ("ES", "FR"):
            t = t.replace('"', '"')
        return t

    def _ensure_sentence_termination(self, text: str) -> str:
        # ensure each paragraph ends with terminal punctuation without relying on \p unicode classes
        paragraphs = re.split(r"\n\n+", text.strip())
        fixed = []
        for p in paragraphs:
            p = p.strip()
            if not p:
                continue
            last = p[-1]
            if last not in ".!?…":
                p = p + "."
            fixed.append(p)
        t = "\n\n".join(fixed)
        # ensure one space after punctuation, none before
        t = re.sub(r"\s+([.,!?;:])", r"\1", t)
        t = re.sub(r"([.,!?;:])\s*", r"\1 ", t)
        return t

    def _split_long_sentences(self, text: str) -> str:
        # heuristic: split sentences longer than ~30 words at commas or conjunctions
        sentences = re.split(r"(?<=[.!?…])\s+", text)
        out = []
        for s in sentences:
            words = s.split()
            if len(words) <= 30:
                out.append(s)
                continue
            out.extend(self._intelligent_split(words))
        return " ".join(out)

    def _intelligent_split(self, words):
        # split near middle at comma or conjunction
        n = len(words)
        if n <= 30:
            return [" ".join(words)]
        mid = n // 2
        # prefer comma near middle
        comma_idx = None
        for i in range(max(10, mid - 10), min(n - 10, mid + 10)):
            if ',' in words[i]:
                comma_idx = i
                break
        if comma_idx is not None:
            first_part = " ".join(words[:comma_idx + 1]).rstrip(", ")
            second_part = " ".join(words[comma_idx + 1:])
            return [first_part + ".", self._capitalize_first(second_part)]
        # fallback: split at nearest conjunction
        conj = {"a", "ale", "však", "zatímco", "protože", "nebo"}
        best = None
        for i in range(max(10, mid - 10), min(n - 10, mid + 10)):
            token = words[i].strip(",").lower()
            if token in conj:
                best = i
                break
        if best is not None:
            first_part = " ".join(words[:best]).rstrip(", ")
            second_part = " ".join(words[best:])
            return [first_part + ".", self._capitalize_first(second_part)]
        # last resort: hard split
        first_part = " ".join(words[:mid]).rstrip(", ")
        second_part = " ".join(words[mid:])
        return [first_part + ".", self._capitalize_first(second_part)]

    def _capitalize_first(self, s: str) -> str:
        return s[:1].upper() + s[1:] if s else s

    def _final_cleanup(self, text: str) -> str:
        t = text
        # collapse duplicate punctuation
        t = re.sub(r"([.!?]){2,}", r"\1", t)
        # ensure spacing rules
        t = re.sub(r"\s+([.,!?;:])", r"\1", t)
        t = re.sub(r"([.,!?;:])\s*", r"\1 ", t)
        # collapse multiple newlines and spaces
        t = re.sub(r"\n\s*\n+", "\n\n", t)
        t = re.sub(r"\s+", " ", t)
        return t.strip()

    # --- GPT assisted editing (optional) ---
    def _gpt_edit(self, text: str) -> str:
        api_key = self.cfg.api_key
        if not api_key:
            # fallback to offline splitting if API missing
            return self._split_long_sentences(text)
        client = OpenAI(api_key=api_key)
        lang_full = {
            'CS': 'Czech', 'EN': 'English', 'DE': 'German', 'ES': 'Spanish', 'FR': 'French'
        }.get(self.lang, 'Czech')

        prompt = (
            f"You are a professional {lang_full} text editor for documentary narration.\n"
            "Rules:\n"
            "1) Split only sentences longer than ~30 words into 2 shorter sentences; keep meaning.\n"
            "2) Fix only obvious grammar/spelling/punctuation errors conservatively.\n"
            "3) Keep documentary, neutral tone.\n"
            "4) Do not add or remove factual content.\n"
            "Return ONLY the processed text."
        )
        try:
            resp = client.chat.completions.create(
                model=self.cfg.model,
                messages=[
                    {"role": "system", "content": "You are a conservative text editor."},
                    {"role": "user", "content": prompt + "\n\nTEXT:\n" + text},
                ],
                temperature=min(self.cfg.temperature_split, self.cfg.temperature_grammar),
                max_tokens=20000,
            )
            out = (resp.choices[0].message.content or "").strip()
            return out if out else text
        except Exception:
            return self._split_long_sentences(text)

    def _n2w_lang(self) -> str:
        mapping = {'CS': 'cs', 'EN': 'en', 'DE': 'de', 'ES': 'es', 'FR': 'fr'}
        return mapping.get(self.lang, 'cs')
