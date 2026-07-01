# CLAUDE.md

このリポジトリで作業する LLM/開発者が最初に読む恒久ドキュメント。
「今の状態・次の一手」は [HANDOFF.md](HANDOFF.md)、決定の理由は [docs/adr/](docs/adr/)、
変更履歴は [CHANGELOG.md](CHANGELOG.md) を参照。

## プロジェクト概要

Jupyter notebook (`.ipynb`) の**構造編集**に特化した MCP サーバー兼 CLI。
GitHub Copilot (VS Code) から MCP stdio 経由で `.ipynb` を編集させるのが主用途。
CLI としても直接使える。PyPI 公開はせず、社内 Git 配布 or ローカル path 指定で `uvx` から叩く想定。

### スコープ境界（意図的に狭い）

- **やること**: セルの構造編集（list / read / insert / edit / patch / delete / move）
- **やらないこと**: カーネル実行。実行は Copilot / Azure Codex 側の既存機能に任せる。
  → 「実行する」系のツールや依存を足したくなったら、まず [ADR-0002](docs/adr/0002-no-kernel-execution.md) を読むこと。

## アーキテクチャ

コアと2つのインターフェースを分離。ロジックは `core.py` に一元化し、CLI/MCP は薄いラッパーに保つ。

```
notebook_edit/
├── core.py        # nbformat 操作の実体。ここだけがロジックを持つ
├── cli.py         # argparse ラッパー（core を呼んで JSON 出力）
└── mcp_server.py  # FastMCP (stdio) ラッパー（core を呼んで tool 化）
```

- CLI と MCP は**同じ core 関数を呼ぶだけ**。ロジックを両方に書かない（[ADR-0001](docs/adr/0001-layered-architecture.md)）。
- 新機能はまず `core.py` に純粋寄りの関数として実装し、両ラッパーから公開する。

## 不変条件（勝手に変えない。変えるなら ADR を追加）

これらは設計判断として確定済み。破るとテストが落ちるか、安全性要件を壊す。

1. **インデックスは 0 始まり、負値は禁止**（AI の off-by-one 事故を防ぐため明示エラー）。
2. **書き込みは必ず `_save()` 経由**: `nbformat.validate()` → `.ipynb.bak`（1世代）→ 一時ファイル → `os.replace`（atomic）。
   個別関数が直接 `nbformat.write()` を呼ばない（[ADR-0006](docs/adr/0006-atomic-write-and-backup.md)）。
3. **outputs は読み取り専用**。outputs を書くツールは作らない。
   コードセルの source を変更（edit/patch）したら `outputs` と `execution_count` をクリアする（[ADR-0003](docs/adr/0003-output-safety.md)）。
   ただし move はクリアしない（source が変わらないため）。
4. **patch_cell の `old` はちょうど1回一致必須**。0回・複数回は `PatchError`（[ADR-0004](docs/adr/0004-patch-uniqueness.md)）。
5. **エラーは `NotebookError` 階層で送出**（`CellIndexError` / `CellTypeError` / `PatchError`）。
   ラッパーはこれを捕捉して整形する（CLI→終了コード1+stderr、MCP→ToolError）（[ADR-0005](docs/adr/0005-custom-exceptions.md)）。
6. **cell_type は `code` / `markdown` / `raw` のみ**。
7. **`list_cells` は `summary`（先頭 `#` コメント block、cap 3行/100字）と `has_error` を返す**
   （旧 `source_preview` は廃止）。要約規約は [ADR-0008](docs/adr/0008-summary-convention.md)。
8. **`read_cell` は outputs を整形して返す**（`outputs_text`/`has_error`/`output_types`）。
   raw な output 辞書は返さない。実行はしない（既存 outputs を読むだけ）（[ADR-0009](docs/adr/0009-output-rendering.md)）。

## 開発フロー

```bash
uv sync                 # 依存インストール
uv run pytest -q        # テスト（現在 24 件）
uv run nb-edit --help   # CLI
uv run nb-edit-mcp      # MCP stdio サーバー（手動起動）
```

MCP を実 stdio で叩く結合確認は現状スクラッチのスクリプトのみ（[HANDOFF.md](HANDOFF.md) 参照、CI 未整備）。

## 新しいツール/機能を追加する手順（チェックリスト）

1. `core.py` に関数を追加。書き込み系は必ず `_load` → 変更 → `_save` の順。エラーは `NotebookError` 系で送出。
2. `tests/test_core.py` にラウンドトリップ + エラーパス + 安全性（bak/atomic）を追加。
3. `mcp_server.py` に `@mcp.tool()` を追加（description は 0始まり・patch推奨・outputs読取専用を明示。モデルがこれを読む）。
4. `cli.py` に subparser を追加。
5. `README.md` のツール表、`CHANGELOG.md` の `[Unreleased]`、必要なら ADR を更新。
6. 設計判断を伴う変更なら **ADR を1本足す**（既存 ADR は書き換えず、Superseded にして新規追加）。

## ドキュメント運用

- **CLAUDE.md**（本ファイ）: 恒久ルール。設計が変わった時だけ更新。
- **HANDOFF.md**: 毎セッション末に「今の状態・次の一手」を上書き。次のセッションはまずここを読む。
- **docs/adr/**: 1決定1ファイル。確定後は不変（覆すなら新 ADR で Supersede）。
- **CHANGELOG.md**: Keep a Changelog 準拠。変更は `[Unreleased]` に追記。
