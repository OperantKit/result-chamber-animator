"""Tests for the renderer / animation API.

These tests use matplotlib's ``Agg`` backend so they run headless in CI.
They do not assert anything pixel-precise — only that frames render
without error and that animation files are produced when requested.
"""

from __future__ import annotations

import matplotlib

matplotlib.use("Agg")

import matplotlib.pyplot as plt  # noqa: E402
import pandas as pd  # noqa: E402
import pytest  # noqa: E402

from result_chamber_animator.chamber import default_two_lever_chamber  # noqa: E402
from result_chamber_animator.renderer import (  # noqa: E402
    StepFrame,
    animate,
    render_frame,
    steps_from_dataframe,
)


@pytest.fixture
def two_step_frames():
    return [
        StepFrame(step=0, chosen_response="lever_left", is_reinforced=False),
        StepFrame(step=1, chosen_response="lever_right", is_reinforced=True),
    ]


class TestStepFrameConversion:
    def test_steps_from_dataframe_basic(self):
        df = pd.DataFrame(
            {
                "step": [0, 1, 2],
                "chosen_response": ["lever_left", "lever_right", "lever_left"],
                "is_reinforced": [False, True, False],
            }
        )
        frames = steps_from_dataframe(df, dt=0.5)
        assert len(frames) == 3
        assert frames[0].chosen_response == "lever_left"
        assert frames[1].is_reinforced is True
        assert frames[2].timestamp == pytest.approx(1.5)

    def test_steps_from_dataframe_missing_columns(self):
        df = pd.DataFrame({"step": [0]})
        with pytest.raises(ValueError, match="missing"):
            steps_from_dataframe(df)


class TestStaticFrameRendering:
    def test_render_single_frame_returns_axes(self, two_step_frames):
        ax = render_frame(two_step_frames[0])
        assert ax is not None
        plt.close("all")

    def test_render_reinforced_frame_does_not_raise(self, two_step_frames):
        ax = render_frame(two_step_frames[1])
        assert ax is not None
        plt.close("all")

    def test_render_unknown_response_raises(self):
        chamber = default_two_lever_chamber()
        bad = StepFrame(step=0, chosen_response="never_seen", is_reinforced=False)
        with pytest.raises(KeyError):
            render_frame(bad, chamber=chamber)
        plt.close("all")


class TestAnimation:
    def test_animate_returns_funcanimation(self, two_step_frames):
        anim = animate(two_step_frames, interval_ms=10)
        from matplotlib.animation import FuncAnimation

        assert isinstance(anim, FuncAnimation)
        plt.close("all")

    def test_animate_empty_frames_raises(self):
        with pytest.raises(ValueError, match="empty"):
            animate([])

    def test_animate_writes_mp4(self, two_step_frames, tmp_path):
        out = tmp_path / "demo.mp4"
        animate(two_step_frames, output_path=out, interval_ms=10, fps=5)
        plt.close("all")
        assert out.exists()
        assert out.stat().st_size > 0

    def test_animate_writes_gif(self, two_step_frames, tmp_path):
        out = tmp_path / "demo.gif"
        animate(two_step_frames, output_path=out, interval_ms=10, fps=5)
        plt.close("all")
        assert out.exists()
        assert out.stat().st_size > 0

    def test_animate_unknown_extension_raises(self, two_step_frames, tmp_path):
        out = tmp_path / "demo.xyz"
        with pytest.raises(ValueError, match="unsupported"):
            animate(two_step_frames, output_path=out)
        plt.close("all")


class TestInterEventBehaviorInjection:
    @pytest.fixture
    def four_step_frames(self):
        return [
            StepFrame(
                step=0, chosen_response="lever_left", is_reinforced=False, timestamp=1.0
            ),
            StepFrame(
                step=1, chosen_response="lever_right", is_reinforced=True, timestamp=2.0
            ),
            StepFrame(
                step=2, chosen_response="lever_left", is_reinforced=False, timestamp=3.0
            ),
            StepFrame(
                step=3, chosen_response="lever_right", is_reinforced=False, timestamp=4.0
            ),
        ]

    def test_filler_increases_total_frame_count(self, four_step_frames):
        from result_chamber_animator.renderer import (
            _expand_with_inter_event_behavior,
        )

        chamber = default_two_lever_chamber()
        # gap_s = 1.0 between consecutive frames; density 2 → 2 fillers per gap.
        specs = _expand_with_inter_event_behavior(
            four_step_frames,
            chamber,
            filler_density_per_s=2.0,
            long_gap_threshold_s=0.0,
            max_fillers_per_gap=10,
            adjunctive_window_s=3.0,
            terminal_window_s=1.5,
            jitter_amplitude=0.0,
            seed=0,
        )
        # 4 recorded + 2 filler in each of the 3 gaps = 4 + 6 = 10
        assert len(specs) == 4 + 3 * 2

    def test_short_gaps_below_threshold_skip_fillers(self, four_step_frames):
        from result_chamber_animator.renderer import (
            _expand_with_inter_event_behavior,
        )

        chamber = default_two_lever_chamber()
        # gap_s = 1.0 < threshold 5.0 → no fillers anywhere.
        specs = _expand_with_inter_event_behavior(
            four_step_frames,
            chamber,
            filler_density_per_s=10.0,
            long_gap_threshold_s=5.0,
            max_fillers_per_gap=100,
            adjunctive_window_s=3.0,
            terminal_window_s=1.5,
            jitter_amplitude=0.0,
            seed=0,
        )
        assert len(specs) == len(four_step_frames)
        assert all(not s.is_filler for s in specs)

    def test_negative_density_raises(self, four_step_frames):
        from result_chamber_animator.renderer import (
            _expand_with_inter_event_behavior,
        )

        chamber = default_two_lever_chamber()
        with pytest.raises(ValueError, match="filler_density_per_s"):
            _expand_with_inter_event_behavior(
                four_step_frames,
                chamber,
                filler_density_per_s=-1.0,
                long_gap_threshold_s=0.0,
                max_fillers_per_gap=10,
                adjunctive_window_s=3.0,
                terminal_window_s=1.5,
                jitter_amplitude=0.0,
                seed=0,
            )

    def test_filler_frames_have_no_active_operandum(self, four_step_frames):
        from result_chamber_animator.renderer import (
            _expand_with_inter_event_behavior,
        )

        chamber = default_two_lever_chamber()
        specs = _expand_with_inter_event_behavior(
            four_step_frames,
            chamber,
            filler_density_per_s=3.0,
            long_gap_threshold_s=0.0,
            max_fillers_per_gap=10,
            adjunctive_window_s=3.0,
            terminal_window_s=1.5,
            jitter_amplitude=0.0,
            seed=0,
        )
        for s in specs:
            if s.is_filler:
                assert s.active_key is None
            else:
                assert s.active_key == s.base.chosen_response

    def test_animate_with_injection_writes_mp4(self, four_step_frames, tmp_path):
        out = tmp_path / "filled.mp4"
        animate(
            four_step_frames,
            output_path=out,
            interval_ms=10,
            fps=8,
            inject_inter_event_behavior=True,
            filler_density_per_s=2.0,
            long_gap_threshold_s=0.0,
            seed=0,
        )
        plt.close("all")
        assert out.exists()
        assert out.stat().st_size > 0


class TestPhaseClassification:
    def test_classify_recently_reinforced_is_adjunctive(self):
        from result_chamber_animator.renderer import _classify_phase

        # 1s after reinforcer, 5s before next response, 3s adjunctive window.
        phase = _classify_phase(
            t=11.0, last_sr_t=10.0, next_response_t=16.0,
            adjunctive_window_s=3.0, terminal_window_s=1.5,
        )
        assert phase == "adjunctive"

    def test_classify_just_before_response_is_terminal(self):
        from result_chamber_animator.renderer import _classify_phase

        # 5s after reinforcer (outside adjunctive); 0.5s before response.
        phase = _classify_phase(
            t=15.5, last_sr_t=10.0, next_response_t=16.0,
            adjunctive_window_s=3.0, terminal_window_s=1.5,
        )
        assert phase == "terminal"

    def test_classify_mid_interval_is_interim(self):
        from result_chamber_animator.renderer import _classify_phase

        # 5s after reinforcer (outside adjunctive); 5s before response (outside terminal).
        phase = _classify_phase(
            t=15.0, last_sr_t=10.0, next_response_t=20.0,
            adjunctive_window_s=3.0, terminal_window_s=1.5,
        )
        assert phase == "interim"

    def test_no_prior_reinforcer_skips_adjunctive(self):
        from result_chamber_animator.renderer import _classify_phase

        # Session start: last_sr_t = -inf; no adjunctive even within window.
        phase = _classify_phase(
            t=0.5, last_sr_t=float("-inf"), next_response_t=10.0,
            adjunctive_window_s=3.0, terminal_window_s=1.5,
        )
        assert phase == "interim"

    def test_phase_field_assigned_on_filler_specs(self):
        from result_chamber_animator.renderer import (
            _expand_with_inter_event_behavior,
        )

        frames = [
            StepFrame(step=0, chosen_response="lever_left", is_reinforced=True, timestamp=1.0),
            StepFrame(step=1, chosen_response="lever_right", is_reinforced=False, timestamp=10.0),
        ]
        chamber = default_two_lever_chamber()
        # gap_s = 9; density 1.0 → 9 fillers spanning t=1.9 .. 9.1.
        specs = _expand_with_inter_event_behavior(
            frames,
            chamber,
            filler_density_per_s=1.0,
            long_gap_threshold_s=0.0,
            max_fillers_per_gap=20,
            adjunctive_window_s=2.0,
            terminal_window_s=1.0,
            jitter_amplitude=0.0,
            seed=0,
        )
        filler_phases = [s.phase for s in specs if s.is_filler]
        assert "adjunctive" in filler_phases  # right after the SR+ at t=1
        assert "interim" in filler_phases     # in the middle
        assert "terminal" in filler_phases    # right before t=10 response


class TestSubjectStyleInIntegration:
    @pytest.mark.parametrize("style", ["sphere", "rat", "pigeon"])
    def test_render_frame_with_each_style(self, style):
        from result_chamber_animator import default_two_lever_chamber

        chamber = default_two_lever_chamber(subject_style=style)
        frame = StepFrame(step=0, chosen_response="lever_left", is_reinforced=False)
        ax = render_frame(frame, chamber=chamber)
        assert ax is not None
        plt.close("all")
