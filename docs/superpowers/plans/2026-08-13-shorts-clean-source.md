# Shorts Clean Source Image Implementation Plan

Date: 2026-08-13

Constraint: prepare and verify locally only. Do not stage, commit, push, or create a
pull request until the user authorizes that work tomorrow.

## Task 1: Lock the persistence contract with failing tests

- Add an overlay test proving source pixels and dimensions are unchanged.
- Add generation tests requiring a separate `source_image_url` for real and mock
  paths.
- Run the focused suite and record the expected RED failures.

## Task 2: Persist the text-free source

- Add `source_image_url` to `ToneResult` as a backward-compatible optional field.
- Add a focused source persistence helper to `overlay.py`.
- Populate the field in both generation services before formatted exports are made.
- Run the focused persistence and generation tests to GREEN.

## Task 3: Make Shorts fail closed

- Change storyboard selection to require `source_image_url`.
- Update fixtures so the raw and formatted files are distinguishable.
- Add regression coverage for legacy records and output-root traversal.
- Verify the model-to-video flow fingerprints and copies the raw source.

## Task 4: Document and verify the prepared model boundary

- Update the API contract with the new response field and legacy behavior.
- Run focused video/API tests, the full test suite, Ruff on changed Python files,
  compile checks, and `git diff --check`.
- Update the project ledger with evidence and tomorrow's PR handoff.
