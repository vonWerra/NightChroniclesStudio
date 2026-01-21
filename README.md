# NightChronicles Studio

Systém pro tvorbu historických YouTube sérií pomocí AI.

---

## 📦 **Moduly**

| Modul | Účel | Status | Model |
|-------|------|--------|-------|
| **outline-generator** | Generování osnov | ✅ Opraveno (v1.1) | GPT-4.1-mini |
| **B_core** | Generování promptů | ✅ Opraveno (v2.0) | - |
| **claude_generator** | Narativní texty | ✅ Opraveno (v2.0) | Claude Opus 4.5 |
| **narration_builder** | Fúze & post-processing | ⏳ K revizi | GPT-4 |
| **elevenlabs_vystup** | TTS (ElevenLabs) | ⏳ K prozkoumání | - |

---

## 🚀 **Quick Start**

### **1. Outline Generator** (hotovo)
```bash
cd outline-generator
python generate_outline.py -l CS -v
```
**Dokumentace:** `outline-generator/QUICK_START.md`

### **2. B_core (Prompts)** (hotovo)
```bash
python B_core/generate_prompts.py --topic "Napoleon" --language CS -y
```
**Dokumentace:** `B_core/README.md`

### **3. Claude Generator (Narration)** (hotovo)
```bash
python claude_generator/runner_cli.py --topic "Napoleon" --language CS --episodes "ep01"
```
**Dokumentace:** `claude_generator/README.md`

---

## 🎯 **Plán**

### **Fáze 1: Opravy modulů** ✅ 3/5
- [x] outline-generator (v1.1)
- [x] B_core (v2.0)
- [x] claude_generator (v2.0)
- [ ] narration_builder
- [ ] elevenlabs_vystup

### **Fáze 2: Sjednocení**
- [ ] Unified output struktura: `projects/{topic}/{lang}/0X_module/`
- [ ] Společné API klienty
- [ ] Jednotné logování

### **Fáze 3: GUI (PySide6)**
- [ ] Main window + 7 tabs
- [ ] Subprocess orchestrace
- [ ] Progress tracking

---

## 📊 **Workflow**

```
1. Outline Generator    → osnova.json (6 epizod × 5 jazyků)
   ↓
2. B_core               → prompty pro Claude
   ↓
3. Claude Generator     → narativní segmenty
   ↓
4. Narration Builder    → spojené epizody + post-processing
   ↓
5. ElevenLabs           → MP3 soubory
   ↓
7. Export               → finální balíčky
```

---

## 🛠️ **Technologie**

- **Python 3.11+**
- **OpenAI API** (GPT-4.1-mini, GPT-4 Turbo)
- **Anthropic API** (Claude Opus)
- **ElevenLabs API** (TTS)
- **PySide6** (GUI - plánováno)
- **Pydantic** (validace)
- **structlog** (logování)

---

## 📝 **Dokumentace**

- Projektový kontext: [nightchronicles_context.md](nightchronicles_context.md)
- Outline Generator: [outline-generator/README.md](outline-generator/README.md)
  - Quick Start: [outline-generator/QUICK_START.md](outline-generator/QUICK_START.md)
  - Changelog: [outline-generator/CHANGES.md](outline-generator/CHANGES.md)
- B_core (Prompts): [B_core/README.md](B_core/README.md)
  - Fixes Summary: [B_core/FIXES_SUMMARY.md](B_core/FIXES_SUMMARY.md)
  - Changelog: [B_core/CHANGELOG_v2.0.md](B_core/CHANGELOG_v2.0.md)
- Claude Generator (Narration): [claude_generator/README.md](claude_generator/README.md)
  - Fixes Summary: [claude_generator/FIXES_SUMMARY.md](claude_generator/FIXES_SUMMARY.md)
  - Changelog: [claude_generator/CHANGELOG_v2.0.md](claude_generator/CHANGELOG_v2.0.md)

---

## 💡 **Status**

🟢 **Outline Generator** – Produkčně připraveno (v1.1)
🟢 **B_core** – Produkčně připraveno (v2.0)
🟢 **Claude Generator** – Produkčně připraveno (v2.0)
🟡 **Ostatní moduly** – Fungují, ale vyžadují cleanup
🔵 **GUI** – V plánu

---

**Aktualizováno:** 2024-01-21
**Verze:** 0.4.0-alpha
