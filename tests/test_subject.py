"""Tests for stylized subject drawings (sphere / rat / pigeon)."""

from __future__ import annotations

import matplotlib

matplotlib.use("Agg")

import matplotlib.pyplot as plt  # noqa: E402
import pytest  # noqa: E402

from result_chamber_animator.chamber import (  # noqa: E402
    Chamber,
    Operandum,
    default_two_lever_chamber,
)
from result_chamber_animator.subject import draw_subject  # noqa: E402


@pytest.fixture(autouse=True)
def _close_after_test():
    yield
    plt.close("all")


def _new_3d_axes():
    fig = plt.figure(figsize=(4, 3))
    return fig, fig.add_subplot(111, projection="3d")


@pytest.mark.parametrize("style", ["sphere", "rat", "pigeon"])
def test_draw_subject_does_not_raise(style):
    chamber = default_two_lever_chamber(subject_style=style)
    _, ax = _new_3d_axes()
    draw_subject(ax, chamber, position=(0.15, 0.10, 0.10), facing=-1.5708)


def test_draw_subject_explicit_style_overrides_chamber():
    chamber = default_two_lever_chamber(subject_style="sphere")
    _, ax = _new_3d_axes()
    # Should not raise; rat drawer uses different primitives.
    draw_subject(
        ax, chamber, position=(0.15, 0.10, 0.10), facing=0.0, style="rat"
    )


def test_draw_subject_unknown_style_raises_via_chamber_validation():
    # Chamber.__post_init__ rejects unknown style at construction time, so
    # draw_subject is never reached with an invalid string from the chamber.
    with pytest.raises(ValueError, match="subject_style"):
        Chamber(
            operanda=(Operandum(key="k", label="K", position=(0.0, 0.0, 0.0)),),
            subject_style="unicorn",  # type: ignore[arg-type]
        )


def test_draw_subject_unknown_style_via_explicit_override_raises():
    chamber = default_two_lever_chamber()
    _, ax = _new_3d_axes()
    with pytest.raises(ValueError, match="unsupported"):
        draw_subject(
            ax, chamber, position=(0.0, 0.0, 0.0), facing=0.0, style="unicorn"  # type: ignore[arg-type]
        )
