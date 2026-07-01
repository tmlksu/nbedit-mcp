# 0007: MCP は FastMCP、path はそのまま受ける

- Status: Accepted
- Date: 2026-07-01

## Context

MCP サーバーは薄いラッパーに留めたい（[ADR-0001](0001-layered-architecture.md)）。
MCP SDK には低レベル `Server` と高レベル `FastMCP` がある。また、ツールが受け取る
notebook path をどう解決するか（相対/絶対、CWD 拘束の要否）を決める必要がある。

## Decision

- **FastMCP デコレータ**（`@mcp.tool()`）を使う。型ヒントから入力スキーマが自動生成され、
  ラッパーの記述量が最小になる。
- path は**そのまま受ける**（サーバーの CWD 基準で解決）。VS Code は stdio サーバーの CWD を
  ワークスペースに設定するため、Copilot の呼び出しと自然に整合する。CWD 拘束は行わない。

## Consequences

- 各ツールは「core を呼んで返す」だけの数行で済む。`NotebookError` は `ToolError` に変換して返す。
- 相対パスがそのまま使え、Copilot 側の利用が素直。
- 制約: CWD 外への書き込みをサーバー側では防がない。防御が必要になったら「絶対化 + CWD 拘束」の新 ADR を検討。

## Alternatives considered

- **低レベル Server + 手書き JSON スキーマ**: 制御は効くが冗長。薄いラッパー方針に反する。却下。
- **path を CWD 配下に拘束**: 安全側だが、当面の主用途（ワークスペース内編集）には過剰。将来オプション化余地あり。
