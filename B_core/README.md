# B_core – Prompt Generator

**Module:** Prompt generation from outline  
**Status:** ✅ Production-ready (v2.0)  
**Last Updated:** 2024-01-21

---

## Purpose

Generates detailed Claude prompts from `osnova.json` files produced by `outline-generator`.

**Input:** `outputs/outline/<topic>/<lang>/osnova.json`  
**Output:** `outputs/prompts/<topic>/<lang>/ep01..epNN/prompts/*.txt`

---

## Quick Start

### Basic Usage

```bash
# Interactive mode (asks for topic and language)
python generate_prompts.py

# CLI mode (specify topic and language)
python generate_prompts.py --topic "Industrial Revolution" --language CS

# With overwrite flag (skip confirmation)
python generate_prompts.py --topic "Napoleon" --language EN -y

# Verbose mode (show detailed logging)
python generate_prompts.py --topic "WW2" --language DE -v
```

---

## Command-Line Arguments

```
--topic TEXT              Topic folder name (case-insensitive)
--language {CS,EN,DE,ES,FR}  Language code
--yes, -y                 Overwrite existing output without asking
--outline-root PATH       Override input outline root
--prompts-root PATH       Override output prompts root
-v, --verbose             Increase verbosity (-v INFO, -vv DEBUG)
```

---

## Environment Variables

```bash
# Unified outputs root (recommended)
export NC_OUTPUTS_ROOT=/path/to/outputs

# Or specific roots (if needed)
export OUTLINE_OUTPUT_ROOT=/path/to/outputs/outline
export PROMPTS_OUTPUT_ROOT=/path/to/outputs/prompts
```

**Default behavior (if not set):**
- Outline input: `outline-generator/output`
- Prompts output: `B_core/outputs`

---

## Output Structure

```
outputs/prompts/
└── <topic>/
    └── <lang>/
        ├── ep01/
        │   ├── prompts/
        │   │   ├── msp_01_execution.txt      # Segment 1 prompt
        │   │   ├── msp_01_fix_template.txt   # Fix instructions
        │   │   ├── msp_02_execution.txt
        │   │   ├── ...
        │   │   └── fusion_instructions.txt   # Episode fusion prompt
        │   └── meta/
        │       ├── episode_context.json      # Structured episode data
        │       ├── params.json               # Copy of config
        │       ├── handoff_phrases.json      # Copy of phrases
        │       └── fusion_prompt.txt         # Copy of template
        ├── ep02/
        │   └── ...
        └── ...
```

---

## Configuration Files

### `config/params.json`

```json
{
  "numbers_style": "digits_for_years",
  "wpm": 145,
  "word_tolerance_percent": 3,
  "tts_pause_seconds_between_segments": 0.7,
  "merge_text_after_segments": false
}
```

**Parameters:**
- `numbers_style` – How to format numbers in narration (e.g., "1914" vs "nineteen fourteen")
- `wpm` – Words per minute for timing calculations
- `word_tolerance_percent` – Allowed variance in word count (±3%)
- `tts_pause_seconds_between_segments` – Pause duration between segments
- `merge_text_after_segments` – Whether to concatenate segments (not used currently)

### `config/handoff_phrases.json`

Transition phrases for smooth segment stitching (used by fusion stage).

### `templates/segment_prompt.txt`

Master template for Claude execution prompts. Placeholders:
- `{LANG}` – Target language code
- `{SERIES_TITLE}` – Series title
- `{EPISODE_NUMBER}` – Episode number
- `{MSP_LABEL}` – Segment focus
- `{WORD_TARGET}` – Target word count
- `{SOURCES_SEGMENT}` – Relevant sources
- etc.

---

## Recent Changes (v2.0)

### ✅ Fixed in v2.0

1. **Robust MSP parsing** – handles various osnova.json formats
2. **Removed hard-coded language** – config is now language-agnostic
3. **Cleaned up obsolete code** – removed unused `CANON_BLOCK` feature

**Details:** See [CHANGELOG_v2.0.md](CHANGELOG_v2.0.md) and [FIXES_SUMMARY.md](FIXES_SUMMARY.md)

---

## Testing

Run unit tests for MSP parsing:

```bash
python test_msp_parsing.py
```

**Expected output:**
```
============================================================
Results: 8 passed, 0 failed
============================================================
```

---

## Integration with NightChronicles Studio

**GUI Tab:** `Prompts`

**Workflow:**
1. User selects topic and language from dropdowns (populated from outline root)
2. Clicks "Run B_core/generate_prompts.py"
3. GUI spawns subprocess with correct arguments
4. Logs displayed in real-time
5. Output available in `outputs/prompts/<topic>/<lang>/`

**Next step:** Claude Generator consumes these prompts to generate narration.

---

## Troubleshooting

### "Topic not found"
- Ensure `outline-generator` has completed for this topic/language
- Check `NC_OUTPUTS_ROOT` or `OUTLINE_OUTPUT_ROOT` environment variable

### "Missing MSP label"
- Osnova.json has malformed episode data
- Run with `-vv` to see detailed error context
- Check [FIXES_SUMMARY.md](FIXES_SUMMARY.md) for supported MSP formats

### "Schema validation failed"
- Episode context doesn't match expected structure
- Update `config/episode_context.schema.json` if you changed the format
- Or fix the osnova.json data

---

## Dependencies

```bash
pip install jsonschema structlog
```

---

## Exit Codes

| Code | Meaning |
|------|---------|
| 0 | Success |
| 2 | Bad inputs (missing files, invalid data) |
| 3 | Schema validation failed |
| 4 | Prompt generation error |
| 5 | Unexpected error |

---

## See Also

- [nightchronicles_context.md](../nightchronicles_context.md) – Project overview
- [outline-generator/README.md](../outline-generator/README.md) – Previous step
- [claude_generator/README.md](../claude_generator/README.md) – Next step
