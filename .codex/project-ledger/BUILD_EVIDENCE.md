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
| 2026-08-10 13:41 KST | Shorts branch final gate | pytest, Ruff, compileall, `pip check`, diff, credential and ignored-artifact checks | `[VERIFIED] 186 passed in 25.46s; every remaining check exited 0` | Clean `codex/rush-hour-shorts-design @ 58f2bb7` |
| 2026-08-10 13:42 KST | Model-to-Shorts integration | Cherry-pick five model commits in order | `[VERIFIED] applied without conflicts` | `codex/model-shorts-integration @ 929c3be` |
| 2026-08-10 13:43 KST | Combined branch tests | `python -m pytest -q` | `[VERIFIED] 244 passed in 30.15s` | Fresh terminal output at `929c3be` |
| 2026-08-10 13:43 KST | Combined static and environment gates | Ruff, compileall, `pip check`, `git diff --check` | `[VERIFIED] every command exited 0` | Fresh terminal output |
| 2026-08-10 13:43 KST | Combined secret and artifact hygiene | credential-shaped name/value scan plus `git check-ignore` | `[VERIFIED] no credential-shaped tracked content; four runtime probes ignored by expected rules` | `var/store.json`, `data/videos/probe.mp4`, `logs/probe.log`, `.env` |
| 2026-08-10 13:43 KST | Pre-push boundary | listener check and `git ls-remote` | `[VERIFIED] no listeners on 8000/8001/8010/8501/8511; fork branch remains f265d43` | No push, PR update, deploy, or publication performed |
