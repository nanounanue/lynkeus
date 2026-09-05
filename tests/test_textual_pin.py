"""The Textual range lynkeus declares is what a consumer can install beside it.

dominoes locks Textual 7.5 for its own table TUI and could not add the shell
while the pin read ``textual<7``: ``uv`` refused to resolve the two together.
These two assertions pin the promise the CHANGELOG makes, so that tightening
the range again is a visible change in this repository rather than a resolver
error in another one.
"""

from __future__ import annotations

from importlib.metadata import requires, version

from packaging.requirements import Requirement

#: The release the sixth consumer locks; the reason the cap moved.
CONSUMER_TEXTUAL = "7.5.0"


def _textual_requirement() -> Requirement:
    parsed = [Requirement(spec) for spec in requires("lynkeus") or ()]
    declared = [requirement for requirement in parsed if requirement.name == "textual"]
    assert len(declared) == 1, f"expected one textual requirement, got {declared}"
    return declared[0]


def test_the_declared_range_admits_the_release_dominoes_locks() -> None:
    requirement = _textual_requirement()
    assert requirement.specifier.contains(CONSUMER_TEXTUAL, prereleases=False), (
        f"lynkeus declares {requirement}, which refuses Textual {CONSUMER_TEXTUAL}"
    )


def test_the_installed_textual_is_inside_the_declared_range() -> None:
    requirement = _textual_requirement()
    installed = version("textual")
    assert requirement.specifier.contains(installed, prereleases=False), (
        f"the environment holds Textual {installed}, outside {requirement}"
    )
