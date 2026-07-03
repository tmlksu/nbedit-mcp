"""Structural editing of Jupyter notebooks (.ipynb).

Core logic lives in :mod:`notebook_edit.core`. The CLI and MCP server are thin
wrappers over the same core functions.
"""

# Single source of truth for the package version (ADR-0016). pyproject reads this
# via hatchling's dynamic version; the CLI (`nb-edit --version`) and the MCP
# server's initialize `serverInfo.version` report it too. Bump this in the
# "Finalize vX.Y.0" release commit so it always matches the git tag.
__version__ = "0.6.0"

from notebook_edit.core import (
    CellIndexError,
    CellTypeError,
    NotebookError,
    PatchError,
    create_notebook,
    delete_cell,
    edit_cell,
    insert_cell,
    insert_cells,
    list_cells,
    move_cell,
    patch_cell,
    read_cells,
)

__all__ = [
    "__version__",
    "NotebookError",
    "CellIndexError",
    "CellTypeError",
    "PatchError",
    "create_notebook",
    "list_cells",
    "read_cells",
    "insert_cell",
    "insert_cells",
    "edit_cell",
    "patch_cell",
    "delete_cell",
    "move_cell",
]
