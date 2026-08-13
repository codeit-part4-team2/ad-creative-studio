# Project State

- Last verified: 2026-08-10 13:43 KST after the fresh combined pre-push gate
- Project root: `G:\Codex\projects\상급프로젝트\team-repo\ad-creative-studio`
- Runtime or engine: `[VERIFIED]` Python model-server project; L4 report used Python 3.11.15, torch 2.12.1+cu132, NVIDIA L4 24 GB.
- Branch and reviewed code/docs commit: `[VERIFIED] codex/model-server-optimization source/docs @ 6ba4aa8; ledger @ 48cc166`
- Worktree state before this handoff update: `[VERIFIED]` clean; branch was 11 commits ahead of its fork remote and unpushed.
- Related Shorts worktree: `[VERIFIED] codex/rush-hour-shorts-design @ 58f2bb7`, clean and unpushed.
- Related integration worktree: `[VERIFIED] codex/model-shorts-integration @ 929c3be`, clean after applying the five new model commits.
- Current milestone: model, Shorts, and combined branches are locally verified and preserved immediately before push; external L4 comparison gates remain open.

## 2026-08-13 render observability update

- Project root: `[VERIFIED] G:\Codex\projects\상급프로젝트\worktrees\ad-creative-studio-video-stage-logging`.
- Base: `[VERIFIED] origin/main @ 603be34`, the squash merge commit for PR #22.
- Branch: `[VERIFIED] codex/video-stage-logging`, created from the current remote main.
- Current milestone: `[VERIFIED]` stage-aware render logs and traceback coverage are implemented locally; the VM failure's actual stage remains `[UNVERIFIED]` until this change is deployed and E2E is rerun.
- VM process mode: `[VERIFIED]` no `ad-service-api.service`; test operation uses direct Uvicorn terminals (`app.backend.main` on 8000 and `model_server.main` on 8001). Both servers were stopped when reported, so live post-deploy log output remains `[UNVERIFIED]`.

## 2026-08-13 Shorts duration-budget update

- Project root: `[VERIFIED] G:\Codex\projects\상급프로젝트\worktrees\ad-creative-studio-shorts-duration-budget`.
- Base: `[VERIFIED] origin/main @ 096ea6815d60739f11fd984e9c44965cd1d603b4`, the squash merge commit for PR #25.
- Branch and implementation: `[VERIFIED] codex/shorts-duration-budget @ 54e5712` plus design commit `1b13cc5`.
- Root cause: `[VERIFIED]` VM job `video_906b946fcef1` produced four WAV files totalling 22.362 seconds; 1.600 seconds of silence yielded a 23.962-second estimate and the 10~15-second guard rejected it before FFmpeg.
- Current milestone: `[VERIFIED]` concise `deadpan-ai-v3`, target-duration padding, and numeric overrun evidence are locally implemented and tested; actual MeloTTS duration and video quality on L4 remain `[UNVERIFIED]` until a new E2E job runs.

## 2026-08-13 Shorts TTS-headroom follow-up

- Project root: `[VERIFIED] G:\Codex\projects\상급프로젝트\worktrees\ad-creative-studio-shorts-tts-headroom`.
- Base: `[VERIFIED] origin/main @ 9304143e1fb6ba3f13d4609a2ea946e358ea7e26`, the merge commit for approved PR #26.
- Branch and implementation: `[VERIFIED] codex/shorts-tts-headroom @ a41031b` plus design commit `b8131d9`.
- Second L4 result: `[VERIFIED]` v3 generated 14.365 seconds of speech and 15.965 seconds including silence; the 15.05-second guard rejected it before FFmpeg. The measured self-aware and CTA clips totalled 8.036 seconds.
- Current milestone: `[VERIFIED]` all four self-aware/CTA variants are shortened under `deadpan-ai-v4`; real MeloTTS duration and final video quality remain `[UNVERIFIED]` until the follow-up PR is deployed and E2E is rerun.

## 2026-08-13 Shorts full-bleed visual update

- Project root: `[VERIFIED] G:\Codex\projects\상급프로젝트\worktrees\ad-creative-studio-shorts-full-bleed`.
- Base: `[VERIFIED] origin/main @ 607e80d8f08cf5e2c760406d041ea495762f2c34`, the merge commit for PR #27.
- Branch: `[VERIFIED] codex/shorts-full-bleed`, locally modified and not staged, committed, pushed, or opened as a PR.
- Current milestone: `[VERIFIED]` the renderer uses a single centered cover crop with no blurred duplicate, dark overlay, or inset card; plain captions use a 3px dark outline over the full image.
- External state: `[UNVERIFIED]` the user reports the preceding v4 VM E2E passed, but no job payload, probe output, or logs were captured in this task. This visual change has not yet run on the L4 VM.

## 2026-08-13 Shorts clean-source model handoff

- Worktree and branch: `[VERIFIED] G:\Codex\projects\상급프로젝트\worktrees\ad-creative-studio-shorts-full-bleed` on `codex/shorts-full-bleed`, still unstaged, uncommitted, unpushed, and without a PR.
- Contract: `[VERIFIED]` each new real or mock `ToneResult` stores a separate text-free `source_image_url`; formatted headline/subcopy exports remain under `images`.
- Shorts boundary: `[VERIFIED]` storyboard construction requires the source URL and rejects legacy results rather than falling back to a copy-baked card.
- Current milestone: `[VERIFIED]` full-bleed rendering and clean-source selection pass the complete local suite. Native 9:16 inference remains `[UNVERIFIED]` and excluded pending an L4 same-input quality, latency, and VRAM comparison.
