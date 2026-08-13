from __future__ import annotations


DEFAULT_NEGATIVE_TERMS = (
    "text",
    "pseudo-text",
    "letters",
    "numbers",
    "logo",
    "watermark",
    "signature",
    "price tag",
    "signboard",
    "poster",
    "user interface",
    "duplicate product",
    "extra appliance",
    "wristwatch",
    "clock",
    "timer",
    "dial",
    "large circular prop",
    "dominant background object",
    "softbox",
    "tripod",
    "studio light",
    "blurry",
    "distorted object",
)

FAST_BACKGROUND_ONLY_TERMS = (
    "foreground product",
    "appliance",
    "cup",
    "package",
)


def merge_negative_prompts(*prompts: str) -> str:
    terms: list[str] = []
    seen: set[str] = set()
    for prompt in prompts:
        for raw_term in prompt.split(","):
            term = raw_term.strip()
            key = term.casefold()
            if not term or key in seen:
                continue
            seen.add(key)
            terms.append(term)
    return ", ".join(terms)


DEFAULT_NEGATIVE_PROMPT = ", ".join(DEFAULT_NEGATIVE_TERMS)
FAST_BACKGROUND_NEGATIVE_PROMPT = merge_negative_prompts(
    DEFAULT_NEGATIVE_PROMPT,
    ", ".join(FAST_BACKGROUND_ONLY_TERMS),
)
