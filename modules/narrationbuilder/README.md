# narrationbuilder (NightChronicles module)

**Version:** 2.0
**Status:** ✅ Production Ready
**Last Updated:** 2024-01-21

---

## Purpose

Merge narration segments from `claude_generator` into a single cohesive final narrative using OpenAI GPT.

**Input:** Segments from `outputs/narration/<topic>/<lang>/epXX/segment_XX.txt`
**Output:** Final narrative in `outputs/final/<topic>/<lang>/episode_XX/episode_XX_final.txt`

---

## Quick Start

### CLI Usage

```bash
python -m narrationbuilder \
  --project-root /path/to/NightChroniclesStudio \
  --topic-id Napoleon \
  --episode-id 01 \
  --lang CS \
  --model gpt-4o
```

### With Custom Parameters

```bash
python -m narrationbuilder \
  --project-root . \
  --topic-id Industrial_Revolution \
  --episode-id 02 \
  --lang EN \
  --model gpt-4-turbo \
  --style "documentary, engaging, accessible" \
  --length-words "2000-2500" \
  --sentence-len "15-30 words"
```

### Dry Run (Build Prompt Only)

```bash
python -m narrationbuilder \
  --project-root . \
  --topic-id Napoleon \
  --episode-id 01 \
  --lang CS \
  --dry-run
```

---

## Environment Variables

### Required

```bash
export OPENAI_API_KEY="sk-..."
```

### Optional

```bash
# Model selection
export GPT_MODEL="gpt-4o"  # Default; alternatives: gpt-4-turbo, gpt-4

# Temperature (0.0-1.0)
export GPT_TEMPERATURE="0.4"  # Default

# Unified outputs root
export NC_OUTPUTS_ROOT="/path/to/outputs"

# Or specific paths
export NARRATION_OUTPUT_ROOT="/path/to/narration"  # Input segments
export FINAL_OUTPUT_ROOT="/path/to/final"          # Output final text
```

---

## Output Structure

```
outputs/final/
└── <topic>/
    └── <lang>/
        └── episode_XX/
            ├── episode_XX_final.txt    # Final narrative
            ├── prompt_pack.json         # System + user prompts
            ├── metrics.json             # Latency, tokens, validation
            └── status.json              # Success/failure status
```

---

## Features (v2.0)

### ✅ **Dynamic Segment Discovery**
Automatically finds all `segment_*.txt` files (not hard-coded to 1-5).

### ✅ **Robust Encoding**
Tries multiple encodings (UTF-8, UTF-8-sig, CP1250, Windows-1250, ISO-8859-2).

### ✅ **Environment-Based Paths**
Respects `NC_OUTPUTS_ROOT`, `NARRATION_OUTPUT_ROOT`, `FINAL_OUTPUT_ROOT`.

### ✅ **Output Validation**
- Word count check
- Language detection (Czech diacritics)
- Quality scoring (0.0-1.0)
- Warnings for issues

### ✅ **Smart Model Handling**
- Default: `gpt-4o` (fast, reliable)
- Fallback: `gpt-4-turbo` on error
- Auto-detects temperature support

### ✅ **Retry Logic**
Automatic retry (3 attempts) with exponential backoff.

---

## Recent Changes (v2.0)

### 🔴 **Critical Fixes**

1. **Dynamic segment loading**
   ❌ Old: Hard-coded 1-5 segments
   ✅ New: Discovers all segment_*.txt files

2. **Valid default model**
   ❌ Old: `"gpt-5"` (invalid)
   ✅ New: `"gpt-4o"` (valid, fast)

3. **Cross-platform paths**
   ❌ Old: Hard-coded `outputs/...`
   ✅ New: Respects `NC_OUTPUTS_ROOT`

4. **Robust encoding**
   ❌ Old: UTF-8 only with error replacement
   ✅ New: Multi-encoding fallback

5. **Output validation**
   ❌ Old: Only checks if empty
   ✅ New: Word count, language, quality score

**Details:** See [CHANGELOG_v2.0.md](CHANGELOG_v2.0.md)

---

## CLI Options

```
--project-root PATH       Path to project root (parent of outputs/)
--topic-id TEXT           Topic slug (e.g., "Napoleon")
--episode-id TEXT         Two-digit episode ID (e.g., "01")
--lang TEXT               Language: CS/EN/DE/ES/FR
--model TEXT              OpenAI model (default: gpt-4o)
--style TEXT              Narrative style (default: "historicko-dokumentarní...")
--length-words TEXT       Target word range (default: "1800-2200")
--sentence-len TEXT       Sentence length target (default: "20-30 slov")
--dry-run                 Build prompt only, no LLM call
```

---

## Exit Codes

| Code | Meaning |
|------|---------|
| 0 | Success |
| 2 | Invalid input (missing segments, bad paths) |
| 3 | Provider error (API failure) |
| 5 | Unexpected error |

---

## Integration with NightChronicles Studio

**GUI Tab:** `Final` (to be implemented)

**Workflow:**
1. User selects topic + language + episode
2. Clicks "Run Final (narrationbuilder)"
3. GUI spawns subprocess with correct paths
4. Logs displayed in real-time
5. Final text available in `outputs/final/`

---

## Troubleshooting

### "Segments directory not found"
- Ensure `claude_generator` has run for this topic/lang/episode
- Check `NARRATION_OUTPUT_ROOT` environment variable
- Verify path: `outputs/narration/<topic>/<lang>/epXX/`

### "Invalid API key"
- Set `OPENAI_API_KEY` environment variable
- Verify key at https://platform.openai.com/api-keys

### "Output too short/long"
- Adjust `--length-words` parameter
- Check segment count (need at least 3-5 segments)
- Review segment quality from `claude_generator`

### "Model not found"
- Update to valid model: `gpt-4o`, `gpt-4-turbo`, `gpt-4`
- Check OpenAI API access for selected model

---

## Dependencies

```bash
pip install -r requirements.txt
```

**Required:**
- `openai>=1.0.0` – OpenAI API client
- `typer>=0.9.0` – CLI framework
- `tenacity>=8.0.0` – Retry logic

---

## See Also

- [claude_generator/README.md](../../claude_generator/README.md) – Previous step (segment generation)
- [nightchronicles_context.md](../../nightchronicles_context.md) – Project overview

---

**Status:** ✅ Production Ready (v2.0)
