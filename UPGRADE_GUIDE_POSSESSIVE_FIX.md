# 🔧 Upgrade Guide: Possessive Pronouns Fix & Sentence Length Validation

## 📋 Přehled změn

Tato aktualizace přidává:

1. ✅ **Odstranění posesivních zájmen** (náš/our/unser) ve všech jazycích
2. ✅ **Validace délky vět** (max 30 slov, soft/strict režim)
3. ✅ **Rozšířené regex vzory** pro české pády (našeho, našem, naší...)
4. ✅ **Cache invalidation** (automatická díky version bump)
5. ✅ **Lepší fallback texty** v generátorech
6. ✅ **Kompletní unit testy** pro nové funkce

---

## 🚀 Jak upgradovat

### 1️⃣ **Smazat starou cache (POVINNÉ)**

```bash
# Manuální způsob
python scripts/clear_narration_cache.py --dry-run  # Náhled
python scripts/clear_narration_cache.py            # Skutečné smazání

# Alternativně přímo
rm -rf outputs/.cache/narration_core/*
```

**Proč?** Staré cache klíče obsahují verzi `v1`, nové jsou `v2` – automatická invalidace funguje, ale manuální cleanup je čistší.

---

### 2️⃣ **Kontrola konfigurace**

#### Nové konfigurační parametry v `FormatterConfig`:

```python
from historical_processor.narration_core.types import FormatterConfig

cfg = FormatterConfig(
    language='CS',
    use_gpt_split=False,
    use_gpt_grammar=False,
    
    # 🆕 NOVÉ PARAMETRY
    strict_sentence_split=False,  # False = varování, True = auto-split
    max_sentence_words=30,        # Limit pro varování/splitting
)
```

#### Režimy:

- **Soft mode** (`strict_sentence_split=False`):
  - Pouze **varuje** přes logger, **nešťepí** věty automaticky
  - Zachovává autorský styl
  - Doporučeno pro **finální produkci**

- **Strict mode** (`strict_sentence_split=True`):
  - Automaticky **štěpí** věty delší než `max_sentence_words`
  - Použitelné pro **první draft** nebo **nouzový režim**

---

### 3️⃣ **Spustit testy**

```bash
pytest tests/test_narration_core_formatter.py -v
pytest tests/test_narration_core_validator.py -v
```

**Očekávané výsledky:**
- ✅ Všechny testy pro odstranění posesiv (**test_possessive_removal_***) projdou
- ✅ Soft mode testy (**test_soft_mode_***) projdou
- ✅ Validátory detekují posesiva (**test_*_detects_possessive**)

---

### 4️⃣ **Re-generovat obsah**

#### Pro stávající projekty:

```bash
# Outline (beze změny)
python outline-generator/generate_outline.py --topic "my_topic" --language CS

# Prompts (aktualizovaná šablona)
python B_core/generate_prompts.py --topic "my_topic" --language CS

# Narrace (s novými pravidly)
python claude_generator/runner_cli.py --topic "my_topic" --language CS --episodes ep01

# Post-processing (s odstraněním posesiv)
python historical_processor/runner_cli.py --input-dir outputs/narration/my_topic/CS/ep01 --episode-mode
```

---

## 🔍 Kontrola výstupů

### ❌ **PŘED (špatně):**

```
Vítejte v prvním dílu našeho dokumentárního seriálu "Bitva o dukelský průsmyk",
kde se budeme zabývat klíčovými událostmi, které ovlivnily průběh celé operace
a měly zásadní dopad na další vývoj situace na východní frontě během závěrečné
fázi druhé světové války v roce 1944.
```

**Problémy:**
- ❌ "našeho" (posesivum)
- ❌ 45 slov v jedné větě

---

### ✅ **PO (správně):**

```
Vítejte v prvním dílu dokumentárního seriálu "Bitva o dukelský průsmyk".
Tato epizoda se zabývá klíčovými událostmi, které ovlivnily průběh operace.
Tyto události měly zásadní dopad na vývoj situace na východní frontě
během závěrečné fáze druhé světové války v roce 1944.
```

**Opraveno:**
- ✅ Žádné posesivum
- ✅ 3 věty: 12, 14, 19 slov
- ✅ Objektivní third-person hlas

---

## 🐛 Debugging

### Problém: Stále vidím "našeho" ve výstupu

**Možné příčiny:**

1. **Stará cache** – Smaž: `rm -rf outputs/.cache/narration_core/*`
2. **GPT mode aktivní** – Zkontroluj: `use_gpt_split=False, use_gpt_grammar=False`
3. **Chyba v API** – Zkontroluj logy: `outputs/*/logs/`

**Test:**

```python
from historical_processor.narration_core.formatter import TextFormatter
from historical_processor.narration_core.types import FormatterConfig

cfg = FormatterConfig(language='CS', use_gpt_split=False, use_gpt_grammar=False)
fmt = TextFormatter(cfg)

test = "Vítejte v prvním dílu našeho dokumentárního seriálu."
result = fmt.format(test)
print(result)
# Očekáváno: "Vítejte v prvním dílu dokumentárního seriálu."
```

---

### Problém: Věty jsou stále příliš dlouhé

**Řešení:**

1. **Aktivuj strict mode:**
   ```python
   cfg = FormatterConfig(..., strict_sentence_split=True)
   ```

2. **Snižš limit:**
   ```python
   cfg = FormatterConfig(..., max_sentence_words=25)
   ```

3. **Zkontroluj warnings:**
   ```python
   import logging
   logging.basicConfig(level=logging.WARNING)
   # Formatter bude logovat varování
   ```

---

## 📊 Statistiky

### Pokryté jazyky:

| Jazyk | Posesiva | Vzory | Status |
|-------|----------|-------|--------|
| 🇨🇿 Čeština | náš, naše, našeho, našem, naší, našich, našimi | 7 pádů | ✅ Plné |
| 🇬🇧 Angličtina | our, ours, my, mine | 4 vzory | ✅ Plné |
| 🇩🇪 Němčina | unser, unsere, unserem, unserer, unseren | 5 pádů | ✅ Plné |
| 🇪🇸 Španělština | nuestro, nuestra, nuestros, nuestras | 4 vzory | ✅ Plné |
| 🇫🇷 Francouzština | notre, nos, mon, ma, mes | 5 vzorů | ✅ Plné |

---

## 🎯 Best Practices

### Pro nové projekty:

1. **Vždy použij soft mode** (`strict_sentence_split=False`)
2. **Zkontroluj warnings** v logách
3. **Re-generuj jen pokud vidíš "exceeds_X_words"**

### Pro stávající projekty:

1. **Smaž cache před re-generací**
2. **Použij strict mode pro první průchod**
3. **Zkontroluj manuálně výstupy s warnings**
4. **Re-generuj pouze problematické segmenty**

---

## 📝 Changelog

### v2 (Current)

- ✅ Possessive pronouns removal (all 5 languages)
- ✅ Sentence length validation (soft/strict modes)
- ✅ Enhanced regex patterns (Czech declensions)
- ✅ Cache version bump (v1 → v2)
- ✅ Improved fallback texts
- ✅ Comprehensive unit tests
- ✅ SegmentQualityValidator class

### v1 (Previous)

- Basic formatting
- Simple sentence splitting
- No possessive handling

---

## 🆘 Support

Pokud narazíš na problém:

1. Spusť testy: `pytest tests/test_narration_core_*.py -v`
2. Zkontroluj logy: `outputs/*/logs/`
3. Zkus debug script: `python scripts/clear_narration_cache.py --dry-run`

---

## ✅ Checklist po upgradu

- [ ] Cache smazána
- [ ] Testy prošly
- [ ] První segment re-generován
- [ ] Žádné posesiva ve výstupu
- [ ] Věty ≤ 30 slov
- [ ] Warnings zkontrolovány
- [ ] Produkční konfigurace nastavena (soft mode)

---

**Poslední aktualizace:** 2024 (AI generated)  
**Verze:** v2.0.0
