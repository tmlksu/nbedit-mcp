# notebook-edit

[![CI](https://github.com/tmlksu/nbedit-mcp/actions/workflows/ci.yml/badge.svg)](https://github.com/tmlksu/nbedit-mcp/actions/workflows/ci.yml)

Jupyter notebook (`.ipynb`) の**構造編集**に特化した MCP サーバー兼 CLI。
カーネル実行は行わない（実行は Copilot / Azure Codex 側の既存機能に任せる）。

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

## MCP サーバー (GitHub Copilot / VS Code)

`.vscode/mcp.json`:

```json
{
  "servers": {
    "notebook-edit": {
      "command": "uvx",
      "args": ["--from", "/path/to/lw-nbedit-mcp", "nb-edit-mcp"]
    }
  }
}
```

社内 Git 配布時は `--from` を Git URL に差し替える:

```json
"args": ["--from", "git+https://<your-git>/lw-nbedit-mcp", "nb-edit-mcp"]
```

パスはサーバーの CWD（VS Code ワークスペース）基準で解決される。

### 公開ツール

| ツール | 引数 | 説明 |
|--------|------|------|
| `list_cells` | `path` | 全セルの概要（プレビュー付き） |
| `read_cell` | `path, index` | セルの全文（コードセルは outputs も） |
| `insert_cell` | `path, index, cell_type, source` | index の前に挿入 |
| `edit_cell` | `path, index, source` | 全文置換 |
| `patch_cell` | `path, index, old, new` | 一意な部分文字列を置換（**推奨**） |
| `delete_cell` | `path, index` | 削除 |
| `move_cell` | `path, from_index, to_index` | 移動 |

`cell_type` は `code` / `markdown` / `raw`。
`patch_cell` の `old` はセル内で**ちょうど1回**一致する必要がある
（0回・複数回はエラー → 文脈を足して一意にする）。

## テスト

```bash
uv run pytest -q
```
