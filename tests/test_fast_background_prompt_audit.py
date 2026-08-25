import pytest

from tools.audit_fast_background_prompts import audit_fast_background_prompts


def _constant_counter(token_count: int):
    return lambda _prompt: token_count


def test_audit_reports_both_sdxl_tokenizer_budgets_for_all_prompts() -> None:
    summary = audit_fast_background_prompts(
        token_counters=(
            _constant_counter(64),
            _constant_counter(65),
        )
    )

    assert summary.combinations == 72
    assert summary.unique_prompts == 72
    assert summary.max_tokens == (64, 65)


def test_audit_rejects_when_second_sdxl_tokenizer_exceeds_clip_limit() -> None:
    with pytest.raises(
        ValueError,
        match=r"tokenizer_2 prompt exceeds CLIP budget: 78/77",
    ):
        audit_fast_background_prompts(
            token_counters=(
                _constant_counter(64),
                _constant_counter(78),
            )
        )
