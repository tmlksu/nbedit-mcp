# 0015: ノートブック新規作成（create_notebook、既存は上書き拒否）

- Status: Accepted
- Date: 2026-07-03

## Context

実利用で「新しい `.ipynb` を作る」際、ユーザー／エージェントが**手で JSON を書いてファイルを作り**、
それから本ツールで編集していた。空 notebook の JSON 骨組み（`nbformat`/`nbformat_minor`/`metadata`/`cells`）
を手書きするのは事故りやすく（minor を間違えると `cell.id` が付かない＝ADR-0014 の id 指定が効かない等）、
本来ツールが担うべき定型作業。

スコープ境界（CLAUDE.md）は「セルの構造編集」。ファイル新規作成はカーネル実行を伴わない構造操作であり、
既存の編集系と地続き。**スコープ内**として追加する。

## Decision

`create_notebook(path, cells=None)` を追加する。

- 空 notebook（`nbformat.v4.new_notebook()`、`nbformat_minor: 5`）を作る。`cells` を渡せば初期セル付き。
  `cells` は `insert_cells` と**同じ形式** `{cell_type, source, summary?}` のリスト（形式・検証を再利用）。
- **既存ファイルは上書き拒否**: `path` が既に存在すれば `NotebookError`（編集は edit 系ツールでやる）。
  作成が既存を潰さないための安全弁。`_save` の atomic/bak（[ADR-0006](0006-atomic-write-and-backup.md)）
  とは別レイヤの保護。
- **親ディレクトリが無ければ `NotebookError`**（勝手に mkdir しない。誤った場所への作成を防ぐ）。
- 書き込みは既存同様 `_save` 経由（validate → 一時ファイル → atomic）。新規なので bak は作られない。
- 初期セルの検証は `insert_cells` の前検証（`_validate_new_cells`）を再利用。不正なら**何も作らず**名指しエラー。
- 戻り値は `{"path", "num_cells", "ids"}`。作成直後から `cell.id` で指せる（4.5+）。

## Consequences

- 「JSON 手書き→編集」の定型が 1 コール（`create_notebook`）に畳まれる。骨組みミス（特に minor）が消える。
- 上書き拒否により、既存 notebook の取り違え作成で内容を失う事故が起きない。
- ツールは 8 → 9。作成は notebook 単位、他は cell 単位という粒度差を description で明示。
- overwrite フラグは今は付けない（YAGNI）。要望が出たら `overwrite=False` を追加検討（HANDOFF）。

## Alternatives considered

- **追加しない（手書き継続）**: 骨組みミスと手間が残る。実利用の観測（毎回手書き）に反する。却下。
- **上書きを許す / mkdir する**: 既存潰し・誤配置のリスク。安全側（拒否）に倒す。必要なら明示フラグで解禁。
- **`insert_cell` 等で存在しない path を自動作成**: どの関数も暗黙にファイルを生む挙動は予測不能で危険。
  作成は専用の1関数に集約し、他は「既存前提」を保つ。却下。
