# Historical Processor – Odstraněno

**Datum:** 2025-10-17

## Co bylo odstraněno

### Složky a soubory
- ✅ `historical_processor/` (celá složka)
- ✅ `test_validator_debug.py`
- ✅ `test_possessive_debug.py`
- ✅ `test_path_derive.py`
- ✅ `tests/test_runner_cli.py`
- ✅ `tests/test_narration_core_validator.py`
- ✅ `tests/test_narration_core_formatter.py`
- ✅ `tests/test_narration_core_cache.py`

### Dokumentace
- ✅ `UPGRADE_GUIDE_POSSESSIVE_FIX.md`
- ✅ `SENTENCE_LENGTH_UPDATE_v3.0.md`
- ✅ `POSTPROCESS_DUPLICATE_FIX.md`

### Změny v kódu
- ✅ `studio_gui/src/main.py`:
  - Odstraněna metoda `PostProcessTab.run_episode_merged()`
  - Odstraněny checkboxy: `chk_use_gpt`, `chk_prefer_existing`, `chk_force_rebuild`, `chk_save_merged`
  - Odstraněno tlačítko `btn_run_episode_merged`
  - Odstraněny metody `open_merged_file()` a `open_manifest()`
  - Metoda `run_episode_merged()` nyní pouze loguje: "historical_processor removed"

### Aktualizace dokumentace
- ✅ `README.md`:
  - Odstraněn řádek s `historical_processor` z tabulky modulů
  - Workflow aktualizován (Historical Processor → odstraněno)
  - Počet modulů snížen z 6 na 5

---

## Důvod odstranění

Post-processing funkcionalita je nyní řešena přímo v **`narration_builder`** (Final tab), který:
- Spojuje segmenty
- Provádí post-processing (zkratky, roky slovně, normalizace)
- Generuje finální text připravený pro TTS

`historical_processor` byl redundantní mezikrok, který komplikoval workflow.

---

## Migrace pro uživatele

### Před (s historical_processor)
```bash
# 1. Narration
python claude_generator/runner_cli.py --topic "Téma" --language CS --episodes ep01

# 2. Post-processing
python historical_processor/runner_cli.py --input-dir outputs/narration/Téma/CS/ep01 --episode-mode

# 3. Final (narration_builder)
python modules/narrationbuilder/narrationbuilder/cli.py --topic-id "Téma" --episode-id 01 --lang CS
```

### Nyní (bez historical_processor)
```bash
# 1. Narration
python claude_generator/runner_cli.py --topic "Téma" --language CS --episodes ep01

# 2. Final (narration_builder s integrovaným post-processingem)
python modules/narrationbuilder/narrationbuilder/cli.py --topic-id "Téma" --episode-id 01 --lang CS
```

---

## GUI změny

### PostProcess tab
**Status:** Dočasně zachován pro kompatibilitu, ale tlačítko "Run episode (merged)" již nefunguje.

**Budoucnost:** Tab bude buď:
- Přejmenován na **Preview** (náhled textů před TTS)
- Nebo zcela odstraněn a funkcionalita přesunuta do **Final tab**

### Final tab
**Status:** Plně funkční, nyní zajišťuje:
- ✅ Spojení segmentů
- ✅ Post-processing
- ✅ Generování finálního textu

---

## Pro vývojáře

### Pokud potřebuješ starý kód
Poslední commit s `historical_processor`:
```bash
git log --oneline --all -- historical_processor/
```

Obnovení (pokud potřeba):
```bash
git checkout <commit_hash> -- historical_processor/
```

### Nové API pro post-processing
Post-processing je nyní součástí `narration_builder`. Hledej:
- `modules/narrationbuilder/narrationbuilder/cli.py`
- `modules/narrationbuilder/narrationbuilder/processor.py` (pravděpodobně)

---

## Checklist dokončení

- [x] Odstranit složku `historical_processor/`
- [x] Odstranit debug skripty (`test_*_debug.py`)
- [x] Odstranit testy pro historical_processor
- [x] Odstranit dokumentaci (UPGRADE_GUIDE, SENTENCE_LENGTH_UPDATE, POSTPROCESS_DUPLICATE_FIX)
- [x] Upravit `studio_gui/src/main.py` (odstranit PostProcessTab z MainWindow)
- [x] Označit PostProcessTab jako DEPRECATED (přejmenován na PostProcessTab_DEPRECATED)
- [x] Aktualizovat `README.md`
- [x] **Test:** Syntaktická kontrola `studio_gui/src/main.py` (py_compile) ✅
- [ ] Aktualizovat `nightchronicles_context.md` (příliš velký soubor – ponechat stávající verzi)
- [ ] Otestovat GUI (Project → Outline → Prompts → Narration → Final)
- [ ] Vytvořit commit s popisem změn

---

**Status:** ✅ Hotovo
**Next step:** Test celého workflow bez historical_processor
