# ✅ E2E Test Ready!

**Status:** Připraveno k testování  
**Datum:** 2024-01-21

---

## 🎯 Co budeme testovat

**Kompletní pipeline:**
```
1. Outline Generator  →  osnova.json
2. B_core            →  prompts/*.txt
3. Claude Generator  →  narration/segment_*.txt
4. Narration Builder →  final/episode_XX_final.txt
```

---

## ✅ Pre-Check

**Skripty dostupné:**
- ✅ `outline-generator/generate_outline.py`
- ✅ `B_core/generate_prompts.py`
- ✅ `claude_generator/runner_cli.py`
- ✅ `modules/narrationbuilder/narrationbuilder/cli.py`

**Python verze:**
- ✅ 3.13.3 (64-bit)

---

## 🚀 Spuštění testu

### **Rychlý automatický test:**

```bash
python test_e2e_workflow.py --topic "TestNapoleon" --lang CS
```

### **Nebo manuálně krok za krokem:**

#### **1. Nastavit API klíče:**
```bash
# Potřebné pro kroky 3 & 4
export ANTHROPIC_API_KEY="sk-ant-..."
export OPENAI_API_KEY="sk-..."
```

#### **2. Nastavit outputs root:**
```bash
export NC_OUTPUTS_ROOT="$(pwd)/outputs"
```

#### **3. Spustit workflow:**

```bash
# STEP 1: Outline
cd outline-generator
python generate_outline.py -l CS -v

# STEP 2: Prompts
cd ../B_core
python generate_prompts.py --topic "YourTopic" --language CS -y

# STEP 3: Narration (VYŽADUJE ANTHROPIC_API_KEY)
cd ../claude_generator
python runner_cli.py --topic "YourTopic" --language CS --episodes "ep01" -v

# STEP 4: Final (VYŽADUJE OPENAI_API_KEY)
cd ../modules/narrationbuilder
python -m narrationbuilder --project-root ../.. --topic-id "YourTopic" --episode-id 01 --lang CS
```

---

## 📋 Kontrolní seznam

Po každém kroku zkontroluj:

### **Krok 1 - Outline:**
```bash
ls outputs/outline/<Topic>/CS/
# Mělo by být:
# - osnova.json ✓
# - generation_log.json ✓
```

### **Krok 2 - Prompts:**
```bash
ls outputs/prompts/<Topic>/CS/ep01/prompts/
# Mělo by být:
# - msp_01_execution.txt ✓
# - msp_02_execution.txt ✓
# - ... (podle počtu segmentů)
```

### **Krok 3 - Narration:**
```bash
ls outputs/narration/<Topic>/CS/ep01/
# Mělo by být:
# - segment_01.txt ✓
# - segment_02.txt ✓
# - ... (podle počtu segmentů)
# - generation_log.json ✓
```

### **Krok 4 - Final:**
```bash
ls outputs/final/<Topic>/CS/episode_01/
# Mělo by být:
# - episode_01_final.txt ✓
# - metrics.json ✓
# - prompt_pack.json ✓
# - status.json ✓
```

---

## ⚠️ Možné problémy

### **Pokud některý krok selže:**

1. **Chybí API klíč:**
   ```bash
   # Zkontroluj
   echo $ANTHROPIC_API_KEY  # pro claude_generator
   echo $OPENAI_API_KEY     # pro narrationbuilder
   ```

2. **Téma nebylo nalezeno:**
   - Zkontroluj přesný název tématu (case-sensitive)
   - Použij název složky z `outputs/outline/`

3. **Moduly nedostupné:**
   ```bash
   # Nainstaluj závislosti
   pip install -r requirements-all.txt
   ```

4. **Cesta nenalezena:**
   ```bash
   # Zkontroluj NC_OUTPUTS_ROOT
   echo $NC_OUTPUTS_ROOT
   ls $NC_OUTPUTS_ROOT
   ```

---

## 📊 Očekávané výsledky

**Při úspěšném testu:**
- ✅ Všechny 4 kroky dokončeny bez chyb
- ✅ Všechny output soubory existují
- ✅ Finální text má 1800-2200 slov
- ✅ Text je soudržný (ne jen spojené segmenty)
- ✅ Správný jazyk (CS/EN/DE/ES/FR)

**Čas:**
- Kompletní workflow: **~10-20 minut**
- Závisí na API response time

---

## 🎓 Co test ověřuje

1. **Integrace modulů** – každý modul správně čte výstupy předchozího
2. **Path resolution** – všechny moduly používají `NC_OUTPUTS_ROOT`
3. **Data flow** – osnova → prompty → segmenty → finální text
4. **Quality** – každý krok produkuje validní výstupy
5. **Error handling** – moduly správně reportují chyby

---

## 📝 Reporting

**Po testu:**

1. **Automatický test** vytvoří:
   ```
   test_e2e_results.json
   ```

2. **Manuální test** – zapiš výsledky:
   - Outline: ✅/❌
   - Prompts: ✅/❌
   - Narration: ✅/❌ (nebo SKIPPED pokud bez API klíče)
   - Final: ✅/❌ (nebo SKIPPED pokud bez API klíče)

3. **Issues found:**
   - (zapiš všechny problémy)

---

## 🔄 Co dál?

**Pokud test projde:**
- ✅ Můžeme pokračovat na **elevenlabs_vystup** (TTS)
- ✅ Nebo aktualizovat **GUI** pro nové funkce
- ✅ Nebo vytvořit **dokumentaci** pro uživatele

**Pokud test selže:**
- 🔧 Opravíme nalezené problémy
- 🧪 Re-test konkrétního kroku
- 📝 Zalogujeme issue

---

## 🚀 Quick Start

**Nejrychlejší způsob:**

```bash
# 1. Set API keys (pokud máš)
export ANTHROPIC_API_KEY="sk-ant-..."
export OPENAI_API_KEY="sk-..."

# 2. Set outputs root
export NC_OUTPUTS_ROOT="$(pwd)/outputs"

# 3. Run test
python test_e2e_workflow.py --topic "TestNapoleon" --lang CS
```

**Nebo bez API klíčů (jen outline + prompts):**

```bash
python test_e2e_workflow.py --topic "TestNapoleon" --lang CS
# Kroky 3 & 4 budou skipped
```

---

**Připraveno! Můžeš spustit test! 🎉**

Chceš:
- **A)** Spustit automatický test? (`python test_e2e_workflow.py ...`)
- **B)** Jít manuálně krok za krokem?
- **C)** Nejdřív zkontrolovat, jestli máš API klíče?
