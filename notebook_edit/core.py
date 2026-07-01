"""Core notebook-editing logic.

Pure-ish functions over a single ``.ipynb`` file. Every mutating function runs
the same safety pipeline on write (see :func:`_save`):

    validate -> back up (.ipynb.bak) -> write temp file -> atomic rename

Outputs (execution results) are read-only from the AI's point of view: no
function writes outputs, and changing a code cell's source clears its stale
outputs and execution count.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

import nbformat
from nbformat import NotebookNode

# Cell types we accept for creation / that Jupyter understands.
_CELL_TYPES = ("code", "markdown", "raw")

# Length of the single-line preview returned by list_cells.
_PREVIEW_LEN = 80

_NBFORMAT_VERSION = 4


# --------------------------------------------------------------------------- #
# Exceptions
# --------------------------------------------------------------------------- #
class NotebookError(Exception):
    """Base class for all expected notebook-editing errors.

    Wrappers (CLI, MCP) catch this to turn a failure into a clean exit code /
    structured error rather than a traceback.
    """


class CellIndexError(NotebookError):
    """A cell index is out of range or otherwise not addressable."""


class CellTypeError(NotebookError):
    """A cell_type value is not one of code/markdown/raw."""


class PatchError(NotebookError):
    """patch_cell's ``old`` string was not found, or was not unique."""


# --------------------------------------------------------------------------- #
# Internal helpers
# --------------------------------------------------------------------------- #
def _load(path: str | os.PathLike) -> NotebookNode:
    """Read and parse a notebook, always as nbformat v4.

    Raises:
        NotebookError: if the file is missing or not a valid notebook.
    """
    p = Path(path)
    if not p.is_file():
        raise NotebookError(f"Notebook not found: {p}")
    try:
        return nbformat.read(str(p), as_version=_NBFORMAT_VERSION)
    except Exception as exc:  # nbformat raises a variety of types
        raise NotebookError(f"Failed to read notebook {p}: {exc}") from exc


def _save(nb: NotebookNode, path: str | os.PathLike) -> None:
    """Validate then atomically write ``nb`` to ``path``.

    Pipeline: ``nbformat.validate`` -> copy existing file to ``<name>.ipynb.bak``
    (single generation, overwritten each time) -> write a sibling temp file ->
    ``os.replace`` (atomic on the same filesystem).
    """
    p = Path(path)
    try:
        nbformat.validate(nb)
    except Exception as exc:
        raise NotebookError(f"Refusing to write invalid notebook: {exc}") from exc

    # One-generation backup of the current on-disk file, if any.
    if p.is_file():
        backup = p.with_suffix(p.suffix + ".bak")
        backup.write_bytes(p.read_bytes())

    # Write to a temp file in the same directory, then atomically rename.
    tmp = p.with_name(f".{p.name}.tmp")
    try:
        with tmp.open("w", encoding="utf-8") as fh:
            nbformat.write(nb, fh)
        os.replace(tmp, p)
    finally:
        if tmp.exists():
            tmp.unlink()


def _check_type(cell_type: str) -> None:
    if cell_type not in _CELL_TYPES:
        raise CellTypeError(
            f"Invalid cell_type {cell_type!r}; expected one of {_CELL_TYPES}"
        )


def _check_index(nb: NotebookNode, index: int, *, action: str) -> None:
    """Validate an index that must point at an existing cell.

    Negative indices are rejected outright to avoid AI off-by-one surprises.
    """
    n = len(nb.cells)
    if not isinstance(index, int):
        raise CellIndexError(f"Cell index must be an int, got {type(index).__name__}")
    if index < 0:
        raise CellIndexError(f"Negative cell index {index} not allowed")
    if index >= n:
        raise CellIndexError(
            f"Cannot {action} cell {index}: notebook has {n} cell(s) (valid 0..{n - 1})"
        )


def _source_str(cell: NotebookNode) -> str:
    """nbformat stores source as str or list[str]; normalize to str."""
    src = cell.get("source", "")
    if isinstance(src, list):
        return "".join(src)
    return src


def _new_cell(cell_type: str, source: str) -> NotebookNode:
    if cell_type == "code":
        return nbformat.v4.new_code_cell(source)
    if cell_type == "markdown":
        return nbformat.v4.new_markdown_cell(source)
    return nbformat.v4.new_raw_cell(source)


def _clear_outputs(cell: NotebookNode) -> None:
    """Drop stale execution results after a code cell's source changes."""
    if cell.get("cell_type") == "code":
        cell["outputs"] = []
        cell["execution_count"] = None


# --------------------------------------------------------------------------- #
# Read-only functions (never write, never create a .bak)
# --------------------------------------------------------------------------- #
def list_cells(path: str | os.PathLike) -> list[dict[str, Any]]:
    """Return a lightweight index of every cell.

    Each entry: ``{index, type, source_preview, num_lines, has_outputs}``.
    ``source_preview`` is the first line, truncated to ~80 chars.
    """
    nb = _load(path)
    result = []
    for i, cell in enumerate(nb.cells):
        source = _source_str(cell)
        first_line = source.split("\n", 1)[0]
        preview = first_line[:_PREVIEW_LEN]
        if len(first_line) > _PREVIEW_LEN:
            preview += "…"
        result.append(
            {
                "index": i,
                "type": cell.get("cell_type"),
                "source_preview": preview,
                "num_lines": source.count("\n") + 1 if source else 0,
                "has_outputs": bool(cell.get("outputs")),
            }
        )
    return result


def read_cell(path: str | os.PathLike, index: int) -> dict[str, Any]:
    """Return the full source (and outputs, for code cells) of one cell."""
    nb = _load(path)
    _check_index(nb, index, action="read")
    cell = nb.cells[index]
    out: dict[str, Any] = {
        "index": index,
        "type": cell.get("cell_type"),
        "source": _source_str(cell),
    }
    if cell.get("cell_type") == "code":
        out["execution_count"] = cell.get("execution_count")
        out["outputs"] = cell.get("outputs", [])
    return out


# --------------------------------------------------------------------------- #
# Mutating functions (load -> mutate -> _save)
# --------------------------------------------------------------------------- #
def insert_cell(
    path: str | os.PathLike, index: int, cell_type: str, source: str
) -> dict[str, Any]:
    """Insert a new cell *before* ``index``. ``index == len`` appends."""
    _check_type(cell_type)
    nb = _load(path)
    n = len(nb.cells)
    if not isinstance(index, int) or index < 0:
        raise CellIndexError(f"Invalid insert index {index!r}")
    if index > n:
        raise CellIndexError(
            f"Cannot insert at {index}: notebook has {n} cell(s) (valid 0..{n})"
        )
    nb.cells.insert(index, _new_cell(cell_type, source))
    _save(nb, path)
    return {"index": index}


def edit_cell(path: str | os.PathLike, index: int, source: str) -> dict[str, Any]:
    """Replace a cell's entire source. Clears outputs if it's a code cell."""
    nb = _load(path)
    _check_index(nb, index, action="edit")
    cell = nb.cells[index]
    cell["source"] = source
    _clear_outputs(cell)
    _save(nb, path)
    return {"index": index}


def patch_cell(
    path: str | os.PathLike, index: int, old: str, new: str
) -> dict[str, Any]:
    """Replace a unique ``old`` substring with ``new`` within one cell.

    ``old`` must occur exactly once (0 or >1 occurrences raise PatchError).
    Clears outputs if it's a code cell.
    """
    nb = _load(path)
    _check_index(nb, index, action="patch")
    cell = nb.cells[index]
    source = _source_str(cell)
    count = source.count(old)
    if count == 0:
        raise PatchError(f"`old` string not found in cell {index}")
    if count > 1:
        raise PatchError(
            f"`old` string is not unique in cell {index} ({count} matches); "
            "include more surrounding context to disambiguate"
        )
    cell["source"] = source.replace(old, new, 1)
    _clear_outputs(cell)
    _save(nb, path)
    return {"index": index, "replacements": 1}


def delete_cell(path: str | os.PathLike, index: int) -> dict[str, Any]:
    """Delete the cell at ``index``."""
    nb = _load(path)
    _check_index(nb, index, action="delete")
    cell_type = nb.cells[index].get("cell_type")
    del nb.cells[index]
    _save(nb, path)
    return {"deleted_index": index, "type": cell_type}


def move_cell(
    path: str | os.PathLike, from_index: int, to_index: int
) -> dict[str, Any]:
    """Move a cell from ``from_index`` to ``to_index`` (final position)."""
    nb = _load(path)
    _check_index(nb, from_index, action="move")
    _check_index(nb, to_index, action="move to")
    cell = nb.cells.pop(from_index)
    nb.cells.insert(to_index, cell)
    _save(nb, path)
    return {"from": from_index, "to": to_index}
