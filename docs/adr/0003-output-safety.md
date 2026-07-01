# 0003: outputs は読み取り専用・source 変更で消去

- Status: Accepted
- Date: 2026-07-01

## Context

AI がセルを編集する時、古い実行結果（outputs）を新しい source と一緒に保存してしまうと、
「コードは変わったのに結果は前のまま」という不整合な notebook が生まれる。これは実害のある事故。

## Decision

- outputs を書き込むツール/引数は提供しない（読み取りは `read_cell` で可能）。
- コードセルの source を変更する操作（`edit_cell` / `patch_cell`）では、
  そのセルの `outputs` を空にし `execution_count` を `None` にリセットする。
- source が変わらない操作（`move_cell` 等）では outputs を保持する。

## Consequences

- 保存された notebook で「source と outputs が食い違う」状態を構造的に作れない。
- 再実行は呼び出し側に委ねる（[ADR-0002](0002-no-kernel-execution.md)）。編集後は必ず未実行状態になる。
- 制約: 「source を微修正しても結果は残したい」ユースケースには応えない（安全性を優先）。

## Alternatives considered

- **outputs をそのまま保持**: 実装は楽だが、まさに上記の不整合事故を許す。却下。
- **編集時に警告だけ出して保持**: MCP 経由だと警告が無視されやすい。強制クリアを選択。
