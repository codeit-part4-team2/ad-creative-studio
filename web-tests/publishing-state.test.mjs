import assert from "node:assert/strict";
import test from "node:test";

import {
  canRetryPublish,
  canSubmitPublish,
  needsPronunciationConfirmation,
} from "../web/lib/publishing-state.mts";

test("only retry-safe terminal publish failures unlock the approved video", () => {
  for (const publishStatus of ["failed", "auth_required", "schedule_expired"]) {
    assert.equal(
      canRetryPublish({
        approval_status: "approved",
        publish_status: publishStatus,
      }),
      true,
    );
  }

  for (const publishStatus of [
    "not_requested",
    "pending",
    "scheduled",
    "needs_review",
  ]) {
    assert.equal(
      canRetryPublish({
        approval_status: "approved",
        publish_status: publishStatus,
      }),
      false,
    );
  }

  assert.equal(
    canRetryPublish({
      approval_status: "pending",
      publish_status: "failed",
    }),
    false,
  );
  assert.equal(
    canSubmitPublish({
      approval_status: "pending",
      publish_status: "not_requested",
    }),
    true,
  );
  assert.equal(
    canSubmitPublish({
      approval_status: "rejected",
      publish_status: "not_requested",
    }),
    false,
  );
});

test("an already reviewed pronunciation does not block a publish retry", () => {
  assert.equal(
    needsPronunciationConfirmation({
      pronunciation_review_required: true,
      pronunciation_reviewed_at: "2026-08-25T08:00:00+09:00",
    }),
    false,
  );
  assert.equal(
    needsPronunciationConfirmation({
      pronunciation_review_required: true,
      pronunciation_reviewed_at: null,
    }),
    true,
  );
});
