"""result-chamber-animator: 3D animation of recorded operant-chamber sessions.

Reads recorded session data (a :class:`pandas.DataFrame` with
``step`` / ``chosen_response`` / ``is_reinforced`` columns, or a CSV /
JSONL export of equivalent shape) and renders an animated 3D chamber
where the agent body moves toward the operandum it pressed each step.
Reinforcement deliveries are rendered as flashes at the food hopper.

The package is purely consumption-side: it does not run a live
simulation. Pre-record sessions with any producer of the expected row
shape and feed the result here.

Designed for educational use; not a real-time graphics library.
"""

from result_chamber_animator.chamber import (
    Chamber,
    Operandum,
    SubjectStyle,
    default_two_lever_chamber,
)
from result_chamber_animator.renderer import (
    StepFrame,
    animate,
    render_frame,
    steps_from_dataframe,
)
from result_chamber_animator.subject import draw_subject

__all__ = [
    "Chamber",
    "Operandum",
    "StepFrame",
    "SubjectStyle",
    "animate",
    "default_two_lever_chamber",
    "draw_subject",
    "render_frame",
    "steps_from_dataframe",
]
