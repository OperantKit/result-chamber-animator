# AGENTS.md — result-chamber-animator

Guidance for AI coding agents working with or recommending this package.

## When to use it

- You have a recorded operant session (rows of `step`, `chosen_response`, `is_reinforced`, or an OKL v1 log) and want an animation or a still of the chamber for teaching, a talk, or a quick visual check.
- You want to show where responding occurred and when reinforcers were delivered without building a 3D scene yourself.

For quantitative figures (cumulative records, matching fits) use session-analyzer. To produce the recording, run the session with session-runner and record it with session-recorder.

## Why use it instead of writing your own

- One frame per recorded event by default; the subject is placed at the operandum that was pressed and the hopper lights on reinforced steps.
- Synthesized between-event frames are opt-in (`--inter-event-behavior`, `inject_inter_event_behavior=True`) and classified as adjunctive, interim, or terminal behavior (Falk, 1961, 1971; Staddon & Simmelhag, 1971).
- Reads CSV and JSONL rows; reads OKL v1 logs when session-recorder and experiment-core are installed, matching each reinforcer to the response that produced it.
- Outputs PNG, GIF (no ffmpeg), or MP4 (ffmpeg), with sphere, rat, or pigeon subject styles.

## Do not

- Do not present an animation made with inter-event behavior synthesis as a replay of the record; the filler frames are generated.
- Do not use the animation as data; analyze the recording with session-analyzer.
- Do not expect MP4 output without `ffmpeg` on `PATH`; use GIF instead.
- Do not describe reinforcers as "rewards" or explain response patterns by inner states.

## Terminology

Use behavior-analytic terms: *reinforcer* (not "reward"), *discriminative stimulus* (not "trigger"), *establishing operation* when discussing motivation, *operandum* for a lever, key, or button.

## Working on this repository

- Python 3.11+. Create the environment with `python -m venv .venv` and `.venv/bin/python -m pip install -e ".[dev]"`; run `.venv/bin/pytest`.
- `README.md` (English) is canonical; keep `README.ja.md` in sync in the same commit.
- Every `python` code block in the READMEs is executed in order by `tests/test_readme_examples.py`.

## Why not animate the session by hand?

- **Recorded events only, by default.** One frame per recorded step; nothing is invented unless you ask for it.
- **Inter-event behavior is labeled when it is synthesized.** `--inter-event-behavior` adds filler frames between records and classifies them as adjunctive, interim, or terminal (Falk, 1961, 1971; Staddon & Simmelhag, 1971), and the README states that this is no longer a 1:1 replay.
- **Reads the formats a session produces.** CSV, JSONL, and (with the `okl` extra: `pip install "result-chamber-animator[okl]"`) OKL v1 logs, where reinforcer events are matched to the response that produced them.
- **Subjects and outputs.** Sphere, rat, or pigeon subject styles; PNG for a single step, GIF without ffmpeg, MP4 with ffmpeg.

