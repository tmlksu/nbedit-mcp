# 0012: 大きい読み出し結果の扱い（cap + バジェット + offset）

- Status: Accepted
- Date: 2026-07-02

## Context

ツール結果はそのまま LLM のコンテキストに注入される。巨大なセル source や大量セルの
一括読み取りは、コンテキスト圧迫・ホスト側の上限による切り詰め（壊れた JSON 混入）・
"lost in the middle" による精度低下を招く。`outputs_text` は 2000 字 cap 済みだが、
`source` は無制限で、`read_cells` にも総量の歯止めが無かった。

## Decision

「黙って切らない・大きいセルはページング・レスポンス総量も上限」を核に、`read_cells` を強化する。

- **セル毎 source 窓**: `source` を `[offset, offset+_SOURCE_WINDOW)`（8000字）に窓化。
  窓が全文を覆わない／`offset>0` の時だけ `source_offset`/`source_length`/`source_truncated` を付す
  （小さいセルはクリーンなまま）。
- **offset パラメータ**: `read_cells(path, indices, offset=0)`。大きいセルは offset をずらして
  数回で読む（文字単位、`patch_cell` の部分文字列と一貫）。
- **総量バジェット**: レスポンスの source+outputs 合計を `_READ_BUDGET`（20000字）で上限。
  超えたら以降のセルを `{index, type, source_length, content_omitted: true}` として返す。
  `_SOURCE_WINDOW + _OUTPUT_TEXT_MAX < _READ_BUDGET` なので**先頭セルは必ず全部入る**。

実行はしない・outputs は読み取り専用（ADR-0002/0003/0009）という前提は不変。

## Consequences

- 巨大セル・大量バッチでもコンテキストを暴走させない。切り詰めは必ずマーカー付きで伝える。
- 大きいセルも offset ページングで全文到達でき、truncate が情報欠損にならない（編集に必要）。
- content_omitted のセルは `source_length` を持つので、モデルは小さいバッチ／offset で読み直せる。
- 制約: cap/バジェットは現状は定数。呼び出し側で調整する projection（`max_chars`/`include_outputs`）は
  将来拡張（HANDOFF 参照）。

## Alternatives considered

- **truncate だけ（offset 無し）**: 大きいセルの続きを取得できず、編集用途で情報欠損。offset を追加。
- **行単位の窓**: モデルには直感的だが、`patch_cell` は部分文字列ベースなので文字単位で統一。
- **resource link で本体を別取得**: 対応クライアントが限られ可搬性が低い。inline+cap を採用。
