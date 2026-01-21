# Claude Generator – AI Narration Generator

**Module:** Narration text generation via Claude API  
**Status:** ✅ Production-ready (v2.0)  
**Model:** Claude Opus 4.5 (`claude-opus-4-20250514`)  
**Last Updated:** 2024-01-21

---

## Purpose

Generates high-quality historical narrative texts from prompts created by `B_core`.

**Input:** Prompts from `outputs/prompts/<topic>/<lang>/epXX/prompts/*.txt`  
**Output:** Narrative segments in `outputs/narration/<topic>/<lang>/epXX/segment_XX.txt`

---

## Quick Start

### **Interactive Mode**
```bash
python claude_generator/claude_generator.py
```
→ Menu lets you select series, language, and episodes

### **CLI Mode (for automation/GUI)**
```bash
python claude_generator/runner_cli.py \
  --topic "Napoleon" \
  --language CS \
  --episodes "ep01,ep02" \
  -v
```

### **Retry Only Failed Segments**
```bash
python claude_generator/runner_cli.py \
  --topic "Napoleon" \
  --language CS \
  --retry-failed
```

### **Process Single Prompt File**
```bash
python claude_generator/runner_cli.py \
  --prompt-file "outputs/prompts/Napoleon/CS/ep01/prompts/msp_01_execution.txt"
```

---

## Command-Line Arguments (runner_cli.py)

```
--topic TEXT              Topic name (e.g., "Napoleon")
--language {CS,EN,DE,ES,FR}  Language code
--episodes TEXT           Comma-separated episode names (e.g., "ep01,ep02")
--prompt-file PATH        Process single prompt file (absolute or relative)
--retry-failed            Only process incomplete episodes
-v, --verbose             Increase verbosity (-v INFO, -vv DEBUG)
```

---

## Environment Variables

```bash
# Required
export ANTHROPIC_API_KEY="sk-ant-..."

# Optional (with defaults)
export CLAUDE_MODEL="claude-opus-4-20250514"  # Model ID
export CLAUDE_TEMPERATURE="0.3"               # 0.0-1.0
export CLAUDE_MAX_TOKENS="8000"               # Max response length
export MAX_ATTEMPTS="3"                       # Retry attempts per segment
export WORD_TOLERANCE="3"                     # ±% word count tolerance
export RATE_LIMIT_DELAY="3.0"                 # Seconds between API calls

# Paths (unified structure recommended)
export NC_OUTPUTS_ROOT="/path/to/outputs"    # Unified root
# OR specific overrides:
export PROMPTS_INPUT_PATH="/custom/prompts"
export NARRATION_OUTPUT_ROOT="/custom/narration"

# Features
export MAX_PARALLEL_SEGMENTS="3"              # Parallel segment processing
export MAX_PARALLEL_EPISODES="2"              # Parallel episode processing
```

---

## Output Structure

```
outputs/narration/
└── <topic>/
    └── <lang>/
        └── epXX/
            ├── segment_01.txt           # Generated narrative
            ├── segment_02.txt
            ├── ...
            ├── fusion_result.txt        # Merged episode text (optional)
            └── generation_log.json      # Metadata + metrics
```

---

## Features

### **1. Smart Generation with Validation**
- Sends prompts to Claude Opus 4.5
- Parses YAML validation from response
- Checks:
  - Word count (±3% tolerance)
  - Opening hook present
  - Closing handoff present
  - **Topic relevance** (new in v2.0)
- Auto-retry up to 3 times if validation fails

### **2. Topic Drift Detection** 🆕
Ensures generated text is about the correct topic:
```
Series: "Napoleon"
Keywords: ["napoleon", "bonaparte"]

Generated text: "Julius Caesar conquered Gaul..."
→ ❌ REJECTED (off-topic, missing keywords)
→ Retry with strict topic instruction
```

### **3. Auto-Retry with Increased Tokens** 🆕
When response is truncated:
```
Attempt 1: max_tokens=8000 → truncated
Attempt 2: max_tokens=9600 (+20%) → success
```

### **4. Advanced Caching**
- Stores successful generations in `.cache/segments/`
- Cache key includes: `series:lang:prompt:params`
- 7-day cache validity
- Isolated by series + language (prevents collisions)

### **5. Parallel Processing**
- **Segments:** Up to 3 segments per episode in parallel
- **Episodes:** Up to 2 episodes at once
- Uses `ThreadPoolExecutor` (async version planned for v2.1)

### **6. Fix Templates**
If first attempt fails:
1. Loads `msp_XX_fix_template.txt`
2. Injects issues from previous attempt
3. Sends refined prompt to Claude
4. Repeats up to 3 times

### **7. Fusion (Episode Merging)**
After all segments generated:
- Reads `fusion_instructions.txt`
- Sends all segments to Claude
- Creates cohesive episode text
- Output: `fusion_result.txt`

### **8. Health Monitoring**
Tracks:
- API calls / errors
- Tokens used / cost
- Segments generated / failed
- Cache hits / misses
- Average response time
- Success rate
- Memory usage (if `psutil` available)

Saves health reports to `logs/health_report_TIMESTAMP.json`

---

## Validation Format

Claude responses must include YAML validation block:

```
Napoleon Bonaparte rose to power through...

---VALIDATION---
est_wordcount: 487
opening_hook_present: yes
closing_handoff_present: yes
segment_focus_covered: yes
overlap_with_other_msps: none
language_check: native-like
max_sentence_length: 32
possessive_pronouns_used: no
notes: Successfully covers Napoleon's rise to power
```

**Parsed fields:**
- `est_wordcount` – Estimated word count
- `opening_hook_present` – Must be "yes"
- `closing_handoff_present` – Must be "yes"
- Other fields informational only

---

## Error Handling

### **Retryable Errors:**
- Network timeouts
- Temporary API errors
- Rate limits (429)

### **Non-Retryable Errors:**
- Invalid API key
- Model not found
- Authentication failures

**Smart retry logic** (v2.0) skips retrying permanent errors.

---

## Performance Metrics

**Typical generation times:**
- Single segment: 10-30 seconds
- Full episode (5 segments): 1-3 minutes (parallel)
- Fusion: 20-40 seconds

**Cache hit rates:**
- First run: 0%
- Re-run same project: ~90%

**Success rates (v2.0):**
- Normal mode: 95-98%
- With topic drift detection: 98-99%

---

## Configuration Examples

### **High-Quality Mode (slower, better)**
```bash
export CLAUDE_TEMPERATURE="0.2"
export CLAUDE_MAX_TOKENS="10000"
export MAX_ATTEMPTS="5"
```

### **Fast Mode (for testing)**
```bash
export CLAUDE_TEMPERATURE="0.5"
export CLAUDE_MAX_TOKENS="6000"
export MAX_ATTEMPTS="2"
export MAX_PARALLEL_SEGMENTS="5"
```

### **Conservative Mode (low rate limits)**
```bash
export RATE_LIMIT_DELAY="5.0"
export MAX_PARALLEL_SEGMENTS="1"
export MAX_PARALLEL_EPISODES="1"
```

---

## Troubleshooting

### **"Invalid API key"**
- Set `ANTHROPIC_API_KEY` environment variable
- Or store in keyring (if `keyring` package installed)
- Check key validity at https://console.anthropic.com

### **"Model not found"**
- Update to latest Anthropic SDK: `pip install anthropic --upgrade`
- Verify model ID: `claude-opus-4-20250514`
- Check supported models at Anthropic docs

### **"Response truncated"**
- ✅ Auto-handled in v2.0 (increases tokens on retry)
- Manual fix: Increase `CLAUDE_MAX_TOKENS`

### **"Off-topic outputs"**
- ✅ Topic drift detection enabled in v2.0
- Check series name matches actual topic
- Review prompt templates in `B_core/templates/`

### **"Cache not working"**
- Clear cache: `rm -rf .cache/segments/*`
- Check cache directory permissions
- Verify `filelock` installed: `pip install filelock`

### **"Slow generation"**
- Enable parallel processing (default: ON)
- Increase `MAX_PARALLEL_SEGMENTS` (default: 3)
- Check network latency to Anthropic API

---

## Integration with NightChronicles Studio

**GUI Tab:** `Narration`

**Workflow:**
1. User selects topic + language from dropdowns
2. Clicks "Send selected episode to Claude"
3. GUI spawns `runner_cli.py` subprocess
4. Logs displayed in real-time
5. On completion, GUI refreshes episode status

**Status indicators:**
- ✅ OK – All segments generated
- ⚠️ PARTIAL – Some segments missing
- ❌ PENDING – No segments yet

---

## Exit Codes (for automation)

| Code | Meaning |
|------|---------|
| 0 | Success |
| 2 | Validation error (config, paths) |
| 3 | API error (invalid key, model not found) |
| 4 | I/O error (missing files) |
| 5 | Unexpected error |

---

## Recent Changes (v2.0)

**Major improvements:**
1. ✅ Upgraded to Claude Opus 4.5
2. ✅ Robust YAML parsing (handles nested code fences)
3. ✅ Topic drift detection
4. ✅ Auto-retry with increased tokens
5. ✅ Cross-platform path handling
6. ✅ Cache isolation by series + language
7. ✅ Smart retry logic (skip permanent errors)

**Details:** See [CHANGELOG_v2.0.md](CHANGELOG_v2.0.md)

---

## Dependencies

```bash
pip install -r requirements.txt
```

**Required:**
- `anthropic>=0.40.0` – Claude API client
- `httpx>=0.27.0` – HTTP client with connection pooling
- `python-dotenv>=1.0.0` – Environment variables
- `pyyaml>=6.0` – YAML parsing

**Optional (recommended):**
- `keyring>=25.0.0` – Secure credential storage
- `psutil>=6.0.0` – System monitoring
- `cryptography>=43.0.0` – Encryption utilities
- `filelock>=3.13.0` – Thread-safe file locking

---

## See Also

- [CHANGELOG_v2.0.md](CHANGELOG_v2.0.md) – Detailed changes
- [B_core/README.md](../B_core/README.md) – Previous step (prompt generation)
- [modules/narrationbuilder/README.md](../modules/narrationbuilder/README.md) – Next step (post-processing)
- [nightchronicles_context.md](../nightchronicles_context.md) – Project overview

---

**Version:** 2.0.0  
**Status:** ✅ Production Ready  
**License:** Internal Use
