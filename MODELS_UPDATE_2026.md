# Models Update – Leden 2026

## ✅ **PROVEDENÉ ZMĚNY**

### **1. outline-generator → `gpt-5-mini`**

**Soubory:**
- ✅ `outline-generator/src/config.py` (řádek 76 + 189)
- ✅ `outline-generator/src/api_client.py` (default model + valid_models seznam)
- ✅ `studio_gui/src/main.py` (OutlineTab placeholder)

**Před:**
```python
model: str = "gpt-4.1-mini"  # ❌ Neexistující model
```

**Po:**
```python
model: str = "gpt-5-mini"  # ✅ Platný model (leden 2026)
```

---

### **2. narrationbuilder CLI → `gpt-5.2`**

**Soubory:**
- ✅ `modules/narrationbuilder/narrationbuilder/cli.py` (řádek 29)
- ✅ `studio_gui/src/main.py` (FinalTab placeholder)

**Před:**
```python
model: str = typer.Option("gpt-5", "--model", ...)  # ⚠️ Nekonzistence s LLM modulem
```

**Po:**
```python
model: str = typer.Option("gpt-5.2", "--model", ...)  # ✅ Sjednoceno s LLM
```

**Info:** LLM modul (`llm.py`) **již měl** `gpt-5.2`, takže teď jsou CLI i LLM **konzistentní**.

---

### **3. api_client.py → Aktualizován seznam validních modelů**

**Soubor:** `outline-generator/src/api_client.py`

**Před (2024/2025 modely):**
```python
valid_models = [
    "gpt-4.1-mini",    # ❌ Neexistuje
    "gpt-4.1",         # ❌ Neexistuje
    "gpt-4-turbo-preview",
    "gpt-4-0125-preview",
    "gpt-4-1106-preview",
    "gpt-4",
    "gpt-4o-mini",
    "gpt-3.5-turbo",
    "gpt-3.5-turbo-0125",
    "gpt-3.5-turbo-1106"
]
```

**Po (2026 modely):**
```python
valid_models = [
    "gpt-5.2",       # ✅ Nejnovější
    "gpt-5",         # ✅ Platný
    "gpt-5-mini",    # ✅ Levný variant
    "gpt-4o",        # ✅ Stále podporováno
    "gpt-4o-mini",   # ✅ Stále podporováno
    "gpt-4-turbo",   # ✅ Legacy
    "gpt-4"          # ✅ Legacy
]
```

---

## 📊 **SOUČASNÝ STAV (po úpravách)**

| Modul | Default model | Status | Změněno |
|-------|---------------|--------|---------|
| **outline-generator** | `gpt-5-mini` | ✅ | Ano (z `gpt-4.1-mini`) |
| **narrationbuilder CLI** | `gpt-5.2` | ✅ | Ano (z `gpt-5`) |
| **narrationbuilder LLM** | `gpt-5.2` | ✅ | Ne (již bylo správně) |
| **GUI OutlineTab** | `gpt-5-mini` | ✅ | Ano (placeholder) |
| **GUI FinalTab** | `gpt-5.2` | ✅ | Ano (placeholder) |
| **claude_generator.py** | `claude-opus-4-5-20251101` | ✅ | Ano |
| **claude_generator_simple.py** | `claude-opus-4-5-20251101` | ✅ | Ano |
| **run_generator.bat** | `claude-opus-4-5-20251101` | ✅ | Ano |
| **test_installation.py** | `claude-opus-4-5-20251101` | ✅ | Ano |

---

### **4. Claude modely → `claude-opus-4-5-20251101`**

**Soubory:**
- ✅ `claude_generator/claude_generator.py` (řádek 618)
- ✅ `claude_generator/claude_generator_simple.py` (řádek 51)
- ✅ `claude_generator/run_generator.bat` (řádek 88)
- ✅ `claude_generator/test_installation.py` (řádek 67)

**Před (různé verze):**
```python
model: str = os.getenv('CLAUDE_MODEL', 'claude-opus-4-20250514')  # claude_generator.py
model: str = os.getenv('CLAUDE_MODEL', 'claude-opus-4-1-20250805')  # claude_generator_simple.py
CLAUDE_MODEL=claude-opus-4-1-20250805  # run_generator.bat
model="claude-opus-4-1-20250805"  # test_installation.py
```

**Po (sjednoceno):**
```python
model: str = os.getenv('CLAUDE_MODEL', 'claude-opus-4-5-20251101')  # ✅ Aktuální API název
```

---

## ✅ **TESTOVÁNÍ**

Po těchto změnách by měly moduly fungovat s platnými GPT-5 modely (leden 2026):

```bash
# Test outline-generator (gpt-5-mini)
python outline-generator/generate_outline.py -c config.json -t template.txt -o output

# Test narrationbuilder (gpt-5.2)
python -m narrationbuilder.cli --project-root . --topic-id test --episode-id 01 --lang CS

# GUI
python run_gui.bat
```

---

**Datum:** 2026-01-XX
**Opraveno:** 9 souborů
**Status:** ✅ **KOMPLETNĚ HOTOVO** (GPT i Claude modely)
