# 0013: 複数セルの一括挿入（insert_cells、単発は残す）

- Status: Accepted
- Date: 2026-07-02

## Context

実利用で、ノートブックのセクションを作る際に `insert_cell` が何度も連続で呼ばれる。
MCP はツール呼び出し1回＝モデルの推論ターン1回なので、N セル挿入は N ターン＋
挿入ごとの index ズレをモデルが手計算する負荷がかかる。一括挿入したい。

## Decision

`insert_cells(path, index, cells)` を追加する。`insert_cell`（単発）は**残す**。

- `cells` は `{cell_type, source, summary?}` のリスト。`index` の前に順序保持で連続挿入
  （`index == len` で末尾追加）。戻り値は `{"indices": [...]}`。
- **atomic + 前検証**: 全 item を先に検証し、1つでも不正なら**該当 item を名指し**して
  `CellTypeError`、**何も書かない**（半端な状態を作らない）。空リストは no-op。
- read を `read_cells` に一本化した（[ADR-0010](0010-batch-read.md)）のと違い、
  **write は単発の低リスク版（insert_cell）を残す**。一発挿入の blast radius を最小に保てる。

## Consequences

- ブロック挿入が 1 往復に畳まれ、index ズレの手計算も不要。モデル負荷が下がる。
- 「input ミスのやり直しが辛い」問題は、前検証（構造ミスは名指しで無変更→該当だけ再送）と
  atomic（半端な状態なし）で緩和。内容ミスは挿入後に patch/edit/delete で個別修正（単発でも同じ）。
- ツールは 7 → 8。単発/一括を用途で使い分ける（description で誘導）。
- 同じ型を将来 `delete_cells` 等に広げる余地（要望が出たら／HANDOFF 参照）。

## Alternatives considered

- **insert_cells に一本化（insert_cell 廃止）**: read と一貫するが、write の単発低リスク版が消える。
  書き込みは blast radius を小さく保てる単発を残す方を選択。
- **追加しない**: round-trip コストと index ズレが残る。実利用の観測（連続 insert）に反する。却下。
