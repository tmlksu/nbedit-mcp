# 0014: セルを id でも指定可能にする（index と併用）

- Status: Accepted
- Date: 2026-07-03

## Context

実利用で「index のミス」、特に **patch を連発する場面**での事故が多い。原因は2種類:

1. **stale index（陳腐化）**: モデルは最初の `list_cells` の通し番号を決め打ちするが、
   1回でも `insert`/`delete`/`move` すると以降の index が全部ズレる。2手目以降が確実に外れる。
2. **数え間違い**: list 出力から位置を目視カウントするときの off-by-one。

さらに危険なのは失敗の質。**index ミスは静かに壊す** — `edit_cell`/`delete_cell` は範囲内なら
別セルを黙って書き換える（unique guard があるのは `patch_cell` だけ）。

nbformat 4.5+（本ツールが生成する `nbformat_minor: 5`）は**全セルに安定した `cell.id` が自動で付く**。
insert/delete/move しても id は変わらない。すでに手元にある識別子を使っていないだけだった。

## Decision

セルを **`index`（0始まり）または `id`（安定文字列）で指定できる**ようにする。両立させ、片方だけ必須。

- 対象が**既存セル**の関数は id 併用可: `read_cells`(`ids`) / `edit_cell` / `patch_cell` /
  `delete_cell` / `move_cell` の from（`from_id`）。
- **挿入位置は index のまま**: `insert_cell` / `insert_cells` の `index`、`move_cell` の `to_index`。
  「N の前に入れる」「N 番目に置く」は本質的に位置概念で、id 化できない（不変条件1は維持）。
- `core._resolve(nb, index=, cell_id=)` に一元化。`index` と `cell_id` は**ちょうど一方**
  （両方・なしは `CellIndexError`）。
- **id ミスは大声で落ちる**: 未発見・重複は `CellIndexError`。index の「静かに別セルを壊す」を回避
  （不変条件2/3の安全思想と同じ方向）。重複 id は `patch` の一意性思想に倣い明示エラー。
- **id を返り値と読み取り結果に必ず含める**: `list_cells` / `read_cells` の各エントリ、および
  `insert*`/`edit`/`patch`/`delete`/`move` の戻り値に `id`（複数は `ids`）を付ける。
  → モデルは `list_cells` を1回見れば以降 id で全部指せ、stale が構造的に起きない。

## Consequences

- patch 連発時の stale index 事故が構造的に消える（id は shift しない）。
- 対象指定ミスが「静かな誤爆」から「即エラー」に変わる（blast radius 縮小）。
- pre-4.5 で id を持たないセルは id 指定できず index のみ（`list_cells` の `id` は `null`）。
  本ツールが作る notebook は 4.5+ なので実害は小さい。読み取り時に id を勝手に付与はしない
  （読み取りは書き込まない原則を維持）。
- MCP の description で「list 済みなら id を優先。id は insert/delete/move で shift しない」と誘導。
- CLI は既存セル指定コマンド（read/edit/patch/delete/move）の対象を `--index`/`--id`
  フラグに寄せる（read-cells は従来の位置 index も残す）。insert は位置 index のまま。

## Alternatives considered

- **id へ全面移行（index 廃止）**: 不変条件1と衝突し、「N の前に挿入」を表現できない。挿入・移動先は
  位置が要る。却下。併用にする。
- **patch を index 不要（notebook 全体で old 一意一致）**: セル境界をまたいだ探索は誤爆源になり、
  outputs クリア対象の特定も曖昧。却下。
- **何もしない**: stale index と静かな誤爆が残る。実利用の観測（patch 連発の事故）に反する。却下。
