"""The dependency range a consumer can rely on."""

from __future__ import annotations

import tomllib
from pathlib import Path

from packaging.requirements import Requirement
from packaging.version import Version


def _runtime_requirement(name: str) -> Requirement:
    text = (Path(__file__).parents[1] / "pyproject.toml").read_text()
    pyproject = tomllib.loads(text)
    for spec in pyproject["project"]["dependencies"]:
        requirement = Requirement(spec)
        if requirement.name == name:
            return requirement
    raise AssertionError(f"{name} is not a runtime dependency")


def test_textual_8_is_admitted_and_the_floor_stays() -> None:
    """azmu's TUI is written against Textual 8; the consumers on 1.0.0 run 6.

    A shell that refuses either cannot be the one shell those projects share.
    """
    textual = _runtime_requirement("textual").specifier
    assert Version("8.2.8") in textual
    assert Version("6.5") in textual
