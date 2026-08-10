# Build Evidence

| Timestamp | Target | Command | Result | Artifact or log |
|---|---|---|---|---|
| 2026-08-10 KST | Model branch tests | `python -m pytest -q` | `[VERIFIED] 175 passed in 20.70s` | Terminal output in current task |
| 2026-08-10 KST | Static checks | `python -m ruff check app model_server tests tools` | `[VERIFIED] All checks passed` | Terminal output in current task |
| 2026-08-10 KST | Syntax | `python -m compileall -q app model_server tests tools` | `[VERIFIED] exit 0` | Terminal output in current task |
| 2026-08-10 KST | Active environment | `python -m pip check` | `[VERIFIED] No broken requirements found` | Does not prove clean model extras installation |
| 2026-08-10 KST | Patch hygiene | `git diff --check` | `[VERIFIED] exit 0` | Terminal output in current task |
| 2026-08-10 13:31 KST | Three-branch baseline | `python -m pytest -q` in model, Shorts, integration worktrees | `[VERIFIED] 175 / 186 / 241 passed` | Fresh terminal output before final changes |
| 2026-08-10 13:39 KST | Final model branch tests | `python -m pytest -q` | `[VERIFIED] 178 passed in 16.73s` | Head source/docs `6ba4aa8` plus pending ledger only |
| 2026-08-10 13:39 KST | Final model static checks | `python -m ruff check app model_server tests tools scripts` | `[VERIFIED] All checks passed` | Fresh terminal output |
| 2026-08-10 13:39 KST | Final model syntax | `python -m compileall -q app model_server tests tools scripts` | `[VERIFIED] exit 0` | Fresh terminal output |
| 2026-08-10 13:39 KST | Active environment | `python -m pip check` | `[VERIFIED] No broken requirements found` | Does not prove a clean model extras install |
| 2026-08-10 13:39 KST | Patch hygiene | `git diff --check` | `[VERIFIED] exit 0` | Fresh terminal output |
