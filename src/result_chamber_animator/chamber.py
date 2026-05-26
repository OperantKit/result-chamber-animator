"""Geometry of the visualised operant chamber.

The chamber is a rectangular box with one or more operanda (levers /
keys) on its front wall and a food hopper centred below them. The
geometry is intentionally minimal — its purpose is pedagogical, not
architectural fidelity to any specific manufacturer's apparatus.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal

__all__ = [
    "Operandum",
    "Chamber",
    "SubjectStyle",
    "default_two_lever_chamber",
]


SubjectStyle = Literal[
    "sphere",
    "rat",
    "pigeon",
    "rat_billboard",
    "pigeon_billboard",
]
_VALID_STYLES: tuple[SubjectStyle, ...] = (
    "sphere",
    "rat",
    "pigeon",
    "rat_billboard",
    "pigeon_billboard",
)


@dataclass(frozen=True)
class Operandum:
    """A lever or key on the chamber's front wall.

    Attributes
    ----------
    key:
        Logical identifier matching the ``chosen_response`` value
        recorded by the simulator (e.g. ``"lever_left"``).
    label:
        Human-readable label shown in the rendered scene.
    position:
        ``(x, y, z)`` coordinates in chamber-local metres of the
        operandum's contact surface.
    """

    key: str
    label: str
    position: tuple[float, float, float]


@dataclass(frozen=True)
class Chamber:
    """Static geometry of a rectangular operant chamber.

    Attributes
    ----------
    size:
        ``(length, width, height)`` of the box, metres.
    operanda:
        Tuple of :class:`Operandum` instances on the front wall.
    hopper_position:
        ``(x, y, z)`` coordinates of the food hopper opening.
    agent_radius:
        Radius of the agent's body sphere, metres.
    """

    size: tuple[float, float, float] = (0.30, 0.25, 0.30)
    operanda: tuple[Operandum, ...] = field(default_factory=tuple)
    hopper_position: tuple[float, float, float] = (0.15, 0.0, 0.05)
    agent_radius: float = 0.05
    subject_style: SubjectStyle = "sphere"

    def __post_init__(self) -> None:
        if self.subject_style not in _VALID_STYLES:
            raise ValueError(
                f"subject_style must be one of {_VALID_STYLES}, "
                f"got {self.subject_style!r}"
            )

    def operandum_keys(self) -> list[str]:
        return [o.key for o in self.operanda]

    def operandum_by_key(self, key: str) -> Operandum:
        for o in self.operanda:
            if o.key == key:
                return o
        raise KeyError(f"unknown operandum key {key!r}")


def default_two_lever_chamber(
    subject_style: SubjectStyle = "sphere",
) -> Chamber:
    """Standard two-lever chamber (left lever / right lever / hopper)."""
    return Chamber(
        size=(0.30, 0.25, 0.30),
        operanda=(
            Operandum(key="lever_left", label="L", position=(0.08, 0.0, 0.15)),
            Operandum(key="lever_right", label="R", position=(0.22, 0.0, 0.15)),
        ),
        hopper_position=(0.15, 0.0, 0.05),
        agent_radius=0.05,
        subject_style=subject_style,
    )
