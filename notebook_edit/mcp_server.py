"""MCP stdio server exposing notebook_edit.core as tools.

Thin wrapper: each tool calls the matching core function and returns its result.
NotebookError is converted to a clean MCP tool error instead of a traceback.
No kernel execution and no output-writing tools are exposed by design.
"""

from __future__ import annotations

from typing import Any

from mcp.server.fastmcp import FastMCP

from notebook_edit import core
from notebook_edit.core import NotebookError

mcp = FastMCP("notebook-edit")


def _guard(fn, *args, **kwargs) -> Any:
    """Run a core call, turning NotebookError into an MCP tool error."""
    try:
        return fn(*args, **kwargs)
    except NotebookError as exc:
        # ToolError renders as an error result the model can read and recover from.
        from mcp.server.fastmcp.exceptions import ToolError

        raise ToolError(str(exc)) from exc


@mcp.tool()
def list_cells(path: str) -> list[dict]:
    """List every cell as a compact outline (cheap overview).

    Returns index, type, summary, num_lines, has_outputs, has_error per cell.
    `summary` is the cell's leading `#` comment block (code) or leading lines
    (markdown/raw); `has_error` flags code cells whose outputs contain an error.
    Cell indices are 0-based. Call this first to orient before editing.
    """
    return _guard(core.list_cells, path)


@mcp.tool()
def read_cells(path: str, indices: list[int], offset: int = 0) -> list[dict]:
    """Read one or more cells at once (pass a list of 0-based indices).

    Prefer a single call with several indices over many single reads. Returns,
    per cell, its source plus (for code cells) execution_count, outputs_text
    (rendered stdout/results, with errors and [image/*] placeholders), has_error,
    and output_types. All indices are validated first: if any is invalid the
    whole call errors. Never executes code; only reads stored outputs.

    Large results are bounded: each cell's source is windowed (~8000 chars) and
    the response total is capped (~20000 chars). A windowed cell carries
    source_truncated/source_length/source_offset — page it by re-reading that
    index with a larger `offset`. Cells past the total budget come back as
    {index, type, source_length, content_omitted: true}; read them separately.
    """
    return _guard(core.read_cells, path, indices, offset)


@mcp.tool()
def insert_cell(
    path: str, index: int, cell_type: str, source: str, summary: str | None = None
) -> dict:
    """Insert a new cell BEFORE `index` (index == cell count appends).

    cell_type must be one of: code, markdown, raw. Indices are 0-based.
    Optionally pass `summary`: a short description stored in cell metadata that
    becomes the cell's `summary` in list_cells (takes precedence over any leading
    `#` comment). Set it so later list_cells calls stay informative.
    """
    return _guard(core.insert_cell, path, index, cell_type, source, summary)


@mcp.tool()
def insert_cells(path: str, index: int, cells: list[dict]) -> dict:
    """Insert several cells at once, contiguously BEFORE `index` (0-based).

    Prefer this over many insert_cell calls when adding a block of cells: one
    round-trip, no index bookkeeping between inserts. `cells` is a list of
    objects {cell_type, source, summary?} inserted in order (index == cell count
    appends). The batch is atomic: all items are validated first, and if any is
    invalid nothing is written and the offending items are named — fix those and
    resend. Returns {"indices": [...]} where the new cells landed.
    """
    return _guard(core.insert_cells, path, index, cells)


@mcp.tool()
def edit_cell(
    path: str, index: int, source: str, summary: str | None = None
) -> dict:
    """Replace a cell's ENTIRE source. For small changes prefer patch_cell.

    Editing a code cell clears its outputs and execution_count (they are stale).
    Optionally pass `summary` to set the cell's metadata summary (omit to keep
    the existing one; pass "" to clear it).
    """
    return _guard(core.edit_cell, path, index, source, summary)


@mcp.tool()
def patch_cell(path: str, index: int, old: str, new: str) -> dict:
    """Preferred edit tool: replace a unique `old` substring with `new` in a cell.

    `old` must occur exactly once in the cell; otherwise this errors and asks for
    more context. Keeps diffs small. Editing a code cell clears its outputs.
    """
    return _guard(core.patch_cell, path, index, old, new)


@mcp.tool()
def delete_cell(path: str, index: int) -> dict:
    """Delete the cell at `index` (0-based)."""
    return _guard(core.delete_cell, path, index)


@mcp.tool()
def move_cell(path: str, from_index: int, to_index: int) -> dict:
    """Move the cell at `from_index` to `to_index` (final position, 0-based)."""
    return _guard(core.move_cell, path, from_index, to_index)


def main() -> None:
    """Console-script entry point: run the stdio server."""
    mcp.run()


if __name__ == "__main__":
    main()
