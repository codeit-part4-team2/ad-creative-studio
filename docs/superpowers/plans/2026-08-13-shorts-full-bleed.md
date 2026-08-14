# Shorts Full-Bleed Visual Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the blurred portrait background and centered image card with a single full-bleed scene image while preserving readable plain captions.

**Architecture:** `video_renderer._make_scene_frame` will perform one centered cover crop into the final 1080x1920 canvas and draw the existing caption directly on that image. The renderer call site no longer needs a crop variant. Caption geometry will share one 3px stroke constant so measurement and drawing remain consistent.

**Tech Stack:** Python, Pillow, pytest, FFmpeg/ffprobe

## Global Constraints

- Do not change model generation, TTS, scene timing, publishing, or API contracts.
- Do not add blur, a dark overlay, an inset image card, a caption box, or a caption shadow.
- Keep output at 1080x1920 H.264/AAC and captions at no more than two lines.
- Do not stage, commit, push, merge, or create a PR without separate user authorization.

---

### Task 1: Lock the full-bleed frame contract

**Files:**
- Modify: `tests/test_comic_caption_layout.py`
- Modify: `tests/test_video_renderer.py`

**Interfaces:**
- Consumes: `_make_scene_frame(*, source, scene, font_path) -> Image.Image`
- Produces: regression coverage for full-bleed pixels, center-subject retention, no blur, and the new layout version

- [x] **Step 1: Write failing tests**

Add a solid-color source test that rejects any `Image.filter` call and asserts that all four frame corners retain the source color. Add a center-subject test using a contrasting central rectangle. Update the caption layout version assertion to `full-bleed-outline-v3`.

- [x] **Step 2: Verify the tests fail for the intended reason**

Run: `python -m pytest -q tests/test_comic_caption_layout.py tests/test_video_renderer.py`

Expected: failure because `_make_scene_frame` still blurs and darkens the source image, and the layout version is still `plain-outline-v2`.

### Task 2: Implement the minimal renderer change

**Files:**
- Modify: `app/backend/services/video_renderer.py`
- Test: `tests/test_comic_caption_layout.py`
- Test: `tests/test_video_renderer.py`

**Interfaces:**
- Consumes: Pillow `ImageOps.fit` with centered cover cropping
- Produces: `_make_scene_frame(*, source, scene, font_path) -> Image.Image`

- [x] **Step 1: Replace the frame composition**

Build the canvas directly with `ImageOps.fit(source.convert("RGB"), (1080, 1920), method=Image.Resampling.LANCZOS, centering=(0.5, 0.5))`, draw the caption, and return RGB. Remove the crop-variant call-site argument and the obsolete `fit_inside` helper.

- [x] **Step 2: Keep caption measurement and drawing consistent**

Define `CAPTION_STROKE_WIDTH = 3`; use it in `_font_and_lines`, caption bounding boxes, and `draw.text`. Set `CAPTION_LAYOUT_VERSION = "full-bleed-outline-v3"`.

- [x] **Step 3: Verify focused tests pass**

Run: `python -m pytest -q tests/test_comic_caption_layout.py tests/test_video_renderer.py`

Expected: all focused tests pass.

### Task 3: Verify the integrated result

**Files:**
- Verify: `app/backend/services/video_renderer.py`
- Verify: `tests/`

**Interfaces:**
- Consumes: the full-bleed frame renderer
- Produces: local test and visual evidence without remote Git mutations

- [x] **Step 1: Run the complete regression suite**

Run: `python -m pytest -q`

Expected: all tests pass with zero failures.

- [x] **Step 2: Render and inspect a portrait preview**

Crop the sharp product image from the supplied screenshot, render it through `_make_scene_frame`, save the result outside the repository, and inspect the resulting 1080x1920 image for full-bleed coverage, centered product placement, and caption readability.

- [x] **Step 3: Review the final diff and repository status**

Run: `git diff --check`, `git diff --stat`, and `git status --short --branch`.

Expected: only renderer, tests, and design/plan documentation are modified; no staged or remote changes exist.
