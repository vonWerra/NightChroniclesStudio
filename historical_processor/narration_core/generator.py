# -*- coding: utf-8 -*-
from __future__ import annotations

from typing import Dict, Optional
from dataclasses import asdict
from openai import OpenAI

from .types import EpisodeContext, GeneratedText, GeneratorConfig
from .cache import NarrationCache


# 🆕 Version bump to invalidate old cache entries
INTRO_PROMPT_VERSION = "v2"
TRANSITION_PROMPT_VERSION = "v2"


class IntroGenerator:
    def __init__(self, api_key: str, cfg: Optional[GeneratorConfig] = None):
        self.client = OpenAI(api_key=api_key)
        self.cfg = cfg or GeneratorConfig()
        self.cache = NarrationCache()

    def generate(self, ctx: EpisodeContext) -> GeneratedText:
        lang_names = {
            'CS': 'Czech',
            'EN': 'English',
            'DE': 'German',
            'ES': 'Spanish',
            'FR': 'French'
        }
        lang_full = lang_names.get(ctx.language, 'Czech')

        series_context_text = '\n'.join(f"- {item}" for item in ctx.series_context)
        episode_desc_text = '\n'.join(f"- {item}" for item in ctx.episode_description)

        user_prompt = f"""You are an experienced documentary narrator and editor. Create a compelling introduction for a historical documentary episode.

SERIES INFORMATION:
- Title: {ctx.series_title}
- Context:
{series_context_text}

EPISODE INFORMATION:
- Episode {ctx.episode_index} of {ctx.total_episodes}
- Title: {ctx.episode_title}
- Description:
{episode_desc_text}

TASK:
Write a 5-6 sentence introduction in {lang_full} that:
1. Situates this episode within the overall series
2. Highlights ONLY the main theme of this episode (no details)
3. Creates anticipation for what follows
4. Uses documentary-style, calm, professional narration
5. Is written for text-to-speech (TTS) - clear, flowing sentences

CRITICAL STYLE RULES (MUST FOLLOW):
- Use OBJECTIVE THIRD-PERSON voice throughout
- NEVER use possessive first-person plural pronouns:
  * English: "our", "my", "ours"
  * Czech: "náš", "naše", "našeho", "našem", "naší"
  * German: "unser", "unsere", "unserem"
  * Spanish: "nuestro", "nuestra", "nuestros"
  * French: "notre", "nos"
- Refer to the series by name: "the documentary series {ctx.series_title}" or "the series {ctx.series_title}" NOT "our series"
- Each sentence MUST be 15-30 words maximum
- If a sentence would naturally exceed 30 words, split it at a comma or conjunction
- Avoid phrases like "we will see", "we will explore", "let us examine"
- Be engaging but maintain objective tone

IMPORTANT:
- Write ONLY the introduction text, nothing else
- No metadata, no labels, no explanations
- Each sentence should be 15-30 words maximum
- Use natural, documentary language
- Be engaging but not sensationalist"""

        payload = {
            "type": "intro",
            "version": INTRO_PROMPT_VERSION,
            "language": ctx.language,
            "series_title": ctx.series_title,
            "episode_title": ctx.episode_title,
            "episode_index": ctx.episode_index,
            "total_episodes": ctx.total_episodes,
            "episode_desc_preview": episode_desc_text[:500],
        }
        cached = self.cache.load(payload)
        if cached:
            return GeneratedText(text=cached.get("text", ""), provenance="gpt", prompt_hash=cached.get("cache_key"))

        try:
            response = self.client.chat.completions.create(
                model=self.cfg.model,
                messages=[
                    {"role": "system", "content": "You are a professional documentary narrator and editor specializing in historical content. You always use objective third-person voice and never use possessive pronouns like 'our' or 'my'."},
                    {"role": "user", "content": user_prompt},
                ],
                temperature=self.cfg.temperature_intro,
                max_tokens=self.cfg.max_tokens_intro,
            )
            text = (response.choices[0].message.content or "").strip()
            cache_key = self.cache.save(payload, {"text": text})
            return GeneratedText(text=text, provenance="gpt", prompt_hash=cache_key)
        except Exception as e:
            # 🆕 Improved fallback without possessives
            if ctx.language == 'CS':
                fallback = f"{ctx.episode_title} je součástí dokumentárního seriálu {ctx.series_title}."
            elif ctx.language == 'DE':
                fallback = f"{ctx.episode_title} ist Teil der Dokumentarserie {ctx.series_title}."
            elif ctx.language == 'ES':
                fallback = f"{ctx.episode_title} es parte de la serie documental {ctx.series_title}."
            elif ctx.language == 'FR':
                fallback = f"{ctx.episode_title} fait partie de la série documentaire {ctx.series_title}."
            else:
                fallback = f"{ctx.episode_title} is part of the documentary series {ctx.series_title}."
            return GeneratedText(text=fallback, provenance="fallback", prompt_hash=None, meta={"error": str(e)})


class TransitionGenerator:
    def __init__(self, api_key: str, cfg: Optional[GeneratorConfig] = None):
        self.client = OpenAI(api_key=api_key)
        self.cfg = cfg or GeneratorConfig()
        self.cache = NarrationCache()

    def generate(self, prev_segment: str, next_segment: str, language: str) -> GeneratedText:
        lang_names = {
            'CS': 'Czech',
            'EN': 'English',
            'DE': 'German',
            'ES': 'Spanish',
            'FR': 'French'
        }
        lang_full = lang_names.get(language, 'Czech')

        prev_end = ' '.join(prev_segment.split()[-150:])
        next_start = ' '.join(next_segment.split()[:150])

        user_prompt = f"""You are an experienced documentary narrator creating smooth transitions between segments.

PREVIOUS SEGMENT (ending):
{prev_end}

NEXT SEGMENT (beginning):
{next_start}

TASK:
Write a 1-2 sentence transition in {lang_full} that:
1. Smoothly connects the previous topic to the next using at least one concrete anchor (time/entity/keyword) present in the context
2. Maintains chronological and thematic continuity
3. Uses neutral, documentary style
4. Does NOT summarize or remove content
5. Avoids meta phrases and does not add new facts
6. Is written for text-to-speech (TTS)

CRITICAL STYLE RULES (MUST FOLLOW):
- Use OBJECTIVE THIRD-PERSON voice throughout
- NEVER use possessive pronouns:
  * English: "our", "my", "ours"
  * Czech: "náš", "naše", "našeho", "našem", "naší"
  * German: "unser", "unsere", "unserem"
  * Spanish: "nuestro", "nuestra"
  * French: "notre", "nos"
- Each sentence MUST be 14-28 words maximum
- Avoid phrases like "we will now turn to", "let us examine"

IMPORTANT:
- Write ONLY the transition text, nothing else
- No metadata, no labels, no explanations
- Each sentence should be ~14-28 words maximum
- Be brief but meaningful
- Maintain the documentary tone"""

        payload = {
            "type": "transition",
            "version": TRANSITION_PROMPT_VERSION,
            "language": language,
            "prev_preview": prev_end[:400],
            "next_preview": next_start[:400],
        }
        cached = self.cache.load(payload)
        if cached:
            return GeneratedText(text=cached.get("text", ""), provenance="gpt", prompt_hash=cached.get("cache_key"))

        try:
            response = self.client.chat.completions.create(
                model=self.cfg.model,
                messages=[
                    {"role": "system", "content": "You are a professional documentary narrator specializing in creating smooth narrative transitions. You always use objective third-person voice."},
                    {"role": "user", "content": user_prompt},
                ],
                temperature=self.cfg.temperature_transition,
                max_tokens=self.cfg.max_tokens_transition,
            )
            text = (response.choices[0].message.content or "").strip()
            cache_key = self.cache.save(payload, {"text": text})
            return GeneratedText(text=text, provenance="gpt", prompt_hash=cache_key)
        except Exception as e:
            # 🆕 Improved multilingual fallback without possessives
            if language == 'CS':
                fallback = "Tato situace přirozeně vedla k dalším událostem."
            elif language == 'DE':
                fallback = "Diese Entwicklung führte natürlich zu weiteren Ereignissen."
            elif language == 'ES':
                fallback = "Esta situación condujo naturalmente a más acontecimientos."
            elif language == 'FR':
                fallback = "Cette situation a naturellement mené à d'autres événements."
            else:
                fallback = "This situation naturally led to further developments."
            return GeneratedText(text=fallback, provenance="fallback", prompt_hash=None, meta={"error": str(e)})
