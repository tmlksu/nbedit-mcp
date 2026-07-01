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
uv run nb-edit read-cell    foo.ipynb 2
uv run nb-edit insert-cell  foo.ipynb 1 code "print('hi')"   # index の前に挿入
uv run nb-edit edit-cell    foo.ipynb 2 "x = 42"             # 全文置換
uv run nb-edit patch-cell   foo.ipynb 2 "x = 42" "x = 99"    # 部分置換（推奨）
uv run nb-edit delete-cell  foo.ipynb 2
uv run nb-edit move-cell    foo.ipynb 0 3
```

- インデックスは 0 始まり。負値は不可。
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
| `list_cells` | `path` | 全セルの目次（`summary` + `has_error`） |
| `read_cell` | `path, index` | セル全文＋出力の整形ビュー（`outputs_text`/`has_error`/`output_types`） |
| `insert_cell` | `path, index, cell_type, source` | index の前に挿入 |
| `edit_cell` | `path, index, source` | 全文置換 |
| `patch_cell` | `path, index, old, new` | 一意な部分文字列を置換（**推奨**） |
| `delete_cell` | `path, index` | 削除 |
| `move_cell` | `path, from_index, to_index` | 移動 |

`cell_type` は `code` / `markdown` / `raw`。
`patch_cell` の `old` はセル内で**ちょうど1回**一致する必要がある
（0回・複数回はエラー → 文脈を足して一意にする）。

### 要約規約と出力の扱い

- **要約**: コードセルの先頭に連続する `#` コメントを書くと、それが `list_cells` の `summary`
  になる（最大 3 行 / 各 100 字）。一覧が目次として機能する。
- **出力**: `read_cell` は既存の実行結果を整形して返す（`outputs_text`：stdout/結果を連結、
  エラーは強調、画像は `[image/png]` プレースホルダ、2000 字で truncate）。
  **セル実行はしない**——実行はクライアント／カーネル側に任せ、本ツールは保存済み outputs を読むだけ。

## テスト

```bash
uv run pytest -q
```
