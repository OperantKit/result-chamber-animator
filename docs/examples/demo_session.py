"""Generate local demo MP4s for visual review.

Reproducible recipe:

    .venv/bin/python docs/examples/demo_session.py

Outputs (gitignored, regenerate locally):
- docs/assets/demo.mp4        — rat style, inter-event behaviour injection on
- docs/assets/demo_strict.mp4 — sphere style, strict frame-to-record fidelity

MP4 export requires ``ffmpeg`` on ``PATH``.
"""

from __future__ import annotations

from pathlib import Path

import matplotlib

matplotlib.use("Agg")  # headless

import contingency  # noqa: E402
import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402

from contingency.entities import ResponseEvent  # noqa: E402

from result_chamber_animator import (  # noqa: E402
    animate,
    default_two_lever_chamber,
    steps_from_dataframe,
)

_RESPONSES = ("lever_left", "lever_right")
_TOTAL_STEPS = 24


def _generate_session() -> list:
    """Drive two FR schedules with a uniform random chooser.

    Standalone reimplementation that talks to ``contingency`` directly,
    so the demo has no dependency outside the package's declared deps.
    """
    rng = np.random.default_rng(42)
    schedules = {
        "lever_left": contingency.ScheduleBuilder.fr(2),
        "lever_right": contingency.ScheduleBuilder.fr(3),
    }

    rows: list[dict] = []
    for step in range(_TOTAL_STEPS):
        chosen = _RESPONSES[int(rng.integers(0, len(_RESPONSES)))]
        now = float(step + 1)
        outcome = schedules[chosen].step(
            now, ResponseEvent(time=now, operandum=chosen)
        )
        rows.append(
            {
                "step": step,
                "chosen_response": chosen,
                "is_reinforced": bool(outcome.reinforced),
            }
        )

    return steps_from_dataframe(pd.DataFrame(rows), dt=1.0)


def main() -> None:
    frames = _generate_session()
    assets = Path(__file__).resolve().parent.parent / "assets"
    assets.mkdir(parents=True, exist_ok=True)

    rat_chamber = default_two_lever_chamber(subject_style="rat")
    out_main = assets / "demo.mp4"
    # dt=1.0 yields 1-s gaps between recorded events; the default
    # long_gap_threshold_s=2.0 would skip every gap and produce a
    # teleporting animation. Lower the gate and bump density so each
    # gap gets ~4 interpolated subject positions.
    animate(
        frames,
        chamber=rat_chamber,
        output_path=out_main,
        fps=12,
        inject_inter_event_behavior=True,
        long_gap_threshold_s=0.0,
        filler_density_per_s=4.0,
        adjunctive_window_s=3.0,
        terminal_window_s=1.5,
        jitter_amplitude=0.005,
        seed=0,
    )
    print(f"wrote {out_main}")

    out_strict = assets / "demo_strict.mp4"
    animate(
        frames,
        chamber=default_two_lever_chamber(subject_style="sphere"),
        output_path=out_strict,
        fps=4,
        inject_inter_event_behavior=False,
    )
    print(f"wrote {out_strict}")


if __name__ == "__main__":
    main()
