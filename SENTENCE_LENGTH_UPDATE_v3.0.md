# 📏 Úprava Délky Vět a Počtu Vět

## 🎯 Nová Nastavení (od verze v2.1.0)

### **Délka vět:**
- **Minimum**: 20 slov
- **Maximum**: 40 slov
- **Doporučený rozsah**: 25-35 slov pro optimální čitelnost

### **Počet vět:**
- **Intro**: 7-13 vět (rozšířeno z původních 5-6)
- **Transitions** (přechody): 7-13 vět (rozšířeno z původních 1-2)
- **Epilog**: 7-13 vět (stejné jako intro/transitions)
- **Segmenty**: bez pevného limitu (dle potřeby obsahu)

---

## 📂 Změněné Soubory

### 1. **types.py** – Nové parametry konfigurace
```python
max_sentence_words: int = 40     # bylo 30
min_sentence_words: int = 20     # nové
```

### 2. **generator.py** – Aktualizované prompty
**IntroGenerator:**
- "Write a 7-13 sentence introduction" (bylo 5-6)
- "Each sentence MUST be 20-40 words" (bylo 15-30)

**TransitionGenerator:**
- "Write a 7-13 sentence transition" (bylo 1-2)
- "Each sentence MUST be 20-40 words" (bylo 14-28)

### 3. **segment_prompt.txt** – Aktualizovaná šablona
- "Each sentence MUST be 20-40 words" (bylo 15-30)

### 4. **formatter.py** – Rozšířená validace
- Kontrola **minimální** délky (20 slov)
- Kontrola **maximální** délky (40 slov)
- Warnings pro obě hranice

### 5. **validator.py** – Aktualizované limity
**TransitionQualityValidator:**
- Kontrola 7-13 vět (bylo 1-2)
- Kontrola 20-40 slov/věta (bylo 14-28)

**SegmentQualityValidator:**
- Kontrola 20-40 slov/věta (bylo max 30)

---

## 🔄 Migrace z v2.0.0 → v2.1.0

### Krok 1: Smaž cache
```bash
python scripts/clear_narration_cache.py
```

### Krok 2: Re-generuj obsah
Pro existující projekty doporučuji re-generovat:
- **Intro** (bude delší, 7-13 vět)
- **Transitions** (budou výrazně delší, 7-13 vět místo 1-2)

```bash
# Re-generuj s novými pravidly
python historical_processor/runner_cli.py \
    --input-dir outputs/narration/my_topic/CS/ep01 \
    --episode-mode \
    --force-rebuild
```

### Krok 3: Kontrola výstupů
Zkontroluj, že:
- Intro má 7-13 vět
- Transitions mají 7-13 vět
- Věty jsou v rozsahu 20-40 slov

---

## 📊 Očekávané Změny ve Výstupech

### **Intro (PŘED vs. PO):**

**PŘED (5-6 vět, 15-30 slov):**
```
Dokumentární seriál "Bitva o Duklu" zkoumá klíčové okamžiky této operace.
Epizoda se zaměřuje na taktické rozhodnutí velitelů.
Sleduje vývoj bojů v průběhu října 1944.
Analyzuje dopady na další průběh války.
Představuje osobní příběhy účastníků bojů.
```

**PO (7-13 vět, 20-40 slov):**
```
Dokumentární seriál "Bitva o Duklu" představuje komplexní pohled na jednu z nejkrvavějších operací východní fronty během závěrečné fáze druhé světové války.
První epizoda série se podrobně zaměřuje na strategické a taktické aspekty plánování operace ze strany sovětského velení během září 1944.
Sledujeme vývoj bojových operací v průběhu října 1944, kdy se intenzita střetů postupně zvyšovala a situace se stávala kritičtější.
Epizoda analyzuje dopad těchto událostí na další průběh války na východní frontě a rozhodnutí spojeneckých velitelů.
Představuje osobní příběhy účastníků bojů z různých perspektiv, včetně sovětských, československých a německých vojáků.
Dokumentární metody zahrnují analýzu archivních materiálů, dobových svědectví a mapových podkladů z této složité operace.
Vše je zasazeno do širšího kontextu závěrečných měsíců války a jejich důsledků pro poválečné uspořádání střední Evropy.
```

### **Transitions (PŘED vs. PO):**

**PŘED (1-2 věty, 14-28 slov):**
```
Tato situace přirozeně vedla k dalším událostem. V následující fázi se situace dramaticky změnila.
```

**PO (7-13 vět, 20-40 slov):**
```
Strategické rozhodnutí sovětského velení v tomto okamžiku mělo dalekosáhlé důsledky pro průběh celé operace během následujících dnů.
Změna taktického přístupu k útočným operacím odráže rostoucí obtíže s koordinací mezi československými a sovětskými jednotkami v terénu.
Tyto komplikace vedly k přehodnocení původních plánů a nutnosti adaptace strategie na aktuální bojovou situaci.
V následující fázi operace se situace dramaticky změnila, když německé obranné linie posílily o další dvě divize převedené z jiných úseků fronty.
Tato nová realita vyžadovala od spojeneckého velení zásadní úpravu taktických postupů a přesuny vlastních jednotek.
Následující události ukázaly, jak důležité bylo rychle reagovat na měnící se podmínky v horském terénu Dukelského průsmyku.
Právě tyto okolnosti vytvořily podmínky pro rozhodující události, které budou popsány v další části této dokumentární rekonstrukce.
```

---

## ⚙️ Ruční Konfigurace

Pokud chceš změnit limity pro konkrétní případy:

```python
from historical_processor.narration_core.types import FormatterConfig

# Varianta A: Ještě delší věty (25-50 slov)
cfg = FormatterConfig(
    language='CS',
    min_sentence_words=25,
    max_sentence_words=50,
    strict_sentence_split=False,
)

# Varianta B: Kratší věty (15-30 slov)
cfg = FormatterConfig(
    language='CS',
    min_sentence_words=15,
    max_sentence_words=30,
    strict_sentence_split=False,
)
```

---

## 🎯 Doporučení

### Pro **nové projekty:**
- Použij výchozí nastavení (20-40 slov, 7-13 vět)
- Zkontroluj první vygenerované intro/transitions
- Případně uprav ručně, pokud je text příliš rozvláčný

### Pro **existující projekty:**
- **Intro/Transitions**: re-generuj (budou delší)
- **Segmenty**: pokud splňují 20-40 slov, není třeba nic měnit
- **Kontrola**: zkontroluj warnings v logách

### Pro **TTS (ElevenLabs):**
- Delší věty = pomalejší tempo (může být lepší pro komplexní obsah)
- 7-13 vět v intro = cca 45-90 sekund audio
- 7-13 vět v transitions = cca 40-80 sekund audio

---

## 📝 Changelog

### v2.1.0 (Current)
- ✅ Délka vět: 20-40 slov (z 15-30)
- ✅ Intro: 7-13 vět (z 5-6)
- ✅ Transitions: 7-13 vět (z 1-2)
- ✅ Epilog: 7-13 vět (nové)
- ✅ Kontrola minimální délky věty
- ✅ Rozšířené warnings

### v2.0.0 (Previous)
- Odstranění posesivních zájmen
- Validace délky vět (max 30 slov)
- Soft mode pro splitting

---

## 🆘 Troubleshooting

### Problém: Transitions jsou příliš dlouhé
**Řešení:**
```python
# Zkus GPT mode pro lepší kontrolu
cfg = FormatterConfig(
    use_gpt_split=True,
    use_gpt_grammar=True,
    api_key=os.environ['OPENAI_API_KEY']
)
```

### Problém: Warnings "sentence_too_short"
**Řešení:**
- Je to normální pro velmi krátké věty
- Pokud chceš povolit kratší věty, sniž `min_sentence_words`
- Nebo ignoruj warnings (soft mode nezabrání generování)

### Problém: Intro je moc dlouhé (> 13 vět)
**Řešení:**
- Zkontroluj, že používáš verzi v2.1.0+
- Smaž cache: `python scripts/clear_narration_cache.py`
- Re-generuj: `--force-rebuild`

---

**Poslední aktualizace:** 2024  
**Verze:** v2.1.0
