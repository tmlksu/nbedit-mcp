# 0016: バージョンの single source of truth（__version__）と名乗り口

- Status: Accepted
- Date: 2026-07-04

## Context

`pyproject.toml` の `version` が v0.1.0〜v0.6.0 のリリース（git tag）を通して **`0.1.0` のまま**据え置かれていた。
配布は `uvx --from git+…@<tag>` の tag 参照なので実害は無かったが、パッケージが自己申告するバージョンが
古いままだった。

VS Code 拡張（VSIX）側でサーバ/CLI のバージョンを表示・利用したい要望が出た。クライアントが版を取る標準的な
経路は (1) MCP initialize の `serverInfo.version`、(2) `nb-edit --version`、(3) インストール済み配布メタデータ
（`importlib.metadata`）。今はどれも `0.1.0`（または未設定）で、拠り所が **tag と pyproject に二分**していた。

## Decision

**`notebook_edit/__init__.py` の `__version__` を唯一の源**にし、すべての名乗り口をそこに揃える。

- `pyproject.toml` は静的 `version` を捨て、`dynamic = ["version"]` +
  `[tool.hatch.version] path = "notebook_edit/__init__.py"` で `__version__` を**ビルド時に読む**。
  → wheel/sdist/`uvx` のメタデータが常に `__version__` と一致する。
- **CLI**: `nb-edit --version` が `__version__` を出力（argparse `action="version"`）。
- **MCP**: `mcp._mcp_server.version = __version__` を設定し、initialize の `serverInfo.version` で名乗る
  （FastMCP は version 引数を公開しないが、low-level `Server.version` に載せれば initialize に伝わる）。
- CLI/MCP は `importlib.metadata` ではなく**リテラルの `__version__` を直接参照**する。ソース実行時
  （再インストール前）でも常にコードと一致させるため。`importlib.metadata` は外部ツール用の副次経路。
- **リリース手順に組み込む**: 「Finalize vX.Y.0」コミットで `__version__` を tag と同じ値に bump し、
  CHANGELOG 確定・annotated tag と**同一コミット群**で揃える（[CLAUDE.md](../../CLAUDE.md) のリリース節）。
  これで 0.1.0 のようなドリフトが再発しない。

## Consequences

- バージョンの拠り所が1つ（`__version__`）に収束。tag・pyproject メタデータ・CLI・MCP が一致する。
- VSIX 側は MCP の `serverInfo.version` か `nb-edit --version` で確実にバージョンを取得できる。
- リリース時に `__version__` の bump を忘れると CI で気付けないため、リリース手順（チェックリスト）に明記する。
  将来 CI で「tag == `__version__`」を検査する余地（要望が出たら／HANDOFF）。
- `mcp._mcp_server` は private 属性への代入。FastMCP が version 引数を公開したら移行する（薄い1行なので低リスク）。

## Alternatives considered

- **pyproject を静的 `version` のまま手動 bump**: 二重管理で今回のドリフトを生んだ元。却下。
- **`__version__` を `importlib.metadata` から取得**: editable/未インストール状態で version が取れない・古い
  値になる罠。ソース実行を主とする本ツールには不向き。リテラルを源にする。
- **MCP は名乗らず CLI だけ**: VSIX が MCP クライアントとして initialize で取れる利点を捨てる。両方出す。
