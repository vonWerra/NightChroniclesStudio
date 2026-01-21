# B_core Changelog v2.0

## 2024-01-XX – Robustness & Cleanup

### ✅ Fixed Issues

#### 1. **Robustní parsing MSP (Main Story Points)**
**Problém:** Kód očekával specifický formát MSP objektů, což způsobovalo crash při různých formátech osnovy.

**Oprava:**
- Přidána funkce `extract_msp_label(msp: Any) -> str`
- Podporuje různé formáty:
  - String: `"Napoleon's rise to power"`
  - Dict s klíčem `"text"`: `{"text": "Napoleon...", "sources_segment": [...]}`
  - Dict s klíčem `"label"`: `{"label": "Napoleon...", ...}`
  - Dict s klíčem `"msp"`: `{"msp": "Napoleon...", ...}`
  - Dict s klíčem `"msp_label"`: `{"msp_label": "Napoleon...", ...}`
- Fallback na episode-level zdroje, pokud segment nemá vlastní `sources_segment`
- Lepší error messages s kontextem (typ MSP, obsah)

**Dopad:** Modul nyní zvládne osnovy z různých verzí outline-generatoru.

---

#### 2. **Odstranění hard-coded jazyka**
**Problém:** `config/params.json` obsahoval `"lang": "en"`, což bylo matoucí – jazyk se předává přes CLI argument `--language`.

**Oprava:**
- Odstraněno `"lang": "en"` z `params.json`
- Jazyk je nyní **vždy** z CLI argumentu (nebo interaktivního výběru)
- Config soubor je univerzální pro všechny jazyky

**Dopad:** Eliminuje riziko záměny jazyků, jasná "single source of truth".

---

#### 3. **Cleanup obsolete kódu**
**Problém:** Template obsahoval `{CANON_BLOCK}` placeholder, který byl vždy prázdný (dead code).

**Oprava:**
- Odstraněna sekce `OPTIONAL REFERENCE (DO NOT OUTPUT) {CANON_BLOCK}` z `segment_prompt.txt`
- Odstraněno `"use_canon": false` z `params.json`
- Odstraněno nastavení `"CANON_BLOCK": ""` v mappingu

**Dopad:** Čistší kód, méně matoucích sekcí pro Claude.

---

### 📋 Upgrading Notes

**Stávající projekty:**
- Žádné breaking changes – vše zpětně kompatibilní
- Pokud máte vlastní kopii `params.json` s `"lang"` klíčem, můžete jej odstranit (není nutné)
- Prompts generované před i po změně jsou identické (kromě absence `CANON_BLOCK` sekce)

**Nové funkce:**
- Lepší kompatibilita s různými formáty osnov
- Jasnější error messages při chybách v datech

---

### 🔧 Technical Details

**Files Changed:**
- `generate_prompts.py` – přidána `extract_msp_label()`, vylepšen error handling
- `config/params.json` – odstraněno `"lang"` a `"use_canon"`
- `templates/segment_prompt.txt` – odstraněna `CANON_BLOCK` sekce

**Testing:**
```bash
# Test with different MSP formats
cd B_core
python generate_prompts.py --topic YourTopic --language CS -v
```

---

### 🎯 Next Steps

**Doporučené vylepšení (pro budoucí verze):**
1. **Batch processing** – `--languages all` pro zpracování všech jazyků najednou
2. **Continue-on-error** – `--continue-on-error` flag pro resilience
3. **Better validation** – přidat pre-flight checks pro osnova.json strukturu
4. **Template improvements** – zjednodušit style requirements (20-40 words → 15-35)

---

### 📖 Documentation

Pro podrobnosti viz:
- [B_core README](README.md) – usage guide
- [nightchronicles_context.md](../nightchronicles_context.md) – projekt overview
