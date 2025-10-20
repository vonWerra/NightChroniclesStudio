---
description: A description of your rule
---

# NightChronicles – Project Context (for Continue in VS Code)

## Cíl (stručně)
- Zrevidovat a **opravit kód** ve všech původních souborech ze ZIPu (odstranit nepřesnosti, sjednotit styl, bezpečnost).
- **Optimalizovat** programy podle platných standardů (PEP8, typing, logging, konfigurace, struktura balíčků).
- Postavit **společné desktop GUI (PySide6/Qt)** se **společným menu** a **kartami (tabs)**,
  kde **každý modul běží samostatně** (nezávisle) jako vlastní proces.
- **Neměnit** formáty výstupů modulů – vše **zůstává samostatné**; GUI jen orchestrace a jednotné ovládání.
- **Jazyky**: uživatel si v GUI **zaškrtávacími políčky** volí z 5 jazyků (CS, EN, DE, ES, FR) pro daný krok (např. osnova).
- **TTS (ElevenLabs)**: uživatel **vybere, které výstupy** převést na řeč; možné je dávkové i selektivní zpracování.

## Princip (nezávislé moduly + společné GUI)
- Každá stávající aplikace = **modul**, běží **nezávisle** (vlastní venv klidně zvlášť).
- GUI (PySide6/Qt) je **jen orchestrátor**: spouští moduly jako **subprocess**, hlídá stav, zobrazuje logy.
- **Vstup** každého kroku = data uložená **předchozím krokem** do společné projektové složky.
- **Výstup** každého kroku = zapisuje **jen do své části** sjednocené složky.
- **Formáty výstupu** modulů **se nemění** (zůstávají tak, jak je modul produkuje).

## UX (tabs)
1. **Project** – výběr Project Root, obecná nastavení, test klíčů.
2. **Outline** – generování/úprava osnovy; **výběr jazyků (CS/EN/DE/ES/FR)** přes checkboxy.
3. **Prompts** – generování promptů z osnovy + šablon; přehled souborů.
4. **Narration** – generování textů; stav segmentů, **Retry failed only**.
5. **Post-process** – přepis zkratek, roky číslem→slovem, intro/přechody; náhled před/po.
6. **TTS (ElevenLabs)** – **výběr, které výstupy převést**; výběr hlasu/rychlosti; preview; batch run.
7. **Export** – balíčky (ZIP), otevřít složku, přehled.

## Sjednocená projektová struktura
