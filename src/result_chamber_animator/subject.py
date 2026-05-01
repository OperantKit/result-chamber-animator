"""Top-down 2D-silhouette drawings of the experimental subject.

The chamber is rendered in 3D (wireframe + operanda + hopper) but the
subject is a 2D illustration laid flat on the chamber floor and rotated
around the vertical axis to face its target. This is the
Live2D / VTuber idiom — a 2D rigged sprite rendered inside a 3D scene —
adapted for textbook-style operant-chamber visualisation.

The silhouettes are encoded in a body-local ``(x, y)`` frame:

* ``+x`` points toward the snout / beak (the subject's forward direction).
* ``+y`` is the subject's left side.
* The origin ``(0, 0)`` is the body centroid (floor-contact point in 3D).

When rendered, the polygon is rotated by the ``facing`` yaw angle
around ``z`` and translated to the subject's world position, then drawn
as a flat polygon at ``z = floor + ε`` using
:class:`mpl_toolkits.mplot3d.art3d.Poly3DCollection`. A small scale
pulse can be applied on free-operant filler frames to give a subtle
"breathing" feel.

References for the silhouette proportions:

* Wikipedia: Operant conditioning chamber.
* Skinner, B. F. (1948). 'Superstition' in the pigeon.
  *Journal of Experimental Psychology*, *38*(2), 168-172.
  https://doi.org/10.1037/h0055873
"""

from __future__ import annotations

import math
from typing import Any

import numpy as np

from result_chamber_animator.chamber import Chamber, SubjectStyle

__all__ = ["draw_subject"]


# ---------------------------------------------------------------------------
# Top-down silhouette vertex arrays (body-local, normalized so head-to-rump = 1)
# ---------------------------------------------------------------------------
# Closed contours, traced clockwise from the snout / beak.
# Coordinate system: +x = forward, +y = subject's left.

RAT_TOPDOWN = np.array(
    [
        # Snout / head — right side of body (+y direction by convention,
        # but since the silhouette is symmetric we trace the +y side first
        # going clockwise as seen from above (+z)).
        (0.55, 0.0),     # snout tip
        (0.50, 0.05),    # snout right
        (0.45, 0.10),    # cheek
        (0.40, 0.16),    # head right
        (0.36, 0.20),    # ear right
        (0.30, 0.18),    # ear back right
        # Shoulder / body widening
        (0.22, 0.18),
        (0.10, 0.20),
        # Hip / widest point
        (-0.05, 0.22),
        (-0.20, 0.22),
        (-0.32, 0.18),
        # Rump
        (-0.40, 0.10),
        # Tail (right edge — tapering)
        (-0.45, 0.04),
        (-0.65, 0.025),
        (-0.90, 0.018),
        (-1.10, 0.012),
        (-1.20, 0.005),  # tail tip right
        # Tail tip left + tail (left edge)
        (-1.20, -0.005),
        (-1.10, -0.012),
        (-0.90, -0.018),
        (-0.65, -0.025),
        (-0.45, -0.04),
        # Rump (left)
        (-0.40, -0.10),
        (-0.32, -0.18),
        (-0.20, -0.22),
        (-0.05, -0.22),
        (0.10, -0.20),
        (0.22, -0.18),
        # Ear left
        (0.30, -0.18),
        (0.36, -0.20),
        (0.40, -0.16),
        (0.45, -0.10),
        (0.50, -0.05),
        (0.55, 0.0),     # close back to snout
    ]
)


PIGEON_TOPDOWN = np.array(
    [
        # Beak (pointed cone shape)
        (0.60, 0.0),     # beak tip
        (0.55, 0.03),
        (0.48, 0.07),
        # Head (round, blends smoothly into body — no neck dip from above)
        (0.42, 0.13),
        (0.38, 0.18),
        # Shoulder / wing leading edge — outline widens continuously
        (0.28, 0.22),
        (0.15, 0.25),
        # Wing curve (folded along flank)
        (0.0, 0.27),
        (-0.18, 0.26),
        (-0.32, 0.22),
        # Tail fan (right side)
        (-0.45, 0.18),
        (-0.58, 0.13),
        (-0.68, 0.07),
        (-0.72, 0.02),
        # Tail centre
        (-0.72, -0.02),
        # Tail fan (left)
        (-0.68, -0.07),
        (-0.58, -0.13),
        (-0.45, -0.18),
        (-0.32, -0.22),
        (-0.18, -0.26),
        (0.0, -0.27),
        (0.15, -0.25),
        (0.28, -0.22),
        (0.38, -0.18),
        (0.42, -0.13),
        (0.48, -0.07),
        (0.55, -0.03),
        (0.60, 0.0),     # close back to beak
    ]
)


# ---------------------------------------------------------------------------
# Public dispatch
# ---------------------------------------------------------------------------


def draw_subject(
    ax: Any,
    chamber: Chamber,
    position: tuple[float, float, float],
    facing: float,
    *,
    style: SubjectStyle | None = None,
    scale_pulse: float = 1.0,
) -> None:
    """Dispatch to the per-style drawer.

    ``position`` is the subject's floor-contact point; the silhouette is
    drawn flat at ``z = position.z + ε``. ``facing`` is the yaw angle
    in radians (``0`` points along ``+x``); the silhouette rotates around
    ``z`` to match. ``scale_pulse`` is a uniform ``xy``-scale multiplier
    used by callers to add a subtle "breathing" effect on free-operant
    filler frames; default ``1.0`` is no pulse.
    """
    chosen = style if style is not None else chamber.subject_style
    if chosen == "sphere":
        _draw_sphere(ax, position, chamber.agent_radius)
        return

    if chosen == "rat":
        silhouette = RAT_TOPDOWN
        face_color = "#3a3a3a"
        scale_factor = 0.11  # body+tail fits within the 0.30 m chamber
    elif chosen == "pigeon":
        silhouette = PIGEON_TOPDOWN
        face_color = "#5b6878"
        scale_factor = 0.13
    else:
        raise ValueError(f"unsupported subject style: {chosen!r}")

    _draw_topdown_silhouette(
        ax,
        position,
        facing,
        silhouette=silhouette,
        scale=scale_factor * scale_pulse,
        face_color=face_color,
    )


# ---------------------------------------------------------------------------
# Sphere baseline
# ---------------------------------------------------------------------------


def _draw_sphere(
    ax: Any, position: tuple[float, float, float], radius: float
) -> None:
    cx, cy, cz = position
    u = np.linspace(0, 2 * np.pi, 16)
    v = np.linspace(0, np.pi, 8)
    sx = radius * np.outer(np.cos(u), np.sin(v))
    sy = radius * np.outer(np.sin(u), np.sin(v))
    sz = radius * np.outer(np.ones_like(u), np.cos(v))
    ax.plot_surface(
        sx + cx,
        sy + cy,
        sz + cz + radius,  # sit on floor
        color="saddlebrown",
        alpha=0.65,
        linewidth=0,
    )


# ---------------------------------------------------------------------------
# Top-down silhouette: 2D in xy plane, yaw-rotated, billboarded onto floor
# ---------------------------------------------------------------------------


def _draw_topdown_silhouette(
    ax: Any,
    position: tuple[float, float, float],
    facing: float,
    *,
    silhouette: np.ndarray,
    scale: float,
    face_color: str,
) -> None:
    """Draw a top-down body-frame silhouette as a flat polygon on the floor.

    The silhouette is rebased so the snout/beak (its body-frame ``+x``
    extreme) lies on the body's anchor; this lets ``position`` mean
    "the subject's nose is here", which lines up with the operandum the
    subject is pressing.
    """
    from mpl_toolkits.mplot3d.art3d import Poly3DCollection

    cx, cy, cz = position

    # Rebase: subtract the silhouette's max-x so the snout sits at body
    # frame x=0; the rest of the body extends in -x.
    rebased = silhouette.copy()
    rebased[:, 0] -= float(rebased[:, 0].max())

    cosa, sina = math.cos(facing), math.sin(facing)
    bx = rebased[:, 0]
    by = rebased[:, 1]
    rx = cosa * bx - sina * by
    ry = sina * bx + cosa * by

    n = len(bx)
    world_x = cx + rx * scale
    world_y = cy + ry * scale
    world_z = np.full(n, cz + 0.003)  # tiny lift so the polygon shows above the floor

    verts_3d = np.column_stack([world_x, world_y, world_z])
    poly = Poly3DCollection(
        [verts_3d],
        facecolor=face_color,
        edgecolor="black",
        linewidth=0.7,
        alpha=0.95,
    )
    ax.add_collection3d(poly)
