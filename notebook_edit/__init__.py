"""Structural editing of Jupyter notebooks (.ipynb).

Core logic lives in :mod:`notebook_edit.core`. The CLI and MCP server are thin
wrappers over the same core functions.
"""

from notebook_edit.core import (
    CellIndexError,
    CellTypeError,
    NotebookError,
    PatchError,
    delete_cell,
    edit_cell,
    insert_cell,
    list_cells,
    move_cell,
    patch_cell,
    read_cell,
)

__all__ = [
    "NotebookError",
    "CellIndexError",
    "CellTypeError",
    "PatchError",
    "list_cells",
    "read_cell",
    "insert_cell",
    "edit_cell",
    "patch_cell",
    "delete_cell",
    "move_cell",
]
