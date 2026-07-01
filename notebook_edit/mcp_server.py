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
    """List every cell with a one-line source preview (cheap overview).

    Returns index, type, source_preview, num_lines, has_outputs for each cell.
    Cell indices are 0-based. Call this first to orient before editing.
    """
    return _guard(core.list_cells, path)


@mcp.tool()
def read_cell(path: str, index: int) -> dict:
    """Read one cell's full source (and outputs/execution_count for code cells).

    Outputs are read-only: no tool writes them, and editing a code cell's source
    clears its stale outputs.
    """
    return _guard(core.read_cell, path, index)


@mcp.tool()
def insert_cell(path: str, index: int, cell_type: str, source: str) -> dict:
    """Insert a new cell BEFORE `index` (index == cell count appends).

    cell_type must be one of: code, markdown, raw. Indices are 0-based.
    """
    return _guard(core.insert_cell, path, index, cell_type, source)


@mcp.tool()
def edit_cell(path: str, index: int, source: str) -> dict:
    """Replace a cell's ENTIRE source. For small changes prefer patch_cell.

    Editing a code cell clears its outputs and execution_count (they are stale).
    """
    return _guard(core.edit_cell, path, index, source)


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
