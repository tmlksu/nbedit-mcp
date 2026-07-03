"""MCP stdio server exposing notebook_edit.core as tools.

Thin wrapper: each tool calls the matching core function and returns its result.
NotebookError is converted to a clean MCP tool error instead of a traceback.
No kernel execution and no output-writing tools are exposed by design.
"""

from __future__ import annotations

from typing import Any

from mcp.server.fastmcp import FastMCP

from notebook_edit import __version__, core
from notebook_edit.core import NotebookError

mcp = FastMCP("notebook-edit")
# Report the package version in the MCP initialize handshake's serverInfo so
# clients (e.g. a VS Code extension) can read it. FastMCP doesn't expose a
# version arg, so set it on the low-level server directly (ADR-0016).
mcp._mcp_server.version = __version__


def _guard(fn, *args, **kwargs) -> Any:
    """Run a core call, turning NotebookError into an MCP tool error."""
    try:
        return fn(*args, **kwargs)
    except NotebookError as exc:
        # ToolError renders as an error result the model can read and recover from.
        from mcp.server.fastmcp.exceptions import ToolError

        raise ToolError(str(exc)) from exc


@mcp.tool()
def create_notebook(path: str, cells: list[dict] | None = None) -> dict:
    """Create a NEW empty .ipynb notebook at `path` (optionally with initial cells).

    Use this instead of hand-writing notebook JSON. `cells` (optional) is a list
    of {cell_type, source, summary?} — the same shape as insert_cells — seeded in
    order; omit it for an empty notebook. Refuses to overwrite an existing file
    and requires the parent directory to exist (both error). The notebook is
    nbformat 4.5, so every created cell gets a stable `id` right away. Returns
    {"path", "num_cells", "ids"}. cell_type must be one of: code, markdown, raw.
    """
    return _guard(core.create_notebook, path, cells)


@mcp.tool()
def list_cells(path: str) -> list[dict]:
    """List every cell as a compact outline (cheap overview).

    Returns index, id, type, summary, num_lines, has_outputs, has_error per cell.
    `id` is the cell's stable identifier: unlike index it does NOT shift when
    cells are inserted/deleted/moved, so prefer addressing later edits by `id`.
    `summary` is the cell's leading `#` comment block (code) or leading lines
    (markdown/raw); `has_error` flags code cells whose outputs contain an error.
    Cell indices are 0-based. Call this first to orient before editing.
    """
    return _guard(core.list_cells, path)


@mcp.tool()
def read_cells(
    path: str,
    indices: list[int] | None = None,
    offset: int = 0,
    ids: list[str] | None = None,
) -> list[dict]:
    """Read one or more cells at once, addressed by `indices` OR `ids`.

    Pass exactly one of `indices` (0-based) or `ids` (stable cell.id from
    list_cells). Ids don't shift when cells move, so prefer them once listed.
    Prefer a single call with several targets over many single reads. Returns,
    per cell, its id and source plus (for code cells) execution_count,
    outputs_text (rendered stdout/results, with errors and [image/*]
    placeholders), has_error, and output_types. All targets are validated first:
    if any is invalid (bad index, unknown/duplicate id) the whole call errors.
    Never executes code; only reads stored outputs.

    Large results are bounded: each cell's source is windowed (~8000 chars) and
    the response total is capped (~20000 chars). A windowed cell carries
    source_truncated/source_length/source_offset — page it by re-reading that
    target with a larger `offset`. Cells past the total budget come back as
    {index, id, type, source_length, content_omitted: true}; read them separately.
    """
    return _guard(core.read_cells, path, indices, offset, ids)


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
    path: str,
    source: str,
    index: int | None = None,
    cell_id: str | None = None,
    summary: str | None = None,
) -> dict:
    """Replace a cell's ENTIRE source. For small changes prefer patch_cell.

    Target the cell by `index` (0-based) OR `cell_id` (stable id from list_cells);
    pass exactly one. Prefer `cell_id` after listing — it doesn't shift when other
    cells change, avoiding off-by-one edits to the wrong cell. Editing a code cell
    clears its outputs and execution_count (they are stale). Optionally pass
    `summary` to set the cell's metadata summary (omit to keep, "" to clear).
    """
    return _guard(core.edit_cell, path, index, source, summary, cell_id)


@mcp.tool()
def patch_cell(
    path: str,
    old: str,
    new: str,
    index: int | None = None,
    cell_id: str | None = None,
) -> dict:
    """Preferred edit tool: replace a unique `old` substring with `new` in a cell.

    Target the cell by `index` (0-based) OR `cell_id` (stable id from list_cells);
    pass exactly one. Prefer `cell_id` when chaining several patches — indices
    shift after inserts/deletes/moves, ids don't, so this avoids patching the
    wrong cell. `old` must occur exactly once in the cell; otherwise this errors
    and asks for more context. Keeps diffs small. Editing a code cell clears its
    outputs.
    """
    return _guard(core.patch_cell, path, index, old, new, cell_id)


@mcp.tool()
def delete_cell(
    path: str, index: int | None = None, cell_id: str | None = None
) -> dict:
    """Delete a cell, addressed by `index` (0-based) OR `cell_id` (exactly one).

    Prefer `cell_id` from list_cells — an id can't drift onto the wrong cell the
    way a stale index can.
    """
    return _guard(core.delete_cell, path, index, cell_id)


@mcp.tool()
def move_cell(
    path: str,
    to_index: int,
    from_index: int | None = None,
    from_id: str | None = None,
) -> dict:
    """Move a cell to `to_index` (final position, 0-based).

    Address the moved cell by `from_index` OR `from_id` (stable id; exactly one);
    the destination `to_index` is always positional. Does not clear outputs.
    """
    return _guard(core.move_cell, path, from_index, to_index, from_id)


def main() -> None:
    """Console-script entry point: run the stdio server."""
    mcp.run()


if __name__ == "__main__":
    main()
