<#
PowerShell helper: rescan_and_check.ps1
- Run fs_index rescans (prompts + narration) headless and save indexes to studio_gui/.tmp
- Prints summary counts and first items for quick inspection.

Usage:
  PS> .\scripts\rescan_and_check.ps1
  PS> .\scripts\rescan_and_check.ps1 -NC_OUTPUTS_ROOT "D:\NightChroniclesStudio\outputs"
  PS> .\scripts\rescan_and_check.ps1 -PythonExe "C:\Python39\python.exe"

Notes:
- This script executes a short Python helper using the Python executable in $PythonExe.
- Run from the project root (where studio_gui/ and claude_generator/ directories live) and ensure your venv (if any) is activated or provide path to Python.
#>

param(
    [string]$NC_OUTPUTS_ROOT,
    [string]$PythonExe = 'python',
    [switch]$NoCleanup
)

function Write-Log {
    param([string]$Message, [string]$Level = 'INFO')
    switch ($Level.ToUpper()) {
        'ERROR' { Write-Host "[$Level] $Message" -ForegroundColor Red }
        'WARN'  { Write-Host "[$Level] $Message" -ForegroundColor Yellow }
        default { Write-Host "[$Level] $Message" }
    }
}

if ($NC_OUTPUTS_ROOT) {
    Write-Log ("Setting NC_OUTPUTS_ROOT={0}" -f $NC_OUTPUTS_ROOT)
    $env:NC_OUTPUTS_ROOT = $NC_OUTPUTS_ROOT
}

# Quick sanity: must be run from project root (presence of studio_gui dir)
if (-not (Test-Path -Path (Join-Path -Path (Get-Location) -ChildPath 'studio_gui'))) {
    Write-Log ("Current folder does not look like project root (studio_gui/ not found). Change to project root and retry.") "ERROR"
    exit 2
}

# Build temporary Python helper
$py = @'
import sys
import traceback
from pathlib import Path

# Ensure project root is importable
proj_root = Path.cwd()
if str(proj_root) not in sys.path:
    sys.path.insert(0, str(proj_root))

try:
    from studio_gui.src import fs_index
except Exception as e:
    print("ERROR: cannot import studio_gui.src.fs_index:", e)
    traceback.print_exc()
    sys.exit(3)

out_dir = Path("studio_gui") / ".tmp"
try:
    out_dir.mkdir(parents=True, exist_ok=True)
except Exception as e:
    print("ERROR: cannot create output dir:", out_dir, e)
    traceback.print_exc()
    sys.exit(4)

def safe_save(path, data):
    try:
        fs_index.save_index(str(path), data)
        print(f"Saved: {path}")
    except Exception as e:
        print(f"ERROR saving {path}:", e)
        traceback.print_exc()

# Prompts
try:
    pr = fs_index.discover_prompts_root()
    print(f"Rescanning prompts root: {pr}")
    pindex = fs_index.scan_prompts_root(pr)
    safe_save(out_dir / "prompts_index.json", pindex)
except Exception as e:
    print("ERROR during prompts scan:", e)
    traceback.print_exc()

# Narration
try:
    nr = fs_index.discover_narration_root()
    print(f"Rescanning narration root: {nr}")
    nindex = fs_index.scan_narration_root(nr)
    safe_save(out_dir / "narration_index.json", nindex)
except Exception as e:
    print("ERROR during narration scan:", e)
    traceback.print_exc()

# Summary
print("\n=== SUMMARY ===")
try:
    if 'pindex' in locals() and pindex:
        tcount = len(pindex.get('topics', {}))
        print(f"Prompts topics: {tcount}")
        for i, t in enumerate(sorted(pindex.get('topics', {}).keys())[:10], 1):
            langs = list(pindex['topics'][t].get('languages', {}).keys())
            print(f"  {i}. {t} (languages: {len(langs)}) -> {langs[:5]}")
    else:
        print("No prompts index available to summarize.")
except Exception:
    print("Could not summarize prompts index")
    traceback.print_exc()

try:
    if 'nindex' in locals() and nindex:
        tcount2 = len(nindex.get('topics', {}))
        print(f"Narration topics: {tcount2}")
        for i, t in enumerate(sorted(nindex.get('topics', {}).keys())[:10], 1):
            langs = list(nindex['topics'][t].get('languages', {}).keys())
            print(f"  {i}. {t} (languages: {len(langs)}) -> {langs[:5]}")
    else:
        print("No narration index available to summarize.")
except Exception:
    print("Could not summarize narration index")
    traceback.print_exc()

print("\nIndexes written to:", out_dir)
print("Done")
'@

# Create temp file
$tmp = [System.IO.Path]::GetTempFileName() + '.py'
try {
    Set-Content -Path $tmp -Value $py -Encoding UTF8 -Force
} catch {
    Write-Log ("Failed to write temporary Python helper to {0}: {1}" -f $tmp, ($_.ToString())) "ERROR"
    exit 5
}

# Run the helper and capture output
try {
    Write-Log ("Running Python helper with executable: {0}" -f $PythonExe)
    $allOutput = & $PythonExe $tmp 2>&1
    $rc = $LASTEXITCODE
    if ($allOutput) {
        Write-Host $allOutput
    }
} catch {
    Write-Log ("Error running Python helper: {0}" -f ($_.ToString())) "ERROR"
    if (-not $NoCleanup) { Remove-Item -Path $tmp -ErrorAction SilentlyContinue }
    exit 6
}

# Cleanup temp file
if (-not $NoCleanup) {
    try { Remove-Item -Path $tmp -ErrorAction SilentlyContinue } catch {}
} else {
    Write-Log ("Note: temp file preserved at {0} (NoCleanup set)." -f $tmp) "WARN"
}

if ($rc -ne 0) {
    Write-Log ("Python helper exited with code {0}" -f $rc) "WARN"
    exit $rc
}

Write-Log ("Rescan+check complete.") "INFO"
exit 0

