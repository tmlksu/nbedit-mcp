# Architecture Decision Records (ADR)

このプロジェクトの設計判断を1決定1ファイルで記録する。目的は**再検討コストの削減**：
「なぜこうなっているか」をここに凍結し、蒸し返しを防ぐ。

## 運用ルール

- 1つの ADR は1つの決定。確定後は原則**書き換えない**。
- 決定を覆す時は、既存 ADR を `Superseded by ADR-XXXX` に変更し、**新しい ADR を追加**する。
- フォーマットは軽量 MADR: `Status` / `Context` / `Decision` / `Consequences` / `Alternatives considered`。
- 新規番号は連番。ファイル名は `NNNN-kebab-title.md`。

## 一覧

| # | タイトル | Status |
|---|---|---|
| [0001](0001-layered-architecture.md) | core / cli / mcp の3層分離 | Accepted |
| [0002](0002-no-kernel-execution.md) | カーネル実行をスコープ外にする | Accepted |
| [0003](0003-output-safety.md) | outputs は読み取り専用・source 変更で消去 | Accepted |
| [0004](0004-patch-uniqueness.md) | patch_cell は一意一致を必須にする | Accepted |
| [0005](0005-custom-exceptions.md) | 独自の NotebookError 例外階層 | Accepted |
| [0006](0006-atomic-write-and-backup.md) | atomic write + 1世代 .bak | Accepted |
| [0007](0007-mcp-fastmcp-and-paths.md) | MCP は FastMCP、path はそのまま受ける | Accepted |
| [0008](0008-summary-convention.md) | 先頭 `#` コメントによるセル要約の規約 | Accepted |
| [0009](0009-output-rendering.md) | 読み取り時の outputs 整形（実行はしない） | Accepted |
| [0010](0010-batch-read.md) | 複数セルの一括読み取り（read_cells に一本化） | Accepted |
| [0011](0011-explicit-summary-metadata.md) | 明示要約を cell metadata に保存（0008 の metadata 却下を修正） | Accepted |
