from __future__ import annotations

import argparse
import json
from collections.abc import Callable, Sequence
from dataclasses import asdict, dataclass

from app.prompt.backgrounds import FAST_SCENE_PURPOSES, build_fast_background_prompt
from app.prompt.templates import TIME_SLOT_TEMPLATES, TONE_TEMPLATES
from model_server.pipelines import build_background_prompt


CLIP_TOKEN_LIMIT = 77
SDXL_MODEL_ID = "stabilityai/stable-diffusion-xl-base-1.0"
TokenCounter = Callable[[str], int]


@dataclass(frozen=True, slots=True)
class PromptAuditSummary:
    combinations: int
    unique_prompts: int
    max_characters: int
    max_tokens: tuple[int, int]


def _all_fast_background_prompts() -> tuple[str, ...]:
    return tuple(
        build_background_prompt(
            build_fast_background_prompt(
                tone=tone,
                time_slot=time_slot,
                scene_purpose=scene_purpose,
            )
        )
        for tone in TONE_TEMPLATES
        for time_slot in TIME_SLOT_TEMPLATES
        for scene_purpose in FAST_SCENE_PURPOSES
    )


def audit_fast_background_prompts(
    *,
    token_counters: Sequence[TokenCounter],
    token_limit: int = CLIP_TOKEN_LIMIT,
) -> PromptAuditSummary:
    """Fail when either SDXL text encoder would truncate a fast prompt."""
    if len(token_counters) != 2:
        raise ValueError("SDXL prompt audit requires exactly two tokenizers")

    prompts = _all_fast_background_prompts()
    max_tokens: list[int] = []
    for index, count_tokens in enumerate(token_counters, start=1):
        measured = [count_tokens(prompt) for prompt in prompts]
        largest = max(measured)
        if largest > token_limit:
            raise ValueError(
                f"tokenizer_{index} prompt exceeds CLIP budget: "
                f"{largest}/{token_limit}"
            )
        max_tokens.append(largest)

    return PromptAuditSummary(
        combinations=len(prompts),
        unique_prompts=len(set(prompts)),
        max_characters=max(map(len, prompts)),
        max_tokens=(max_tokens[0], max_tokens[1]),
    )


def _token_counter(tokenizer: object) -> TokenCounter:
    def count(prompt: str) -> int:
        encoded = tokenizer(
            prompt,
            add_special_tokens=True,
            truncation=False,
            return_attention_mask=False,
        )
        return len(encoded["input_ids"])

    return count


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Audit every fast background prompt with both SDXL tokenizers."
    )
    parser.add_argument("--model-id", default=SDXL_MODEL_ID)
    parser.add_argument(
        "--allow-download",
        action="store_true",
        help="Allow tokenizer files to be fetched when they are not cached.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    try:
        from transformers import AutoTokenizer
    except ImportError as exc:
        raise SystemExit(
            "transformers is required; install the model optional dependencies"
        ) from exc

    tokenizers = tuple(
        AutoTokenizer.from_pretrained(
            args.model_id,
            subfolder=subfolder,
            local_files_only=not args.allow_download,
        )
        for subfolder in ("tokenizer", "tokenizer_2")
    )
    summary = audit_fast_background_prompts(
        token_counters=tuple(_token_counter(tokenizer) for tokenizer in tokenizers)
    )
    print(json.dumps(asdict(summary), ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
