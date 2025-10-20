# NightChronicles – Project Context

## Cíl (stručně)
- Zrevidovat a opravit kód ve všech původních souborech (sjednocení stylu, bezpečnost, stabilita).
- Optimalizovat programy podle platných standardů (PEP8, typing, logging, konfigurace, struktura balíčků).
- Postavit společné desktop GUI (PySide6/Qt) se společným menu a kartami (tabs), kde každý modul běží samostatně (subprocess).
- Neměnit formáty výstupů modulů – GUI je pouze orchestrátor.
- Jazyky: uživatel si v GUI volí z 5 jazyků (CS, EN, DE, ES, FR) pro daný krok (např. osnova).
- TTS (ElevenLabs): uživatel vybere, které výstupy převést na řeč; dávkové i selektivní zpracování.

## Princip (nezávislé moduly + společné GUI)
- Každá stávající aplikace = modul; může mít vlastní venv.
- GUI (PySide6/Qt) spouští moduly jako subprocess, hlídá stav a zobrazuje logy.
- Vstup každého kroku = data uložená předchozím krokem do společné složky outputs/.
- Výstup každého kroku = zapisuje jen do své složky v outputs/ (bez duplicitních podadresářů).
- Formáty výstupů modulů se nemění.

## UX (tabs)
1. Project – výběr Project Root, obecná nastavení, test klíčů.
2. Outline – generování/úprava osnovy; výběr jazyků (CS/EN/DE/ES/FR) přes checkboxy.
3. Prompts – generování promptů z osnovy + šablon; přehled souborů.
4. Narration – generování textů; stav segmentů, Retry failed only.
5. Post-process – přepis zkratek, roky číslem→slovem, intro/přechody; náhled před/po.
6. TTS (ElevenLabs) – výběr, které výstupy převést; výběr hlasu/rychlosti; preview; batch run.
7. Export – balíčky (ZIP), otevřít složku, přehled.

## Sjednocená projektová struktura (aktualizováno)
- Outputs root (NC_OUTPUTS_ROOT) slouží jako kořenová složka.
- Přístupná podoba nyní (bez duplicitního 'narration' ve vnořených složkách):
  - outline/ → {téma}/{jazyk}/osnova.json | osnova.txt
  - prompts/ → {téma}/{jazyk}/epXX/prompts/…
  - narration/ → {téma}/{jazyk}/epXX/segment_XX.txt, fusion_result.txt
  - postprocess/ → {téma}/{jazyk}/epXX/… (texty pro TTS)
  - tts/ → {téma}/{jazyk}/epXX/… .mp3
  - export/ → finální balíčky (plán)

Poznámka: dříve se někde vytvářela cesta s opakovaným ".../narration/.../epXX/narration/...". To bylo opraveno — generator i runner vytváří výstupy přímo do <outputs>/<module>/<topic>/<lang>/<ep>/. Zároveň jsme sjednotili pojmenování složky {téma} napříč moduly tak, aby odpovídala názvu v outline (s diakritikou). Legacy složky se slug názvy jsou nadále čitelné (GUI/CLI používají resolver, který mapuje outline název na slug i zpět).

## Env proměnné (priorita)
- NC_OUTPUTS_ROOT … kořen outputs/
- OUTLINE_OUTPUT_ROOT, PROMPTS_OUTPUT_ROOT, NARRATION_OUTPUT_ROOT, POSTPROC_OUTPUT_ROOT, TTS_OUTPUT_ROOT
- Priorita: konkrétní OUTPUT_ROOT pro modul > NC_OUTPUTS_ROOT/<module> > fallback na původní cesty v modulu.

## Subprocess kontrakt (pro GUI)
- CLI
  - -v/-vv zvyšuje verbosity (INFO/DEBUG).
  - Výstup na stdout/stderr v UTF-8.
- Exit codes
  - 0 OK
  - 2 validation/config/input error
  - 3 API error (OpenAI/Anthropic/HTTP)
  - 4 file I/O error
  - 5 unexpected error
- Logování
  - structlog (dev renderer pro konzoli), úrovně dle -v.
  - Jedna řádka = jeden log event; tracebacky pouze při kritických chybách.
- I/O
  - Vše v UTF-8.
  - Cache používá JSON (ne pickle) + integrita (SHA-256 hash pro klíče).
- Bezpečnost
  - Žádné klíče v repu; .env v .gitignore; .env.example s placeholdery.

## Technologie
- Python 3.11+
- Pydantic (modely/validace), structlog (logování), backoff (retry), python-dotenv (.env)
- OpenAI (AsyncOpenAI), Anthropic (Claude), httpx (timeout/pooled klient), jsonschema (validace JSON)
- ElevenLabs SDK v2 (text_to_speech.convert, VoiceSettings, speed)
- PySide6 (GUI)
- pytest/pytest-asyncio

## Stav (hotovo vs zbývá)
Hotovo:
- outline-generator revidován (PEP8/typing/UTF-8/logging/exit codes/caching JSON+hash/timeout) + vylepšení.
- Centralizace výstupů do outputs/ a odstranění duplicitního 'narration' v cestách.
- B_core/generate_prompts.py vylepšen (CLI parametry, logging, bezpečné mazání výstupu).
- GUI (PySide6) – Studio GUI plně funkční v základních částech:
  - Project tab: nastavení NC_OUTPUTS_ROOT (QSettings).
  - Outline tab: konfigurace a spuštění outline-generatoru jako subprocess.
  - Prompts tab: spuštění generate_prompts a stream logů.
  - Narration tab: indexování prompts, seznam epizod, poslání jednoho promptu (--prompt-file) nebo celé epizody, stream logů, Cancel/Terminate.
- Subprocess orchestrace (QProcess wrapper) a non-interactive runner (claude_generator/runner_cli.py) upraveny tak, aby zapisovaly výstupy přímo do <outputs_root>/<topic>/<lang>/<ep>/.
- Základní unit testy a utility (cache, sanitize_path) přidány a zelené.

Zbývá (priorita):
- Post-process tab — preview před/po + spuštění postprocess modulu (historical_processor) a možnost aplikace změn před TTS.
- TTS tab (ElevenLabs) — UI pro výběr textů, hlas/rychlost, preview, batch run s concurrency a backoff.
- Export tab — balíčkování do outputs/export (ZIP s manifest.json obsahujícím sha256 checksumy) a "Open package folder".
- Retry-fine control v Narration: per-segment status view, "Retry selected segment" (via --prompt-file), a "Retry failed only" batch.
- Tests & CI: přidat unit tests pro SubprocessController, fs_index a runner_cli s mocky; GitHub Actions workflow.

## Shrnutí cíle
Dodat stabilní, bezpečnou a přehlednou orchestraci samostatných modulů s jednotnou strukturou výstupů a jedním GUI, bez změny formátu produkovaných souborů. Zvláštní důraz nyní: odstranění duplicitních podsložek v cestách k výstupům a konzistence mezi generátorem a GUI.

## Recent changes (2025-10-11)
- claude_generator hardening:
  - Přidáno _strip_code_fences() — odstranění markdown code fences před YAML parsingem (řeší YAML parse chyby).
  - Debug logging: PROMPT_FILES (exec path + short hash) a SENT PROMPT TRUNC (first ~800 chars) logují, co se skutečně posílá do API.
  - Lightweight topic sanity check — varování pokud se v promptu nezmiňuje series title.
  - Forced-retry prefix: při retry (attempt >1) se před prompt přidá přísné „ONLY write about <series>..." aby se snížil model drift.
  - Fix-template augmentation: při retry se automaticky doplňuje instrukce "Ensure the output meets the full target word count. Extend narrative depth where needed." aby model generoval dostatečně dlouhý text.
  - Cache policy změny: ukládáme do cache pouze validní (success=True) výsledky; při čtení cache se validace proti target_words (pokud dostupné) aby se zabránilo použití příliš krátkých výstupů.
  - Zvýšení timeouts: httpx Client a AsyncClient timeout na 180s (read) a connect=20s; RATE_LIMIT_DELAY default 3s (env override možný).
  - Diagnostika truncation: logujeme elapsed a (pokud SDK poskytne) finish_reason a flag truncated — pomáhá ladit, zda model skončil dříve.

- Cache / nástroje:
  - Přidány skripty v scripts/:
    - inspect_cache.py — vypíše .cache/segments obsah + snippet (pro audit).
    - clean_bad_cache.py — jednoduché filtrování a smazání podezřelých cache záznamů (např. obsahuje "silk road").
    - invalidate_cache_series.py — invalidace cache pro konkrétní series/lang podle promptů.
  - Při troubleshootingu byly automaticky odstraněny tři nevhodné cache záznamy obsahující cizí téma.

- GUI a orchestrace:
  - PostProcess tab: preview (dry-run), Apply, run-episode / run-selected segments, retry failed only, concurrency control — orchestrace přes subprocess (QProcess wrapper).
  - Subprocess kontrakt respektován; runner_cli a qprocess wrapper streamují logy zpět do GUI.

- CLI / runner:
  - historical_processor/runner_cli.py — non-interactive postprocess runner s --dry-run, --preset, --rules, --concurrency.
  - claude_generator/runner_cli.py — non-interactive narration runner, nyní s DEBUG logging a lepším chováním cache/retry.

- Testy a CI:
  - Přidány unit tests: tests/test_claude_fixes.py (strip fences), tests/test_runner_cli.py (runner_cli dry-run/process_file).
  - Lokální pytest prošel zeleně (smoke tests).

- Konfigurace / bezpečnost:
  - Config fallback rules: priorita PROMPTS_INPUT_PATH / NC_OUTPUTS_ROOT; přidány doporučené env variables (NC_OUTPUTS_ROOT, PROMPTS_INPUT_PATH) a .env usage.
  - SecureCredentialManager.get_api_key používá keyring fallback + env; žádné klíče v repu.
  - sanitize_path striktně validuje zapisování pouze do povolených kořenů.

## Jak diagnostikovat problém s generováním (rychlý checklist)
1. V shellu nastav NC_OUTPUTS_ROOT a PROMPTS_INPUT_PATH (platí jen pro aktuální relaci):
   $env:NC_OUTPUTS_ROOT = 'D:\NightChroniclesStudio\outputs'
   $env:PROMPTS_INPUT_PATH = 'D:\NightChroniclesStudio\outputs\prompts'
2. Spusť runner pro konkrétní prompt:
   python claude_generator/runner_cli.py --prompt-file outputs/prompts/<series>/<lang>/<ep>/prompts/msp_01_execution.txt
3. Najdi poslední generation log a vytáhni auditorní řádky:
   $f = Get-ChildItem -Path . -Filter "generation_*.log" -Recurse | Sort-Object LastWriteTime -Descending | Select-Object -First 1
   Get-Content $f.FullName | Select-String -Pattern "PROMPT_FILES","SENT PROMPT TRUNC" -Context 10,10
4. Kontroluj:
   - PROMPT_FILES -> správný exec soubor
   - SENT PROMPT TRUNC -> prvních ~800 znaků promptu, existence forced prefixu a extra_instruction
   - API elapsed a finish_reason (loguje se jako DEBUG)
   - Pokud vidíš "Response likely truncated" nebo finish_reason obsahuje "max", zvaž zvýšení timeoutu nebo rozdělení promptu.

## Doporučené další kroky
- Přidat CI job (GH Actions) s ruff/black/mypy/pytest a pre-commit hooks.
- Dodat TTS tab (ElevenLabs) s preview a batch run s concurrency/backoff.
- Přidat vizuální diff v PostProcess tab (source vs preview) a možnost rollbacku.
- Zavést per‑run manifest/log (outputs/logs/manifest.json) se záznamy prompt_hash -> request_id -> elapsed -> finish_reason pro historickou analýzu.

Recent changes (2025-10-16)
- GUI: Project tab — "Rescan outputs" (progress bar, cancel, BG scanning), indexy se ukládají do studio_gui/.tmp (prompts_index.json, narration_index.json).
- fs_index: scan_prompts_root / scan_narration_root — podpora cancel (threading.Event) a progress callback; helpery save/load index.
- GUI: Prompts/Narration/PostProcess tably preferují cached indexy (.tmp) a podporují set_prompt_index()/set_narration_index() pro programmatic refresh.
- GUI Narration: přidán resolver názvu tématu (NFKD/slug matching) + robustnější práce s cestami.
- Runner/CLI (narration): claude_generator/runner_cli.py — resolver názvu tématu + robustní paths.
- Prompts generator: B_core/generate_prompts.py zapisuje do outputs/prompts/<exact outline topic name>/<lang>/… (sjednoceno s outline).
- Monorepo requirements: requirements-all*.txt a instalační skripty.
- Orchestrace: qprocess_runner parsed_log signal, buffering, timeout/terminate; process_runner timeout/cancel.
- Security & config: claude_generator/.env.example, .gitignore, structlog v requirements.

Recent changes (2025-10-17) — GUI hardening + persist
- QSettings scope: přidán OrganizationName/ApplicationName; Project tab nyní po startu přečte uložený NC_OUTPUTS_ROOT, nebo (pokud chybí) adoptuje env a uloží do QSettings. Po restartu GUI tak není nutné ručně nastavovat env.
- Narration tab: opravy auto‑výběru a signálů
  - Po refresh_topics se automaticky vybere první topic a zavolá on_topic_changed(sel).
  - Přidán „force populate from index“: pokud signály UI neběží, jazyk a epizody se naplní přímo z narration_index.json (bez on_topic_changed).
  - Po addItems(langs) se explicitně volá setCurrentIndex(0); populate_episodes má fallback, pokud currentText() vrátí prázdný string (vezme itemText(0)).
  - Debug logy do studio_gui/.tmp/narration_debug.log: refresh_topics i on_topic_changed; LogPane hlásí on_topic_changed a Languages resolved: [...].
- PostProcess tab: přidán minimální „force populate from index“ (bezpečné naplnění jazyků a epizod z indexu jako fallback).
- Deprecation fix: nahrazeno datetime.utcnow() -> timezone-aware datetime.now(datetime.UTC) v debug zápisech.
- Project tab Rescan: stav "Done" se ne vždy propisuje do labelu (UI kosmetika), ale indexy se ukládají; fix v dalším kroku (QTimer/queued signals).

Poznámka:
- Index persistence umožňuje rychlé UI refresh bez opakovaného skenování; rescan lze spustit manuálně z Project tab nebo zapnout automaticky (preference).
- Parsed JSON logs (structlog JSONRenderer) jsou streamovány z procesů a GUI je parsuje přes parsed_log signal — plánovaný parsed_log inspector panel (PostProcess/Project) je následující krok.

Pokud chceš, mohu tento soubor dále rozšířit o přesné seznamy změněných souborů, ukázkové příkazy pro lokální testování a krátký checklist pro deploy (rotace klíčů, commit .env removal, atd.).

---

Prepared context for next session (ready-to-use)

Co je ověřeno (E2E)
- End-to-end: Outline → Prompts → Narration je funkční (vygenerována osnova, prompty, a text z konkrétního promptu pro CS).
- GUI resolvery správně mapují názvy témat mezi outline a prompts/narration (diakritika vs slug).

Níže je stručné, ale konkrétní shrnutí stavu a kroků, které jsem přidal a které by měly umožnit plynulý další vývoj v příští session.

1) Hlavní upravené soubory (rychlý přehled)
- studio_gui/src/qprocess_runner.py — robustní QProcess wrapper (parsed_log signal, buffering, timeout, graceful terminate/kill).
- studio_gui/src/process_runner.py — async subprocess runner s timeout/cancel a bezpečným line-reading.
- studio_gui/src/main.py — Project/Prompts/Narration/PostProcess tably: Rescan outputs (progress + cancel), progress bar, cancel, persist index do studio_gui/.tmp, set_prompt_index/set_narration_index metody, integrace s qprocess wrapper.
- studio_gui/src/fs_index.py — scan_prompts_root / scan_narration_root s podporou progress callback a cancellation; save_index / load_index.
- claude_generator/runner_cli.py — safe structlog import, verbosity flags, typing fixes, robust runtime import.
- claude_generator/.env.example — bezpečný placeholder (.env > .gitignore).
- .gitignore — přidání ignore pravidel (včetně .env).
- requirements.txt — přidán structlog.

2) Lokální testy / smoke-check (krok‑po‑kroku)
- Aktivujte venv a nainstalujte dependencies:
  .venv\Scripts\activate   (Windows PowerShell)
  pip install -r requirements.txt
- Spusť GUI (smoke):
  python -m studio_gui.src.main
- V Project tab: vyberte NC_OUTPUTS_ROOT nebo použijte defaulty, klikněte Rescan outputs;
  - Sledujte progress bar a LogPane; po dokončení zkontrolujte studio_gui/.tmp/prompts_index.json a narration_index.json
- Ověřte v Prompts/Narration: rychlé načtení témat z cache a správné zobrazení epizod/segmentů.
- Spusť sample runner (bez API) pro integraci logů:
  python claude_generator/runner_cli.py --prompt-file outputs/prompts/<series>/<lang>/<ep>/prompts/msp_01_execution.txt
  - Sledujte streamované structlog JSON eventy v GUI logu (parsed_log -> JSON строки).

3) Bezpečnostní checklist (nutné provést pokud .env obsahoval klíče)
- Nepřidávat skutečný claude_generator/.env do repa; lokálně:
  move claude_generator/.env C:\secure\path\ or Remove-Item
- Rotujte klíče pokud byly commitnuté/pushnuté do remote.
- Pokud byl .env pushnut, použijte git filter-repo nebo BFG a koordinujte s týmem.

4) Co je nejdůležitější dělat dál (priority next session)
- Dovršit PostProcess tab (priorita):
  - Diff viewer (source vs preview) — minimálně difflib.HtmlDiff; později side-by-side s barevným zvýrazněním.
  - Apply/rollback do outputs/postprocess/<téma>/<jazyk>/<ep>/… + meta JSON (source_path, SHA-256, timestamp, processor_version).
  - Per-segment run / Retry failed only + stabilnější stavové přechody a log parsing.
  - (Volitelné) ParsedLog inspector panel pro JSON události (Project/PostProcess).
- TTS tab (ElevenLabs): selection UI, preview, batch run s concurrency/backoff.
- CI & testy: unit testy pro qprocess_runner, process_runner, fs_index, runner_cli + GH Actions workflow.

5) Jak mě v příští session rychle obnovit (pro vás)
- Ujistěte se, že NC_OUTPUTS_ROOT je správně nastaven nebo že outputs/ existuje v repo root.
- Otevřete GUI a spusťte Rescan outputs (rychlé ověření indexu).
- Pokud chcete pokračovat v konkrétním úkolu napište: "pokračuj: parsed_log" nebo "pokračuj: postprocess diff" — hned navážu.

---

Tento dodatek jsem přidal přímo do nightchronicles_context.md, takže při další session budu schopný rychle načíst stav projektu, indexy (.tmp) a pokračovat v práci přesně tam, kde jsme skončili.

---

Next-session quickstart (co udělat okamžitě po otevření repozitáře)
- Otevři projekt root v IDE a aktivuj venv:
  - Windows PowerShell: .\.venv\Scripts\Activate.ps1
  - nebo: .\.venv\Scripts\activate
- Ověř závislosti (pokud chybí):
  .\.venv\Scripts\python.exe -m pip install -r outline-generator\requirements.txt
  nebo pro celé repo (pokud máš centralní requirements): pip install -r requirements.txt
- Nastav environment proměnné pro lokální testování (přepni cesty podle potřeby):
  $env:NC_OUTPUTS_ROOT = 'D:\NightChroniclesStudio\outputs'
  $env:OUTLINE_OUTPUT_ROOT = "$env:NC_OUTPUTS_ROOT\outline"
- Rychlý parse check hlavního PS skriptu (volitelně):
  $s = Get-Content -Raw -LiteralPath 'scripts/rescan_and_check.ps1'; [scriptblock]::Create($s) | Out-Null; Write-Output 'PARSE_OK'

Co zkontrolovat jako první (stav projektu)
1) studio_gui/.tmp — indexy a outline_config_gui.json
   - Get-ChildItem .\studio_gui\.tmp -File | Format-Table Name,Length,LastWriteTime
   - Validace JSON: python -c "import json; json.load(open('studio_gui/.tmp/outline_config_gui.json'))" && echo OK
2) outline-generator dry-run (ověřit šablonu a config):
   .\.venv\Scripts\python.exe outline-generator\generate_outline.py -c studio_gui\.tmp\outline_config_gui.json -t outline-generator\templates\outline_master.txt --dry-run -v
3) GUI smoke: spustit Studio GUI (pokud chcete UI):
   .\.venv\Scripts\python.exe -m studio_gui.src.main
   - V Project tab stisknout Rescan outputs a kontrolovat log pane a .tmp indexy

Kde pokračovat (prioritní úkoly, krůček po krůčku)
- Priority A (bezprostřední):
  1. Dokončit PostProcess tab: implementovat unified diff viewer (source vs postprocessed) + Apply/rollback, per-segment retry.
     - Hledat: studio_gui/src/tabs/postprocess_* a historical_processor/runner_cli.py
  2. Dodat TTS tab (ElevenLabs): selection UI, preview, batch run s concurrency+backoff.
     - Hledat: studio_gui/src/tts_tab.py (nebo vytvořit nový) a tts runner v tts/ nebo integrační wrapper.
  3. Přidat unit testy + CI job pro subprocess orchestrace a fs_index.
     - Testy umístit do tests/ a GH Actions workflow v .github/workflows/ci.yml

- Priority B (vylepšení/údržba):
  1. Přidat parsed_log inspector panel pro zobrazení a filtrování streamovaných JSON log událostí.
  2. Dokončit Export tab: ZIP + manifest.json (sha256) + Open folder.
  3. Rozšířit runner_cli mock/no-API režim pro lokální dev bez API klíčů.

Konkrétní checklist pro následující session (GUI stability + PostProcess)
- [ ] Narration tab: sjednotit načítání jazyků/epizod — vždy použít index key z narration_index.json (bez závislosti na combobox signálech); přidat unit test (index → UI list) a manuální smoke.
- [ ] Narration tab: doplnit explicitní volání setCurrentIndex(0) i pro Topic combo po addItems() a QTimer.singleShot(0, ...) na on_topic_changed(sel) (zajištění běhu v hlavním threadu).
- [ ] Project tab: opravit přepnutí stavu labelu na "Done" po rescan (queued connection/ensure main thread).
- [ ] PostProcess: implementovat diff preview (difflib.HtmlDiff) ve split view (source/preview) + uložit Apply s meta (SHA256, source_path, timestamp, processor_version).
- [ ] Připravit PR: feature/gui-stability-narration + feature/gui-postprocess-diff; přidat unit testy (fs_index → UI, qprocess_runner) a GH Actions workflow.

Důležité soubory a trasy (rychlá reference)
- GUI: studio_gui/src/main.py, studio_gui/src/qprocess_runner.py, studio_gui/src/process_runner.py, studio_gui/src/fs_index.py
- Outline generator: outline-generator/generate_outline.py, outline-generator/src/generator.py, outline-generator/templates/outline_master.txt
- Prompts: B_core/generate_prompts.py (výstupy do outputs/prompts/<exact_topic_name>/...)
- Narration/claude: claude_generator/runner_cli.py, claude_generator/src/...
- Postprocess: historical_processor/runner_cli.py, historical_processor/src/...
- Scripts: scripts/rescan_and_check.ps1, scripts/inspect_cache.py, scripts/clean_bad_cache.py, scripts/install_all_requirements.ps1/.sh

Dev / deploy zásady (zabezpečení + CI)
- Žádné tajné klíče v repu. .env files jsou v .gitignore; vždy používat .env.example jako šablonu.
- Pokud se zjistí, že byl klíč commitnutý, rotovat klíč a použít git filter-repo/BFG pro odstranění historie.
- CI pipeline minimálně spouštět: ruff/black, mypy, pytest; označit integrational tests jako workflow-run-with-secrets (cron nebo manual).

Protokol změn / co evidovat v PR
- Shrnutí funkcionality: co se mění (skripty, GUI, runner), kde jsou dopady na výstupní strukturu, body kompatibility.
- Testy: co bylo přidáno / co je potřeba přidat.
- Jak spustit lokálně (krátký návod v PR popisu).

Kontakt a kontext
- Pokud se narazí na chybné indexy, první krok: spustit scripts/rescan_and_check.ps1 (nebo v PowerShellu použít .\.venv\Scripts\python.exe scripts/rescan_and_check.ps1?) a zkontrolovat studio_gui/.tmp/*.json
- Při problémech s API: zkontrolovat outline-generator/.env a environment proměnné (OPENAI_API_KEY / ANTHROPIC_API_KEY); pokud chybí, použít mock/no-API režim nebo dry-run.

Poznámka pro dalšího developera (co očekávám po návratu)
- Chci vidět small, focused PR s jedním major úkolem (např. postprocess diff nebo TTS tab). PR by měl obsahovat:
  - změny kódu (moduly + GUI) < 400 LOC preferovaně
  - jednotkové testy pro novou funkcionalitu
  - krok za krokem jak to lokálně spustit (README snippet)

---

Tento rozšířený kontext je nyní součástí nightchronicles_context.md a měl by umožnit hladký start v příští session — okamžitě víme, kde hledat, jak spustit lokálně a jaké priority řešit.

---

Aktualizace pro další session (2025-10-17)
- Stav: připraveno pokračovat na PostProcess diff viewer a TTS tab. Indexy jsou v studio_gui/.tmp.
- Co udělat při startu:
  1) Otevřít IDE v rootu repa.
  2) Aktivovat projektový venv a nainstalovat závislosti: pip install -r requirements.txt
  3) Nastavit NC_OUTPUTS_ROOT (např. export NC_OUTPUTS_ROOT=./outputs).
  4) Spustit GUI: python -m studio_gui.src.main a v Project tab spustit Rescan outputs.
- Rychlý prioritní plán na příští session:
  A) PostProcess diff viewer: implementovat HtmlDiff-based preview, tlačítka Preview/Apply/Rollback, integrity meta (SHA-256).
  B) TTS tab: UI pro výběr segmentů, výběr hlasu/rychlosti, preview single segment, batch run s concurrency a backoff.
  C) Unit tests: přidat testy pro postprocess runner, qprocess_runner a fs_index; přidat CI job.
- Očekávané výstupy po session:
  - Funkční PostProcess tab s možností preview a apply + per-segment retry.
  - TTS tab umožňující preview a dávkové zpracování s robustním backoffem.
  - Min. 5 unit testů pokrývajících klíčové části orchestrace.

Poznámky k implementaci
- Při ukládání apply vždy generovat meta JSON s fields: source_path, result_path, sha256_source, sha256_result, timestamp, processor_version.
- TTS runner musí podporovat --concurrency a exponential backoff (backoff package) a použít ElevenLabs SDK v non-blocking režimu (thread/async wrapper). Logovat parsed JSON events.
- PostProcess a TTS runnery volat jako subprocess (QProcess/async runner) a streamovat structlog JSON events do GUI (parsed_log signal).

Další kroky
- Pokud souhlasíš, mohu okamžitě implementovat PostProcess diff viewer (vytvořit studio_gui/src/tabs/postprocess_diff.py) a přidat odpovídající unit testy.
- Alternativně můžu začít TTS tab (studio_gui/src/tabs/tts_tab.py) — napiš, co preferuješ.

---

Tento soubor jsem aktualizoval 2025-10-17, připraveno pro další session.

Rekapitulace (stav k 2025-10-17)
- Hotovo (klíčové body):
  - Outline generator: revisited, PEP8/typing, JSON cache + integrity, zvýšené timeouty.
  - Prompts generator: výstupy zapisují do sjednoceného outputs/prompts/<exact_topic_name>/…; metadata zachovány.
  - Narration runner (claude_generator): robustní runner_cli, cache policy, strip fences, forced-retry augmentation, resolver názvu tématu.
  - GUI (studio_gui): základní tably (Project/Outline/Prompts/Narration) funkční; Rescan outputs s persistencí indexů (studio_gui/.tmp); qprocess_runner a async process_runner pro streamované structlog JSON události.
  - Subprocess kontrakt a log streaming: structlog JSONRenderer, parsed_log signal, buffering a safe terminate.
  - Utility / scripts: inspect_cache.py, clean_bad_cache.py, invalidate_cache_series.py.
  - Základní unit testy: strip fences, runner_cli dry-run; lokální pytest prošel.

- Zbývá (priorita):
  A) PostProcess tab
    - Implementovat diff preview (HtmlDiff), Preview/Apply/Rollback, meta (SHA-256) pro applied results.
    - Spouštění historical_processor jako subprocess s dry-run/commit režimy a per-segment retry.
  B) TTS tab (ElevenLabs)
    - UI pro výběr segmentů, hlas/rychlost, preview; batch run s concurrency a exponential backoff.
  C) Export tab
    - ZIP packaging + manifest.json (sha256 checksums) a možnost otevřít výstupní složku.
  D) Tests & CI
    - Unit tests pro qprocess_runner, process_runner, fs_index; přidat GH Actions job (ruff/black/mypy/pytest).
  E) Retry control v Narration
    - Per-segment status view, Retry selected segment, Retry failed only.

- Okamžité kroky pro příští session (konkrétní):
  1) Implementovat PostProcess diff viewer (studio_gui/src/tabs/postprocess_diff.py) + unit test(s) pro diff renderer.
  2) Přidat tlačítka Preview/Apply/Rollback v GUI a zajistit, že Apply vytváří meta JSON (source_path, result_path, sha256_source, sha256_result, timestamp, processor_version).
  3) Zapracovat TTS runner skeleton (CLI podporující --concurrency, backoff) a jednoduché UI pro preview jednoho segmentu.
  4) Přidat minimálně 3 unit testy pro qprocess_runner a fs_index a nakonfigurovat základní GH Actions workflow.

- Rychlý start (co udělat lokálně):
  - Aktivovat venv a nainstalovat deps: pip install -r requirements.txt
  - Nastavit NC_OUTPUTS_ROOT (např. export NC_OUTPUTS_ROOT=./outputs)
  - Spustit GUI a Rescan outputs: python -m studio_gui.src.main -> Project tab -> Rescan outputs
  - Spustit sample runner (dry-run): python claude_generator/runner_cli.py --prompt-file outputs/prompts/<series>/<lang>/<ep>/prompts/msp_01_execution.txt

- Doporučení pro PR/CI:
  - Dělit změny do malých PR (feature: postprocess-diff, feature: tts-tab). Každý PR s 1–2 unit testy a instrukcí k lokálnímu spuštění.
  - Přidat pre-commit + GH Actions job: ruff, black, mypy (typové kontroly) a pytest (smoke tests).

---




Recent changes (2025-10-17 � late) � NarrationTab fixes + entrypoint + stability
- GUI NarrationTab:
  - Added Segments list (lst_segments) and status map to track per-segment processing.
  - Replaced legacy _last_index usage with proper _prompt_index/_narration_index + normalized topic matching via _find_index_topic.
  - Added _resolve_topic_dir for case/diacritics-insensitive mapping.
  - Fixed auto-population flow: after refresh_topics(), on_topic_changed() is triggered via QTimer.singleShot(0, ...) and Topic combo auto-selects first item when empty.
  - Fixed timezone in debug logs: datetime.now(timezone.utc) used consistently.
  - populate_episodes(): normalized key lookup also for prompts index; better fallback logic.
- PromptsTab: removed duplicate set_prompt_index definition.
- PostProcessTab:
  - Removed duplicate prompts_root; added osnova_root().
  - Temporarily added stub methods (run_selected_segments, retry_failed_only, run_episode_merged, apply_current, _on_process_finished, open_output_folder/open_merged_file/open_manifest) � will be replaced by full implementation.
- Entry point:
  - Added MainWindow and main() with QSettings scope: QCoreApplication.setOrganizationName( NightChronicles), QCoreApplication.setApplicationName(StudioGUI).
- Build: studio_gui/src/main.py compile check (py_compile) passes.

Impact
- Narration tab now loads Languages and Episodes automatically after Topics; UI state is consistent even bez ru�n� interakce.
- Project tab persistence remains (QSettings). Rescan outputs propaguje indexy do tabs (set_prompt_index/set_narration_index), NarrationTab pracuje i bez index� (fallback FS scan).

Known limitations / follow-ups
- PostProcessTab metody jsou zat�m stuby � implementovat diff viewer, Apply/Rollback, episode runner.
- NarrationTab.refresh_topics preferuje topics z prompts indexu (prompts_index.json). Do budoucna zv�it preferenci narration_index.json (u�ivatelsky l�pe odpov�d� hotov�m v�stup�m).

Next-session plan (aktualizov�no)
A) PostProcess tab (priorita):
- Implementovat HtmlDiff-based preview + side-by-side view.
- Apply+meta JSON (source_path, result_path, sha256_source/result, timestamp UTC, processor_version) a Rollback.
- Orchestrace historical_processor (dry-run/commit), per-segment run a retry failed only.

B) TTS tab (ElevenLabs):
- UI pro v�b�r segment� (podle postprocess v�stup�), nastaven� hlasu/rychlosti, preview, batch run s concurrency/backoff.

C) Stabilita + testy:
- Unit testy: NarrationTab (index � UI, auto-select, normalized matching), qprocess_runner, fs_index.
- GH Actions: ruff/black/mypy/pytest (smoke), s matrix pro win32/x64.

Quick smoke (GUI)
- pip install -r requirements.txt
- Set-Item Env:NC_OUTPUTS_ROOT (nebo vybrat v Project tab)
- python -m studio_gui.src.main � Project: Rescan outputs � Narration: zkontrolovat Topics � Languages � Episodes (auto-populated)

Troubleshooting (Narration)
- Pokud se Languages/episodes nenapln�: zkontroluj studio_gui/.tmp/*index.json, p��padn� spus� Rescan outputs (Project tab).
- U t�mat s diakritikou ov��, �e slo�ky v outputs odpov�daj� outline n�zvu (resolver NFKD/slug funguje v GUI i runneru).

