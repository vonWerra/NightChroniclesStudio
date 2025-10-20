APPLY PATCH - Phase 4: NarrationTab migration

Prerequisites
- You have a local clone of the NightChronicles repo
- You are on a clean working tree (no uncommitted changes)

Steps
1) Ensure you're on main and clean
   git checkout main
   git pull origin main
   git status  # should be clean

2) Create feature branch
   git checkout -b feat/refactor/narration-tab-fs-helpers

3) Apply patch (dry-run first)
   git apply --check phase4_narration_tab_migration.patch

   If the check passes:
   git apply phase4_narration_tab_migration.patch

4) Verify changes
   git status
   git diff   # review changes, ensure only expected files modified

5) Stage and commit
   git add studio_gui/src/main.py tests/utils/test_fs_helpers.py studio_gui/src/utils/__init__.py commit_message.txt
   git commit -F commit_message.txt

6) Run checks locally
   python -m py_compile studio_gui/src/main.py
   pytest tests/utils/ -q

7) Push branch and open PR
   git push --set-upstream origin feat/refactor/narration-tab-fs-helpers
   Create PR using pr_description.md as description

Troubleshooting
- If git apply fails: inspect patch hunks and apply manually (edit files, then git add/commit)
- If pytest shows failing tests: run the failing tests with -vv and provide the traceback

