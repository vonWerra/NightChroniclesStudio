# ⚡ Quick Start – Outline Generator

## 🚀 **Spuštění za 3 kroky**

### **1. Nastavte API klíč**
```bash
# Upravte .env soubor:
notepad .env

# Přidejte:
OPENAI_API_KEY=sk-proj-your-key-here
GPT_MODEL=gpt-4.1-mini
```

### **2. Test konfigurace (zdarma)**
```bash
python generate_outline.py --dry-run -v
```
**Očekávaný výstup:**
```
[OK] Configuration is valid
[OK] Would generate outlines for: CS, EN, ES, FR, DE
```

### **3. Vygenerujte osnovu**
```bash
# Jeden jazyk (CS):
python generate_outline.py -l CS -v

# Všechny jazyky:
python generate_outline.py -v
```

---

## 💰 **Ceny**

| Akce | Cena | Čas |
|------|------|-----|
| 1 jazyk (CS) | $0.004 | ~2 min |
| 5 jazyků | $0.02 | ~10 min |
| Paralelně (--parallel) | $0.02 | ~3 min |

---

## 📂 **Kde najdu výstupy?**

```
outline-generator/output/
└── Vznik_Československa/  (název tématu z config)
    ├── CS/
    │   ├── osnova.json  (strukturovaná data)
    │   └── osnova.txt   (čitelný přehled)
    ├── EN/
    ├── DE/
    ├── ES/
    └── FR/
```

---

## ⚙️ **Změna tématu**

Upravte `config/outline_config.json`:
```json
{
  "topic": "Váš nový název tématu",
  "languages": ["CS", "EN"],
  "episodes": 6
}
```

---

## 📝 **Více info**

- **README.md** – Kompletní dokumentace
- **CHANGES.md** – Changelog všech úprav
- `--help` – Všechny CLI parametry

---

## 🆘 **Problémy?**

### **Model not found:**
```bash
# V .env změňte na:
GPT_MODEL=gpt-4o-mini
# nebo
GPT_MODEL=gpt-4-turbo-preview
```

### **Rate limit:**
Počkejte 1 minutu, pak zkuste znovu.

### **Encoding chyby:**
Už opraveno! Pokud přetrvávají, napište.

---

**Připraveno! Spusťte test.** 🎉
