# Changelog

本プロジェクトの変更履歴。[Keep a Changelog](https://keepachangelog.com/ja/1.1.0/) 準拠、
バージョンは [Semantic Versioning](https://semver.org/lang/ja/) に従う。

## [Unreleased]

（次の変更をここに追記する）

## [0.1.0] - 2026-07-02

初回リリース。core / CLI / MCP(stdio) の3経路、CI、実利用（VS Code + Copilot）検証まで完了。

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

[Unreleased]: https://github.com/tmlksu/nbedit-mcp/compare/v0.1.0...HEAD
[0.1.0]: https://github.com/tmlksu/nbedit-mcp/releases/tag/v0.1.0
