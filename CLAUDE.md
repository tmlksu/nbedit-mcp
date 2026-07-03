# CLAUDE.md

このリポジトリで作業する LLM/開発者が最初に読む恒久ドキュメント。
「今の状態・次の一手」は [HANDOFF.md](HANDOFF.md)、決定の理由は [docs/adr/](docs/adr/)、
変更履歴は [CHANGELOG.md](CHANGELOG.md) を参照。

## プロジェクト概要

Jupyter notebook (`.ipynb`) の**構造編集**に特化した MCP サーバー兼 CLI。
MCP 対応クライアント（AI エージェント）から stdio 経由で `.ipynb` を編集させるのが主用途。
CLI としても直接使える。Git URL またはローカル path 指定で `uvx` から実行できる。

### スコープ境界（意図的に狭い）

- **やること**: セルの構造編集（list / read / insert / edit / patch / delete / move）
- **やらないこと**: カーネル実行。実行は呼び出し側のクライアント／カーネルに任せる。
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
7. **`list_cells` の `summary` の優先順位は metadata > 先頭 `#` コメント > 先頭行**（cap 3行/100字）、
   と `has_error` を返す（旧 `source_preview` は廃止）。要約規約は
   [ADR-0008](docs/adr/0008-summary-convention.md) + [ADR-0011](docs/adr/0011-explicit-summary-metadata.md)。
8. **読み取りは `read_cells(path, indices, offset=0)` に一本化**（単一は `[i]`）。全 index を先に検証し、
   不正があれば列挙して `CellIndexError`（部分成功なし）（[ADR-0010](docs/adr/0010-batch-read.md)）。
   結果は cap 済み: source は 8000字窓（`offset` でページング）、レスポンス総量 20000字で以降は
   `content_omitted`。切り詰めは必ずマーカー付きで返す（[ADR-0012](docs/adr/0012-large-read-limits.md)）。
9. **outputs は整形して返す**（`outputs_text`/`has_error`/`output_types`）。raw な output 辞書は返さない。
   実行はしない（既存 outputs を読むだけ）（[ADR-0009](docs/adr/0009-output-rendering.md)）。
10. **`insert_cell`/`edit_cell` の optional `summary` は `cell.metadata['summary']` に保存**
    （[ADR-0011](docs/adr/0011-explicit-summary-metadata.md)）。
11. **一括挿入 `insert_cells(path, index, cells)` は atomic**（全 item 前検証→1回で書く）。
    単発 `insert_cell` は残す（write は低リスク版を保持）（[ADR-0013](docs/adr/0013-batch-insert.md)）。
12. **既存セルは `index` または `id` で指定**（`read`/`edit`/`patch`/`delete`/`move` の対象）。
    `core._resolve` に一元化し、両方・なしはエラー。id（nbformat 4.5+ の `cell.id`）は shift しない。
    未発見・重複 id は `CellIndexError` で即エラー（静かな誤爆を作らない）。**挿入位置は index のまま**
    （`insert*` の `index`、`move` の `to_index`）。`list_cells`/`read_cells`/各変更系の戻り値は `id` を含む
    （[ADR-0014](docs/adr/0014-cell-id-addressing.md)）。
13. **`create_notebook` は既存ファイルを上書きしない**（存在すれば `NotebookError`）。親ディレクトリが
    無ければエラー（勝手に mkdir しない）。初期セルは `insert_cells` 形式・前検証を再利用し、不正なら何も作らない
    （[ADR-0015](docs/adr/0015-create-notebook.md)）。作成は notebook 単位、他ツールは cell 単位（既存前提）。
14. **バージョンの源は `notebook_edit/__init__.py` の `__version__` ただ1つ**（[ADR-0016](docs/adr/0016-version-single-source.md)）。
    pyproject は `dynamic=["version"]` で hatchling がここを読む。CLI（`nb-edit --version`）と MCP の
    initialize `serverInfo.version` も `__version__` を名乗る（`mcp._mcp_server.version` に設定）。
    静的な `version=` を pyproject に**書き戻さない**（0.1.0 ドリフトの原因）。

## 開発フロー

```bash
uv sync                 # 依存インストール
uv run pytest -q        # テスト（現在 75 件）
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

## リリース手順（バージョンは tag と `__version__` を必ず揃える）

配布は `uvx --from git+…@<tag>` の **git tag 参照**。バージョンの源は `__version__`（不変条件14）。
tag を切るときは `__version__` も同じ値に上げる。過去に pyproject が `0.1.0` のまま取り残された事故
（[ADR-0016](docs/adr/0016-version-single-source.md)）を再発させないため、次の順で行う:

1. feature コミット（core/tests/wrappers/ADR/README、CHANGELOG は `[Unreleased]` のまま）。
2. **finalize コミット**「Finalize vX.Y.0 …」で3点を同時に:
   - `notebook_edit/__init__.py` の `__version__` を `X.Y.0` に bump、
   - `CHANGELOG.md` の `[Unreleased]` を `[X.Y.0] - <date>` に確定、
   - `HANDOFF.md` を「リリース済み」に更新。
3. `uv sync`（editable メタデータを新 version に更新）→ `uv run pytest -q` green を確認。
   `nb-edit --version` == `importlib.metadata.version("notebook-edit")` == tag を目視確認。
4. annotated tag `vX.Y.0`（前例の tagger メッセージ形式）→ `git push origin main` と `git push origin vX.Y.0`。
