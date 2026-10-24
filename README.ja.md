# result-chamber-animator

:gb: [English README](README.md)

result-chamber-animator は、記録済みのオペラント実験のセッションを、実験箱のアニメーションにします。被験体は各ステップで反応したオペランダム（レバー）の位置へ動き、その反応が強化されたときには餌の給餌器（ホッパー）が光ります。授業や結果の発表のための道具で、すでに記録されたデータを再生するだけです。[OperantKit](https://github.com/OperantKit) の中では、[session-recorder](https://github.com/OperantKit/session-recorder) が書くセッションログに加え、単純な CSV と JSONL のファイルを読みます。

- **既定では、記録された出来事 1 つにつき 1 コマです。** 指定しない限り、何も足しません。
- **合成したコマには、合成したことを明示します。** 任意で足せる出来事の間のコマは、強化と強化の間の行動についての公刊された説明に従うもので、データではなくモデルとして扱います。
- **PNG・GIF・MP4 に出力できます。** 1 ステップの静止画、追加のソフトなしの GIF、ffmpeg があれば MP4 です。

AI コーディングエージェント向けの案内は [AGENTS.md](AGENTS.md) にあります。

<p align="center"><img src="docs/assets/thumbnail.png" width="420" alt="左右のレバーと黄色い給餌器のある 3D の実験箱。給餌器のそばにラットのシルエット。タイトルは t=13.0s resp=lever_left +SR"></p>

## インストール

Python 3.11 以上が必要です。result-chamber-animator はまだ PyPI に登録されていないため、`pip install result-chamber-animator` は今のところ使えません。GitHub から入れてください。

```bash
pip install git+https://github.com/OperantKit/result-chamber-animator
```

CSV と JSONL の入力ならこれで足ります。OKL のセッションログも読むには、session-recorder と、それが必要とする OperantKit のパッケージを、依存の解決をせずに足してください。

```bash
G=git+https://github.com/OperantKit
pip install --no-deps $G/contingency-dsl-py $G/contingency-py $G/experiment-core $G/session-recorder
```

MP4 の出力には、`PATH` 上の `ffmpeg` が必要です。

## 例

記録済みのセッションをアニメーション GIF にします。

```python
import matplotlib

matplotlib.use("Agg")  # 画面なしで描く

import pandas as pd

from result_chamber_animator import animate, steps_from_dataframe

# 記録済みのセッション：各ステップで押されたオペランダムと、強化されたかどうか。
rows = pd.DataFrame(
    {
        "step": range(8),
        "chosen_response": ["lever_left", "lever_left", "lever_right", "lever_left",
                            "lever_right", "lever_right", "lever_left", "lever_right"],
        "is_reinforced": [False, True, False, False, False, True, True, False],
    }
)
frames = steps_from_dataframe(rows, dt=1.0)
print(len(frames), sum(f.is_reinforced for f in frames))  # 8 3
animate(frames, output_path="session.gif", fps=4)  # GIF は ffmpeg 不要。ffmpeg があれば .mp4 も可
```

各コマでは、そのステップで押されたオペランダムの位置に被験体が置かれます。強化されたステップでは給餌器が光り、タイトルに `+SR` が出ます。同じ行を CSV ファイルに保存すれば、コマンドラインからも同じ GIF が作れます：`result-chamber-animator session.csv --gif session.gif`。

## 使い方

### 入力

- **CSV または JSONL**（`.csv`、`.jsonl`、`.ndjson`）。列は `step`、`chosen_response`（既定の 2 レバーの実験箱では `lever_left` か `lever_right`）、`is_reinforced` です。
- **OKL v1 のセッションログ**（それ以外のファイルで、1 行目が `# OKL v1` のもの）。session-recorder が必要です。各反応はそのオペランダム（0 = 左レバー、1 = 右レバー）の位置に描かれ、同じオペランダムへの強化子が 50 ミリ秒以内に続けば強化されたものと数えます。強化子の出来事では、被験体は給餌器の位置に置かれます。

### コマンドライン

```bash
# MP4（PATH 上の ffmpeg が必要）
result-chamber-animator session.csv --mp4 out.mp4 --fps 10

# GIF（ffmpeg 不要、ファイルは大きめ）
result-chamber-animator session.csv --gif out.gif --fps 5

# 1 ステップを静止画に
result-chamber-animator session.csv --frame 42 --png frame42.png

# 既定の球の代わりにラットやハト
result-chamber-animator session.csv --mp4 out.mp4 --subject rat

# 記録された出来事の間に合成したコマを足す（下を参照）
result-chamber-animator session.csv --mp4 out.mp4 --subject rat --inter-event-behavior --fps 12
```

合成するコマの時間窓の長さや乱数の種を含むすべてのオプションは、`result-chamber-animator --help` で確認できます。

### 被験体

実験箱は 3D で描きます。被験体は実験箱の床に置いた真上から見た平たい図で、反応するオペランダムの方を向くよう回転します。

| `--subject` | 描くもの |
|---|---|
| `sphere`（既定） | 茶色の球。被験体を位置としてだけ示します |
| `rat` | 真上から見たラットのシルエット：鼻先、耳、胴、尾 |
| `pigeon` | 真上から見たハトのシルエット：くちばし、頭、胴、扇形の尾 |

### 記録された出来事の間の行動

`--inter-event-behavior`（`animate` では `inject_inter_event_behavior=True`）を付けると、記録された出来事の間にコマを足し、それぞれを強化と強化の間の行動の 3 つのフェイズのどれかに割り当てます。

| フェイズ | いつ | 被験体を描く位置 | 文献 |
|---|---|---|---|
| **付随（adjunctive）** | 強化子の後 `adjunctive_window_s` 以内 | 給餌器のそば | Falk (1961, 1971) |
| **中間（interim）** | 間隔の中ほど | 実験箱の壁に沿って歩く | Staddon & Simmelhag (1971); Timberlake & Lucas (1985) |
| **終端（terminal）** | 次に記録された反応の前 `terminal_window_s` 以内 | これから押すオペランダムへ近づく | Staddon & Simmelhag (1971) |

2 つの時間窓が重なるところでは付随のフェイズを優先するため、強化子の直後の短い間隔が終端と分類されることはありません。これらのコマでは、図がわずかに（約 ±4%）伸び縮みします。

```python
animate(
    frames,
    inject_inter_event_behavior=True,  # 既定ではオフ
    adjunctive_window_s=3.0,            # 強化子の後：給餌器のそば
    terminal_window_s=1.5,              # 反応の前：オペランダムへ接近
    jitter_amplitude=0.005,             # ランダムなずれの最大値（メートル）
    seed=0,                             # 同じ種なら同じコマ
    fps=12,
    output_path="between.gif",
)
```

**合成したコマは、記録された出来事に対応しません。** これは出来事の間の時間のモデルであり、データの再生ではありません。給餌器が光るのは、記録上で強化されたステップだけです。アニメーションを記録と 1 対 1 で対応させる必要があるときは、このオプションをオフにしてください。

[`docs/examples/demo_session.py`](docs/examples/demo_session.py) は、2 本のデモ MP4 を `docs/assets/` に書き出します。出来事の間のコマを合成したラット（12 fps）と、記録されたステップだけの球（4 fps）です。

## 制限

- 記録済みのデータを再生するだけで、セッションは走らせません。
- 記録されたステップや出来事 1 つが 1 コマです。合成したコマをオンにしない限り、出来事の間の時間は描きません。
- 実験箱は 2 本のレバーと給餌器のある単純な箱で、特定のメーカーの装置を模したものではありません。
- OKL のログでは、反応がオペランダムを記録している必要があります。反応にオペランダムが無いログは、既定の実験箱に左右のレバーしか無いため、`KeyError: unknown operandum key 'lever'` で止まります。
- MP4 の出力には `ffmpeg` が必要です。

## 開発

```bash
python -m venv .venv
.venv/bin/python -m pip install -e ".[dev]"
.venv/bin/python -m pytest
```

この README と `README.md` の `python` のコードブロックはすべて、`tests/test_readme_examples.py` が実行します。

## 参考文献

- Falk, J. L. (1961). Production of polydipsia in normal rats by an intermittent food schedule. *Science*, *133*(3447), 195-196. https://doi.org/10.1126/science.133.3447.195
- Falk, J. L. (1971). The nature and determinants of adjunctive behavior. *Physiology & Behavior*, *6*(5), 577-588. https://doi.org/10.1016/0031-9384(71)90209-5
- Staddon, J. E. R., & Simmelhag, V. L. (1971). The "superstition" experiment: A reexamination of its implications for the principles of adaptive behavior. *Psychological Review*, *78*(1), 3-43. https://doi.org/10.1037/h0030305
- Timberlake, W., & Lucas, G. A. (1985). The basis of superstitious behavior: Chance contingency, stimulus substitution, or appetitive behavior? *Journal of the Experimental Analysis of Behavior*, *44*(3), 279-299. https://doi.org/10.1901/jeab.1985.44-279

## ライセンス

MIT（`pyproject.toml` で宣言。リポジトリに LICENSE ファイルはありません）。
