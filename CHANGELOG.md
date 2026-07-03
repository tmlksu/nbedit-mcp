# Changelog

本プロジェクトの変更履歴。[Keep a Changelog](https://keepachangelog.com/ja/1.1.0/) 準拠、
バージョンは [Semantic Versioning](https://semver.org/lang/ja/) に従う。

## [Unreleased]

### Added

- **セルを `id` でも指定可能に**（index と併用、ADR-0014）。nbformat 4.5+ の安定した `cell.id` を使い、
  insert/delete/move で index がズレても同じセルを指し続けられる。patch 連発時の stale index 事故を防ぐ。
  - `read_cells(path, indices=None, offset=0, ids=None)`: `indices` か `ids` の一方で指定。
  - `edit_cell` / `patch_cell` / `delete_cell` に `cell_id`、`move_cell` に `from_id` を追加（対象セルの指定）。
    挿入位置（`insert*` の `index`、`move` の `to_index`）は index のまま。
  - 未発見・重複 id は `CellIndexError` で**即エラー**（index の「静かに別セルを書き換える」を回避）。
  - `list_cells` / `read_cells` の各エントリと、`insert*`/`edit`/`patch`/`delete`/`move` の戻り値に
    `id`（複数は `ids`）を追加。→ 一覧を1回見れば以降 id で全部指せる。

### Changed

- CLI: 既存セルを指すコマンド（`edit-cell`/`patch-cell`/`delete-cell`）の対象指定を位置 index から
  `--index` / `--id`（排他・必須）に変更。`move-cell` は `--from-index` / `--from-id` を追加（移動先 `to_index`
  は位置引数のまま）。`read-cells` は従来の位置 index を残しつつ `--id` を追加。

## [0.5.0] - 2026-07-02

複数セルの一括挿入（連続 insert_cell の round-trip を削減）。

### Added

- `insert_cells(path, index, cells)`: 複数セルを `index` の前に連続挿入（1往復・index ズレ管理不要）。
  `cells` は `{cell_type, source, summary?}` のリスト。atomic（全 item 前検証、不正なら該当を名指しして
  無変更）。戻り値 `{"indices": [...]}`。単発 `insert_cell` は残す。ADR-0013。
- CLI `insert-cells path index --json '[...]'`。

## [0.4.0] - 2026-07-02

大きい読み出し結果でコンテキストを圧迫しないためのサイズ上限。

### Added

- `read_cells` のサイズ上限（ADR-0012）。各セルの `source` を 8000字窓に切り、
  `source_offset`/`source_length`/`source_truncated` を付与。`offset` 引数でページング可能。
- `read_cells` のレスポンス総量バジェット 20000字。超過分は
  `{index, type, source_length, content_omitted: true}` として返す。
- CLI `read-cells` に `--offset`。ADR-0012。

## [0.3.0] - 2026-07-02

複数セルの一括読み取りと、明示的なセル要約（metadata 保存）。

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

[Unreleased]: https://github.com/tmlksu/nbedit-mcp/compare/v0.5.0...HEAD
[0.5.0]: https://github.com/tmlksu/nbedit-mcp/compare/v0.4.0...v0.5.0
[0.4.0]: https://github.com/tmlksu/nbedit-mcp/compare/v0.3.0...v0.4.0
[0.3.0]: https://github.com/tmlksu/nbedit-mcp/compare/v0.2.0...v0.3.0
[0.2.0]: https://github.com/tmlksu/nbedit-mcp/compare/v0.1.0...v0.2.0
[0.1.0]: https://github.com/tmlksu/nbedit-mcp/releases/tag/v0.1.0
