# HANDOFF

次のセッション（人間 or LLM）が最初に読むファイル。「今どこまで出来ていて、次に何をするか」だけを書く。
恒久ルールは [CLAUDE.md](CLAUDE.md)、決定理由は [docs/adr/](docs/adr/)、変更履歴は [CHANGELOG.md](CHANGELOG.md)。

**最終更新: 2026-07-01**

## 現在地（一言で）

v0.1.0 の骨格が完成し、GitHub（`git@github.com:tmlksu/nbedit-mcp.git`）の `main` に push 済み。
core / CLI / MCP(stdio) の3経路すべてテスト済み（**27 passed**）。CI も整備済み。
次は「実利用での検証」と「リリース」フェーズ。

## 完成しているもの（検証済み）

- `notebook_edit/{core,cli,mcp_server,__init__}.py` — 7 機能すべて実装。
- `tests/test_core.py`（24 件）+ `tests/test_mcp_stdio.py`（3 件）— `uv run pytest -q` で **27 passed**。
  stdio テストは `python -m notebook_edit.mcp_server` を実サブプロセス起動し、tool 列挙 /
  insert→patch→read / エラー時 `isError` を検証。
- `.github/workflows/ci.yml` — Python 3.10/3.11/3.12 で `uv sync` → `pytest`（push/PR トリガ）。
- ドキュメント一式（README / CLAUDE.md / ADR 0001–0007 / CHANGELOG / 本ファイル）。

## 次の一手（優先度順）

1. **CI が緑になるか確認**（push 後、Actions タブ）。初回失敗するなら uv キャッシュ or Python
   セットアップ周りが原因のことが多い。
2. **実利用検証（VS Code + Copilot）**
   `.vscode/mcp.json` に `--from git+https://github.com/tmlksu/nbedit-mcp nb-edit-mcp` を設定し、
   実際に Copilot から `.ipynb` を編集させて挙動・description の効き具合を確認する。
3. **タグ付け / リリース**
   `v0.1.0` タグを打つ（CHANGELOG のリンクが有効化される）。
4. **README に CI バッジ**を貼る（Actions が緑になってから）。

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
