# Shorts Clean Source Image Design

Date: 2026-08-13

## Problem

The generation pipeline currently keeps only formatted advertising exports. Those
exports already contain the headline and subcopy. The Shorts storyboard then picks
the `sns_card` export and uses it as the hero image, so full-bleed rendering can
enlarge baked-in copy underneath the video captions.

## Decision

Persist the model server output once, before resizing or drawing copy, as a separate
`source_image_url` on every new `ToneResult`. Formatted exports remain in `images`
and keep their existing UI and download behavior. The Shorts storyboard consumes
only `source_image_url`.

The local mock generator also writes a text-free placeholder source so local API and
E2E tests preserve the same contract. A legacy result without `source_image_url`
fails closed with a message instructing the user to regenerate the advertisement;
it must never fall back to a copy-baked formatted card.

## Data flow

1. Receive or create a text-free RGB image.
2. Save it under `data/outputs` without resize, crop, or text overlay.
3. Generate the existing formatted exports from the same in-memory image.
4. Store the source URL separately from the formatted `images` mapping.
5. Resolve and fingerprint only the source URL when building a Shorts storyboard.

## Safety and compatibility

- Source URLs must use the existing `/files/outputs/` boundary.
- The existing resolved-path containment and file-existence checks remain mandatory.
- `source_image_url` is optional at schema-read time so old persisted records remain
  readable, but video creation requires a non-empty valid value.
- The raw source is not added to the formatted export mapping, so bulk download and
  result-card UI behavior do not change.

## Scope boundary

This change adds no model inference and no GPU load. Native 9:16 model generation is
intentionally excluded: it needs a separate L4 quality, latency, and VRAM benchmark
before becoming a production default.

## Verification

- Unit-test lossless source persistence and URL separation.
- Verify real and mock generation both populate the new field.
- Verify the storyboard chooses the raw source even when a formatted card exists.
- Verify legacy results and path traversal fail closed.
- Run focused, dependent, and full regression suites before tomorrow's PR.
