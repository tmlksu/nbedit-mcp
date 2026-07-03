# notebook-edit

[![CI](https://github.com/tmlksu/nbedit-mcp/actions/workflows/ci.yml/badge.svg)](https://github.com/tmlksu/nbedit-mcp/actions/workflows/ci.yml)

Jupyter notebook (`.ipynb`) の**構造編集**に特化した MCP サーバー兼 CLI。
カーネル実行は行わない（実行は呼び出し側のクライアント／カーネルに任せる）。

コアロジック (`core.py`) を CLI (`cli.py`) と MCP サーバー (`mcp_server.py`) が
薄くラップする構成。ロジックは一箇所だけ。

```
notebook_edit/
├── core.py        # nbformat 操作の実体
├── cli.py         # argparse ラッパー
└── mcp_server.py  # FastMCP (stdio) ラッパー
```

## 安全性

- 書き込み前に `nbformat.validate()` を通す（不正なら書かない）
- 一時ファイル → `os.replace` による atomic write
- 書き込み前に `.ipynb.bak` を1世代だけ残す
- outputs（実行結果）は読み取り専用。コードセルの source を変更すると、
  古い outputs と execution_count はクリアされる（stale な実行結果の混入を防止）

## セットアップ

```bash
uv sync
```

## CLI

```bash
uv run nb-edit list-cells   foo.ipynb
uv run nb-edit read-cells   foo.ipynb 0 2 5                  # 複数 index を一括
uv run nb-edit read-cells   foo.ipynb --id a1b2c3d4          # id で読む
uv run nb-edit insert-cell  foo.ipynb 1 code "print('hi')" --summary "挨拶"  # 1セル挿入
uv run nb-edit insert-cells foo.ipynb 1 --json '[{"cell_type":"code","source":"import os"}]'  # 一括
uv run nb-edit edit-cell    foo.ipynb "x = 42" --index 2     # 全文置換
uv run nb-edit patch-cell   foo.ipynb "x = 42" "x = 99" --id a1b2c3d4  # 部分置換（推奨）
uv run nb-edit delete-cell  foo.ipynb --index 2
uv run nb-edit move-cell    foo.ipynb 3 --from-id a1b2c3d4   # id のセルを 3 番目へ
```

- インデックスは 0 始まり。負値は不可。
- 既存セルを指す `edit`/`patch`/`delete`/`move`/`read` は **`--index` または `--id`**（id は
  `list-cells` が返す安定 ID。insert/delete/move してもズレない）。挿入位置は index のまま。
- 結果は JSON で stdout に出力。エラーは stderr + 終了コード 1。

## MCP サーバー

MCP 対応クライアントの stdio サーバー設定に `nb-edit-mcp` を登録する。設定ファイルの
場所・形式はクライアントによって異なるが、`command` / `args` は概ね共通。

ローカルの作業コピーを使う場合:

```json
{
  "servers": {
    "notebook-edit": {
      "command": "uvx",
      "args": ["--from", "/path/to/nbedit-mcp", "nb-edit-mcp"]
    }
  }
}
```

Git から取得する場合は `--from` を Git URL に差し替える:

```json
"args": ["--from", "git+https://github.com/<owner>/nbedit-mcp", "nb-edit-mcp"]
```

相対パスはサーバーの CWD（通常はクライアントが開いているプロジェクト）基準で解決される。

### 公開ツール

| ツール | 引数 | 説明 |
|--------|------|------|
| `list_cells` | `path` | 全セルの目次（`id` + `summary` + `has_error`） |
| `read_cells` | `path, [indices], [offset], [ids]` | 複数セルを一括読み取り（`indices` か `ids` の一方。source 窓＋`outputs_text`/`has_error`/`output_types`） |
| `insert_cell` | `path, index, cell_type, source, [summary]` | index の前に1セル挿入 |
| `insert_cells` | `path, index, cells` | 複数セルを index の前に一括挿入（atomic） |
| `edit_cell` | `path, source, [index|cell_id], [summary]` | 全文置換 |
| `patch_cell` | `path, old, new, [index|cell_id]` | 一意な部分文字列を置換（**推奨**） |
| `delete_cell` | `path, [index|cell_id]` | 削除 |
| `move_cell` | `path, to_index, [from_index|from_id]` | 移動（移動先は index、対象は index/id） |

`cell_type` は `code` / `markdown` / `raw`。
`patch_cell` の `old` はセル内で**ちょうど1回**一致する必要がある
（0回・複数回はエラー → 文脈を足して一意にする）。

- **セル指定**: 既存セルを指すツール（`read`/`edit`/`patch`/`delete`/`move` の対象）は
  **`index`（0始まり）または `id`（安定 ID）のどちらか一方**。`id` は `list_cells`/`read_cells` が返し、
  insert/delete/move してもズレないので、一覧後は `id` 指定が安全（stale index 事故を防ぐ）。
  見つからない／重複 id は**即エラー**（index の「静かに別セルを書き換える」を回避）。ADR-0014。
  挿入位置（`insert*` の `index`、`move` の `to_index`）は位置概念なので index のまま。
  各変更系の戻り値も `id`（複数は `ids`）を返す。

### 要約規約と出力の扱い

- **要約**: `list_cells` の `summary` は **metadata > 先頭 `#` コメント > 先頭行** の優先順位
  （最大 3 行 / 各 100 字）。`insert_cell` / `edit_cell` の `summary` 引数で明示指定すると
  `cell.metadata['summary']` に保存され、以降の一覧が確実に目次として機能する。
- **出力**: `read_cells` は既存の実行結果を整形して返す（`outputs_text`：stdout/結果を連結、
  エラーは強調、画像は `[image/png]` プレースホルダ、2000 字で truncate）。
  **セル実行はしない**——実行はクライアント／カーネル側に任せ、本ツールは保存済み outputs を読むだけ。
- **サイズ上限**: `read_cells` は結果を cap する。各セルの `source` は 8000 字窓
  （`source_truncated`/`source_length` 付き、`offset` でページング）、レスポンス総量は 20000 字。
  超過分のセルは `content_omitted: true` で返るので、小さいバッチや `offset` で読み直す。

## テスト

```bash
uv run pytest -q
```
