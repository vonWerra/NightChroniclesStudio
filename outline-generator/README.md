# YouTube Series Outline Generator

Refaktorovaný systém pro generování strukturovaných osnov historických YouTube sérií v různých jazycích pomocí AI.

## ✨ Klíčové vylepšení

- **Asynchronní zpracování** - paralelní generování pro všechny jazyky
- **Robustní error handling** - exponential backoff pro API volání
- **Strukturované logování** - detailní logy s `structlog`
- **Cache systém** - ukládání mezivýsledků pro rychlejší opakované běhy
- **Monitoring** - sledování nákladů, tokenů a výkonu
- **CLI interface** - profesionální příkazová řádka s argparse
- **Validace dat** - Pydantic modely pro všechny datové struktury
- **Unit testy** - kompletní test suite s pytest
- **Cross-platform** - funguje na Windows, Linux i macOS
- **UTF-8 podpora** - správné kódování všech souborů

## 📁 Struktura projektu

```
outline-generator/
├── src/
│   ├── __init__.py
│   ├── api_client.py     # API client s retry logikou
│   ├── cache.py          # Cache manager
│   ├── config.py         # Konfigurace a validace
│   ├── generator.py      # Hlavní generátor
│   ├── logger.py         # Strukturované logování
│   ├── models.py         # Pydantic modely
│   └── monitor.py        # Monitoring metrik
├── tests/
│   └── test_generator.py # Unit testy
├── config/
│   └── outline_config.json
├── templates/
│   └── outline_master.txt
├── output/               # Generované výstupy
├── logs/                # Logy a reporty
├── .cache/              # Cache soubory
├── .env                 # Konfigurace prostředí
├── requirements.txt
└── generate_outline.py  # Hlavní skript
```

## 🚀 Instalace

1. **Klonování repozitáře**
```bash
git clone <repository>
cd outline-generator
```

2. **Vytvoření virtuálního prostředí**
```bash
python -m venv venv
source venv/bin/activate  # Linux/Mac
# nebo
venv\Scripts\activate  # Windows
```

3. **Instalace závislostí**
```bash
pip install -r requirements.txt
```

4. **Konfigurace prostředí**
```bash
cp .env.example .env
# Editujte .env a vložte váš OpenAI API klíč
```

## 📝 Použití

### Základní použití
```bash
python generate_outline.py
```

### Pokročilé možnosti
```bash
# Paralelní zpracování všech jazyků
python generate_outline.py --parallel

# Pouze specifické jazyky
python generate_outline.py -l CS EN

# Vlastní cesty k souborům
python generate_outline.py -c my_config.json -t my_template.txt -o my_output/

# Dry run - pouze validace
python generate_outline.py --dry-run

# Verbose mode pro debugging
python generate_outline.py -vv

# Vypnutí cache
python generate_outline.py --no-cache
```

### CLI Parametry
- `-c, --config` - Cesta ke konfiguračnímu souboru
- `-t, --template` - Cesta k šabloně
- `-o, --output` - Výstupní adresář
- `-l, --languages` - Jazyky k vygenerování (CS, EN, DE, ES, FR)
- `-p, --parallel` - Paralelní zpracování
- `--cache/--no-cache` - Zapnutí/vypnutí cache
- `-v, --verbose` - Zvýšení detailnosti logů (-vv pro DEBUG)
- `--dry-run` - Pouze validace bez generování

## ⚙️ Konfigurace

### Konfigurace v `outline_config.json`:
```json
{
  "TOPIC": "Vznik Československa",
  "LANGUAGES": ["CS", "EN", "DE", "ES", "FR"],
  "EPISODES": "auto",
  "EPISODE_MINUTES": 60,
  "MSP_PER_EPISODE": 5,
  "TOLERANCE_MIN": 55,
  "TOLERANCE_MAX": 65
}
```

### Prostředí v `.env`:
```bash
OPENAI_API_KEY=sk-...
GPT_MODEL=gpt-4.1-mini
GPT_TEMPERATURE=0.3
GPT_MAX_TOKENS=6000
```

## 📊 Monitoring

Systém automaticky sleduje:
- Počet API volání a jejich úspěšnost
- Spotřebu tokenů
- Odhadované náklady
- Cache hit rate
- Průměrnou dobu odpovědi

Reporty se ukládají do `logs/monitor_report_*.json`

## 🧪 Testování

```bash
# Spuštění všech testů
pytest

# S coverage reportem
pytest --cov=src

# Pouze specifické testy
pytest tests/test_generator.py::TestConfig

# Verbose mode
pytest -v
```

## 🔄 Cache systém

Cache automaticky ukládá:
- Vygenerované osnovy pro každý jazyk
- Platnost 24 hodin (konfigurovatelné)
- Automatické čištění starých záznamů

Správa cache:
```bash
# Vypnutí cache
python generate_outline.py --no-cache

# Vyčištění cache
rm -rf .cache/
```

## 📈 Výkonnostní optimalizace

- **Paralelní zpracování**: 5 jazyků najednou místo postupně
- **Connection pooling**: Znovupoužití HTTP spojení
- **Cache**: Eliminace duplicitních API volání
- **Exponential backoff**: Automatické opakování při chybách

## 🐛 Řešení problémů

### Chyby kódování
Všechny soubory jsou v UTF-8. Pokud vidíte rozbité znaky:
1. Zkontrolujte kódování v editoru
2. Použijte `encoding='utf-8'` při čtení souborů

### API limity
Při překročení rate limitů:
- Systém automaticky zpomalí pomocí exponential backoff
- Použijte `--no-parallel` pro sekvenční zpracování

### Nedostatečná paměť
Pro velké projekty:
- Zpracovávejte méně jazyků najednou
- Snižte `max_tokens` v .env
- Použijte sekvenční místo paralelního zpracování

## 📝 Příklad výstupu

```
output/
└── Vznik_Československa/
    ├── CS/
    │   ├── osnova.json
    │   └── osnova.txt
    ├── EN/
    │   ├── osnova.json
    │   └── osnova.txt
    └── ...
```

## 🤝 Přispívání

1. Fork projektu
2. Vytvořte feature branch (`git checkout -b feature/AmazingFeature`)
3. Commitujte změny (`git commit -m 'Add some AmazingFeature'`)
4. Push do branch (`git push origin feature/AmazingFeature`)
5. Otevřete Pull Request

## 📄 Licence

MIT License - viz LICENSE soubor

## 🙏 Poděkování

- OpenAI za GPT API
- Pydantic za validaci dat
- Structlog za logging framework
- Všem přispěvatelům
