#!/usr/bin/env python3
"""
End-to-End Workflow Test
Tests complete pipeline: Outline → Prompts → Narration → Final

Usage:
    python test_e2e_workflow.py --topic "TestTopic" --lang CS
"""
from __future__ import annotations

import sys
import os
import subprocess
import json
from pathlib import Path
from typing import Optional
import argparse
from datetime import datetime

# Colors for terminal output
class Colors:
    GREEN = '\033[92m'
    RED = '\033[91m'
    YELLOW = '\033[93m'
    BLUE = '\033[94m'
    BOLD = '\033[1m'
    END = '\033[0m'

def log(msg: str, level: str = "INFO"):
    colors = {"INFO": Colors.BLUE, "SUCCESS": Colors.GREEN, "ERROR": Colors.RED, "WARN": Colors.YELLOW}
    color = colors.get(level, "")
    print(f"{color}[{level}] {msg}{Colors.END}")

def run_command(cmd: list[str], cwd: Optional[str] = None, check: bool = True) -> tuple[int, str, str]:
    """Run command and return (exit_code, stdout, stderr)"""
    log(f"Running: {' '.join(cmd)}", "INFO")
    try:
        result = subprocess.run(
            cmd,
            cwd=cwd,
            capture_output=True,
            text=True,
            encoding='utf-8',
            errors='replace'
        )
        if check and result.returncode != 0:
            log(f"Command failed with exit code {result.returncode}", "ERROR")
            log(f"STDOUT: {result.stdout}", "ERROR")
            log(f"STDERR: {result.stderr}", "ERROR")
        return result.returncode, result.stdout, result.stderr
    except Exception as e:
        log(f"Exception running command: {e}", "ERROR")
        return 1, "", str(e)

def check_file_exists(path: Path, description: str) -> bool:
    if path.exists():
        log(f"[OK] Found: {description} ({path})", "SUCCESS")
        return True
    else:
        log(f"[FAIL] Missing: {description} ({path})", "ERROR")
        return False

def check_json_valid(path: Path, description: str) -> bool:
    try:
        with open(path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        log(f"[OK] Valid JSON: {description}", "SUCCESS")
        return True
    except Exception as e:
        log(f"[FAIL] Invalid JSON: {description} - {e}", "ERROR")
        return False

def main():
    parser = argparse.ArgumentParser(description="E2E Workflow Test")
    parser.add_argument("--topic", default="TestNapoleon", help="Test topic name")
    parser.add_argument("--lang", default="CS", choices=["CS", "EN", "DE", "ES", "FR"], help="Language")
    parser.add_argument("--skip-outline", action="store_true", help="Skip outline generation (use existing)")
    parser.add_argument("--skip-prompts", action="store_true", help="Skip prompts generation (use existing)")
    parser.add_argument("--skip-narration", action="store_true", help="Skip narration generation (use existing)")
    parser.add_argument("--episode", default="01", help="Episode to test")
    args = parser.parse_args()

    topic = args.topic
    lang = args.lang
    episode_id = args.episode

    log(f"Starting E2E Test: {topic} / {lang} / ep{episode_id}", "INFO")
    log(f"Timestamp: {datetime.now().isoformat()}", "INFO")

    # Setup paths
    repo_root = Path.cwd()
    outputs_root = repo_root / "outputs"

    # Set environment for unified outputs
    os.environ["NC_OUTPUTS_ROOT"] = str(outputs_root)

    results = {
        "topic": topic,
        "lang": lang,
        "episode": episode_id,
        "timestamp": datetime.now().isoformat(),
        "steps": {}
    }

    # ============================================
    # STEP 1: Outline Generator
    # ============================================
    if not args.skip_outline:
        log("\n" + "="*60, "INFO")
        log("STEP 1: Outline Generator", "INFO")
        log("="*60, "INFO")

        outline_script = repo_root / "outline-generator" / "generate_outline.py"
        outline_config = repo_root / "outline-generator" / "config" / "outline_config.json"
        outline_template = repo_root / "outline-generator" / "templates" / "outline_master.txt"

        # Modify config for test (or use existing)
        # For quick test, we'll use existing config

        cmd = [
            sys.executable,
            str(outline_script),
            "-l", lang,
            "-c", str(outline_config),
            "-t", str(outline_template),
            "-o", str(outputs_root / "outline"),
            "-v"
        ]

        code, stdout, stderr = run_command(cmd, check=False)
        results["steps"]["outline"] = {
            "exit_code": code,
            "success": code == 0
        }

        if code != 0:
            log("Outline generation FAILED", "ERROR")
            # Continue anyway for testing
    else:
        log("Skipping outline generation (using existing)", "WARN")
        results["steps"]["outline"] = {"skipped": True}

    # Check outline outputs
    outline_dir = outputs_root / "outline" / topic / lang
    osnova_file = outline_dir / "osnova.json"

    if not check_file_exists(osnova_file, "osnova.json"):
        log("Cannot continue without osnova.json", "ERROR")
        return 1

    check_json_valid(osnova_file, "osnova.json")

    # ============================================
    # STEP 2: B_core (Prompts)
    # ============================================
    if not args.skip_prompts:
        log("\n" + "="*60, "INFO")
        log("STEP 2: B_core (Prompts Generation)", "INFO")
        log("="*60, "INFO")

        prompts_script = repo_root / "B_core" / "generate_prompts.py"

        cmd = [
            sys.executable,
            str(prompts_script),
            "--topic", topic,
            "--language", lang,
            "-y",  # auto-overwrite
            "-v"
        ]

        code, stdout, stderr = run_command(cmd, check=False)
        results["steps"]["prompts"] = {
            "exit_code": code,
            "success": code == 0
        }

        if code != 0:
            log("Prompts generation FAILED", "ERROR")
    else:
        log("Skipping prompts generation (using existing)", "WARN")
        results["steps"]["prompts"] = {"skipped": True}

    # Check prompts outputs
    prompts_dir = outputs_root / "prompts" / topic / lang / f"ep{episode_id}"
    prompts_folder = prompts_dir / "prompts"
    meta_folder = prompts_dir / "meta"
    episode_context = meta_folder / "episode_context.json"

    if not check_file_exists(prompts_folder, "prompts folder"):
        log("Cannot continue without prompts", "ERROR")
        return 1

    if check_file_exists(episode_context, "episode_context.json"):
        check_json_valid(episode_context, "episode_context.json")
        # Count prompts
        prompt_files = list(prompts_folder.glob("msp_*_execution.txt"))
        log(f"Found {len(prompt_files)} execution prompts", "INFO")

    # ============================================
    # STEP 3: Claude Generator (Narration)
    # ============================================
    if not args.skip_narration:
        log("\n" + "="*60, "INFO")
        log("STEP 3: Claude Generator (Narration)", "INFO")
        log("="*60, "INFO")

        # Check if API key is set
        if not os.environ.get("ANTHROPIC_API_KEY"):
            log("ANTHROPIC_API_KEY not set - skipping narration", "WARN")
            results["steps"]["narration"] = {"skipped": True, "reason": "no_api_key"}
        else:
            runner_script = repo_root / "claude_generator" / "runner_cli.py"

            cmd = [
                sys.executable,
                str(runner_script),
                "--topic", topic,
                "--language", lang,
                "--episodes", f"ep{episode_id}",
                "-v"
            ]

            code, stdout, stderr = run_command(cmd, check=False)
            results["steps"]["narration"] = {
                "exit_code": code,
                "success": code == 0
            }

            if code != 0:
                log("Narration generation FAILED", "ERROR")
    else:
        log("Skipping narration generation (using existing)", "WARN")
        results["steps"]["narration"] = {"skipped": True}

    # Check narration outputs
    narration_dir = outputs_root / "narration" / topic / lang / f"ep{episode_id}"

    if check_file_exists(narration_dir, "narration directory"):
        segment_files = list(narration_dir.glob("segment_*.txt"))
        log(f"Found {len(segment_files)} segment files", "INFO")
        results["steps"]["narration"]["segment_count"] = len(segment_files)

        # Check generation log
        gen_log = narration_dir / "generation_log.json"
        if check_file_exists(gen_log, "generation_log.json"):
            check_json_valid(gen_log, "generation_log.json")

    # ============================================
    # STEP 4: Narration Builder (Final)
    # ============================================
    log("\n" + "="*60, "INFO")
    log("STEP 4: Narration Builder (Final)", "INFO")
    log("="*60, "INFO")

    # Check if API key is set
    if not os.environ.get("OPENAI_API_KEY"):
        log("OPENAI_API_KEY not set - skipping final", "WARN")
        results["steps"]["final"] = {"skipped": True, "reason": "no_api_key"}
    else:
        # Import and run narration builder
        try:
            # Use CLI
            cmd = [
                sys.executable, "-m", "narrationbuilder",
                "--project-root", str(repo_root),
                "--topic-id", topic,
                "--episode-id", episode_id,
                "--lang", lang,
                "--model", "gpt-4o"
            ]

            code, stdout, stderr = run_command(cmd, cwd=str(repo_root / "modules" / "narrationbuilder"), check=False)
            results["steps"]["final"] = {
                "exit_code": code,
                "success": code == 0
            }

            if code != 0:
                log("Final generation FAILED", "ERROR")
        except Exception as e:
            log(f"Exception running narrationbuilder: {e}", "ERROR")
            results["steps"]["final"] = {"error": str(e)}

    # Check final outputs
    final_dir = outputs_root / "final" / topic / lang / f"episode_{episode_id}"
    final_file = final_dir / f"episode_{episode_id}_final.txt"
    final_metrics = final_dir / "metrics.json"

    if check_file_exists(final_file, "final narrative"):
        # Check size
        size = final_file.stat().st_size
        log(f"Final file size: {size} bytes", "INFO")

        # Count words
        try:
            text = final_file.read_text(encoding='utf-8')
            word_count = len(text.split())
            log(f"Final word count: {word_count} words", "INFO")
            results["steps"]["final"]["word_count"] = word_count
        except Exception as e:
            log(f"Error reading final file: {e}", "ERROR")

    if check_file_exists(final_metrics, "metrics.json"):
        check_json_valid(final_metrics, "metrics.json")

    # ============================================
    # SUMMARY
    # ============================================
    log("\n" + "="*60, "INFO")
    log("TEST SUMMARY", "INFO")
    log("="*60, "INFO")

    all_success = True
    for step, data in results["steps"].items():
        if data.get("skipped"):
            log(f"{step.upper()}: SKIPPED ({data.get('reason', 'user')})", "WARN")
        elif data.get("success"):
            log(f"{step.upper()}: SUCCESS", "SUCCESS")
        else:
            log(f"{step.upper()}: FAILED (exit_code={data.get('exit_code', '?')})", "ERROR")
            all_success = False

    # Save results
    results_file = repo_root / "test_e2e_results.json"
    with open(results_file, 'w', encoding='utf-8') as f:
        json.dump(results, f, indent=2, ensure_ascii=False)
    log(f"\nResults saved to: {results_file}", "INFO")

    if all_success:
        log("\n[OK] E2E TEST PASSED", "SUCCESS")
        return 0
    else:
        log("\n[FAIL] E2E TEST FAILED", "ERROR")
        return 1

if __name__ == "__main__":
    sys.exit(main())
