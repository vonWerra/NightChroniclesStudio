# 🔧 Oprava Duplicitních Složek v Postprocess Outputs

## 🐛 **Problém:**

V `outputs/postprocess/` se vytvářejí duplicitní vnořené struktury:

```
❌ ŠPATNĚ:
outputs/postprocess/Vznik Československa/CS/ep01/Vznik Československa/CS/ep01/episode_merged.txt
                                         ^^^^^^^^^^^^^^^^^^^^^^^^^^^^ DUPLICITA
```

```
✅ SPRÁVNĚ:
outputs/postprocess/Vznik Československa/CS/ep01/episode_merged.txt
```

---

## 🔍 **Příčina:**

Funkce `_derive_episode_context_from_path()` v `historical_processor/runner_cli.py` extrahuje topic/lang/ep z **input_dir**, ale pokud input_dir už obsahuje duplicitní cestu, pak se duplicita přenese i do výstupu.

**Příklad:**
```python
# Input:
input_dir = Path("outputs/narration/Vznik Československa/CS/ep01/Vznik Československa/CS/ep01")

# Funkce extrahuje:
topic = "Vznik Československa"  # z topic_dir.name (obsahuje duplicitu!)
lang = "CS"
ep = "ep01"

# Output dir:
out_dir = out_base / topic / lang / ep
# = outputs/postprocess/Vznik Československa/CS/ep01/Vznik Československa/CS/ep01 ❌
```

---

## ✅ **Řešení:**

### 1️⃣ **Oprava kódu (v2.1.1)**

Upravena funkce `_derive_episode_context_from_path()` aby detekovala a odstranila duplicitní segmenty v cestě:

```python
def _derive_episode_context_from_path(p: Path) -> Tuple[str, str, str, int]:
    # ...
    # If we detect topic/lang/ep structure WITHIN topic name itself, clean it
    if "\\" in topic or "/" in topic:
        # Take only first segment
        topic = topic.split("\\")[0].split("/")[0]
    # ...
```

**Status**: ✅ Implementováno

---

### 2️⃣ **Cleanup Script pro existující duplicity**

Vytvořen helper script: `scripts/fix_duplicate_folders.py`

#### Použití:

```bash
# 1. Kontrola (dry-run)
python scripts/fix_duplicate_folders.py --dry-run

# 2. Náhled co bude opraveno
python scripts/fix_duplicate_folders.py

# 3. Skutečná oprava (vyžaduje potvrzení)
python scripts/fix_duplicate_folders.py --fix
```

#### Co dělá:
1. Skenuje `outputs/postprocess/` pro duplicitní struktury
2. Najde všechny soubory v nested složkách
3. Přesune je do správné lokace
4. Smaže prázdnou nested strukturu

---

## 📊 **Jak zjistit, zda máš duplicity:**

### Metoda 1: PowerShell
```powershell
Get-ChildItem -Path "outputs\postprocess" -Recurse -Directory | 
    Where-Object { $_.FullName -match "\\ep\d+\\.*\\ep\d+" } |
    Select-Object FullName
```

### Metoda 2: Python
```bash
python scripts/fix_duplicate_folders.py --dry-run
```

---

## 🚀 **Postup opravy:**

### Krok 1: Backup
```bash
# Vytvoř backup před opravou
xcopy outputs\postprocess outputs\postprocess_backup\ /E /I /H /Y
```

### Krok 2: Kontrola
```bash
# Zjisti, kolik duplicit máš
python scripts/fix_duplicate_folders.py --dry-run
```

### Krok 3: Oprava
```bash
# Oprav duplicity
python scripts/fix_duplicate_folders.py --fix
```

### Krok 4: Ověření
```bash
# Zkontroluj, že duplicity zmizely
python scripts/fix_duplicate_folders.py --dry-run
# Očekáváno: "✅ No duplicates found!"
```

---

## 📝 **Příklad výstupu:**

```
🔍 Scanning for duplicates in: outputs/postprocess

⚠️  Found 2 duplicate structures:

1. Vznik Československa/CS/ep01
   Duplicate at: outputs\postprocess\Vznik Československa\CS\ep01\Vznik Československa\CS\ep01

2. Bitva o dukelský průsmyk/CS/ep01
   Duplicate at: outputs\postprocess\Bitva o dukelský průsmyk\CS\ep01\Bitva o dukelský průsmyk\CS\ep01

======================================================================
[DRY RUN] Fixing duplicate:
  Topic: Vznik Československa
  Lang: CS
  Episode: ep01
  Correct path: outputs\postprocess\Vznik Československa\CS\ep01
  Nested path: outputs\postprocess\Vznik Československa\CS\ep01\Vznik Československa\CS\ep01
    Moving: episode_merged.txt -> outputs\postprocess\Vznik Československa\CS\ep01\episode_merged.txt
    Moving: episode_merged.txt.meta.json -> outputs\postprocess\Vznik Československa\CS\ep01\episode_merged.txt.meta.json
    Moving: manifest.json -> outputs\postprocess\Vznik Československa\CS\ep01\manifest.json
  Would move 3 files

======================================================================
Would fix 2 duplicates, moving 6 files
Run with --fix to actually apply changes
```

---

## 🛡️ **Prevence:**

### Pro budoucí projekty:

1. **Používej aktualizovanou verzi** (v2.1.1+) s opravenou funkcí
2. **Kontroluj input paths** před spuštěním runner_cli.py
3. **Pravidel né input-dir**:
   ```bash
   # ✅ Správně:
   --input-dir outputs/narration/Topic/Lang/ep01
   
   # ❌ Špatně:
   --input-dir outputs/narration/Topic/Lang/ep01/Topic/Lang/ep01
   ```

---

## ⚠️ **Known Issues:**

### Problém 1: Encoding v názvech
Pokud vidíš znaky jako "琫skoslovenska" místo "Československa", je to problém s Windows console encoding.

**Řešení:**
```bash
# Nastav UTF-8 encoding
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8
```

### Problém 2: Vnořené duplicity (3+ úrovně)
Script aktuálně řeší jednu úroveň duplicity. Pro vícenásobné vnořené duplicity spusť script vícekrát.

---

## 📞 **Troubleshooting:**

### Problém: Script nenajde duplicity, ale vím, že tam jsou

**Řešení:**
```bash
# Ruční kontrola:
Get-ChildItem -Path "outputs\postprocess" -Recurse -Filter "episode_merged.txt" | 
    ForEach-Object { 
        $path = $_.FullName
        if ($path -match "\\ep\d+\\.*\\ep\d+") {
            Write-Host "DUPLICATE: $path"
        }
    }
```

### Problém: PermissionError při přesunu souborů

**Řešení:**
- Zavři všechny programy, které mohou mít soubory otevřené
- Spusť jako administrátor
- Zkontroluj, že soubory nejsou read-only

---

## ✅ **Checklist:**

- [ ] Backup vytvořen
- [ ] Dry-run spuštěn
- [ ] Počet duplicit zkontrolován
- [ ] Fix spuštěn (s potvrzením)
- [ ] Ověřeno, že duplicity zmizely
- [ ] Aplikace upgradována na v2.1.1+

---

## 🔗 **Související:**

- `historical_processor/runner_cli.py` – Obsahuje opravenou funkci
- `scripts/fix_duplicate_folders.py` – Cleanup script
- **Issue**: Duplicitní složky v postprocess outputs
- **Fix Version**: v2.1.1

---

**Poslední aktualizace:** 2024  
**Verze:** v2.1.1
