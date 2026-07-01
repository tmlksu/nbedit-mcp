# 0006: atomic write + 1世代 .bak

- Status: Accepted
- Date: 2026-07-01

## Context

`.ipynb` は JSON で、書き込み途中でプロセスが死ぬとファイルが壊れる。AI が編集する以上、
「本体を壊さない」ことは削れない要件。加えて、直前状態への手戻り手段も欲しい。

## Decision

全ての書き込みを `core._save()` に集約し、以下のパイプラインを必ず通す:

1. `nbformat.validate()` — 不正なら書かずに `NotebookError`
2. 既存ファイルを `<name>.ipynb.bak` にコピー（1世代のみ、毎回上書き）
3. 同ディレクトリの一時ファイルに書く
4. `os.replace()` で atomic に置換（同一 FS 上で原子的）

## Consequences

- 書き込み中断でも本体か .bak のどちらかは無傷。
- 検証を通らない notebook は保存されない。
- `.bak` は `.gitignore` 済み。1世代のみなので履歴は残らない（履歴が要れば Git 側で担保）。
- 制約: 一時ファイルと本体が別 FS だと `os.replace` が原子的でない。通常は同ディレクトリ生成で回避。

## Alternatives considered

- **直接上書き**: 実装は単純だが中断で破損。要件違反。却下。
- **多世代バックアップ**: 過剰。バージョン管理は Git の役目。1世代に留める。
