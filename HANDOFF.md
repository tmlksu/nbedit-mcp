# HANDOFF

次のセッション（人間 or LLM）が最初に読むファイル。「今どこまで出来ていて、次に何をするか」だけを書く。
恒久ルールは [CLAUDE.md](CLAUDE.md)、決定理由は [docs/adr/](docs/adr/)、変更履歴は [CHANGELOG.md](CHANGELOG.md)。

**最終更新: 2026-07-02**

## 現在地（一言で）

**v0.2.0 リリース済み**（タグ `v0.2.0`、`main`）。v0.1.0 の全経路に加え、要約アウトライン
（`list_cells` の `summary` + `has_error`）と outputs 整形読み取り（`read_cell` の `outputs_text`
/`has_error`/`output_types`）を追加。実行機能は入れていない（ADR-0002/0003 維持）。テスト 33 passed。

## 完成しているもの（検証済み）

- `notebook_edit/{core,cli,mcp_server,__init__}.py` — 7 機能すべて実装。
- `tests/test_core.py`（24 件）+ `tests/test_mcp_stdio.py`（3 件）— `uv run pytest -q` で **27 passed**。
  stdio テストは `python -m notebook_edit.mcp_server` を実サブプロセス起動し、tool 列挙 /
  insert→patch→read / エラー時 `isError` を検証。
- `.github/workflows/ci.yml` — Python 3.10/3.11/3.12 で `uv sync` → `pytest`（push/PR トリガ）。
- ドキュメント一式（README / CLAUDE.md / ADR 0001–0007 / CHANGELOG / 本ファイル）。

## 次の一手（優先度順・任意）

1. **社内 Git への配布**: 会社の Git に置き、`.vscode/mcp.json` を
   `--from git+<社内URL> nb-edit-mcp` で各自設定する運用に乗せる。
2. **CI の Node20 非推奨警告**（非ブロッキング）: `actions/checkout` / `astral-sh/setup-uv` を
   新しい major に上げると消える。緊急ではない。
3. **機能拡張の検討ネタ**（要望が出たら ADR とセットで）:
   - patch の `replace_all` オプション（[ADR-0004](docs/adr/0004-patch-uniqueness.md)）
   - path の CWD 拘束（[ADR-0007](docs/adr/0007-mcp-fastmcp-and-paths.md)）
   - raw セル専用テストの追加

## 済み（〜v0.2.0）

- v0.2.0: 要約アウトライン + outputs 整形読み取り（ADR-0008/0009）、33 passed。
- core / CLI / MCP(stdio) 実装、CI green（3.10/3.11/3.12）。
- 実利用検証: VS Code + Copilot(Agent) から `nb-edit-mcp` を叩き、`.ipynb` 編集に成功。
  `.ipynb.bak` 生成・outputs 空維持を実データで確認。
- `examples/` は `.gitkeep` のみ追跡、`*.ipynb` は gitignore（スクラッチ置き場）。

## 未決 / 検討メモ（着手前に判断が要るもの）

- **path の CWD 拘束**（[ADR-0007](docs/adr/0007-mcp-fastmcp-and-paths.md)）: 現状は拘束なし。
  ワークスペース外への誤書き込みを防ぐ要求が出たら、絶対化+拘束を新 ADR で追加。
- **patch の replace_all オプション**（[ADR-0004](docs/adr/0004-patch-uniqueness.md)）: 現状は一意必須。
  一括置換の要望が出たらフラグ追加を検討。
- **raw セルのテスト**: core は対応済みだが専用テストは薄い。1 の作業ついでに足すと良い。

## 資料の場所

- 恒久ルール・不変条件: [CLAUDE.md](CLAUDE.md)
- 「なぜこうなってる?」: [docs/adr/](docs/adr/)
- リモート: `git@github.com:tmlksu/nbedit-mcp.git`（public、branch `main`）
