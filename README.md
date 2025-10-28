# NightChronicles Studio

Systém pro tvorbu historických YouTube sérií pomocí AI.

---

## 📦 **Moduly**

| Modul | Účel | Status | Model |
|-------|------|--------|-------|
| **outline-generator** | Generování osnov | ✅ Opraveno | GPT-4.1-mini |
| **B_core** | Generování promptů | ⏳ K opravě | - |
| **claude_generator** | Narativní texty | ✅ Funkční | Claude Opus |
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

---

## 🎯 **Plán**

### **Fáze 1: Opravy modulů** ✅ 1/6
- [x] outline-generator
- [ ] B_core
- [ ] claude_generator (revize)
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

---

## 💡 **Status**

🟢 **Outline Generator** – Produkčně připraveno
🟡 **Ostatní moduly** – Fungují, ale vyžadují cleanup
🔵 **GUI** – V plánu

---

**Aktualizováno:** 2024-10-08
**Verze:** 0.2.0-alpha
