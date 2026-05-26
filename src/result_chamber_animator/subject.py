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
from functools import lru_cache
from pathlib import Path
from typing import Any

import numpy as np

from result_chamber_animator.chamber import Chamber, SubjectStyle

__all__ = ["draw_subject"]


# Body length (forward span) for billboard variants, metres. Texture aspect
# ratio is preserved: height = body_length * (H_px / W_px).
_BILLBOARD_BODY_LENGTH_M: dict[str, float] = {
    "rat_billboard": 0.18,
    "pigeon_billboard": 0.15,
}

# Sampling grid resolution for textured billboards. The longer image axis
# uses ``_BILLBOARD_GRID_LONG`` cells; the shorter axis is scaled to keep
# square cells in body-local space.
_BILLBOARD_GRID_LONG = 32


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
    subject_assets_dir: Path | None = None,
) -> None:
    """Dispatch to the per-style drawer.

    ``position`` is the subject's floor-contact point. ``facing`` is the
    yaw angle in radians (``0`` points along ``+x``); the subject rotates
    around ``z`` to match. ``scale_pulse`` is a uniform scale multiplier
    used by callers to add a subtle "breathing" effect on free-operant
    filler frames; default ``1.0`` is no pulse.

    ``subject_assets_dir`` is required when ``style`` (or the chamber's
    ``subject_style``) is a ``*_billboard`` variant. The directory must
    contain ``rat_neutral.png`` and/or ``pigeon_neutral.png`` (RGBA, with
    the snout/beak facing the image's left edge and the body upright).
    """
    chosen = style if style is not None else chamber.subject_style
    if chosen == "sphere":
        _draw_sphere(ax, position, chamber.agent_radius)
        return

    if chosen in ("rat_billboard", "pigeon_billboard"):
        species = chosen.split("_", 1)[0]
        texture_path = _resolve_billboard_texture(chosen, subject_assets_dir)
        _draw_billboard_textured(
            ax,
            position,
            facing,
            texture_path=texture_path,
            body_length_m=_BILLBOARD_BODY_LENGTH_M[chosen] * scale_pulse,
            species=species,
        )
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


# ---------------------------------------------------------------------------
# Textured billboard: 2D RGBA sprite standing as a vertical 3D quad
# ---------------------------------------------------------------------------


def _resolve_billboard_texture(
    style: str,
    subject_assets_dir: Path | None,
) -> Path:
    """Locate the RGBA texture for a billboard style under ``subject_assets_dir``.

    Convention: ``<assets_dir>/<species>_neutral.png`` where ``<species>``
    is ``rat`` or ``pigeon``. The texture must depict the animal in side
    profile with the snout/beak facing the image's left edge and the body
    upright (image top = subject's dorsal up).
    """
    if subject_assets_dir is None:
        raise ValueError(
            f"subject_style={style!r} requires subject_assets_dir; pass it via "
            f"render_frame()/animate(), or use a non-billboard subject style."
        )
    species = style.split("_", 1)[0]
    path = subject_assets_dir / f"{species}_neutral.png"
    if not path.exists():
        raise FileNotFoundError(f"billboard texture not found: {path}")
    return path


@lru_cache(maxsize=8)
def _load_texture_rgba(path_str: str) -> np.ndarray:
    """Load an RGBA texture as float32 in ``[0, 1]``; cached by path string."""
    from PIL import Image

    img = Image.open(path_str).convert("RGBA")
    return np.asarray(img, dtype=np.float32) / 255.0


def _draw_billboard_textured(
    ax: Any,
    position: tuple[float, float, float],
    facing: float,
    *,
    texture_path: Path,
    body_length_m: float,
    species: str,
) -> None:
    """Render a textured vertical 3D quad ("billboard") at ``position``.

    The quad stands perpendicular to the floor along the ``facing`` yaw
    (``0`` rad → quad spans ``+x`` / ``-x`` direction). The texture's
    left edge maps to body-local ``+u`` (forward, snout) and top edge
    to ``+v`` (up). Texture aspect ratio is preserved.

    The quad is sampled into a regular grid (``_BILLBOARD_GRID_LONG`` cells
    along the longer texture axis, proportional on the shorter) and rendered
    via :class:`mpl_toolkits.mplot3d.art3d.Poly3DCollection`. Each cell
    receives the per-pixel RGBA colour at its centre, including alpha — so
    transparent background pixels of the source texture are preserved.
    """
    from mpl_toolkits.mplot3d.art3d import Poly3DCollection

    img = _load_texture_rgba(str(texture_path))
    h_px, w_px, _ = img.shape

    # Preserve texture aspect: width = body_length_m, height proportional.
    width_m = body_length_m
    height_m = width_m * (h_px / w_px)

    # Grid resolution: longer axis gets _BILLBOARD_GRID_LONG cells.
    if w_px >= h_px:
        n_u = _BILLBOARD_GRID_LONG
        n_v = max(2, int(round(n_u * h_px / w_px)))
    else:
        n_v = _BILLBOARD_GRID_LONG
        n_u = max(2, int(round(n_v * w_px / h_px)))

    # Body-local grid vertices. Snout (body-local +u extreme) sits at
    # u=0 so that callers passing ``position`` = "subject's snout" line
    # the leading edge up with the operandum, matching the rebase
    # convention used by the top-down silhouette path.
    u = np.linspace(-width_m, 0.0, n_u + 1)
    v = np.linspace(0.0, height_m, n_v + 1)
    U, V = np.meshgrid(u, v)  # (n_v+1, n_u+1)

    # Rotate body-local +u into world (x, y) via facing yaw; +v stays world +z.
    cosa = math.cos(facing)
    sina = math.sin(facing)
    cx, cy, cz = position
    X = cx + U * cosa
    Y = cy + U * sina
    Z = cz + V

    # Per-cell texture sampling. Cell (j, i) center maps to:
    #   forward (i high)  -> image left  (px_x near 0)
    #   up      (j high)  -> image top   (px_y near 0)
    i_idx = np.arange(n_u)
    j_idx = np.arange(n_v)
    px_x = ((1.0 - (i_idx + 0.5) / n_u) * (w_px - 1)).astype(int)
    px_y = ((1.0 - (j_idx + 0.5) / n_v) * (h_px - 1)).astype(int)
    facecolors = img[np.ix_(px_y, px_x)]  # (n_v, n_u, 4) RGBA in [0, 1]

    # Build quad list: one quad per (j, i) cell.
    verts_list: list[list[tuple[float, float, float]]] = []
    colors_list: list[tuple[float, float, float, float]] = []
    for j in range(n_v):
        for i in range(n_u):
            alpha = float(facecolors[j, i, 3])
            if alpha <= 1e-3:
                continue  # skip fully-transparent cells (background)
            quad = [
                (float(X[j, i]),     float(Y[j, i]),     float(Z[j, i])),
                (float(X[j, i + 1]), float(Y[j, i + 1]), float(Z[j, i + 1])),
                (float(X[j + 1, i + 1]), float(Y[j + 1, i + 1]), float(Z[j + 1, i + 1])),
                (float(X[j + 1, i]), float(Y[j + 1, i]), float(Z[j + 1, i])),
            ]
            verts_list.append(quad)
            colors_list.append(
                (
                    float(facecolors[j, i, 0]),
                    float(facecolors[j, i, 1]),
                    float(facecolors[j, i, 2]),
                    alpha,
                )
            )

    if not verts_list:  # fully transparent texture; nothing to draw
        return

    poly = Poly3DCollection(
        verts_list,
        facecolors=colors_list,
        edgecolors="none",
        linewidths=0.0,
    )
    # Tag the species so renderers / debuggers can identify the artist layer.
    poly.set_label(f"{species}_billboard")
    ax.add_collection3d(poly)
