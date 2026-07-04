# 0017: 書き込みの楽観ロック（expected_rev / notebook_rev）

- Status: Accepted
- Date: 2026-07-04

## Context

実運用で、VS Code（実行エンジン）が notebook を開いて実行し、その結果を LLM が読み、本ツールで編集する、
という使い方をする。本ツールの書き込みは `os.replace` でディスクを差し替える（[ADR-0006](0006-atomic-write-and-backup.md)）
が、**外部（VS Code 等）が同じファイルを保存したことを検知しない**。そのため:

- LLM が read した時点の版と、書き込み直前のディスクの版がズレていても、そのまま上書きしてしまう
  （外部の変更を**サイレントに握り潰す**）。

ファイル内部の source↔outputs 整合は [ADR-0003](0003-output-safety.md) で担保済み。ここで扱うのは
**「read してから write するまでにファイルが外部で変わった」競合の検知**。カーネル実行の内製
（[ADR-0002](0002-no-kernel-execution.md)）は行わない——本 ADR はスコープを広げず、競合を*検知*するだけ。

## Decision

**楽観的並行制御（optimistic concurrency）**を入れる。index/id と同じ「静かに壊さず大声で落とす」方針。

- `_rev(path)` = ファイル内容の `sha256` 先頭 12 桁。**内容ハッシュ**なので、同一内容の再保存では
  変わらず（偽の競合を作らない）、mtime の不安定さにも依存しない。
- `notebook_rev(path)` を追加。現在の rev だけを返す（`{"path", "rev"}`）。read せず token を取りたい時、
  および外部ウォッチャー（VS Code 拡張等）が外部変更を検知する用途にも使える。
- 変更系（`insert_cell`/`insert_cells`/`edit_cell`/`patch_cell`/`delete_cell`/`move_cell`）に
  **optional `expected_rev`** を足す。**省略時は現状どおり無検査**（後方互換）。
- 検査は書き込みの単一チョークポイント `_save` で行う（[不変条件2](../../CLAUDE.md)）。**backup を作る前**に、
  ディスクの現 rev が `expected_rev` と一致するか確認し、違えば `NotebookError`
  「変わっている（expected X, now Y）。読み直して再試行」で**書かずに拒否**。
- 変更系の戻り値に**書き込み後の新しい `rev`** を含める。これを次の `expected_rev` に渡せば、
  **re-read せず安全に連続編集**できる（chain）。

## Consequences

- 「read → (外部が保存) → write」でのサイレント上書きが、**即エラー**に変わる。LLM は読み直して再試行できる。
- 依存追加なし。`_save` に数行 + 各ラッパーに1引数。カーネル実行の議論（ADR-0002）には触れない。
- 限界（正直に明記）: これは**本ツール側の上書きを止める**だけ。VS Code 側が外部変更を reload するかは管轄外
  （双方向同期は拡張側の責務）。`notebook_rev` はその拡張側実装の材料にもなる。
- TOCTOU 窓は「_save 内の rev 照合〜os.replace」まで最小化。単一プロセス同期実行なので実害は無視できる。

## Alternatives considered

- **mtime/サイズで判定**: 実装は楽だが mtime は FS・エディタ依存で不安定、同秒保存を取りこぼす。内容ハッシュを選択。
- **read_cells/list_cells の戻り値を `{rev, cells}` に変える**: rev の入手は自然になるが、最も使うツールの
  返り値形状を破壊し churn が大きい。追加関数 `notebook_rev` + 変更系の戻り値 rev で非破壊に留める。
- **常に強制チェック（expected_rev 必須）**: 既存呼び出しと単発編集を壊す。opt-in（省略時無検査）にする。
- **実行内製で単一書き手にする**: ADR-0002 の Supersede が必要な大改修で、VS Code を実行から外さない限り
  競合は「2つの kernel」に移るだけ。本 quick win の範囲外。
