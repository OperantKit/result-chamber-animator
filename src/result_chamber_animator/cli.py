"""``result-chamber-animator`` CLI entry point.

Consumes a CSV / JSONL with ``step`` / ``chosen_response`` /
``is_reinforced`` columns and renders either a static frame
(``--frame N``) or an animation
(``--mp4 PATH`` / ``--gif PATH``). MP4 is the primary animation format;
GIF is kept as a fallback for environments without ``ffmpeg``.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import pandas as pd

from result_chamber_animator.chamber import default_two_lever_chamber
from result_chamber_animator.renderer import (
    HOPPER_KEY,
    REST_KEY,
    StepFrame,
    animate,
    render_frame,
    steps_from_dataframe,
)


def _operandum_to_key(operandum: int | None) -> str:
    """Map an integer operandum index to the default chamber's key string.

    Convention: operandum 0 -> ``lever_left``, 1 -> ``lever_right``.
    Single-operandum (``None``) sessions map to ``lever``. Higher
    indices fall through to a generic ``lever_{n}`` so unusual chambers
    do not silently collapse onto the two-lever default.
    """
    if operandum is None:
        return "lever"
    if operandum == 0:
        return "lever_left"
    if operandum == 1:
        return "lever_right"
    return f"lever_{operandum}"


_REINFORCER_LATENCY_TOLERANCE_S = 0.05  # ~50 ms; covers hardware feeder dispatch lag


def _load_osl_v1(path: Path) -> pd.DataFrame:
    """Convert an OKL v1 session log into the renderer's per-event tabular format.

    Every :class:`experiment_core.events.SessionEvent` becomes one row.
    The renderer dispatches on the ``event_type`` column to position the
    subject and update the title bar:

    * ``response`` — subject at the recorded operandum.
      ``is_reinforced`` is ``True`` when a
      :class:`~experiment_core.events.ReinforcerStartEvent` for the
      same operandum follows the response within
      :data:`_REINFORCER_LATENCY_TOLERANCE_S` (covers hardware feeder
      dispatch latency).
    * ``reinforcer_start`` / ``reinforcer_end`` — subject at the food
      magazine, hopper flashing on start.
    * ``component_change`` — subject at rest pose; ``component`` column
      tracks the multiple-schedule context (``"C1"`` / ``"C2"`` /
      ``"ICI"`` / ``"INIT"``).
    * ``state_change`` — title-bar update only; subject stays at rest.

    All timestamps are the real OKL session timestamps (canonical
    seconds), not synthetic step indices.
    """
    import experiment_core
    import session_recorder

    log = session_recorder.read_log(str(path))

    # Pre-compute reinforcer keys for response→reinforcement matching.
    reinforcer_lookup = sorted(
        (
            (e.timestamp, e.operandum)
            for e in log.events
            if isinstance(e, experiment_core.ReinforcerStartEvent)
        ),
        key=lambda x: x[0],
    )
    consumed: set[int] = set()

    def _is_response_reinforced(evt: experiment_core.ResponseEvent) -> bool:
        for j, (rt, rop) in enumerate(reinforcer_lookup):
            if j in consumed or rop != evt.operandum:
                continue
            dt = rt - evt.timestamp
            if 0.0 <= dt <= _REINFORCER_LATENCY_TOLERANCE_S:
                consumed.add(j)
                return True
        return False

    component = "INIT"
    rows: list[dict[str, object]] = []
    for i, evt in enumerate(log.events):
        if isinstance(evt, experiment_core.ComponentChangeEvent):
            component = evt.to_component
            rows.append(
                {
                    "step": i,
                    "chosen_response": REST_KEY,
                    "is_reinforced": False,
                    "timestamp": float(evt.timestamp),
                    "event_type": "component_change",
                    "component": component,
                }
            )
        elif isinstance(evt, experiment_core.ResponseEvent):
            rows.append(
                {
                    "step": i,
                    "chosen_response": _operandum_to_key(evt.operandum),
                    "is_reinforced": _is_response_reinforced(evt),
                    "timestamp": float(evt.timestamp),
                    "event_type": "response",
                    "component": component,
                }
            )
        elif isinstance(evt, experiment_core.ReinforcerStartEvent):
            rows.append(
                {
                    "step": i,
                    "chosen_response": HOPPER_KEY,
                    "is_reinforced": True,
                    "timestamp": float(evt.timestamp),
                    "event_type": "reinforcer_start",
                    "component": component,
                }
            )
        elif isinstance(evt, experiment_core.ReinforcerEndEvent):
            rows.append(
                {
                    "step": i,
                    "chosen_response": HOPPER_KEY,
                    "is_reinforced": False,
                    "timestamp": float(evt.timestamp),
                    "event_type": "reinforcer_end",
                    "component": component,
                }
            )
        elif isinstance(evt, experiment_core.StateChangeEvent):
            rows.append(
                {
                    "step": i,
                    "chosen_response": REST_KEY,
                    "is_reinforced": False,
                    "timestamp": float(evt.timestamp),
                    "event_type": "state_change",
                    "component": component,
                }
            )
        # Other event types (phase markers, dro_onset, ...) skipped silently.
    return pd.DataFrame(rows)


def _looks_like_osl_v1(path: Path) -> bool:
    try:
        with path.open(encoding="utf-8") as f:
            return f.readline().strip().startswith("# OKL v1")
    except OSError:
        return False


def _load_records(path: Path) -> pd.DataFrame:
    suffix = path.suffix.lower()
    if suffix == ".csv":
        return pd.read_csv(path)
    if suffix in (".jsonl", ".ndjson"):
        rows = [json.loads(line) for line in path.read_text().splitlines() if line]
        return pd.DataFrame(rows)
    # OKL v1: detect by magic line on .txt / .osl / .log inputs.
    if _looks_like_osl_v1(path):
        return _load_osl_v1(path)
    raise SystemExit(f"unsupported input format: {path.suffix}")


def _build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="result-chamber-animator",
        description="3D animation of recorded operant-chamber sessions.",
    )
    p.add_argument(
        "input",
        type=Path,
        help="Path to a CSV / JSONL recording with step / chosen_response / is_reinforced columns.",
    )
    out = p.add_mutually_exclusive_group(required=True)
    out.add_argument("--frame", type=int, help="Render a single step as a static PNG.")
    out.add_argument(
        "--mp4",
        type=Path,
        help="Render an MP4 (primary format; requires ffmpeg on PATH).",
    )
    out.add_argument(
        "--gif",
        type=Path,
        help="Render an animated GIF (fallback when ffmpeg is unavailable).",
    )
    p.add_argument("--png", type=Path, help="Output PNG path when --frame is set.")
    p.add_argument("--dt", type=float, default=1.0, help="Step duration in seconds.")
    p.add_argument(
        "--fps", type=int, default=5, help="Frames per second for animation output."
    )
    p.add_argument(
        "--subject",
        choices=("sphere", "rat", "pigeon"),
        default="sphere",
        help="Subject illustration style. Default: sphere.",
    )
    p.add_argument(
        "--inter-event-behavior",
        action="store_true",
        help=(
            "Insert filler frames between recorded steps and classify each "
            "as adjunctive (post-reinforcement; Falk 1961), interim "
            "(Staddon & Simmelhag 1971), or terminal (approaching next "
            "response; Staddon & Simmelhag 1971). Synthesised frames do NOT "
            "match recorded events 1:1; turn off for strict fidelity."
        ),
    )
    p.add_argument(
        "--filler-density-per-s",
        type=float,
        default=0.5,
        help=(
            "Filler frames per second of real session time when "
            "--inter-event-behavior is on. A 60-s ICI at density 0.5 "
            "yields 30 filler frames. Default: 0.5."
        ),
    )
    p.add_argument(
        "--long-gap-threshold-s",
        type=float,
        default=2.0,
        help=(
            "Skip filler entirely for inter-event gaps shorter than this. "
            "Default: 2.0 (response bursts get no filler)."
        ),
    )
    p.add_argument(
        "--max-fillers-per-gap",
        type=int,
        default=30,
        help="Hard cap on filler frames per gap. Default: 30.",
    )
    p.add_argument(
        "--adjunctive-window",
        type=float,
        default=3.0,
        help=(
            "Seconds after a reinforcer during which fillers are classified "
            "as adjunctive (subject at hopper; Falk 1961, 1971). Default: 3.0."
        ),
    )
    p.add_argument(
        "--terminal-window",
        type=float,
        default=1.5,
        help=(
            "Seconds before the next recorded response during which fillers "
            "are classified as terminal (subject approaching operandum; "
            "Staddon & Simmelhag 1971). Default: 1.5."
        ),
    )
    p.add_argument(
        "--jitter",
        type=float,
        default=0.005,
        help="Max random offset (m) added to filler positions. Default: 0.005.",
    )
    p.add_argument(
        "--seed",
        type=int,
        default=None,
        help="RNG seed for filler-frame jitter (deterministic when set).",
    )
    return p


def main(argv: list[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)
    df = _load_records(args.input)
    frames = steps_from_dataframe(df, dt=args.dt)
    chamber = default_two_lever_chamber(subject_style=args.subject)

    import matplotlib  # noqa: E402

    if args.mp4 or args.gif:
        matplotlib.use("Agg")
        animate(
            frames,
            chamber=chamber,
            output_path=args.mp4 or args.gif,
            fps=args.fps,
            inject_inter_event_behavior=args.inter_event_behavior,
            filler_density_per_s=args.filler_density_per_s,
            long_gap_threshold_s=args.long_gap_threshold_s,
            max_fillers_per_gap=args.max_fillers_per_gap,
            adjunctive_window_s=args.adjunctive_window,
            terminal_window_s=args.terminal_window,
            jitter_amplitude=args.jitter,
            seed=args.seed,
        )
        return 0

    # Static frame mode.
    if args.frame is None:
        raise SystemExit("--frame must be set when --mp4/--gif are not.")
    target = next((f for f in frames if f.step == args.frame), None)
    if target is None:
        raise SystemExit(f"no step {args.frame!r} found in {args.input}")
    out_png = args.png or args.input.with_suffix(f".step{args.frame}.png")
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    fig = plt.figure(figsize=(6, 5))
    ax = fig.add_subplot(111, projection="3d")
    render_frame(target, chamber=chamber, ax=ax)
    fig.savefig(out_png, dpi=120, bbox_inches="tight")
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())


__all__ = ["main", "StepFrame"]
