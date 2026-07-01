# 0001: core / cli / mcp の3層分離

- Status: Accepted
- Date: 2026-07-01

## Context

同じ notebook 編集ロジックを「CLI」と「MCP サーバー」の2経路から使いたい。
ロジックを両方に書くと二重管理になり、片方だけ直す事故が起きる。

## Decision

ロジックを `core.py` に一元化し、`cli.py`（argparse）と `mcp_server.py`（FastMCP）は
core 関数を呼ぶだけの薄いラッパーにする。core は純粋寄り（副作用はファイル I/O のみ）に保つ。

## Consequences

- 新機能は core に1回書けば両インターフェースに反映できる。
- テストは core に集中させれば大部分をカバーできる（ラッパーは配線のみ）。
- 制約: ラッパー固有の都合（引数整形など）を core に漏らさないよう注意する。

## Alternatives considered

- **CLI に全ロジック、MCP は CLI を subprocess 呼び出し**: プロセス起動コスト・エラー伝播が煩雑。却下。
- **MCP を主、CLI は薄い client**: CLI 単体利用（コンテキスト不要な場面）で MCP 依存を持ち込むのが過剰。却下。
