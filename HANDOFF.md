# HANDOFF

次のセッション（人間 or LLM）が最初に読むファイル。「今どこまで出来ていて、次に何をするか」だけを書く。
恒久ルールは [CLAUDE.md](CLAUDE.md)、決定理由は [docs/adr/](docs/adr/)、変更履歴は [CHANGELOG.md](CHANGELOG.md)。

**最終更新: 2026-07-04**

## 現在地（一言で）

**[Unreleased]（未タグ・未コミット）: 書き込みの楽観ロック**。変更系に optional `expected_rev`、`notebook_rev`
を追加（[ADR-0017](docs/adr/0017-write-revision-guard.md)）。read 時点から外部でファイルが変われば書き込みを
拒否＝VS Code 等とのサイレント上書きを防ぐ。カーネル実行はしない（ADR-0002 は不変、競合の*検知*のみ）。
ツールは **10**、テスト **83 passed**。※ 直前の **v0.7.0**（create_notebook＋バージョン単一源）はリリース済み。
→ 次リリース = **v0.8.0** 候補（リリース時 `__version__`→0.8.0 に bump、CLAUDE.md「リリース手順」参照）。

## 完成しているもの（検証済み）

- `notebook_edit/{core,cli,mcp_server,__init__}.py` — 10 機能。`__version__` は `__init__.py` の1箇所
  （現在 `0.7.0`、pyproject は hatchling dynamic）。楽観ロックは `_rev`（内容ハッシュ）＋
  `_save(nb, path, expected_rev)` の単一チョークポイントで照合（backup 前に拒否）。変更系は新 `rev` を返す。
- `tests/test_core.py`（78 件）+ `tests/test_mcp_stdio.py`（6 件）— `uv run pytest -q` で **83 passed**。
  stdio は tool 列挙（10個）/ insert→patch→read / id 往復 / serverInfo.version / **rev ガード（stale で isError）** を検証。
- CLI/MCP 実機確認: `notebook-rev` → 正 rev で patch 通過 → 外部変更 → stale rev で
  「Notebook changed on disk …」拒否＋ファイル保全 を確認。
- `.github/workflows/ci.yml` — Python 3.10/3.11/3.12 で `uv sync` → `pytest`（push/PR トリガ）。
- ドキュメント一式（README / CLAUDE.md / ADR 0001–0007 / CHANGELOG / 本ファイル）。

## 次の一手（優先度順・任意）

1. **配布**: クライアントの MCP 設定に `--from git+<repo URL> nb-edit-mcp`
   （またはローカル path）を登録する運用に乗せる。
2. **CI の Node20 非推奨警告**（非ブロッキング）: `actions/checkout` / `astral-sh/setup-uv` を
   新しい major に上げると消える。緊急ではない。
3. **機能拡張の検討ネタ**（要望が出たら ADR とセットで）:
   - `delete_cells` / `edit_cells` など他の一括 write（[ADR-0013](docs/adr/0013-batch-insert.md) の型を横展開）
   - `read_cells` の projection 引数（`max_chars`/`include_outputs`）で呼び出し側が verbosity 制御（[ADR-0012](docs/adr/0012-large-read-limits.md) が deferred）
   - `set_summary(path, index, summary)` ツール: source を変えず既存セルに要約を付与（[ADR-0011](docs/adr/0011-explicit-summary-metadata.md) の Alternatives）
   - `read_cells` の範囲指定（"5-8"）（[ADR-0010](docs/adr/0010-batch-read.md)）
   - patch の `replace_all` オプション（[ADR-0004](docs/adr/0004-patch-uniqueness.md)）
   - path の CWD 拘束（[ADR-0007](docs/adr/0007-mcp-fastmcp-and-paths.md)）
   - raw セル専用テストの追加

## 済み（〜v0.7.0 + Unreleased）

- [Unreleased]: 書き込み楽観ロック（`expected_rev`/`notebook_rev`、変更系は新 rev を返す）（ADR-0017）、83 passed。ツール 10。

- v0.7.0: `create_notebook`（新規作成・上書き拒否・親dir必須、ADR-0015）＋ バージョン single source
  （`__version__`、pyproject dynamic、`--version`、MCP serverInfo、ADR-0016）、75 passed。ツール 9。
- v0.6.0: セル id 併用アドレッシング（read/edit/patch/delete/move で index|id）（ADR-0014）、67 passed。
  戻り値・list/read に `id` を追加。CLI は対象指定を `--index`/`--id` に変更（insert 位置は index のまま）。
- v0.5.0: 複数セル一括挿入 insert_cells（atomic）（ADR-0013）、52 passed。
- v0.4.0: read_cells のサイズ上限（source 窓 + 総量バジェット + offset）（ADR-0012）。
- v0.3.0: 複数セル一括読み取り + 明示要約（metadata）（ADR-0010/0011）。
- v0.2.0: 要約アウトライン + outputs 整形読み取り（ADR-0008/0009）。
- core / CLI / MCP(stdio) 実装、CI green（3.10/3.11/3.12）。
- 実利用検証: MCP クライアント（AI エージェント）から `nb-edit-mcp` を叩き、`.ipynb` 編集に成功。
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
