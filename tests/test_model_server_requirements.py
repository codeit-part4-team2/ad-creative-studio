from __future__ import annotations

import re
from pathlib import Path


EXACT_REQUIREMENT = re.compile(
    r"[A-Za-z0-9_.-]+(?:\[[A-Za-z0-9_,.-]+\])?==[^\s;]+"
)


def test_model_server_direct_dependencies_are_exactly_pinned() -> None:
    requirements_file = Path("model_server/requirements.txt")
    requirements = [
        line.strip()
        for line in requirements_file.read_text(encoding="utf-8").splitlines()
        if line.strip() and not line.lstrip().startswith("#")
    ]

    assert requirements
    assert all(EXACT_REQUIREMENT.fullmatch(item) for item in requirements)
