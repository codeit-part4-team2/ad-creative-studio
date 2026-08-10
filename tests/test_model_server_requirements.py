from __future__ import annotations

import re
import tomllib
from pathlib import Path

from packaging.requirements import Requirement
from packaging.utils import canonicalize_name
from packaging.version import Version


EXACT_REQUIREMENT = re.compile(
    r"[A-Za-z0-9_.-]+(?:\[[A-Za-z0-9_,.-]+\])?==[^\s;]+"
)


def _requirement_lines(requirements_file: Path) -> list[str]:
    return [
        line.strip()
        for line in requirements_file.read_text(encoding="utf-8").splitlines()
        if line.strip() and not line.lstrip().startswith("#")
    ]


def test_model_server_direct_dependencies_are_exactly_pinned() -> None:
    requirements_file = Path("model_server/requirements.txt")
    requirements = _requirement_lines(requirements_file)

    assert requirements
    assert all(EXACT_REQUIREMENT.fullmatch(item) for item in requirements)


def test_model_server_pins_satisfy_project_model_constraints() -> None:
    project = tomllib.loads(Path("pyproject.toml").read_text(encoding="utf-8"))
    model_constraints = {
        canonicalize_name(requirement.name): requirement
        for raw in project["project"]["optional-dependencies"]["model"]
        for requirement in [Requirement(raw)]
    }
    exact_pins = {
        canonicalize_name(requirement.name): requirement
        for raw in _requirement_lines(Path("model_server/requirements.txt"))
        for requirement in [Requirement(raw)]
    }

    for name, constraint in model_constraints.items():
        if name not in exact_pins:
            continue
        pin = exact_pins[name]
        pinned_version = next(
            Version(item.version)
            for item in pin.specifier
            if item.operator == "=="
        )
        assert pinned_version in constraint.specifier, (
            f"{pin} does not satisfy project constraint {constraint}"
        )
