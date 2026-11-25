"""Run the README examples so the documented commands keep working.

Every ```python block of one README runs in order in a shared namespace (later
blocks reuse the imports of earlier ones) inside a temporary directory
(examples write files), and what it prints is compared with its comments.

Every ``result-chamber-animator ...`` line of the ```bash blocks runs as a
subprocess on ``session.csv``: the rows of the python example saved as CSV, as
the README text after the example says. Lines that write MP4 are skipped when
``ffmpeg`` is not on ``PATH``.
"""

from __future__ import annotations

import contextlib
import io
import re
import shlex
import shutil
import subprocess
import sys
from pathlib import Path

import matplotlib

matplotlib.use("Agg")

import matplotlib.pyplot as plt  # noqa: E402
import pytest  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
READMES = ("README.md", "README.ja.md")
COMMAND = "result-chamber-animator"
_BLOCK = re.compile(r"```python\n(.*?)```", re.DOTALL)
_BASH_BLOCK = re.compile(r"```bash\n(.*?)```", re.DOTALL)


def _blocks(name: str) -> list[str]:
    return _BLOCK.findall((ROOT / name).read_text(encoding="utf-8"))


def _documented_output(code: str) -> list[str]:
    """Output lines a README block documents in the comments of its ``print`` lines."""

    def clean(comment: str) -> str:
        return comment.split(" — ")[0].rstrip()  # drop a trailing " — note"

    expected: list[str] = []
    lines = code.splitlines()
    for i, line in enumerate(lines):
        if not line.lstrip().startswith("print("):
            continue
        _, same_line, comment = line.partition("  # ")
        if same_line:  # print(x)  # X
            expected.append(clean(comment))
            continue
        for nxt in lines[i + 1 :]:  # comment lines directly below the print
            if nxt.startswith("#  ") and expected:  # "#" + 2 spaces: continues the line above
                expected[-1] += " " + clean(nxt[1:].strip())
            elif nxt.startswith("# "):
                expected.append(clean(nxt[2:]))
            else:
                break
    return expected


def _cli_lines(name: str) -> list[str]:
    """The ``result-chamber-animator`` lines of the bash blocks, continuations joined."""
    lines: list[str] = []
    for block in _BASH_BLOCK.findall((ROOT / name).read_text(encoding="utf-8")):
        joined = block.replace("\\\n", " ")
        lines.extend(
            line.strip() for line in joined.splitlines() if line.strip().startswith(COMMAND + " ")
        )
    return lines


def _run_python_blocks(name: str) -> dict[str, object]:
    namespace: dict[str, object] = {}
    for index, block in enumerate(_blocks(name)):
        exec(compile(block, f"{name}#{index}", "exec"), namespace)
    plt.close("all")  # the examples run once per test; do not keep their figures open
    return namespace


def _executable() -> str:
    beside = Path(sys.executable).parent / COMMAND
    if beside.exists():
        return str(beside)
    found = shutil.which(COMMAND)
    if found is None:
        pytest.fail(f"{COMMAND} is not installed in this environment")
    return found


@pytest.mark.parametrize("name", READMES)
def test_readme_examples_run(name: str, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    blocks = _blocks(name)
    assert blocks
    expected = [line for block in blocks for line in _documented_output(block)]
    assert expected, f"{name} documents no output"
    monkeypatch.chdir(tmp_path)
    out = io.StringIO()
    with contextlib.redirect_stdout(out):
        _run_python_blocks(name)
    assert out.getvalue().splitlines() == expected


_CLI_CASES = [(name, line) for name in READMES for line in _cli_lines(name)]


def test_readme_has_cli_examples() -> None:
    for name in READMES:
        assert _cli_lines(name), f"no {COMMAND} line in the bash blocks of {name}"


@pytest.mark.parametrize(
    ("name", "line"), _CLI_CASES, ids=[f"{name}:{line}" for name, line in _CLI_CASES]
)
def test_readme_cli_example_runs(
    name: str, line: str, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    if "--mp4" in line and shutil.which("ffmpeg") is None:
        pytest.skip("ffmpeg is not on PATH")
    monkeypatch.chdir(tmp_path)
    namespace = _run_python_blocks(name)
    namespace["rows"].to_csv("session.csv", index=False)  # type: ignore[attr-defined]
    argv = [_executable(), *shlex.split(line)[1:]]
    result = subprocess.run(argv, capture_output=True, text=True, timeout=300)
    assert result.returncode == 0, f"{line}\nstdout:\n{result.stdout}\nstderr:\n{result.stderr}"
