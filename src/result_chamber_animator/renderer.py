"""3D rendering and animation of recorded operant-chamber step records.

Frame model
-----------
Each step is a :class:`StepFrame` carrying:

* ``step`` — integer step index
* ``chosen_response`` — operandum key the agent pressed
* ``is_reinforced`` — whether reinforcement was delivered
* ``timestamp`` — canonical seconds (``step * dt``)

A scene composes the static
:class:`~result_chamber_animator.chamber.Chamber` geometry with a moving
agent body. Each step's render moves the agent toward the operandum
that was pressed; reinforcement causes a hopper flash.

Optional **inter-event behaviour synthesis**
(``inject_inter_event_behavior=True``) inserts filler sub-frames
between recorded steps and assigns each filler to one of three
behaviour-analytic phases, following the post-Skinnerian taxonomy of
schedule-induced behaviour:

* **Adjunctive / post-reinforcement** (Falk, 1961, 1971): the period
  immediately following a reinforcer, when the subject typically
  contacts the food magazine, drinks (polydipsia), or grooms. Rendered
  near the hopper.
* **Interim** (Staddon & Simmelhag, 1971; Timberlake & Lucas, 1985):
  the middle of an inter-event gap, when the subject is doing
  schedule-induced wandering or displacement-like activities not
  directly tied to the contingency. Rendered drifting around the
  chamber centre.
* **Terminal** (Staddon & Simmelhag, 1971): the period just before the
  next response, when the subject is oriented toward and approaching
  the operandum. Rendered interpolating toward the next pressed key.

These filler frames do **not** correspond to recorded events — they
are visual filler driven by a behaviour-systems model of the inter-
event interval. The recorded reinforcement flash fires only on the
actual recorded step. Turn injection off whenever the visualisation
must match the record 1:1.

References
----------
Falk, J. L. (1961). Production of polydipsia in normal rats by an
intermittent food schedule. *Science*, *133*(3447), 195-196.
https://doi.org/10.1126/science.133.3447.195

Falk, J. L. (1971). The nature and determinants of adjunctive
behavior. *Physiology & Behavior*, *6*(5), 577-588.
https://doi.org/10.1016/0031-9384(71)90209-5

Staddon, J. E. R., & Simmelhag, V. L. (1971). The "superstition"
experiment: A reexamination of its implications for the principles of
adaptive behavior. *Psychological Review*, *78*(1), 3-43.
https://doi.org/10.1037/h0030305

Timberlake, W., & Lucas, G. A. (1985). The basis of superstitious
behavior: Chance contingency, stimulus substitution, or appetitive
behavior? *Journal of the Experimental Analysis of Behavior*, *44*(3),
279-299. https://doi.org/10.1901/jeab.1985.44-279
"""

from __future__ import annotations

import math
from collections.abc import Iterable
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from result_chamber_animator.chamber import Chamber, default_two_lever_chamber
from result_chamber_animator.subject import draw_subject

__all__ = [
    "StepFrame",
    "render_frame",
    "animate",
    "steps_from_dataframe",
]


#: Sentinel ``chosen_response`` values for non-response events.
HOPPER_KEY = "<hopper>"
REST_KEY = "<rest>"


@dataclass(frozen=True)
class StepFrame:
    """One step's worth of state for the renderer.

    ``event_type`` distinguishes recorded events. Defaults to
    ``"response"`` so producers that emit only response rows keep
    working unchanged. OKL v1 replay populates the full set:
    ``response`` / ``reinforcer_start`` / ``reinforcer_end`` /
    ``component_change`` / ``state_change``.

    ``component`` is the active multiple-schedule component context
    (``"C1"`` / ``"C2"`` / ``"ICI"`` / ``"INIT"``) at the time of the
    event, used by the renderer to grey out operanda when the schedule
    is inactive.
    """

    step: int
    chosen_response: str
    is_reinforced: bool
    timestamp: float = 0.0
    event_type: str = "response"
    component: str | None = None


def steps_from_dataframe(
    df: pd.DataFrame,
    *,
    dt: float = 1.0,
) -> list[StepFrame]:
    """Convert a tabular session record to :class:`StepFrame` records.

    Required columns: ``step``, ``chosen_response``, ``is_reinforced``.
    Optional columns (used for OKL v1 replay):

    * ``timestamp`` — real session timestamp in seconds. When present,
      overrides the synthetic ``step * dt`` value.
    * ``event_type`` — see :class:`StepFrame`.
    * ``component`` — see :class:`StepFrame`.
    """
    required = {"step", "chosen_response", "is_reinforced"}
    missing = required - set(df.columns)
    if missing:
        raise ValueError(f"DataFrame missing required columns: {sorted(missing)}")

    has_ts = "timestamp" in df.columns
    has_evt = "event_type" in df.columns
    has_comp = "component" in df.columns

    frames: list[StepFrame] = []
    for _, row in df.iterrows():
        step = int(row["step"])
        if has_ts and pd.notna(row["timestamp"]):
            ts = float(row["timestamp"])
        else:
            ts = float(step + 1) * dt
        evt_type = str(row["event_type"]) if has_evt and pd.notna(row["event_type"]) else "response"
        comp_val = row["component"] if has_comp else None
        comp = str(comp_val) if comp_val is not None and pd.notna(comp_val) else None
        frames.append(
            StepFrame(
                step=step,
                chosen_response=str(row["chosen_response"]),
                is_reinforced=bool(row["is_reinforced"]),
                timestamp=ts,
                event_type=evt_type,
                component=comp,
            )
        )
    return frames


# ---------------------------------------------------------------------------
# Internal: per-render-frame spec, possibly synthesised
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class _FrameSpec:
    base: StepFrame
    position: tuple[float, float, float]
    facing: float
    is_filler: bool = False
    active_key: str | None = None  # operandum to highlight (None during filler)
    scale_pulse: float = 1.0  # Live2D-style breathing factor on filler frames
    phase: str = "recorded"  # "recorded" | "adjunctive" | "interim" | "terminal"


def _agent_position_for(chamber: Chamber, key: str) -> tuple[float, float, float]:
    """Snout / nose position for a subject contacting ``key``.

    The convention is **subject's leading edge** = where the snout (rat)
    or beak (pigeon) lands on the operandum. The 2D silhouette is
    rebased internally so its nose sits at this point and the body
    extends backward into the chamber.

    Special sentinels:

    * :data:`HOPPER_KEY` (``"<hopper>"``) — anchor at the food magazine
      (used for ``reinforcer_start`` / ``reinforcer_end`` events and the
      adjunctive phase).
    * :data:`REST_KEY` (``"<rest>"``) — anchor at the chamber wall midway
      back from the operandum panel (used for non-positional events
      like ``state_change`` / ``component_change`` when no recent
      response anchors the subject elsewhere).
    """
    if key == HOPPER_KEY:
        return _hopper_anchor(chamber)
    if key == REST_KEY:
        # Default rest position: just behind the centre of the operandum panel.
        lx, _ly, _ = chamber.size
        return (lx / 2.0, 0.10, 0.0)
    op = chamber.operandum_by_key(key)
    ox, oy, _ = op.position
    return (ox, oy + 0.02, 0.0)


def _facing_toward_operandum(
    pos: tuple[float, float, float],
    operandum_position: tuple[float, float, float],
) -> float:
    dx = operandum_position[0] - pos[0]
    dy = operandum_position[1] - pos[1]
    if dx == 0.0 and dy == 0.0:
        return -math.pi / 2  # face -y by default (operanda are on +y=0 wall)
    return math.atan2(dy, dx)


def _spec_for_recorded(chamber: Chamber, frame: StepFrame) -> _FrameSpec:
    """Build a render spec for a recorded event (non-filler).

    Dispatches on :attr:`StepFrame.event_type` so OKL v1 replay can
    render reinforcer / component / state events alongside responses.
    """
    pos = _agent_position_for(chamber, frame.chosen_response)
    is_response = frame.event_type == "response"
    is_reinforcer = frame.event_type in ("reinforcer_start", "reinforcer_end")

    # Active operandum highlight: only meaningful for response events.
    active_key: str | None
    if is_response:
        active_key = frame.chosen_response
    else:
        active_key = None

    # Facing: face the operandum if a response, the hopper if reinforcer,
    # the panel if at rest.
    if is_response:
        op_pos = chamber.operandum_by_key(frame.chosen_response).position
        facing = _facing_toward_operandum(pos, op_pos)
    elif is_reinforcer:
        facing = _facing_toward_operandum(pos, chamber.hopper_position)
    else:
        facing = -math.pi / 2  # face the operandum panel (-y direction)

    return _FrameSpec(
        base=frame,
        position=pos,
        facing=facing,
        is_filler=False,
        active_key=active_key,
        phase=frame.event_type,
    )


def _classify_phase(
    t: float,
    last_sr_t: float,
    next_response_t: float,
    *,
    adjunctive_window_s: float,
    terminal_window_s: float,
) -> str:
    """Classify a filler timestamp into adjunctive / interim / terminal.

    Precedence (Falk 1961/1971 + Staddon & Simmelhag 1971):

    1. If a reinforcer was delivered within ``adjunctive_window_s``
       before ``t``, the phase is **adjunctive** (subject lingering at
       the magazine, drinking, grooming).
    2. Otherwise, if the next recorded response is within
       ``terminal_window_s`` after ``t``, the phase is **terminal**
       (subject orienting toward / approaching the operandum).
    3. Otherwise, the phase is **interim** (schedule-induced
       wandering, displacement activities).
    """
    if math.isfinite(last_sr_t) and (t - last_sr_t) <= adjunctive_window_s:
        return "adjunctive"
    if (next_response_t - t) <= terminal_window_s:
        return "terminal"
    return "interim"


def _hopper_anchor(chamber: Chamber) -> tuple[float, float, float]:
    """Floor-contact point in front of the food magazine (adjunctive zone)."""
    hx, hy, _ = chamber.hopper_position
    return (hx, hy + 0.05, 0.0)


def _chamber_center(chamber: Chamber) -> tuple[float, float, float]:
    """Floor-contact point in the chamber centre (legacy fallback only)."""
    lx, ly, _ = chamber.size
    return (lx / 2.0, ly / 2.0, 0.0)


def _wall_path_point(
    chamber: Chamber, s: float
) -> tuple[float, float, float]:
    """Parametric point on the chamber's interior perimeter.

    ``s ∈ [0, 1)`` traces the wall counter-clockwise as viewed from
    above, anchored at a 5-cm interior offset from each wall (so the
    subject's body never clips through the wireframe). Used to model
    rat/pigeon thigmotaxic locomotion (Treit & Fundytus, 1988) during
    the interim phase of inter-event filler frames.
    """
    lx, ly, _ = chamber.size
    margin = 0.05
    s = s % 1.0
    if s < 0.25:
        u = s / 0.25
        return (margin + (lx - 2 * margin) * u, margin, 0.0)
    if s < 0.50:
        u = (s - 0.25) / 0.25
        return (lx - margin, margin + (ly - 2 * margin) * u, 0.0)
    if s < 0.75:
        u = (s - 0.50) / 0.25
        return (lx - margin - (lx - 2 * margin) * u, ly - margin, 0.0)
    u = (s - 0.75) / 0.25
    return (margin, ly - margin - (ly - 2 * margin) * u, 0.0)


def _facing_along_wall(s: float) -> float:
    """Yaw angle tangent to the wall-following parametric path at ``s``.

    Subject faces the direction of motion along the perimeter walk.
    """
    s = s % 1.0
    if s < 0.25:
        return 0.0  # +x along bottom wall
    if s < 0.50:
        return math.pi / 2  # +y along right wall
    if s < 0.75:
        return math.pi  # -x along top wall
    return -math.pi / 2  # -y along left wall


def _operandum_position_or_none(
    chamber: Chamber, key: str
) -> tuple[float, float, float] | None:
    if key in (HOPPER_KEY, REST_KEY):
        return None
    try:
        return chamber.operandum_by_key(key).position
    except KeyError:
        return None


def _expand_with_inter_event_behavior(
    frames: list[StepFrame],
    chamber: Chamber,
    *,
    filler_density_per_s: float,
    long_gap_threshold_s: float,
    max_fillers_per_gap: int,
    adjunctive_window_s: float,
    terminal_window_s: float,
    jitter_amplitude: float,
    seed: int | None,
) -> list[_FrameSpec]:
    """Expand a recorded sequence by inserting phase-classified filler frames.

    Filler density is **proportional to real time**: each gap of length
    ``Δt`` between consecutive recorded events receives
    ``min(max_fillers_per_gap, int(Δt * filler_density_per_s))`` filler
    frames, with gaps shorter than ``long_gap_threshold_s`` getting
    none. This keeps the visualisation honest to the OKL session
    timeline — a 60-s ICI gets many filler frames, while a 0.1-s
    response burst gets zero.

    Phase positioning (literature-grounded; see
    ``.local/reference/ici-behavior/``):

    * **Adjunctive** — at/near the food magazine. Falk (1961, 1971);
      Schlinger et al. (2008).
    * **Interim** — wall-following thigmotaxic locomotion along the
      chamber perimeter. Treit & Fundytus (1988); Anderson &
      Shettleworth (1977).
    * **Terminal** — linear approach to the next pressed operandum.
      Staddon & Simmelhag (1971).
    """
    if filler_density_per_s < 0:
        raise ValueError(
            f"filler_density_per_s must be >= 0, got {filler_density_per_s!r}"
        )
    if max_fillers_per_gap < 0:
        raise ValueError(
            f"max_fillers_per_gap must be >= 0, got {max_fillers_per_gap!r}"
        )

    rng = np.random.default_rng(seed)
    out: list[_FrameSpec] = []

    last_sr_t = float("-inf")
    hopper = _hopper_anchor(chamber)

    for i, frame in enumerate(frames):
        out.append(_spec_for_recorded(chamber, frame))
        if frame.is_reinforced or frame.event_type == "reinforcer_start":
            last_sr_t = frame.timestamp

        if i + 1 >= len(frames):
            continue

        nxt = frames[i + 1]
        t0 = frame.timestamp
        t1 = nxt.timestamp
        gap_s = max(0.0, t1 - t0)

        if gap_s < long_gap_threshold_s:
            continue
        n_fillers = min(
            max_fillers_per_gap, int(round(gap_s * filler_density_per_s))
        )
        if n_fillers <= 0:
            continue

        # Anchor positions for the gap.
        p_next = _agent_position_for(chamber, nxt.chosen_response)
        op_next_pos = _operandum_position_or_none(chamber, nxt.chosen_response)

        # Random starting phase angle on the wall path so successive gaps
        # don't all start the wall-walk at the same corner.
        wall_s_offset = float(rng.uniform(0.0, 1.0))

        for k in range(1, n_fillers + 1):
            tau = k / (n_fillers + 1)
            t_filler = t0 + gap_s * tau
            phase = _classify_phase(
                t_filler,
                last_sr_t,
                t1,
                adjunctive_window_s=adjunctive_window_s,
                terminal_window_s=terminal_window_s,
            )

            if phase == "adjunctive":
                base_pos = hopper
                facing = _facing_toward_operandum(base_pos, chamber.hopper_position)
            elif phase == "terminal":
                # Linear approach from the most recent anchor to p_next over
                # the terminal window.
                start = (
                    hopper
                    if math.isfinite(last_sr_t)
                    and (t_filler - last_sr_t)
                    <= adjunctive_window_s + terminal_window_s
                    else _wall_path_point(chamber, wall_s_offset)
                )
                t_term = max(
                    0.0,
                    min(1.0, (terminal_window_s - (t1 - t_filler)) / terminal_window_s),
                )
                base_pos = (
                    start[0] + (p_next[0] - start[0]) * t_term,
                    start[1] + (p_next[1] - start[1]) * t_term,
                    start[2],
                )
                facing = (
                    _facing_toward_operandum(base_pos, op_next_pos)
                    if op_next_pos is not None
                    else -math.pi / 2
                )
            else:  # interim — thigmotaxic wall-following
                # Walk roughly half of the perimeter across the gap, with a
                # random starting offset so trajectories vary between gaps.
                wall_s = wall_s_offset + 0.5 * tau
                base_pos = _wall_path_point(chamber, wall_s)
                facing = _facing_along_wall(wall_s)

            jitter = rng.uniform(-jitter_amplitude, jitter_amplitude, size=2)
            x = base_pos[0] + float(jitter[0])
            y = base_pos[1] + float(jitter[1])
            z = base_pos[2]

            pulse = 1.0 + 0.04 * math.sin(math.pi * tau)

            out.append(
                _FrameSpec(
                    base=frame,
                    position=(x, y, z),
                    facing=facing,
                    is_filler=True,
                    active_key=None,
                    scale_pulse=pulse,
                    phase=phase,
                )
            )

    return out


# ---------------------------------------------------------------------------
# Geometry helpers
# ---------------------------------------------------------------------------


def _draw_chamber_wireframe(ax: Any, chamber: Chamber) -> None:
    lx, ly, lz = chamber.size
    corners = np.array(
        [
            [0, 0, 0], [lx, 0, 0], [lx, ly, 0], [0, ly, 0],
            [0, 0, lz], [lx, 0, lz], [lx, ly, lz], [0, ly, lz],
        ]
    )
    edges = [
        (0, 1), (1, 2), (2, 3), (3, 0),
        (4, 5), (5, 6), (6, 7), (7, 4),
        (0, 4), (1, 5), (2, 6), (3, 7),
    ]
    for i, j in edges:
        ax.plot(
            [corners[i, 0], corners[j, 0]],
            [corners[i, 1], corners[j, 1]],
            [corners[i, 2], corners[j, 2]],
            color="black",
            linewidth=0.7,
        )


def _draw_operanda(ax: Any, chamber: Chamber, *, active_key: str | None = None) -> None:
    for op in chamber.operanda:
        x, y, z = op.position
        color = "red" if op.key == active_key else "gray"
        size = 200 if op.key == active_key else 100
        ax.scatter([x], [y], [z], s=size, c=color, edgecolors="black", linewidths=1.0)
        ax.text(x, y - 0.02, z + 0.02, op.label, fontsize=10)


def _draw_hopper(ax: Any, chamber: Chamber, *, flash: bool = False) -> None:
    x, y, z = chamber.hopper_position
    color = "yellow" if flash else "lightgray"
    size = 350 if flash else 150
    ax.scatter(
        [x], [y], [z],
        s=size, c=color, marker="s", edgecolors="black", linewidths=1.0,
    )


# ---------------------------------------------------------------------------
# Public rendering API
# ---------------------------------------------------------------------------


def render_frame(
    frame: StepFrame,
    *,
    chamber: Chamber | None = None,
    ax: Any | None = None,
    subject_assets_dir: Path | None = None,
) -> Any:
    """Render a single :class:`StepFrame` onto a 3D axes.

    Returns the matplotlib axes used. Intended for static figures and as
    the per-frame callback for recorded-only animations. Uses the
    chamber's ``subject_style`` to draw the subject.

    ``subject_assets_dir`` is forwarded to
    :func:`~result_chamber_animator.subject.draw_subject` and is required
    when the chamber's ``subject_style`` is a ``*_billboard`` variant.
    """
    if chamber is None:
        chamber = default_two_lever_chamber()
    spec = _spec_for_recorded(chamber, frame)
    return _render_spec(
        spec, chamber=chamber, ax=ax, subject_assets_dir=subject_assets_dir
    )


def _render_spec(
    spec: _FrameSpec,
    *,
    chamber: Chamber,
    ax: Any | None,
    subject_assets_dir: Path | None = None,
) -> Any:
    import matplotlib.pyplot as plt
    from mpl_toolkits.mplot3d import Axes3D  # noqa: F401

    if ax is None:
        fig = plt.figure(figsize=(6, 5))
        ax = fig.add_subplot(111, projection="3d")
    else:
        ax.cla()

    _draw_chamber_wireframe(ax, chamber)
    _draw_operanda(ax, chamber, active_key=spec.active_key)
    flash = spec.base.is_reinforced and not spec.is_filler
    _draw_hopper(ax, chamber, flash=flash)
    draw_subject(
        ax,
        chamber,
        spec.position,
        spec.facing,
        scale_pulse=spec.scale_pulse,
        subject_assets_dir=subject_assets_dir,
    )

    lx, ly, lz = chamber.size
    ax.set_xlim(0, lx)
    ax.set_ylim(0, ly)
    ax.set_zlim(0, lz)
    ax.set_xlabel("x (m)")
    ax.set_ylabel("y (m)")
    ax.set_zlabel("z (m)")

    comp = f"  comp={spec.base.component}" if spec.base.component else ""
    if spec.is_filler:
        ax.set_title(
            f"t≈{spec.base.timestamp:.1f}s  ({spec.phase}){comp}"
        )
    else:
        sr_tag = " +SR" if spec.base.is_reinforced else ""
        evt = spec.base.event_type
        if evt == "response":
            detail = f"resp={spec.base.chosen_response}{sr_tag}"
        elif evt == "reinforcer_start":
            detail = "reinforcer_start"
        elif evt == "reinforcer_end":
            detail = "reinforcer_end"
        else:
            detail = evt
        ax.set_title(
            f"t={spec.base.timestamp:.1f}s  {detail}{comp}"
        )
    return ax


def animate(
    frames: Iterable[StepFrame],
    *,
    chamber: Chamber | None = None,
    output_path: str | Path | None = None,
    interval_ms: int = 100,
    fps: int = 10,
    inject_inter_event_behavior: bool = False,
    filler_density_per_s: float = 0.5,
    long_gap_threshold_s: float = 2.0,
    max_fillers_per_gap: int = 30,
    adjunctive_window_s: float = 3.0,
    terminal_window_s: float = 1.5,
    jitter_amplitude: float = 0.005,
    seed: int | None = None,
    subject_assets_dir: Path | None = None,
) -> Any:
    """Build a matplotlib :class:`FuncAnimation` over a sequence of frames.

    Parameters
    ----------
    frames:
        Iterable of :class:`StepFrame`.
    chamber:
        Optional :class:`Chamber`. Defaults to the canonical two-lever
        chamber (``subject_style="sphere"``).
    output_path:
        Where to save the rendered animation. ``None`` = no save. If
        provided, must end in ``.mp4`` (FFmpeg, primary) or ``.gif``
        (Pillow, fallback).
    interval_ms:
        Inter-frame delay during live playback (ms).
    fps:
        Frames-per-second for saved files.
    inject_inter_event_behavior:
        When ``True``, synthesise filler frames between recorded events
        and assign each to one of three behaviour-analytic phases —
        **adjunctive** / **interim** / **terminal** — following Falk
        (1961, 1971), Staddon & Simmelhag (1971), Anderson &
        Shettleworth (1977), and Treit & Fundytus (1988). See module
        docstring for details. Filler frames do **not** correspond to
        recorded events; the reinforcement flash fires only on the
        original recorded step. Off by default for strict
        frame-to-record fidelity.
    filler_density_per_s:
        Filler frames per second of real session time. A 60-s ICI at
        density ``0.5`` produces 30 filler frames. Total per-gap count
        is clamped by ``max_fillers_per_gap``.
    long_gap_threshold_s:
        Gaps shorter than this (seconds) skip filler entirely — useful
        for ignoring response bursts where consecutive responses are
        milliseconds apart.
    max_fillers_per_gap:
        Hard upper bound on filler frames per gap. Prevents huge
        ICI / timeout periods from dominating the frame count.
    adjunctive_window_s:
        Seconds after a reinforcer during which fillers are classified
        as **adjunctive** (subject at the hopper). Default ``3.0``.
    terminal_window_s:
        Seconds before the next recorded response during which fillers
        are classified as **terminal** (subject approaching the next
        operandum). Default ``1.5``. Adjunctive precedes terminal at
        their boundary — the magazine-orienting phase wins for short
        inter-event intervals.
    jitter_amplitude:
        Maximum random offset (metres) added to interpolated subject
        positions on filler frames. ``0.0`` = no jitter.
    seed:
        Optional RNG seed for the position jitter.
    """
    import matplotlib.pyplot as plt
    from matplotlib.animation import FuncAnimation
    from mpl_toolkits.mplot3d import Axes3D  # noqa: F401

    if chamber is None:
        chamber = default_two_lever_chamber()

    frame_list = list(frames)
    if not frame_list:
        raise ValueError("animate(): frames is empty")

    if inject_inter_event_behavior:
        specs = _expand_with_inter_event_behavior(
            frame_list,
            chamber,
            filler_density_per_s=filler_density_per_s,
            long_gap_threshold_s=long_gap_threshold_s,
            max_fillers_per_gap=max_fillers_per_gap,
            adjunctive_window_s=adjunctive_window_s,
            terminal_window_s=terminal_window_s,
            jitter_amplitude=jitter_amplitude,
            seed=seed,
        )
    else:
        specs = [_spec_for_recorded(chamber, f) for f in frame_list]

    fig = plt.figure(figsize=(6, 5))
    ax = fig.add_subplot(111, projection="3d")

    def _update(i: int) -> Any:
        _render_spec(
            specs[i], chamber=chamber, ax=ax, subject_assets_dir=subject_assets_dir
        )
        return [ax]

    anim = FuncAnimation(
        fig,
        _update,
        frames=len(specs),
        interval=interval_ms,
        blit=False,
        repeat=False,
    )

    if output_path is not None:
        path = Path(output_path)
        suffix = path.suffix.lower()
        if suffix == ".mp4":
            anim.save(str(path), writer="ffmpeg", fps=fps)
        elif suffix == ".gif":
            anim.save(str(path), writer="pillow", fps=fps)
        else:
            raise ValueError(
                f"unsupported output format {suffix!r}; use .mp4 or .gif"
            )

    return anim
