#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Text Processor - Zpracování a rozdělení textu
"""

import re
import unicodedata
from typing import List, Optional
from langdetect import detect
from colorama import Fore


class TextProcessor:
    """Zpracování a manipulace s textem"""

    # Výchozí maximální délka pro TTS
    DEFAULT_MAX_CHARS = 9000

    def __init__(self):
        """Inicializace text procesoru"""
        pass

    def split_for_tts(self, text: str, max_chars: int = DEFAULT_MAX_CHARS) -> List[str]:
        """
        Rozdělí text na části pro TTS

        Args:
            text: Text k rozdělení
            max_chars: Maximální počet znaků na část

        Returns:
            Seznam částí textu
        """
        print(f"\n{Fore.YELLOW}Rozdělení textu pro TTS...")

        chunks = []
        sentences = self._split_into_sentences(text)

        current_chunk = ""
        for sentence in sentences:
            # Zkontrolovat, zda by přidání věty nepřekročilo limit
            if len(current_chunk) + len(sentence) + 1 < max_chars:
                current_chunk += sentence + " "
            else:
                # Uložit aktuální chunk a začít nový
                if current_chunk:
                    chunks.append(current_chunk.strip())
                current_chunk = sentence + " "

        # Uložit poslední chunk
        if current_chunk:
            chunks.append(current_chunk.strip())

        print(f"Text rozdělen na {len(chunks)} částí")

        # Vypsat informace o částech
        for i, chunk in enumerate(chunks, 1):
            print(f"  Část {i}: {len(chunk)} znaků")

        return chunks

    def _split_into_sentences(self, text: str) -> List[str]:
        """
        Rozdělí text na věty

        Args:
            text: Text k rozdělení

        Returns:
            Seznam vět
        """
        # Rozdělit podle koncových znaků vět
        sentences = re.split(r'(?<=[.!?])\s+', text)

        # Filtrovat prázdné věty
        sentences = [s for s in sentences if s.strip()]

        return sentences

    def detect_language(self, text: str) -> str:
        """
        Detekuje jazyk textu

        Args:
            text: Text k detekci

        Returns:
            Kód jazyka
        """
        try:
            # Použít pouze prvních 500 znaků pro detekci
            sample = text[:500]
            lang_code = detect(sample)

            # Mapování jazykových kódů
            lang_map = {
                'cs': 'cs',
                'en': 'en',
                'de': 'de',
                'es': 'es',
                'fr': 'fr',
                'sk': 'cs'  # Slovenština -> čeština
            }

            return lang_map.get(lang_code, 'cs')

        except Exception:
            # Výchozí jazyk při chybě
            return 'cs'

    def normalize_string(self, s: str) -> str:
        """
        Normalizuje string - odstraní diakritiku a převede na lowercase

        Args:
            s: String k normalizaci

        Returns:
            Normalizovaný string
        """
        # NFD rozložení
        s = unicodedata.normalize('NFD', s)

        # Odstranit diakritická znaménka
        s = ''.join(char for char in s if unicodedata.category(char) != 'Mn')

        # Převést na lowercase a odstranit mezery
        return s.lower().replace(' ', '').replace('_', '')

    def prepare_for_tts(self, text: str) -> str:
        """
        Připraví text pro TTS

        Args:
            text: Text k přípravě

        Returns:
            Upravený text pro TTS
        """
        # Nahradit číslovky slovem (základní příklady)
        replacements = {
            '1': 'jeden',
            '2': 'dva',
            '3': 'tři',
            '4': 'čtyři',
            '5': 'pět',
            '6': 'šest',
            '7': 'sedm',
            '8': 'osm',
            '9': 'devět',
            '10': 'deset'
        }

        for num, word in replacements.items():
            # Nahradit pouze samostatná čísla
            text = re.sub(r'\b' + num + r'\b', word, text)

        # Rozepsat zkratky
        abbreviations = {
            'např.': 'například',
            'tj.': 'to jest',
            'tzv.': 'takzvaný',
            'atd.': 'a tak dále',
            'apod.': 'a podobně',
            'č.': 'číslo',
            'str.': 'strana'
        }

        for abbr, full in abbreviations.items():
            text = text.replace(abbr, full)

        return text

    def count_words(self, text: str) -> int:
        """
        Spočítá slova v textu

        Args:
            text: Text ke spočítání

        Returns:
            Počet slov
        """
        words = text.split()
        return len(words)

    def extract_preview(self, text: str, length: int = 100) -> str:
        """
        Vytvoří náhled textu

        Args:
            text: Text pro náhled
            length: Délka náhledu

        Returns:
            Náhled textu
        """
        preview = text[:length].replace('\n', ' ')

        # Přidat trojtečky pokud je text delší
        if len(text) > length:
            preview += '...'

        return preview

    def merge_segments(self, segments: List[str], separator: str = "\n\n") -> str:
        """
        Spojí segmenty do jednoho textu

        Args:
            segments: Seznam segmentů
            separator: Oddělovač

        Returns:
            Spojený text
        """
        return separator.join(segments)

    def clean_for_gpt(self, text: str) -> str:
        """
        Vyčistí text pro zpracování GPT

        Args:
            text: Text k vyčištění

        Returns:
            Vyčištěný text
        """
        # Odstranit vícenásobné mezery
        text = re.sub(r'\s+', ' ', text)

        # Odstranit mezery na začátku a konci
        text = text.strip()

        # Zajistit mezeru po tečce
        text = re.sub(r'\.(?=[A-Z])', '. ', text)

        return text

    def validate_sentence_length(self, text: str, max_words: int = 30) -> List[str]:
        """
        Validuje délku vět pro TTS

        Args:
            text: Text k validaci
            max_words: Maximální počet slov na větu

        Returns:
            Seznam vět, které překračují limit
        """
        sentences = self._split_into_sentences(text)
        long_sentences = []

        for sentence in sentences:
            word_count = len(sentence.split())
            if word_count > max_words:
                long_sentences.append(f"{sentence[:50]}... ({word_count} slov)")

        return long_sentences
