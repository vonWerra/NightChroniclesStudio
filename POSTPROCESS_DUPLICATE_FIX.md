# 🔧 Oprava Duplicitních Složek v Postprocess (v2.1.2)

## 🐛 **Problém:**

Při generování postprocess výstupů se vytvářejí duplicitní vnořené složky:

```
❌ ŠPATNĚ:
D:\NightChroniclesStudio\outputs\postprocess\Vznik Československa\CS\ep01\Vznik Československa\CS\ep01\episode_merged.txt
                                                                  ^^^^^^^^^^^^^^^^^^^^^^^^^^^^ DUPLICITA
```

```
✅ SPRÁVNĚ:
D:\NightChroniclesStudio\outputs\postprocess\Vznik Československa\CS\ep01\episode_merged.txt
```

---

## 🔍 **Příčina:**

Pokud `runner_cli.py` dostal jako **input_dir** cestu, která už obsahovala "postprocess" ve své cestě (například při re-generaci), extrahoval topic/lang/ep z duplicitní struktury a vytvořil další duplicitní vrstvu.

**Příklad:**
```python
# Input (špatný - postprocess s duplicitou):
in_dir = Path("outputs/postprocess/Topic/CS/ep01/Topic/CS/ep01")

# Funkce _derive_episode_context_from_path() extrahovala:
topic = "Topic"
lang = "CS"
ep = "ep01"

# Vytvoření out_dir:
out_dir = out_base / topic / lang / ep
# = outputs/postprocess/Topic/CS/ep01  ← správně!

# ALE: segmenty se četly z in_dir, který už byl duplicitní,
# takže další běh mohl vytvořit další vrstvu
```

---

## ✅ **Řešení (v2.1.2):**

### 1️⃣ **Detekce postprocess input_dir**

V `process_episode_dir()` přidána logika:

```python
# Pokud in_dir obsahuje "postprocess" ve své cestě,
# najdi odpovídající narration složku a použij tu místo toho
if "postprocess" in str(in_dir).lower():
    narration_candidate = narration_root / topic_guess / lang_guess / ep_guess
    if narration_candidate.exists():
        actual_input = narration_candidate  # Použij narration místo postprocess
```

**Efekt:**
- Pokud se spustí postprocess s input_dir = "outputs/postprocess/...", automaticky se přepne na "outputs/narration/..."
- Čte segmenty z **narration** (nikdy z postprocess duplicit)
- Výstup je vždy **čistý**: `outputs/postprocess/Topic/Lang/ep/`

---

### 2️⃣ **Použití actual_input místo in_dir**

```python
# Místo:
seg_files = _collect_txt_files(in_dir)  # ❌ Mohl být postprocess

# Nyní:
seg_files = _collect_txt_files(actual_input)  # ✅ Vždy narration
```

---

## 📂 **Změněné soubory:**

1. ✅ `historical_processor/runner_cli.py` – Funkce `process_episode_dir()`
   - ➕ Detekce "postprocess" v input_dir
   - ➕ Automatické přepnutí na narration složku
   - ➕ Logging změny vstupní cesty

---

## 🧪 **Test:**

```bash
# Vygeneruj postprocess (nyní by NE MĚLO vytvořit duplicitu)
python historical_processor/runner_cli.py \
    --input-dir outputs/narration/Vznik\ Československa/CS/ep01 \
    --episode-mode \
    --use-gpt

# Zkontroluj strukturu
python scripts/fix_duplicate_folders.py --dry-run
# Očekáváno: "No duplicates found!"
```

---

## 🔧 **Cleanup existujících duplicit:**

Pokud máš stále duplicity z předchozích běhů:

```bash
# 1. Cleanup postprocess duplicit
python scripts/fix_duplicate_folders.py --root "outputs/postprocess" --fix

# 2. Ověření
python scripts/fix_duplicate_folders.py --root "outputs/postprocess" --dry-run
```

---

## 📊 **Před vs. Po:**

### **PŘED (v2.1.1):**

```bash
# Input:
--input-dir outputs/narration/Topic/CS/ep01

# Output (OK):
outputs/postprocess/Topic/CS/ep01/episode_merged.txt ✅

# Ale pokud se spustilo znovu s:
--input-dir outputs/postprocess/Topic/CS/ep01

# Output (DUPLICITA!):
outputs/postprocess/Topic/CS/ep01/Topic/CS/ep01/episode_merged.txt ❌
```

---

### **PO (v2.1.2):**

```bash
# Input (narration):
--input-dir outputs/narration/Topic/CS/ep01

# Output:
outputs/postprocess/Topic/CS/ep01/episode_merged.txt ✅

# Input (postprocess - automaticky přepne na narration):
--input-dir outputs/postprocess/Topic/CS/ep01

# LOGGER: "using_narration_input": "outputs/narration/Topic/CS/ep01"

# Output:
outputs/postprocess/Topic/CS/ep01/episode_merged.txt ✅ (ŽÁDNÁ DUPLICITA)
```

---

## 🛡️ **Prevence:**

### **Doporučené workflow:**

```bash
# 1. Vždy používej narration jako input
python historical_processor/runner_cli.py \
    --input-dir outputs/narration/Topic/Lang/ep01 \
    --episode-mode

# 2. Pokud potřebuješ re-generovat, použij --force-rebuild
python historical_processor/runner_cli.py \
    --input-dir outputs/narration/Topic/Lang/ep01 \
    --episode-mode \
    --force-rebuild
```

---

## ⚠️ **Známé limitace:**

### 1. Pokud narration složka neexistuje

Pokud spustíš s postprocess input_dir a **narration už neexistuje**, script bude číst z postprocess (může vytvořit duplicitu, pokud tam už duplicita je).

**Řešení:** Vždy uchovej narration výstupy, nebo smaž postprocess a re-generuj z narration.

---

### 2. Ručně vytvořené postprocess složky

Pokud někdo ručně vytvořil postprocess složku s jiným obsahem než narration, fix ji přepíše.

**Řešení:** Vždy generuj postprocess z narration pomocí runner_cli.

---

## 📝 **Changelog:**

### v2.1.2 (Current)
- ✅ Detekce "postprocess" v input_dir
- ✅ Automatické přepnutí na narration složku
- ✅ Prevence duplicit při re-generaci
- ✅ Logging změny vstupní cesty

### v2.1.1
- Cleanup script pro odstranění existujících duplicit
- Vylepšená `_derive_episode_context_from_path()`

### v2.1.0
- Úprava délky vět (20-40 slov)
- Intro/transitions (7-13 vět)

### v2.0.0
- Odstranění posesivních zájmen
- Validace délky vět

---

## ✅ **Checklist:**

- [ ] Upgradován na v2.1.2
- [ ] Smazány existující duplicity (`fix_duplicate_folders.py`)
- [ ] Testováno generování postprocess
- [ ] Ověřeno, že se nevytvářejí nové duplicity
- [ ] Dokumentace přečtena

---

**Poslední aktualizace:** 2024  
**Verze:** v2.1.2  
**Status:** ✅ Vyřešeno
