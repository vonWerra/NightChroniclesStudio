# 📋 Změny v2.1.0 – Úprava Délky Vět a Počtu Vět

## 🎯 **Shrnutí změn:**

| Parametr | v2.0.0 (PŘED) | v2.1.0 (PO) | Změna |
|----------|---------------|-------------|-------|
| **Délka vět** | 15-30 slov | 20-40 slov | ➕ 10 slov |
| **Intro – počet vět** | 5-6 vět | 7-13 vět | ➕ 7 vět |
| **Transitions – počet vět** | 1-2 věty | 7-13 vět | ➕ 11 vět |
| **Epilog – počet vět** | - | 7-13 vět | ➕ Nové |
| **Min. délka věty** | - (nekontrolováno) | 20 slov | ➕ Nové |

---

## 📂 **Změněné soubory:**

### 1. `historical_processor/narration_core/types.py`
```diff
- max_sentence_words: int = 30
+ max_sentence_words: int = 40
+ min_sentence_words: int = 20  # NOVÉ
```

### 2. `historical_processor/narration_core/generator.py`

#### IntroGenerator:
```diff
- Write a 5-6 sentence introduction
+ Write a 7-13 sentence introduction

- Each sentence MUST be 15-30 words maximum
+ Each sentence MUST be 20-40 words
+ Aim for 7-13 sentences total
```

#### TransitionGenerator:
```diff
- Write a 1-2 sentence transition
+ Write a 7-13 sentence transition

- Each sentence MUST be 14-28 words maximum
+ Each sentence MUST be 20-40 words
+ Aim for 7-13 sentences total
```

### 3. `B_core/templates/segment_prompt.txt`
```diff
- Each sentence MUST be 15-30 words maximum
+ Each sentence MUST be 20-40 words
```

### 4. `historical_processor/narration_core/formatter.py`
```diff
  def _validate_and_split_sentences():
+     min_words = getattr(self.cfg, 'min_sentence_words', 20)
+     if word_count < min_words:
+         self.warnings.append(f"sentence_too_short_{word_count}_words")

  def _intelligent_split():
- max_words: int = 30
+ max_words: int = 40

  def _gpt_edit():
- "1) Split only sentences longer than ~30 words"
+ "1) Split only sentences longer than 40 words"
```

### 5. `historical_processor/narration_core/validator.py`

#### TransitionQualityValidator:
```diff
- # 1) sentence count 1–2
+ # 1) sentence count 7–13
- if len(sentences) > 2:
+ if len(sentences) < 7:
+     reasons.append("too_few_sentences")
+ if len(sentences) > 13:
      reasons.append("too_many_sentences")

- # Check sentence length (14-28 words)
+ # Check sentence length (20-40 words)
- if word_count < 14:
+ if word_count < 20:
- elif word_count > 28:
+ elif word_count > 40:
```

#### SegmentQualityValidator:
```diff
- def validate(self, text: str, max_sentence_words: int = 30):
+ def validate(self, text: str, min_sentence_words: int = 20, max_sentence_words: int = 40):

+ if word_count < min_sentence_words:
+     reasons.append("sentence_too_short")
```

---

## 📊 **Dopad na výstupy:**

### **Délka textu (orientačně):**

| Typ | v2.0.0 | v2.1.0 | Změna |
|-----|--------|--------|-------|
| **Intro** | 90-180 slov | 140-520 slov | **+289%** |
| **Transitions** | 14-56 slov | 140-520 slov | **+857%** |
| **Audio (TTS)** | Intro: 30-60s | Intro: 45-90s | +30s |
| **Audio (TTS)** | Trans: 5-15s | Trans: 40-80s | +60s |

### **Příklady:**

#### Intro:
- **v2.0.0**: cca 135 slov (6 vět × 22.5 slov)
- **v2.1.0**: cca 330 slov (11 vět × 30 slov)

#### Transitions:
- **v2.0.0**: cca 35 slov (1.5 věty × 23 slov)
- **v2.1.0**: cca 330 slov (11 vět × 30 slov)

---

## ⚠️ **Breaking Changes:**

### 1. **TransitionQualityValidator**
Starý kód očekávající 1-2 věty v transitions **selže**:
```python
tv = TransitionQualityValidator('CS')
result = tv.validate(prev, next, "Krátký přechod.")
# v2.0.0: OK
# v2.1.0: FAIL (too_few_sentences_1_minimum_7)
```

**Řešení:** Re-generuj transitions s novými pravidly.

### 2. **Test Suite**
Testy kontrolující staré limity **selžou**:
```python
# Starý test
assert len(sentences) <= 2  # ❌ FAIL v v2.1.0

# Nový test
assert 7 <= len(sentences) <= 13  # ✅ OK
```

**Řešení:** Aktualizuj testy (viz níže).

---

## 🧪 **Aktualizace testů:**

```python
# tests/test_narration_core_validator.py

# PŘED (v2.0.0):
def test_transition_validator_sentence_count():
    too_long = "Věta jedna. Věta dva. Věta tři."
    assert not res.ok
    assert "too_many_sentences" in res.reasons  # > 2 věty

# PO (v2.1.0):
def test_transition_validator_sentence_count():
    too_short = "Věta jedna. Věta dva."  # Pouze 2 věty
    res = tv.validate(prev, next_, too_short)
    assert not res.ok
    assert "too_few_sentences" in res.reasons  # < 7 vět
    
    too_long = " ".join([f"Věta {i}." for i in range(15)])  # 15 vět
    res = tv.validate(prev, next_, too_long)
    assert not res.ok
    assert "too_many_sentences" in res.reasons  # > 13 vět
```

---

## 🚀 **Deployment:**

### Krok 1: Backup
```bash
git commit -am "Backup before v2.1.0 upgrade"
```

### Krok 2: Smaž cache
```bash
python scripts/clear_narration_cache.py
```

### Krok 3: Spusť testy
```bash
# Některé testy SELŽOU (očekávané)
pytest tests/test_narration_core_validator.py -v
```

### Krok 4: Re-generuj obsah
```bash
# Pro každý projekt:
python historical_processor/runner_cli.py \
    --input-dir outputs/narration/my_topic/CS/ep01 \
    --episode-mode \
    --force-rebuild
```

### Krok 5: Kontrola
- ✅ Intro má 7-13 vět
- ✅ Transitions mají 7-13 vět
- ✅ Věty jsou 20-40 slov
- ✅ Žádné posesiva
- ✅ Objektivní third-person hlas

---

## 📝 **Rollback (pokud je třeba):**

Pokud nové nastavení nevyhovuje:

```bash
# Vrať se na v2.0.0
git revert HEAD

# Nebo ruční úprava types.py:
max_sentence_words: int = 30  # místo 40
min_sentence_words: int = 15  # místo 20

# A generator.py:
"Write a 5-6 sentence introduction"  # místo 7-13
```

---

## 🎯 **Doporučení:**

### Pro **produkční projekty:**
1. Testuj na **jedné epizodě** před masovou re-generací
2. Zkontroluj **audio délku** (TTS může být delší)
3. Případně **uprav ručně** pokud je intro/transitions moc rozvláčné

### Pro **nové projekty:**
- Použij v2.1.0 přímo
- Nastavení jsou optimalizovaná pro **delší, detailnější naraci**

### Pro **krátké projekty:**
- Možná preferuješ v2.0.0 (kratší intro/transitions)
- Nebo custom config s nižšími limity

---

## ✅ **Checklist:**

- [ ] Backup současného stavu
- [ ] Smazána cache
- [ ] Re-generováno intro
- [ ] Re-generovány transitions
- [ ] Kontrola délky vět (20-40 slov)
- [ ] Kontrola počtu vět (7-13)
- [ ] Poslechnutí TTS (délka OK?)
- [ ] Dokumentace aktualizována

---

**Verze:** v2.1.0  
**Datum:** 2024  
**Breaking Changes:** ✅ Ano (validator, test suite)  
**Backward Compatible:** ❌ Ne (vyžaduje re-generaci)
