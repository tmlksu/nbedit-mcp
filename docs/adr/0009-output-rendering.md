# 0009: 読み取り時の outputs 整形

- Status: Accepted
- Date: 2026-07-02

## Context

AI が「実行結果を見たい」場面がある。実行自体は Copilot 側に残す（[ADR-0002](0002-no-kernel-execution.md)）が、
**既存の outputs を読む**のはスコープ内。ただし nbformat の raw な output 辞書は
base64 画像や mimebundle を含み、そのまま AI コンテキストへ流すのは無駄が多く読みにくい。

## Decision

`read_cell` はコードセルの outputs を**整形して**返す（raw な output 辞書は返さない）。

- stream → text 連結、`execute_result`/`display_data` → `text/plain`、画像は `[image/png]` プレースホルダ。
- error → `ename: evalue` + traceback を強調表示。
- 全体を 2000 字で truncate。
- 戻り値: `outputs_text`（整形済 str）/ `has_error`（bool）/ `output_types`（list）。
- `list_cells` にも `has_error` を出し、一覧で「どのセルがコケてるか」を可視化。

実行はしない。ここで読むのはファイルに既に保存された outputs のみ（[ADR-0003](0003-output-safety.md) の read-only 範囲内）。

## Consequences

- AI が結果・エラーを軽量に確認でき、編集→（Copilot が実行）→確認のループが回る。
- base64 画像などの重い raw をコンテキストに流さない。
- 破壊的変更: `read_cell` の `outputs`(raw) → `outputs_text`/`has_error`/`output_types`（pre-1.0 のため許容）。
- 制約: raw output が必要な高度な用途には応えない（read-only の整形ビューに徹する）。

## Alternatives considered

- **raw outputs をそのまま返す**: 重く読みにくい。AI 用途に不適。却下。
- **実行機能を足して結果を得る**: [ADR-0002](0002-no-kernel-execution.md) 違反。依存肥大。却下。
