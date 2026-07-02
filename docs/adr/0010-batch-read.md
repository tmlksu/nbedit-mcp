# 0010: 複数セルの一括読み取り（read_cells）

- Status: Accepted
- Date: 2026-07-02

## Context

実利用では一度に複数セルを読む場面が多い。単一の `read_cell` を N 回呼ぶと、
MCP のツール呼び出しごとの往復（レイテンシ＋クライアントのターン）が N 回発生して非効率。

## Decision

`read_cell`（単一）を廃し、**`read_cells(path, indices: list[int])`** に一本化する。

- 各要素は従来の read_cell と同じセルビュー（source + コードセルは outputs 整形）。
- **strict 検証**: 先に全 index を検証し、範囲外／負値があれば**該当を列挙して** `CellIndexError`。
  部分成功で黙って歯抜けにしない（ADR-0005 の明示エラー方針と一貫）。
- 重複 index は許容し、要求順のまま返す。空リストは `[]`。
- 単一読み取りは `[i]` を渡す。ツール総数は 7 のまま。

## Consequences

- 複数セル読み取りが1往復に畳まれ、実用上のレイテンシが大きく減る。
- ツールが1つ（read_cells）に集約され、モデルの選択に迷いがない。
- 破壊的変更: `read_cell` 廃止（pre-1.0 のため許容）。
- 注: FastMCP は list 戻り値を要素ごとの content ブロックに展開する（クライアントは各ブロックを1セルとして解釈）。

## Alternatives considered

- **read_cell を残して read_cells を併設**: 似たツールが2つでモデルの選択が曖昧。一本化を選択。
- **範囲指定文字列（"5-8"）**: 表現力は高いがパースが要る。まずは list of int に絞り、将来拡張の余地とする。
