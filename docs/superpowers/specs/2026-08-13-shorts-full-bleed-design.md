# Shorts Full-Bleed Visual Design

## Problem

The current renderer enlarges each square scene image into a blurred portrait background, darkens it, and then places a second sharp image inside a centered card. The repeated image and large empty margins make a high-quality generated product photo look like a low-quality slideshow.

## Decision

Render each generated scene image once as a full-bleed 1080x1920 frame. Use a centered cover crop (`ImageOps.fit`) so the product remains centered while excess side background is removed. Do not add blur, a dark overlay, an inset card, or caption panels.

Captions remain white text with a dark outline and no shadow. Increase the outline from 2px to 3px so text stays readable over both light and dark generated backgrounds. Keep the existing scene order, static-image presentation, deadpan TTS, comic script, duration budget, FFmpeg encoding, and YouTube workflow unchanged.

## Quality and Safety Constraints

- Output remains 1080x1920 H.264/AAC.
- Source images remain unchanged on disk; cropping occurs only in the rendered frame.
- Product placement relies on the existing centered-subject generation prompt.
- Caption layout remains at most two lines and keeps the existing top/bottom safe areas.
- No model download, GPU pipeline change, TTS change, or duration change is included.
- The user-reported E2E pass is context only; this change requires fresh local renderer regression tests and a visual preview.

## Rejected Alternatives

- Native portrait diffusion generation: potentially best composition, but changes the model/GPU contract and requires new L4 quality/performance validation.
- Larger centered card: preserves the duplicated-image visual hierarchy that caused the quality problem.
- Motion or Ken Burns effects: adds complexity and can expose crop artifacts; it is outside this focused visual-layout improvement.
