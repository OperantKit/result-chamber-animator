# result-chamber-animator

:gb: [English README](README.md)

記録済みオペラント箱セッションの 3D アニメーション化ツール。
セッション記録（`step` / `chosen_response` / `is_reinforced` 列を持つ
CSV / JSONL）を読み込み、各ステップで押された操作体（lever / key）に
エージェント本体が移動するオペラント箱を描画する。強化が発生した
ステップでは餌ホッパーが発光する。

本パッケージは消費側専用 — ライブシミュレーションは行わない。
事前に同じ行形式を出力する任意の producer でセッションを記録し、
その結果を本ツールに渡して使う。

教育用途を想定した最小構成。リアルタイム描画ライブラリではない。

## デモ

並立 FR(2)（左 lever）/ FR(3)（右 lever）に対して uniform random choice
を 24 合成ステップ走らせた結果。上から見たラット silhouette + **inter-event
behaviour 合成** — 記録間の補間フレームを Falk (1961, 1971) および
Staddon & Simmelhag (1971) に従い 3 相（adjunctive: 餌ホッパー前、
interim: チャンバ中央で wandering、terminal: 次の operandum へ接近）に
分類して描画する。強化が起きたステップで餌ホッパー（下のグレー四角）が
黄色く発光する。デモ MP4 は commit されていないため、ローカルで
[`docs/examples/demo_session.py`](docs/examples/demo_session.py) を
実行して生成する:

```bash
.venv/bin/python docs/examples/demo_session.py
# 出力:
#   docs/assets/demo.mp4         — ラット + 3 相 inter-event behaviour、12 fps
#   docs/assets/demo_strict.mp4  — 球 + 記録ステップのみ、4 fps
```

厳密フィデリティ版は球スタイル・1 記録ステップ = 1 フレーム・合成
フィルタなし。可視化を記録イベントと 1:1 対応させたい場合に使う。

## 概要

```
任意のセッション producer
        │  (実行 + 記録)
        ▼
+-------------------------+        +-------------------------+
|  CSV / JSONL recording  |  -->   | result-chamber-animator |
+-------------------------+        +-------------------------+
                                            │
                       ┌────────────────────┼────────────────────┐
                       ▼                    ▼                    ▼
                   静止画 PNG        アニメーション MP4     アニメーション GIF
```

公開 API:

```python
from result_chamber_animator import (
    Chamber, Operandum, default_two_lever_chamber,
    StepFrame, render_frame, animate, steps_from_dataframe,
)
```

CLI:

```bash
# 主デモ: ラット + 3 相 inter-event behaviour
result-chamber-animator session.csv --mp4 out.mp4 \
    --subject rat --inter-event-behavior --fps 12

# 厳密 1 記録 = 1 フレーム（デフォルト, 球スタイル）
result-chamber-animator session.csv --mp4 out.mp4 --fps 4
```

## インストール

```bash
mise exec -- python -m venv .venv
.venv/bin/python -m pip install -e ".[dev]"
```

## テスト実行

```bash
.venv/bin/python -m pytest -q
```

## CLI

```bash
# セッション全体を MP4 に（ffmpeg が PATH 上に必要）
result-chamber-animator session.csv --mp4 out.mp4 --fps 10

# GIF フォールバック（ffmpeg 不要、ファイルサイズは大きくなる）
result-chamber-animator session.csv --gif out.gif --fps 5

# 単一ステップの静止画 PNG
result-chamber-animator session.csv --frame 42 --png frame42.png

# JSONL 入力（session_recorder からのエクスポートなど）
result-chamber-animator session.jsonl --mp4 out.mp4

# ラット / ハト風被験体
result-chamber-animator session.csv --mp4 out.mp4 --subject rat
result-chamber-animator session.csv --mp4 out.mp4 --subject pigeon

# 記録間にフィルタフレームを挿入し、各フレームを adjunctive / interim
# / terminal の 3 相に分類する（下記「Inter-event behaviour 合成」参照）。
# 記録と 1:1 対応しない合成フレームなので、厳密フィデリティが必要な
# 場合は OFF にする。
result-chamber-animator session.csv --mp4 out.mp4 \
    --inter-event-behavior --fps 12

# 相ウィンドウの調整
result-chamber-animator session.csv --mp4 out.mp4 \
    --inter-event-behavior \
    --adjunctive-window 3.0 --terminal-window 1.5

# --seed で jitter を再現可能に
result-chamber-animator session.csv --mp4 out.mp4 \
    --inter-event-behavior --seed 0
```

## 被験体イラストのスタイル

チャンバ自体は 3D（ワイヤーフレーム + operanda + 餌ホッパー）で描画
するが、被験体は **チャンバ床に貼り付けた 2D 上面シルエットを鉛直軸
まわりに回転させて方向を合わせる** Live2D / VTuber 流儀（2D rigged
スプライトを 3D シーン内に配置する手法）を採用している。教科書風の
operant-chamber 図解との相性が良い。

| `--subject` | 描画される内容 | 補足 |
|---|---|---|
| `sphere`（デフォルト） | 床に置いた茶色い球 1 個 | 最小ベースライン。被験体を「位置」だけに抽象化 |
| `rat` | 上から見たラット silhouette: 尖った吻、耳、胴体、長く細い尻尾 | 塗りつぶし polygon, 約 33 頂点 |
| `pigeon` | 上から見たハト silhouette: 尖ったくちばし、頭、胴体、尾扇 | 塗りつぶし polygon, 約 28 頂点 |

シルエットはチャンバの鉛直軸まわりに回転し、吻 / くちばしが押した
operandum 方向を向く。`--free-operant` 補間フレームでは、わずかな
正弦波のスケール脈動（約 ±4%）が加わり「呼吸」しているような印象を
与える。`--free-operant` を OFF にすれば脈動も消え、記録 1 ステップ
= 1 フレームに戻る。

## Inter-event behaviour 合成

シミュレータは離散整数ステップでイベントを記録する。実際にはイベント
の合間に被験体は何かをしており、行動分析学はその「何か」を時間的に
構造化された連続列として特徴づけてきた。本レンダラは記録間にフィルタ
フレームを挿入し、各フレームをスキナー以降の標準的分類に基づき 3 相に
分類する:

| 相 | タイミング | 描画位置 | 出典 |
|---|---|---|---|
| **Adjunctive（補助行動相）** | 強化後 `adjunctive_window_s` 秒以内 | 餌ホッパー前（強化後の摂食・飲水・グルーミング；Falk の adjunctive） | Falk (1961); Falk (1971) |
| **Terminal（終末相）** | 次の記録反応の `terminal_window_s` 秒以内 | 直前の anchor から押される operandum へ移動 | Staddon & Simmelhag (1971) |
| **Interim（合間相）** | それ以外（イベント間の中盤） | チャンバ中央で wandering — schedule-induced な displacement 様活動 | Staddon & Simmelhag (1971); Timberlake & Lucas (1985) |

境界では adjunctive が terminal に優先する — 短い inter-event 間隔
（例: dt=1s で強化直後の次反応）が「terminal」に分類されると経験的相
順序と矛盾するため、強化直後はまず magazine 指向相とする。

```python
animate(
    frames,
    inject_inter_event_behavior=True,  # デフォルト OFF
    adjunctive_window_s=3.0,            # 強化後 hopper 指向相の長さ
    terminal_window_s=1.5,              # 反応前 approach 相の長さ
    jitter_amplitude=0.005,             # 最大ランダム変位（m）
    seed=0,                             # jitter を決定的にする
    fps=12,
)
```

**合成フレームは記録イベントに対応しない**。これは inter-event 区間の
*behaviour-systems モデル* であり、データのリプレイではない。強化
フラッシュは実際の記録ステップでのみ発火する。可視化を記録と 1:1
一致させたい場合は必ず OFF にすること。

参考文献 (APA 7):

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

## プログラムからの利用

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

## 制約

- 記録済みデータの消費側ツール。ライブシミュレーションは行わない。
- 離散時間。記録された各ステップを 1 フレームとして描画する。
- ジオメトリは意図的に簡素（直方体チャンバ、球型エージェント、
  特定メーカーの装置寸法は再現しない）。
- MP4 出力には `ffmpeg` が `PATH` 上に必要。

## 参考文献

- Skinner, B. F. (1938). *The behavior of organisms: An experimental
  analysis*. Appleton-Century.
- Lattal, K. A. (2004). Steps and pips in the history of the cumulative
  recorder. *Journal of the Experimental Analysis of Behavior*, *82*(3),
  329-355. https://doi.org/10.1901/jeab.2004.82-329
