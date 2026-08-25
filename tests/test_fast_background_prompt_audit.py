from argparse import Namespace

import pytest

from tools import audit_fast_background_prompts as prompt_audit
from tools.audit_fast_background_prompts import (
    audit_fast_background_prompts,
    load_sdxl_token_counters,
)


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


def test_loader_uses_both_sdxl_clip_tokenizer_subfolders() -> None:
    load_calls: list[tuple[str, str, bool]] = []

    class RecordingClipTokenizer:
        @classmethod
        def from_pretrained(
            cls,
            model_id: str,
            *,
            subfolder: str,
            local_files_only: bool,
        ):
            load_calls.append((model_id, subfolder, local_files_only))
            token_count = 64 if subfolder == "tokenizer" else 65
            return lambda _prompt, **_kwargs: {
                "input_ids": list(range(token_count))
            }

    counters = load_sdxl_token_counters(
        model_id="local/sdxl",
        local_files_only=True,
        tokenizer_class=RecordingClipTokenizer,
    )

    assert [counter("scene") for counter in counters] == [64, 65]
    assert load_calls == [
        ("local/sdxl", "tokenizer", True),
        ("local/sdxl", "tokenizer_2", True),
    ]


def test_main_audits_the_counters_loaded_by_cli_arguments(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    monkeypatch.setattr(
        prompt_audit,
        "parse_args",
        lambda: Namespace(model_id="local/sdxl", allow_download=False),
    )
    monkeypatch.setattr(
        prompt_audit,
        "load_sdxl_token_counters",
        lambda **_kwargs: (_constant_counter(64), _constant_counter(65)),
    )

    assert prompt_audit.main() == 0
    assert '"combinations": 72' in capsys.readouterr().out
