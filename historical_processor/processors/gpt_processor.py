#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
GPT Processor - Zpracování textu pomocí OpenAI GPT
"""

import time
from typing import List, Tuple, Optional
from pathlib import Path
from openai import OpenAI
from colorama import Fore


class GPTProcessor:
    """Zpracování textu pomocí GPT modelů"""

    # Mapování modelů a jejich cen za 1K tokenů
    MODELS = {
        'gpt-4.1': {'name': 'gpt-4.1', 'cost_per_1k': 0.005},
        'gpt-4.1-mini': {'name': 'gpt-4.1-mini', 'cost_per_1k': 0.002},
        'gpt-4-turbo-preview': {'name': 'gpt-4-turbo-preview', 'cost_per_1k': 0.01},
        'gpt-4': {'name': 'gpt-4', 'cost_per_1k': 0.03},
        'gpt-3.5-turbo': {'name': 'gpt-3.5-turbo', 'cost_per_1k': 0.002}
    }

    def __init__(self, config_manager):
        """
        Inicializace GPT procesoru

        Args:
            config_manager: Instance ConfigManager
        """
        self.config = config_manager
        self.client = OpenAI(api_key=config_manager.get('openai_api_key'))
        self.system_prompt = self._load_system_prompt()

    def _load_system_prompt(self) -> str:
        """Načte systémový prompt"""
        return """# Systémový Prompt – Multijazyčná historická série

## Role:
Jsi zkušený editor a vypravěč. Tvým úkolem je přetvářet historické segmenty do plynulé, dokumentární narace vhodné pro převod textu na řeč (TTS).

## KRITICKÉ PRAVIDLO:
**MUSÍŠ zachovat VŠECHNY informace, fakta a detaily ze segmentů. Text může být DELŠÍ než originál (kvůli přechodům a úvodu), ale NIKDY kratší. Žádné zkracování, sumarizace nebo vynechávání!**

## Pravidla zpracování:
1. **Detekce jazyka**: Zpracuj text v jazyce vstupních segmentů
2. **Gramatické opravy**: Oprav všechny gramatické a stylistické chyby
3. **Chronologické řazení**: Seřaď segmenty chronologicky podle dat a událostí
4. **Spojení segmentů**: Spoj všechny segmenty do jedné souvislé narace
5. **Přechody**: Mezi segmenty vlož krátké přechody (2-5 vět) pro plynulou návaznost
6. **Zachování obsahu**: VŠECHNY věty, fakta a informace musí být zachovány

## Formátování pro TTS:
- Délka vět: 20-30 slov maximum
- Číslovky 1-999: vypisuj slovem
- Roky: piš slovně (např. "devatenáct set čtrnáct")
- Zkratky: rozepiš (např. → například)
- **KRITICKÉ: Odstraň VŠECHNY odkazy na zdroje, analýzy, studie, výzkumy**
- **Prezentuj vše jako přímé vyprávění faktů**
- **Používej plná jména POUZE u historických osobností, institucí, dokumentů a událostí**

## PŘÍMÁ NARACE - transformace:
- "Podle Miroslava Hrocha se proces odvíjel ve třech fázích" → "Proces se odvíjel ve třech fázích"
- Prostě vyprávěj fakta přímo, jako objektivní realitu, bez jakýchkoli odkazů na zdroje.

## KONTROLA:
Před odevzdáním zkontroluj, že výstupní text obsahuje VŠECHNY informace z KAŽDÉHO segmentu."""

    def process_segments(self, segments: List[Path], outline: str,
                        episode_num: str, language: str,
                        model_name: str = 'gpt-4.1') -> Tuple[str, float]:
        """
        Zpracuje segmenty pomocí GPT

        Args:
            segments: Seznam cest k segmentům
            outline: Text osnovy
            episode_num: Číslo epizody
            language: Kód jazyka
            model_name: Název GPT modelu

        Returns:
            Tuple (zpracovaný text, odhadovaná cena)
        """
        # Načíst a spojit segmenty
        segments_text = self._load_segments(segments)
        total_chars = len(segments_text)

        # Zkontrolovat velikost pro starší modely
        if total_chars > 30000 and model_name in ["gpt-4", "gpt-3.5-turbo"]:
            print(f"{Fore.YELLOW}⚠ Varování: Text má {total_chars:,} znaků")
            print(f"Model {model_name} má omezený kontext.")

        # Připravit prompt
        user_prompt = self._prepare_user_prompt(
            segments_text, outline, episode_num, language, total_chars
        )

        # Získat parametry modelu
        model_info = self.MODELS.get(model_name, self.MODELS['gpt-4.1'])

        # Odhadnout cenu
        max_output_tokens = min(int(total_chars / 3), 16000)
        estimated_tokens = (len(self.system_prompt) + len(user_prompt)) / 4
        estimated_cost = (estimated_tokens / 1000) * model_info['cost_per_1k']

        print(f"\n{Fore.CYAN}Parametry zpracování:")
        print(f"  Model: {model_name}")
        print(f"  Vstupní znaky: {total_chars:,}")
        print(f"  Max výstupní tokeny: {max_output_tokens:,}")
        print(f"  Odhadovaná cena: ${estimated_cost:.3f}")

        # Zpracovat pomocí GPT
        print(f"\n{Fore.YELLOW}Zpracovávám... (může trvat 30-60 sekund)")

        result = self._call_gpt(
            model_info['name'],
            self.system_prompt,
            user_prompt,
            max_output_tokens,
            model_info['cost_per_1k']
        )

        return result

    def _load_segments(self, segments: List[Path]) -> str:
        """
        Načte a spojí segmenty

        Args:
            segments: Seznam cest k segmentům

        Returns:
            Spojený text segmentů
        """
        segments_text = ""
        for seg in segments:
            with open(seg, 'r', encoding='utf-8') as f:
                content = f.read()
                segments_text += f"\n\n--- SEGMENT {seg.name} ---\n{content}"

        return segments_text

    def _prepare_user_prompt(self, segments_text: str, outline: str,
                            episode_num: str, language: str,
                            total_chars: int) -> str:
        """
        Připraví uživatelský prompt

        Args:
            segments_text: Text segmentů
            outline: Osnova epizody
            episode_num: Číslo epizody
            language: Jazyk
            total_chars: Celkový počet znaků

        Returns:
            Uživatelský prompt
        """
        return f"""Zpracuj následující historické segmenty pro epizodu {episode_num}.

DŮLEŽITÉ: Vstupní text má {total_chars} znaků. Výstup MUSÍ mít minimálně stejnou délku.

OSNOVA EPIZODY:
{outline if outline else "Osnova není k dispozici"}

SEGMENTY K ZPRACOVÁNÍ:
{segments_text}

INSTRUKCE:
1. Vytvoř krátký úvodní text (5-6 vět)
2. Chronologicky seřaď a spoj VŠECHNY segmenty
3. Vlož plynulé přechody mezi segmenty
4. ABSOLUTNĚ ŽÁDNÉ zkracování - zachovej 100% informací
5. Odstraň VŠECHNY zmínky o zdrojích, autorech, studiích
6. Prezentuj vše jako přímé vyprávění faktů
7. Výstup v jazyce: {language}
8. Minimální délka: {int(total_chars * 0.9)} znaků

Vrať POUZE finální naraci. ŽÁDNÉ ZKRACOVÁNÍ!"""

    def _call_gpt(self, model: str, system_prompt: str,
                 user_prompt: str, max_tokens: int,
                 cost_per_1k: float) -> Tuple[str, float]:
        """
        Zavolá GPT API

        Args:
            model: Název modelu
            system_prompt: Systémový prompt
            user_prompt: Uživatelský prompt
            max_tokens: Max počet tokenů
            cost_per_1k: Cena za 1000 tokenů

        Returns:
            Tuple (výsledný text, skutečná cena)
        """
        max_retries = 3

        for attempt in range(max_retries):
            try:
                response = self.client.chat.completions.create(
                    model=model,
                    messages=[
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": user_prompt}
                    ],
                    temperature=0.3,
                    max_tokens=max_tokens
                )

                result = response.choices[0].message.content

                # Vypočítat skutečnou cenu
                actual_cost = 0.0
                if hasattr(response, 'usage'):
                    actual_tokens = response.usage.total_tokens
                    actual_cost = (actual_tokens / 1000) * cost_per_1k

                    print(f"{Fore.GREEN}✓ Zpracování dokončeno!")
                    print(f"  Výstupní znaky: {len(result):,}")
                    print(f"  Skutečné tokeny: {actual_tokens:,}")
                    print(f"  Skutečná cena: ${actual_cost:.3f}")

                return result, actual_cost

            except Exception as e:
                print(f"{Fore.RED}Pokus {attempt+1}/{max_retries} selhal: {e}")

                if attempt < max_retries - 1:
                    print(f"{Fore.YELLOW}Zkouším znovu za 5 sekund...")
                    time.sleep(5)
                else:
                    raise Exception(f"GPT zpracování selhalo po {max_retries} pokusech")

    def validate_output(self, output_text: str, input_text: str) -> bool:
        """
        Validuje výstup GPT

        Args:
            output_text: Výstupní text z GPT
            input_text: Původní vstupní text

        Returns:
            True pokud je výstup validní
        """
        output_chars = len(output_text)
        input_chars = len(input_text)

        if output_chars < input_chars * 0.7:
            print(f"{Fore.YELLOW}⚠ Varování: Výstup ({output_chars:,} znaků) "
                  f"je kratší než vstup ({input_chars:,} znaků)")
            return False

        return True
