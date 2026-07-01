# 0005: 独自の NotebookError 例外階層

- Status: Accepted
- Date: 2026-07-01

## Context

core は CLI と MCP の2つのラッパーから使われる。エラー時、各ラッパーは
「想定内の失敗（不正 index など）」と「想定外のバグ」を区別して扱いたい。
組み込み例外（IndexError/ValueError）だと区別が曖昧で、メッセージ制御も弱い。

## Decision

`NotebookError` を基底とする小さな例外階層を core に定義する:

- `NotebookError`（基底）
- `CellIndexError` — index 範囲外・負値
- `CellTypeError` — cell_type が code/markdown/raw 以外
- `PatchError` — patch の old が不一致/非一意

ラッパーは `NotebookError` を捕捉して整形する（CLI→終了コード1+stderr、MCP→ToolError）。
想定外の例外は握りつぶさず伝播させる。

## Consequences

- 「ユーザ入力起因の失敗」と「バグ」がコード上で明確に分かれる。
- メッセージを一箇所（core）で管理でき、両ラッパーで一貫する。
- 制約: 新しい失敗種別を足す時は例外クラスも増やす（乱立させない）。

## Alternatives considered

- **組み込み例外のみ**: コードは減るが、ラッパーが広い型を catch する必要があり誤捕捉のリスク。却下。
- **エラーを返り値（Result 型）で表現**: Python では例外の方が素直。却下。
