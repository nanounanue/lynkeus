"""Pilot helpers and a snapshot fixture for consumers' tests.

Add ``pytest_plugins = ["lynkeus.testing"]`` to a ``conftest.py`` and use::

    def test_runs(shell_snapshot):
        assert shell_snapshot(my_app(), keys=["2"])

``settle`` waits for every thread worker (adapter reads) to finish and the
screen to repaint, which is what makes a snapshot deterministic.
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable, Sequence
from pathlib import Path
from typing import Any

import pytest
from textual.app import App
from textual.pilot import Pilot

SIZE = (110, 34)


async def settle(pilot: Pilot[Any], ticks: int = 3) -> None:
    """Wait for workers, then let the screen repaint."""
    await pilot.app.workers.wait_for_complete()
    for _ in range(ticks):
        await pilot.pause()


async def press(pilot: Pilot[Any], *keys: str) -> None:
    """Press keys, settling after each."""
    for key in keys:
        await pilot.press(key)
        await settle(pilot)


async def screenshot(app: App[Any], path: Path, keys: Sequence[str] = ()) -> Path:
    """Drive ``app`` with ``keys`` and save an SVG screenshot to ``path``."""
    async with app.run_test(size=SIZE) as pilot:
        await settle(pilot)
        await press(pilot, *keys)
        app.save_screenshot(str(path))
    return path


@pytest.fixture
def shell_snapshot(snap_compare: Any) -> Callable[..., bool]:
    """``shell_snapshot(app, keys=[...], before=async fn)`` → snapshot comparison."""

    def compare(
        app: App[Any],
        *,
        keys: Sequence[str] = (),
        size: tuple[int, int] = SIZE,
        before: Callable[[Pilot[Any]], Awaitable[None]] | None = None,
    ) -> bool:
        async def run_before(pilot: Pilot[Any]) -> None:
            await settle(pilot)
            await press(pilot, *keys)
            if before is not None:
                await before(pilot)
                await settle(pilot)

        return snap_compare(app, terminal_size=size, run_before=run_before)

    return compare
