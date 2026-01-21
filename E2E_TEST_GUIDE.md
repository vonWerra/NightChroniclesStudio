# 🧪 End-to-End Workflow Test Guide

**Účel:** Otestovat kompletní pipeline od osnovy po finální text.

**Čas:** ~15-30 minut (závisí na API response time)

---

## 📋 Prerequisites

### **1. API klíče**
```bash
# Required
export ANTHROPIC_API_KEY="sk-ant-..."
export OPENAI_API_KEY="sk-..."

# Verify
echo $ANTHROPIC_API_KEY
echo $OPENAI_API_KEY
```

### **2. Environment setup**
```bash
# Unified outputs root (recommended)
export NC_OUTPUTS_ROOT="$(pwd)/outputs"

# Verify
echo $NC_OUTPUTS_ROOT
```

### **3. Dependencies**
```bash
# Install all dependencies
pip install -r requirements-all.txt

# Or individual modules
pip install -r outline-generator/requirements.txt
pip install -r B_core/requirements.txt  # (if has requirements.txt)
pip install -r claude_generator/requirements.txt
pip install -r modules/narrationbuilder/requirements.txt
```

---

## 🚀 Test Execution

### **Option A: Automated Test Script** ⭐ (Recommended)

```bash
# Run complete E2E test
python test_e2e_workflow.py --topic "TestNapoleon" --lang CS

# Skip steps if already have data
python test_e2e_workflow.py --topic "TestNapoleon" --lang CS --skip-outline --skip-prompts

# Different language
python test_e2e_workflow.py --topic "TestWW2" --lang EN
```

**Expected output:**
```
[INFO] Starting E2E Test: TestNapoleon / CS / ep01
[INFO] STEP 1: Outline Generator
[SUCCESS] ✓ Found: osnova.json
[INFO] STEP 2: B_core (Prompts Generation)
[SUCCESS] ✓ Found: prompts folder
[INFO] Found 5 execution prompts
[INFO] STEP 3: Claude Generator (Narration)
[SUCCESS] ✓ Found: narration directory
[INFO] Found 5 segment files
[INFO] STEP 4: Narration Builder (Final)
[SUCCESS] ✓ Found: final narrative
[INFO] Final word count: 2034 words
[SUCCESS] ✓ E2E TEST PASSED
```

---

### **Option B: Manual Step-by-Step** 🔧

#### **STEP 1: Generate Outline**

```bash
cd outline-generator

# Interactive mode
python generate_outline.py -l CS -v

# Or specify topic in config
python generate_outline.py \
  -l CS \
  -c config/outline_config.json \
  -t templates/outline_master.txt \
  -o ../outputs/outline \
  -v
```

**Verify:**
```bash
# Check output
ls ../outputs/outline/<YourTopic>/CS/

# Should see:
# - osnova.json
# - generation_log.json
# - cache/ (if cache enabled)
```

**Check osnova.json:**
```bash
cat ../outputs/outline/<YourTopic>/CS/osnova.json | jq '.episodes | length'
# Should show number of episodes (e.g., 6)
```

---

#### **STEP 2: Generate Prompts**

```bash
cd ../B_core

# With topic selection
python generate_prompts.py --topic "<YourTopic>" --language CS -y -v

# Example
python generate_prompts.py --topic "Napoleon" --language CS -y -v
```

**Verify:**
```bash
# Check output
ls ../outputs/prompts/<YourTopic>/CS/ep01/prompts/

# Should see:
# - msp_01_execution.txt
# - msp_01_fix_template.txt
# - msp_02_execution.txt
# - ...
# - fusion_instructions.txt
```

**Count prompts:**
```bash
ls ../outputs/prompts/<YourTopic>/CS/ep01/prompts/msp_*_execution.txt | wc -l
# Should match segment count from osnova
```

---

#### **STEP 3: Generate Narration (Claude)**

```bash
cd ../claude_generator

# Single episode
python runner_cli.py \
  --topic "<YourTopic>" \
  --language CS \
  --episodes "ep01" \
  -v

# Multiple episodes
python runner_cli.py \
  --topic "<YourTopic>" \
  --language CS \
  --episodes "ep01,ep02" \
  -v
```

**Verify:**
```bash
# Check output
ls ../outputs/narration/<YourTopic>/CS/ep01/

# Should see:
# - segment_01.txt
# - segment_02.txt
# - ...
# - generation_log.json
```

**Check segment quality:**
```bash
# Word count of first segment
wc -w ../outputs/narration/<YourTopic>/CS/ep01/segment_01.txt

# View segment
cat ../outputs/narration/<YourTopic>/CS/ep01/segment_01.txt
```

**Check generation log:**
```bash
cat ../outputs/narration/<YourTopic>/CS/ep01/generation_log.json | jq '.successful_segments'
# Should equal total_segments
```

---

#### **STEP 4: Generate Final Narrative**

```bash
cd ../modules/narrationbuilder

# Run narrationbuilder
python -m narrationbuilder \
  --project-root ../.. \
  --topic-id "<YourTopic>" \
  --episode-id 01 \
  --lang CS \
  --model gpt-4o
```

**Verify:**
```bash
# Check output
ls ../../outputs/final/<YourTopic>/CS/episode_01/

# Should see:
# - episode_01_final.txt
# - prompt_pack.json
# - metrics.json
# - status.json
```

**Check final quality:**
```bash
# Word count
wc -w ../../outputs/final/<YourTopic>/CS/episode_01/episode_01_final.txt

# View final
cat ../../outputs/final/<YourTopic>/CS/episode_01/episode_01_final.txt

# Check metrics
cat ../../outputs/final/<YourTopic>/CS/episode_01/metrics.json | jq '.'
```

---

## ✅ Validation Checklist

### **After each step, verify:**

- [x] **Outline:**
  - [ ] `osnova.json` exists and is valid JSON
  - [ ] Has correct number of episodes
  - [ ] Each episode has title, description, MSP, sources

- [x] **Prompts:**
  - [ ] `prompts/` folder exists for each episode
  - [ ] Execution prompts match segment count
  - [ ] `episode_context.json` exists in `meta/`

- [x] **Narration:**
  - [ ] Segment files exist (segment_01.txt, etc.)
  - [ ] Segments have reasonable word count (~400-600 words)
  - [ ] `generation_log.json` shows success
  - [ ] Segments are in correct language (Czech/English/etc.)

- [x] **Final:**
  - [ ] `episode_XX_final.txt` exists
  - [ ] Word count in target range (1800-2200 default)
  - [ ] `metrics.json` shows validation passed
  - [ ] Text is cohesive and flows well

---

## 🐛 Troubleshooting

### **Outline fails:**
```bash
# Check API key
echo $OPENAI_API_KEY

# Verify config
cat outline-generator/config/outline_config.json | jq '.'

# Check template
ls outline-generator/templates/outline_master.txt
```

### **Prompts fails:**
```bash
# Check osnova exists
ls outputs/outline/<YourTopic>/CS/osnova.json

# Verify topic name matches (case-sensitive)
ls outputs/outline/
```

### **Narration fails:**
```bash
# Check API key
echo $ANTHROPIC_API_KEY

# Verify prompts exist
ls outputs/prompts/<YourTopic>/CS/ep01/prompts/

# Check logs
tail -f claude_generator/.logs/generation_*.log
```

### **Final fails:**
```bash
# Check API key
echo $OPENAI_API_KEY

# Verify segments exist
ls outputs/narration/<YourTopic>/CS/ep01/segment_*.txt

# Count segments
ls outputs/narration/<YourTopic>/CS/ep01/segment_*.txt | wc -l

# Check if narrationbuilder can find segments
cd modules/narrationbuilder
python -m narrationbuilder --project-root ../.. --topic-id "<YourTopic>" --episode-id 01 --lang CS --dry-run
```

---

## 📊 Expected Timings

| Step | Approximate Time |
|------|------------------|
| **Outline** (6 episodes, 1 lang) | 2-5 minutes |
| **Prompts** (1 lang, all episodes) | <1 minute |
| **Narration** (1 episode, 5 segments) | 3-8 minutes |
| **Final** (1 episode) | 30-90 seconds |
| **TOTAL** | ~10-20 minutes |

---

## 🎯 Success Criteria

**Complete E2E test is successful if:**

1. ✅ All 4 steps complete without errors
2. ✅ All output files exist in correct locations
3. ✅ Final narrative has:
   - Word count in target range
   - Correct language
   - Cohesive flow (not just concatenated segments)
   - No technical errors (encoding issues, etc.)

---

## 📝 Results

**Record your results:**

```bash
# View automated test results
cat test_e2e_results.json | jq '.'
```

**Or manually:**
- Outline: ✅/❌
- Prompts: ✅/❌
- Narration: ✅/❌
- Final: ✅/❌

**Issues found:**
- [ ] (list any issues)

**Next steps:**
- [ ] Fix issues
- [ ] Re-test
- [ ] Or proceed to elevenlabs_vystup (TTS)

---

## 🔄 Quick Re-Test

**After fixes, quickly re-test:**

```bash
# Re-run just failed step
python test_e2e_workflow.py \
  --topic "TestNapoleon" \
  --lang CS \
  --skip-outline \
  --skip-prompts
  # (skips successful steps)

# Or manual re-run of specific step
cd claude_generator
python runner_cli.py --topic "Napoleon" --language CS --episodes "ep01" --retry-failed
```

---

**Ready to test?** 🚀

```bash
# Quick start:
python test_e2e_workflow.py --topic "TestNapoleon" --lang CS
```
