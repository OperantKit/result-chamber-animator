"""Tests for the chamber geometry."""

from __future__ import annotations

import dataclasses

import pytest

from result_chamber_animator.chamber import (
    Chamber,
    Operandum,
    default_two_lever_chamber,
)


def test_default_chamber_has_two_levers():
    ch = default_two_lever_chamber()
    keys = ch.operandum_keys()
    assert keys == ["lever_left", "lever_right"]


def test_operandum_lookup_by_key():
    ch = default_two_lever_chamber()
    op = ch.operandum_by_key("lever_left")
    assert isinstance(op, Operandum)
    assert op.label == "L"


def test_unknown_operandum_raises():
    ch = default_two_lever_chamber()
    with pytest.raises(KeyError):
        ch.operandum_by_key("nope")


def test_chamber_is_frozen():
    ch = default_two_lever_chamber()
    with pytest.raises(dataclasses.FrozenInstanceError):
        ch.size = (1.0, 1.0, 1.0)  # type: ignore[misc]


def test_operanda_within_chamber_box():
    ch = default_two_lever_chamber()
    lx, ly, lz = ch.size
    for op in ch.operanda:
        x, y, z = op.position
        assert 0 <= x <= lx
        assert 0 <= y <= ly
        assert 0 <= z <= lz


def test_custom_chamber_constructor():
    ch = Chamber(
        size=(1.0, 1.0, 1.0),
        operanda=(Operandum(key="k", label="K", position=(0.5, 0.0, 0.5)),),
        hopper_position=(0.5, 0.0, 0.1),
        agent_radius=0.1,
    )
    assert ch.operandum_keys() == ["k"]


def test_default_subject_style_is_sphere():
    ch = default_two_lever_chamber()
    assert ch.subject_style == "sphere"


def test_subject_style_override_via_factory():
    for style in ("sphere", "rat", "pigeon"):
        ch = default_two_lever_chamber(subject_style=style)
        assert ch.subject_style == style


def test_invalid_subject_style_raises():
    with pytest.raises(ValueError, match="subject_style"):
        Chamber(
            operanda=(Operandum(key="k", label="K", position=(0.5, 0.0, 0.5)),),
            subject_style="alien",  # type: ignore[arg-type]
        )
