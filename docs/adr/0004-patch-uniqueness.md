# 0004: patch_cell は一意一致を必須にする

- Status: Accepted
- Date: 2026-07-01

## Context

`patch_cell(old, new)` は diff ノイズを減らす本命ツール。だが `old` がセル内に複数回現れる時、
どこを置換するか曖昧だと AI が意図しない箇所を書き換える危険がある。

## Decision

`old` はセル内で**ちょうど1回**一致することを必須とする。
0回一致・2回以上一致はいずれも `PatchError` を送出し、「文脈を足して一意にせよ」と促す。
Anthropic の str_replace editor と同じ契約。

## Consequences

- AI は曖昧な置換を強制的に回避し、必ず一意な文脈を指定する。
- 返り値は常に `{"replacements": 1}`（契約上固定）。スキーマが安定する。
- 制約: 「全部まとめて置換」はできない。必要になったら `replace_all` フラグを足す新 ADR を検討。

## Alternatives considered

- **全一致を置換**: 一括編集は楽だが over-edit を silently 許す。却下。
- **最初の一致だけ置換**: 「最初」がどこか AI に見えず、事故りやすい。却下。
