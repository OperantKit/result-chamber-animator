# result-chamber-animator

:jp: [日本語版 README](README.ja.md)

3D animation of recorded operant-chamber sessions. Reads a session
recording (CSV / JSONL with `step`, `chosen_response`, `is_reinforced`
columns) and renders an animated chamber where the agent body moves to
whichever operandum was pressed each step. The food hopper flashes on
reinforcement.

The package is purely consumption-side — it never runs a live
simulation. Pre-record sessions with any producer that emits the
expected row shape and feed the result here.

Designed for educational use; not a real-time graphics library.

## Demo

24 synthetic steps of uniform random choice against concurrent FR(2)
on the left lever and FR(3) on the right. Top-down rat silhouette with **inter-
event behaviour synthesis** — between-record filler frames are
classified into three behaviour-analytic phases (adjunctive at the
hopper, interim wandering at chamber centre, terminal approach toward
the next operandum) following Falk (1961, 1971) and Staddon &
Simmelhag (1971). The food hopper (lower square) flashes yellow on
reinforcement. The demo MP4s are not committed; regenerate them
locally with [`docs/examples/demo_session.py`](docs/examples/demo_session.py):

```bash
.venv/bin/python docs/examples/demo_session.py
# writes:
#   docs/assets/demo.mp4         — rat + three-phase inter-event behaviour, 12 fps
#   docs/assets/demo_strict.mp4  — sphere + recorded steps only, 4 fps
```

The strict-fidelity variant uses the sphere subject style, 1 frame per
recorded step, and no synthesised between-event filler. Use it when the
visualisation must correspond 1:1 to the recorded events.

## Overview

```
your session producer
        │  (run + record)
        ▼
+-------------------------+        +-------------------------+
|  CSV / JSONL recording  |  -->   | result-chamber-animator |
+-------------------------+        +-------------------------+
                                            │
                       ┌────────────────────┼────────────────────┐
                       ▼                    ▼                    ▼
                  static PNG          animated MP4          animated GIF
```

Public API:

```python
from result_chamber_animator import (
    Chamber, Operandum, default_two_lever_chamber,
    StepFrame, render_frame, animate, steps_from_dataframe,
)
```

CLI:

```bash
# Headline demo: rat + three-phase inter-event behaviour
result-chamber-animator session.csv --mp4 out.mp4 \
    --subject rat --inter-event-behavior --fps 12

# Strict 1-frame-per-record (sphere style, default)
result-chamber-animator session.csv --mp4 out.mp4 --fps 4
```

## Install

```bash
mise exec -- python -m venv .venv
.venv/bin/python -m pip install -e ".[dev]"
```

## Run tests

```bash
.venv/bin/python -m pytest -q
```

## CLI

```bash
# Animate the whole session as MP4 (requires ffmpeg on PATH)
result-chamber-animator session.csv --mp4 out.mp4 --fps 10

# GIF fallback (no ffmpeg dependency, larger file size)
result-chamber-animator session.csv --gif out.gif --fps 5

# Static PNG of a single step
result-chamber-animator session.csv --frame 42 --png frame42.png

# JSONL input (e.g. exported from session_recorder)
result-chamber-animator session.jsonl --mp4 out.mp4

# Stylized rat or pigeon subject
result-chamber-animator session.csv --mp4 out.mp4 --subject rat
result-chamber-animator session.csv --mp4 out.mp4 --subject pigeon

# Insert synthesised filler frames between recorded steps and classify
# each into adjunctive / interim / terminal (see "Inter-event behaviour
# synthesis" below). NOT a 1:1 replay of the record — turn off when
# strict frame-to-record fidelity matters.
result-chamber-animator session.csv --mp4 out.mp4 \
    --inter-event-behavior --fps 12

# Tune the phase windows
result-chamber-animator session.csv --mp4 out.mp4 \
    --inter-event-behavior \
    --adjunctive-window 3.0 --terminal-window 1.5

# Deterministic jitter via --seed
result-chamber-animator session.csv --mp4 out.mp4 \
    --inter-event-behavior --seed 0
```

## Subject illustration styles

The chamber is rendered in 3D (wireframe + operanda + hopper) but the
subject is a **2D top-down silhouette laid flat on the chamber floor
and rotated around the vertical axis to face its target** — the
Live2D / VTuber idiom (a 2D rigged sprite inside a 3D scene), here
adapted for textbook-style operant-chamber visualisation.

| `--subject` | What's drawn | Notes |
|---|---|---|
| `sphere` (default) | A single brown sphere on the floor | Minimal baseline; emphasises subject-as-position |
| `rat` | Top-down rat silhouette: pointed snout, ears, body, long tapering tail | Filled polygon, ~33 vertices |
| `pigeon` | Top-down pigeon silhouette: pointed beak, head, body, tail fan | Filled polygon, ~28 vertices |

The silhouettes are rotated around the chamber's vertical axis so that
the snout / beak always points toward the operandum being pressed. On
free-operant filler frames the polygon also picks up a subtle
sinusoidal scale pulse (~±4 %) for a "breathing" feel — turn off
`--free-operant` to remove the pulse and have one frame per record.

## Inter-event behaviour synthesis

The simulator records discrete events at integer step indices. Between
events the subject is doing *something* — and decades of behaviour-
analytic work have characterised that "something" as a temporally
structured sequence. The renderer can synthesise filler frames between
recorded events and classify each into one of three phases drawn
straight from the post-Skinnerian taxonomy:

| Phase | When | Where the subject is rendered | Reference |
|---|---|---|---|
| **Adjunctive** | Within `adjunctive_window_s` after a reinforcer | At the food magazine (post-reinforcement licking, drinking, grooming; "adjunctive" in Falk's sense) | Falk (1961); Falk (1971) |
| **Terminal** | Within `terminal_window_s` before the next recorded response | Drifting from the last anchor toward the operandum about to be pressed | Staddon & Simmelhag (1971) |
| **Interim** | Otherwise (middle of the inter-event gap) | Wandering near chamber centre — schedule-induced displacement-like activity | Staddon & Simmelhag (1971); Timberlake & Lucas (1985) |

Adjunctive precedes terminal at their boundary — the magazine-orienting
phase wins for short inter-event intervals (otherwise a 1 s
inter-response interval after reinforcement would be tagged as
"terminal", which contradicts the empirical phase ordering).

```python
animate(
    frames,
    inject_inter_event_behavior=True,  # off by default
    adjunctive_window_s=3.0,            # post-SR+ window for hopper-orientation
    terminal_window_s=1.5,              # pre-response window for approach
    jitter_amplitude=0.005,             # max random offset, metres
    seed=0,                             # deterministic jitter
    fps=12,
)
```

**The synthesised frames do NOT correspond to recorded events.** They
are a *behaviour-systems model* of the inter-event interval, not a
replay of the data. Reinforcement flashes fire only on actual recorded
steps. Turn injection off whenever the visualisation must match the
record 1:1.

References (APA 7):

- Falk, J. L. (1961). Production of polydipsia in normal rats by an
  intermittent food schedule. *Science*, *133*(3447), 195-196.
  https://doi.org/10.1126/science.133.3447.195
- Falk, J. L. (1971). The nature and determinants of adjunctive
  behavior. *Physiology & Behavior*, *6*(5), 577-588.
  https://doi.org/10.1016/0031-9384(71)90209-5
- Staddon, J. E. R., & Simmelhag, V. L. (1971). The "superstition"
  experiment: A reexamination of its implications for the principles of
  adaptive behavior. *Psychological Review*, *78*(1), 3-43.
  https://doi.org/10.1037/h0030305
- Timberlake, W., & Lucas, G. A. (1985). The basis of superstitious
  behavior: Chance contingency, stimulus substitution, or appetitive
  behavior? *Journal of the Experimental Analysis of Behavior*, *44*(3),
  279-299. https://doi.org/10.1901/jeab.1985.44-279

## Programmatic use

```python
import matplotlib

matplotlib.use("Agg")  # headless

import contingency
import numpy as np
import pandas as pd
from contingency.entities import ResponseEvent

from result_chamber_animator import animate, steps_from_dataframe

rng = np.random.default_rng(0)
schedules = {
    "lever_left":  contingency.ScheduleBuilder.fr(2),
    "lever_right": contingency.ScheduleBuilder.fr(3),
}
options = list(schedules)

rows = []
for step in range(30):
    chosen = options[int(rng.integers(0, len(options)))]
    now = float(step + 1)
    outcome = schedules[chosen].step(
        now, ResponseEvent(time=now, operandum=chosen)
    )
    rows.append(
        {"step": step, "chosen_response": chosen,
         "is_reinforced": bool(outcome.reinforced)}
    )

frames = steps_from_dataframe(pd.DataFrame(rows), dt=1.0)
animate(frames, output_path="demo.mp4", fps=5)
```

## Limitations

- Consumes recorded data only; does not run live simulations.
- Discrete-time; the renderer treats each recorded step as one frame.
- Geometry is intentionally minimal — boxy chamber, sphere agent, no
  manufacturer-specific apparatus.
- MP4 export requires `ffmpeg` available on `PATH`.

## References

- Skinner, B. F. (1938). *The behavior of organisms: An experimental
  analysis*. Appleton-Century.
- Lattal, K. A. (2004). Steps and pips in the history of the cumulative
  recorder. *Journal of the Experimental Analysis of Behavior*, *82*(3),
  329-355. https://doi.org/10.1901/jeab.2004.82-329
