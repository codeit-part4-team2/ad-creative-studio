# Natural Comic Captions Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make rush-hour Shorts copy more natural and funny, exclude generated text from scene backgrounds, and render plain readable captions without shadows or boxes.

**Architecture:** Keep the four-scene storyboard and MeloTTS interfaces unchanged. Select a factual copy template deterministically from a small in-code bank, strengthen the existing scene-generation prompt boundary, and simplify Pillow caption rasterization to one white fill plus a two-pixel dark outline.

**Tech Stack:** Python 3.11+, dataclasses, hashlib, Pillow, pytest, FFmpeg/ffprobe

## Global Constraints

- Preserve the four scene kinds: `INTRO`, `SELF_AWARE`, `BENEFIT`, `CTA`.
- Record the changed script contract as `deadpan-ai-v2`.
- Use only the stored product name and first stored selling point; invent no price, discount, or performance claim.
- Keep MeloTTS, pronunciation lexicon, `/infer`, YouTube, and approval interfaces unchanged.
- Caption fill is `#F8FAFC`; outline is `#121826` at 2px.
- Use no caption shadow, blur, box, or tone accent color.
- Add no OCR or other model dependency.

---

### Task 1: Deterministic Natural Comic Script

**Files:**
- Modify: `tests/test_comic_script.py`
- Modify: `app/backend/services/comic_script.py`

**Interfaces:**
- Consumes: `build_comic_script(product_name: str, selling_points: tuple[str, ...], time_slot: str, lexicon: PronunciationLexicon) -> ComicScript`
- Produces: the same function with `ComicScript.version == "deadpan-ai-v2"` and deterministic natural templates.

- [ ] **Step 1: Write failing behavior tests**

Add tests that assert the exact four kinds, `deadpan-ai-v2`, deterministic output for repeated input, one dry self-aware sentence, and exact use of only the first selling point. The first selling point must appear in both display and pronunciation forms while the second must not appear.

```python
assert first == second
assert first.version == "deadpan-ai-v2"
assert "과장은 안 하겠습니다" in self_aware.display_text
assert benefit.display_text == "주요 특징을 말씀드리면, USB-C 충전입니다."
assert benefit.spoken_text == "주요 특징을 말씀드리면, 유에스비 씨 충전입니다."
assert all("8시간 사용" not in line.display_text for line in first.lines)
```

- [ ] **Step 2: Verify RED**

Run: `python -m pytest tests/test_comic_script.py -q`

Expected: failure because the current version is `deadpan-ai-v1` and the current copy uses the old stiff templates.

- [ ] **Step 3: Implement deterministic template selection**

Set `SCRIPT_VERSION = "deadpan-ai-v2"`. Add two template tuples per rush-hour slot and select one with a stable SHA-256 byte derived from normalized product name plus time slot. Format display and spoken variants independently through the existing lexicon results.

The selected four lines must retain these responsibilities:

```python
intro = f"{product}, 출근길에 짧게 소개할게요."
self_aware = "광고라서 칭찬은 해야 합니다. 과장은 안 하겠습니다."
benefit = f"주요 특징을 말씀드리면, {selling_point}입니다."
cta = "필요하셨다면 확인해 보세요. 저는 계속 여기 있겠습니다."
```

Use these exact two banks.

```python
MORNING_TEMPLATES = (
    (
        "{product}, 출근길에 짧게 소개할게요.",
        "광고라서 칭찬은 해야 합니다. 과장은 안 하겠습니다.",
        "필요하셨다면 확인해 보세요. 저는 계속 여기 있겠습니다.",
    ),
    (
        "바쁜 아침이니 {product}부터 보여드릴게요.",
        "저는 잠이 없어서 아침 광고도 괜찮습니다.",
        "출근 전에 한 번 확인해 보세요. 저는 지각하지 않습니다.",
    ),
)
EVENING_TEMPLATES = (
    (
        "{product}, 퇴근길에 짧게 소개할게요.",
        "저는 퇴근이 없습니다. 광고는 계속할 수 있습니다.",
        "필요하셨다면 확인해 보세요. 저는 먼저 퇴근하지 않겠습니다.",
    ),
    (
        "퇴근 중이시라면 {product}만 보고 가세요.",
        "광고라서 활기차야 합니다. 목소리는 이게 최선입니다.",
        "퇴근길에 한 번 확인해 보세요. 저는 계속 여기 있겠습니다.",
    ),
)
```

Both banks use `"주요 특징을 말씀드리면, {selling_point}입니다."` for the
benefit line. When no selling point exists, retain
`"제품의 주요 특징을 확인해 보세요."`.

- [ ] **Step 4: Verify GREEN**

Run: `python -m pytest tests/test_comic_script.py tests/test_storyboard.py -q`

Expected: all tests pass with updated literal expectations.

- [ ] **Step 5: Commit**

```bash
git add app/backend/services/comic_script.py tests/test_comic_script.py tests/test_storyboard.py
git commit -m "feat: make rush-hour comic copy more natural"
```

### Task 2: Text-Free Scene Prompt Boundary

**Files:**
- Modify: `tests/test_scene_images.py`
- Modify: `app/backend/services/scene_images.py`
- Modify: `docs/integration_checklist.md`

**Interfaces:**
- Consumes: `_scene_prompt(purpose: str, tone: str, time_slot: str) -> str` and `NEGATIVE_PROMPT` through `SceneImageProvider.build(...)` request payloads.
- Produces: prompts that explicitly forbid readable text, pseudo-text, numbers, signage, price labels, UI, typography, watermark, and signature.

- [ ] **Step 1: Write failing request-boundary test**

Extend the real request payload test to assert these literal concepts appear in every request:

```python
for forbidden in (
    "readable text", "pseudo-text", "numbers", "price tag",
    "signboard", "poster", "user interface", "watermark", "signature",
):
    assert forbidden in negative_prompt
assert "blank unmarked surfaces" in image_prompt
assert "no readable text or symbols anywhere" in image_prompt
```

- [ ] **Step 2: Verify RED**

Run: `python -m pytest tests/test_scene_images.py::test_provider_passes_existing_infer_contract_fields -q`

Expected: failure on the first newly required prompt phrase.

- [ ] **Step 3: Strengthen both prompt directions**

Expand `NEGATIVE_PROMPT` with the complete forbidden list and finish `_scene_prompt` with blank, unmarked, text-free surface instructions. Do not add a new model call or OCR dependency.

- [ ] **Step 4: Record the human approval gate**

Update `docs/integration_checklist.md` so generated letters, fake lettering, numbers, labels, signs, UI, and watermarks fail human approval even when `product_preserved=true`.

- [ ] **Step 5: Verify GREEN and commit**

Run: `python -m pytest tests/test_scene_images.py -q`

```bash
git add app/backend/services/scene_images.py tests/test_scene_images.py docs/integration_checklist.md
git commit -m "fix: exclude generated text from shorts scenes"
```

### Task 3: Plain Readable Caption Rasterization

**Files:**
- Modify: `tests/test_video_renderer.py`
- Modify: `app/backend/services/video_renderer.py`

**Interfaces:**
- Consumes: `_draw_caption(canvas: Image.Image, *, scene: StoryboardScene, font_path: Path) -> None`.
- Produces: `CAPTION_LAYOUT_VERSION = "plain-outline-v2"` and direct caption drawing with white fill and a 2px dark outline.

- [ ] **Step 1: Write failing raster behavior tests**

Render a real caption onto solid white, light gray, and near-black RGBA canvases using the bundled NanumGothic font. Assert that the caption safe region contains both near-white fill pixels and dark outline pixels. Patch `ImageFilter.GaussianBlur` only around `_draw_caption` to raise if the caption path attempts blur, and use an `accent_terms` fixture to assert no exact tone accent color appears.

```python
assert any(max(pixel[:3]) >= 245 for pixel in caption_pixels)
assert any(max(pixel[:3]) <= 40 for pixel in caption_pixels)
assert (231, 213, 165) not in {pixel[:3] for pixel in caption_pixels}
```

- [ ] **Step 2: Verify RED**

Run: `python -m pytest tests/test_video_renderer.py -q`

Expected: failure because the current caption path applies a Gaussian-blurred shadow, 3px outline, and premium tone accent.

- [ ] **Step 3: Implement the plain caption**

Change text measurement and drawing to `stroke_width=2`, `fill="#F8FAFC"`, and `stroke_fill="#121826"`. Delete the shadow layer, shadow blur, accent lookup, and accent redraw. Remove the now-unused caption `tone` argument while leaving image tone generation unchanged.

- [ ] **Step 4: Verify GREEN**

Run: `python -m pytest tests/test_video_renderer.py -q`

Expected: raster tests and the real FFmpeg voiced-AAC integration test pass.

- [ ] **Step 5: Commit**

```bash
git add app/backend/services/video_renderer.py tests/test_video_renderer.py
git commit -m "style: simplify shorts captions"
```

### Task 4: Full Verification and PR #22 Handoff

**Files:**
- Modify if needed: `docs/integration_checklist.md`
- Modify: existing PR #22 metadata and comment; do not create a duplicate PR.

**Interfaces:**
- Consumes: all changes from Tasks 1-3.
- Produces: a clean branch, successful CI, Ready PR #22, and a PM merge-permission message.

- [ ] **Step 1: Run focused verification**

```bash
python -m pytest tests/test_comic_script.py tests/test_storyboard.py tests/test_scene_images.py tests/test_video_renderer.py -q
python -m ruff check app/backend/services/comic_script.py app/backend/services/scene_images.py app/backend/services/video_renderer.py tests/test_comic_script.py tests/test_scene_images.py tests/test_video_renderer.py
```

- [ ] **Step 2: Run the full suite**

Run: `python -m pytest -q`

Expected: zero failures.

- [ ] **Step 3: Inspect rendered samples**

Create test frames on white, light gray, and near-black backgrounds in a temporary directory, open them for visual inspection, and confirm there is no shadow, box, or accent color and the text remains readable. Do not commit temporary samples.

- [ ] **Step 4: Push and watch CI**

```bash
git push origin codex/shorts-quality-ops-hardening
gh pr checks 22 --watch
```

- [ ] **Step 5: Mark Ready and request review**

After local tests, visual inspection, and CI all pass:

```bash
gh pr ready 22
```

Comment on PR #22 with the exact behavior changes, verification counts, TTS human-check status, remaining image/video human gate, and ask the PM to re-review and approve merging.
