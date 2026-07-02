# 0011: 明示的な要約を cell metadata に保存

- Status: Accepted
- Date: 2026-07-02
- Amends: [ADR-0008](0008-summary-convention.md)（metadata 却下の判断を覆す）

## Context

[ADR-0008](0008-summary-convention.md) は要約を「先頭 `#` コメント」から導出する規約とし、
metadata フィールド案は「notebook を汚す/相互運用」を理由に却下した。
だが実利用で「先頭コメント頼みは soft すぎる（モデルが書かないと要約が育たない）」という知見が出た。
明示的に要約を指定・永続でき、次回以降の `list_cells` が確実に情報量を持つ手段が欲しい。

## Decision

`insert_cell` / `edit_cell` に optional 引数 **`summary`** を追加し、指定時は
**`cell.metadata['summary']`** に保存する。

- `list_cells` の `summary` の優先順位: **metadata['summary'] > 先頭 `#` コメント > 先頭行プレビュー**。
- metadata 要約も cap（3行/100字）を適用。
- `edit_cell`: `summary=None` は既存を保持、文字列で設定、空文字で削除。
- nbformat v4 の cell metadata は追加プロパティ可の合法な拡張点で、他ツールは未知キーを保持する。
  ADR-0008 が懸念した「汚す/非互換」は実際には限定的、と再評価した。

ADR-0008 の**先頭コメント規約はフォールバックとして存続**する（本 ADR は metadata 却下の一点のみを覆す）。

## Consequences

- コードと要約を分離でき、source を変えずに要約を付与・更新できる。source 編集をまたいで永続。
- モデルへ「summary を指定せよ」と促せる（tool description）ので、要約が確実に育つ。
- トレードオフ: metadata の要約は notebook を開いても見えず、source と乖離（stale）しうる。
  → 可視性優先なら先頭コメント規約（ADR-0008）を使えばよい。両者は優先順位で共存する。

## Alternatives considered

- **先頭コメントに前置**（source に `# {summary}` 挿入）: ADR-0008 と一貫し可視だが、
  既存規約とほぼ同義で新規性が薄く、全文編集で消える。metadata 保存を選択。
- **専用 set_summary ツール**: source を変えず既存セルに要約を付けられるが、ツールが増える。
  要望が出たら追加を検討（HANDOFF 参照）。
