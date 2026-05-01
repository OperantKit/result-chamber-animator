"""CLI smoke tests for ``result-chamber-animator``."""

from __future__ import annotations

import json

import pandas as pd

from result_chamber_animator.cli import main


def _write_csv(tmp_path):
    df = pd.DataFrame(
        {
            "step": [0, 1, 2],
            "chosen_response": ["lever_left", "lever_right", "lever_left"],
            "is_reinforced": [False, True, False],
        }
    )
    p = tmp_path / "session.csv"
    df.to_csv(p, index=False)
    return p


def _write_jsonl(tmp_path):
    rows = [
        {"step": 0, "chosen_response": "lever_left", "is_reinforced": False},
        {"step": 1, "chosen_response": "lever_right", "is_reinforced": True},
    ]
    p = tmp_path / "session.jsonl"
    p.write_text("\n".join(json.dumps(r) for r in rows))
    return p


def test_cli_static_frame(tmp_path):
    csv = _write_csv(tmp_path)
    png = tmp_path / "frame.png"
    rc = main([str(csv), "--frame", "1", "--png", str(png)])
    assert rc == 0
    assert png.exists()
    assert png.stat().st_size > 0


def test_cli_mp4_animation(tmp_path):
    csv = _write_csv(tmp_path)
    mp4 = tmp_path / "out.mp4"
    rc = main([str(csv), "--mp4", str(mp4), "--fps", "5"])
    assert rc == 0
    assert mp4.exists()


def test_cli_gif_animation(tmp_path):
    csv = _write_csv(tmp_path)
    gif = tmp_path / "out.gif"
    rc = main([str(csv), "--gif", str(gif), "--fps", "5"])
    assert rc == 0
    assert gif.exists()


def test_cli_jsonl_input(tmp_path):
    jsonl = _write_jsonl(tmp_path)
    mp4 = tmp_path / "out.mp4"
    rc = main([str(jsonl), "--mp4", str(mp4)])
    assert rc == 0
    assert mp4.exists()
