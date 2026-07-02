# Changelog

本プロジェクトの変更履歴。[Keep a Changelog](https://keepachangelog.com/ja/1.1.0/) 準拠、
バージョンは [Semantic Versioning](https://semver.org/lang/ja/) に従う。

## [Unreleased]

### Added

- `read_cells(path, indices)`: 複数セルを1回で読み取る（要求順・重複可）。全 index を先に検証し、
  不正があれば列挙して `CellIndexError`（部分成功なし）。ADR-0010。
- `insert_cell` / `edit_cell` に optional `summary` 引数。`cell.metadata['summary']` に保存し、
  `list_cells` の `summary` で **metadata > 先頭 `#` コメント > 先頭行** の優先で表示。ADR-0011。
- ADR 0010（batch read）/ 0011（明示要約の metadata 保存、0008 の metadata 却下を修正）。

### Changed (breaking, pre-1.0)

- `read_cell`（単一）を廃し `read_cells`（複数）に一本化。単一読み取りは `[i]` を渡す。

## [0.2.0] - 2026-07-02

要約アウトラインと出力の整形読み取り。実行機能は追加していない（ADR-0002/0003 維持）。

### Added

- `list_cells` に `summary`（先頭 `#` コメント block、cap 3行/100字。無ければ1行プレビュー）と
  `has_error`（コードセルの outputs にエラーがあるか）を追加。要約規約は ADR-0008。
- `read_cell` にコードセル outputs の整形ビュー `outputs_text` / `has_error` / `output_types` を追加
  （stream/結果連結、エラー強調、画像は `[image/png]`、2000字 truncate）。実行はしない。ADR-0009。
- ADR 0008（要約規約）/ 0009（outputs 整形）。insert/edit の tool description に要約規約を明記。

### Changed (breaking, pre-1.0)

- `list_cells`: `source_preview`（1行）→ `summary`（複数行可）に置換。
- `read_cell`: raw な `outputs` を廃し `outputs_text` / `has_error` / `output_types` に置換。

## [0.1.0] - 2026-07-02

初回リリース。core / CLI / MCP(stdio) の3経路、CI、MCP クライアントからの実利用検証まで完了。

### Added

- コアロジック `notebook_edit/core.py`: `list_cells` / `read_cell` / `insert_cell` /
  `edit_cell` / `patch_cell` / `delete_cell` / `move_cell`。
- 独自例外階層 `NotebookError` / `CellIndexError` / `CellTypeError` / `PatchError`。
- 安全な書き込みパイプライン `_save()`: `nbformat.validate` → 1世代 `.ipynb.bak` →
  一時ファイル → `os.replace`（atomic）。
- コードセルの source 変更時に stale な outputs / execution_count を消去。
- CLI `notebook_edit/cli.py`（argparse、エントリポイント `nb-edit`）。JSON 出力・終了コード。
- MCP stdio サーバー `notebook_edit/mcp_server.py`（FastMCP、エントリポイント `nb-edit-mcp`）。
  7 ツールを公開、`NotebookError` を `ToolError` に変換。
- pytest スイート `tests/test_core.py`（24 件）+ `tests/test_mcp_stdio.py`（3 件、
  サーバーを実サブプロセス起動して tool 列挙・ラウンドトリップ・`isError` を検証）。計 27 件。
- dev 依存 `pytest-asyncio`（stdio テスト用、`asyncio_mode = "auto"`）。
- GitHub Actions CI `.github/workflows/ci.yml`: Python 3.10/3.11/3.12 で `uv sync` → `pytest`。
- ドキュメント: README（CI バッジ付き）、CLAUDE.md、ADR 0001–0007、本 CHANGELOG、HANDOFF.md。
- パッケージング: `pyproject.toml`（hatchling、2 エントリポイント、依存 `nbformat` + `mcp`）。

[Unreleased]: https://github.com/tmlksu/nbedit-mcp/compare/v0.2.0...HEAD
[0.2.0]: https://github.com/tmlksu/nbedit-mcp/compare/v0.1.0...v0.2.0
[0.1.0]: https://github.com/tmlksu/nbedit-mcp/releases/tag/v0.1.0
