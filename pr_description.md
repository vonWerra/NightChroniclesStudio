### Title: refactor(NarrationTab): migrate to fs_helpers utilities

Consolidates filesystem helper functions into shared utils module to eliminate code duplication.

Summary
- ✅ Removed ~45 lines of duplicate code
- ✅ Added 13 comprehensive unit tests
- ✅ Maintained full backward compatibility via wrapper methods
- ✅ All tests passing, GUI verified

Files changed
- `studio_gui/src/main.py` - removed duplicates, added wrappers
- `tests/utils/test_fs_helpers.py` - NEW (13 tests)

Testing
- Unit tests: 13/13 ✓
- Syntax check: ✓
- GUI smoke test: ✓

Next steps
- Apply same pattern to PostProcessTab
- Optional: Remove wrappers in future PR (direct calls to utils)

Requested reviewers: @your-team

Notes: Use provided patch to apply changes locally and run the verification steps in APPLY_PATCH.md
