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

# Caps for the leading-comment summary returned by list_cells.
_SUMMARY_MAX_LINES = 3
_SUMMARY_LINE_LEN = 100

# Cap for rendered output text returned per cell by read_cells.
_OUTPUT_TEXT_MAX = 2000

# Per-cell source window (chars) returned by read_cells; page past it with offset.
_SOURCE_WINDOW = 8000

# Total source+outputs budget (chars) for a single read_cells response. Cells
# beyond it are returned as content_omitted. Kept > _SOURCE_WINDOW + _OUTPUT_TEXT_MAX
# so the first requested cell always fits.
_READ_BUDGET = 20000

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


def _resolve(
    nb: NotebookNode,
    *,
    index: int | None = None,
    cell_id: str | None = None,
    action: str,
) -> int:
    """Resolve a target existing cell to its 0-based position.

    Exactly one of ``index`` / ``cell_id`` must be given. ``cell_id`` matches the
    stable ``cell.id`` (nbformat 4.5+): a miss or a duplicate raises loudly rather
    than silently touching the wrong cell — unlike a plausible-but-wrong index.
    """
    provided = (index is not None) + (cell_id is not None)
    if provided == 0:
        raise CellIndexError(f"Provide an index or a cell id to {action} a cell")
    if provided == 2:
        raise CellIndexError(
            f"Provide either index or cell id to {action}, not both"
        )
    if cell_id is not None:
        if not isinstance(cell_id, str):
            raise CellIndexError(
                f"Cell id must be a string, got {type(cell_id).__name__}"
            )
        matches = [i for i, c in enumerate(nb.cells) if c.get("id") == cell_id]
        if not matches:
            raise CellIndexError(
                f"No cell with id {cell_id!r}: notebook has {len(nb.cells)} cell(s) "
                "(ids are listed by list_cells / read_cells)"
            )
        if len(matches) > 1:
            raise CellIndexError(
                f"Cell id {cell_id!r} is not unique ({len(matches)} matches)"
            )
        return matches[0]
    _check_index(nb, index, action=action)
    return index


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


def _truncate(text: str, limit: int) -> str:
    return text if len(text) <= limit else text[:limit] + "…"


def _cap_lines(lines: list[str]) -> str:
    """Strip, drop empties, cap line count/length, join."""
    picked = [
        _truncate(ln.strip(), _SUMMARY_LINE_LEN)
        for ln in lines
        if ln.strip()
    ][:_SUMMARY_MAX_LINES]
    return "\n".join(picked)


def _set_summary(cell: NotebookNode, summary: str | None) -> None:
    """Store an explicit summary in cell metadata (or clear it).

    ``None`` leaves any existing summary untouched; a blank string removes it.
    """
    if summary is None:
        return
    summary = summary.strip()
    if summary:
        cell.metadata["summary"] = summary
    else:
        cell.metadata.pop("summary", None)


def _summary(cell: NotebookNode) -> str:
    """A short, capped summary of a cell for the outline.

    Precedence:
    1. An explicit ``metadata['summary']`` set via insert/edit_cell.
    2. For code cells, the leading contiguous block of ``#`` comment lines
       (iteration stops at the first non-comment line, blank lines included);
       a code cell without a leading comment falls back to a single
       first-non-empty-line preview.
    3. Markdown/raw cells use their leading non-empty lines.

    Capped at ``_SUMMARY_MAX_LINES`` lines of ``_SUMMARY_LINE_LEN`` chars each.
    """
    explicit = cell.get("metadata", {}).get("summary")
    if explicit and explicit.strip():
        return _cap_lines(explicit.split("\n"))

    lines = _source_str(cell).split("\n")
    picked: list[str] = []

    if cell.get("cell_type") == "code":
        for line in lines:
            if line.lstrip().startswith("#"):
                picked.append(line.strip())
            else:
                break
        if not picked:
            # No header comment: one-line preview of the code.
            first = next((ln.strip() for ln in lines if ln.strip()), "")
            picked = [first] if first else []
    else:
        # markdown / raw: leading non-empty lines.
        for line in lines:
            if line.strip():
                picked.append(line.strip())
                if len(picked) >= _SUMMARY_MAX_LINES:
                    break

    picked = [_truncate(line, _SUMMARY_LINE_LEN) for line in picked[:_SUMMARY_MAX_LINES]]
    return "\n".join(picked)


def _render_outputs(cell: NotebookNode) -> dict[str, Any]:
    """Render a code cell's outputs into an AI-friendly summary.

    Returns ``{outputs_text, has_error, output_types}``. Raw output dicts (which
    may carry large base64 image blobs) are never returned; images become a
    ``[image/png]`` placeholder. Errors surface as ``ename: evalue`` plus the
    traceback. The combined text is capped at ``_OUTPUT_TEXT_MAX`` chars.
    """
    parts: list[str] = []
    types: list[str] = []
    has_error = False

    for out in cell.get("outputs", []):
        otype = out.get("output_type")
        types.append(otype)
        if otype == "stream":
            parts.append(out.get("text", ""))
        elif otype in ("execute_result", "display_data"):
            data = out.get("data", {})
            if "text/plain" in data:
                parts.append(data["text/plain"])
            for mime in data:
                if mime.startswith("image/"):
                    parts.append(f"[{mime}]")
        elif otype == "error":
            has_error = True
            ename = out.get("ename", "Error")
            evalue = out.get("evalue", "")
            tb = "\n".join(out.get("traceback", []))
            parts.append(f"{ename}: {evalue}\n{tb}".rstrip())

    text = "\n".join(p.rstrip("\n") for p in parts if p.strip())
    return {
        "outputs_text": _truncate(text, _OUTPUT_TEXT_MAX),
        "has_error": has_error,
        "output_types": types,
    }


# --------------------------------------------------------------------------- #
# Read-only functions (never write, never create a .bak)
# --------------------------------------------------------------------------- #
def list_cells(path: str | os.PathLike) -> list[dict[str, Any]]:
    """Return a lightweight index (outline) of every cell.

    Each entry: ``{index, type, summary, num_lines, has_outputs, has_error}``.
    ``summary`` is the leading ``#`` comment block (code) or leading non-empty
    lines (markdown/raw), capped; see :func:`_summary`.
    """
    nb = _load(path)
    result = []
    for i, cell in enumerate(nb.cells):
        source = _source_str(cell)
        is_code = cell.get("cell_type") == "code"
        result.append(
            {
                "index": i,
                "id": cell.get("id"),
                "type": cell.get("cell_type"),
                "summary": _summary(cell),
                "num_lines": source.count("\n") + 1 if source else 0,
                "has_outputs": bool(cell.get("outputs")),
                "has_error": is_code
                and any(o.get("output_type") == "error" for o in cell.get("outputs", [])),
            }
        )
    return result


def _cell_view(cell: NotebookNode, index: int, offset: int = 0) -> dict[str, Any]:
    """Read-view of one cell.

    ``source`` is windowed to ``[offset, offset + _SOURCE_WINDOW)``. When the
    window does not cover the whole source (or ``offset > 0``), the extra keys
    ``source_offset`` / ``source_length`` / ``source_truncated`` are added so the
    caller can page with ``offset``; small cells stay clean. Code cells also get
    ``execution_count`` and rendered outputs.
    """
    full = _source_str(cell)
    window = full[offset : offset + _SOURCE_WINDOW]
    out: dict[str, Any] = {
        "index": index,
        "id": cell.get("id"),
        "type": cell.get("cell_type"),
        "source": window,
    }
    if offset > 0 or len(window) < len(full):
        out["source_offset"] = offset
        out["source_length"] = len(full)
        out["source_truncated"] = True
    if cell.get("cell_type") == "code":
        out["execution_count"] = cell.get("execution_count")
        out.update(_render_outputs(cell))
    return out


def _resolve_read_ids(nb: NotebookNode, ids: list[str]) -> list[int]:
    """Resolve a list of cell ids to positions, all up front.

    Mirrors read_cells' index strictness: every offender (not found or not
    unique) is collected and reported in one ``CellIndexError`` — no partial read.
    """
    if not isinstance(ids, list):
        raise CellIndexError("ids must be a list of cell-id strings")
    positions: list[int] = []
    bad: list[str] = []
    for cid in ids:
        matches = [i for i, c in enumerate(nb.cells) if c.get("id") == cid]
        if len(matches) == 1:
            positions.append(matches[0])
        else:
            bad.append(cid)
    if bad:
        raise CellIndexError(
            f"Invalid cell id(s) {bad}: not found or not unique "
            "(ids are listed by list_cells / read_cells)"
        )
    return positions


def read_cells(
    path: str | os.PathLike,
    indices: list[int] | None = None,
    offset: int = 0,
    ids: list[str] | None = None,
) -> list[dict[str, Any]]:
    """Read one or more cells in a single call, in the requested order.

    Address the cells by ``indices`` (0-based) **or** by ``ids`` (stable
    ``cell.id``) — pass exactly one. Ids don't shift when cells are inserted /
    deleted / moved, so they are safer once you've listed the notebook.

    Each result is a view of a cell (source windowed to ``_SOURCE_WINDOW`` chars
    starting at ``offset``, plus rendered outputs for code cells) and carries the
    cell's ``id``. All targets are validated up front: if any is out of range,
    negative, or an unknown/duplicate id the whole call fails with a
    ``CellIndexError`` listing the offenders. Duplicates in the request are
    allowed and returned as given.

    The combined source+outputs size of the response is capped at ``_READ_BUDGET``
    chars: once reached, remaining cells are returned as ``{index, id, type,
    source_length, content_omitted: True}`` (read them in a smaller batch or page
    with ``offset``). Use ``offset`` to page through a cell larger than the window.
    """
    if not isinstance(offset, int) or isinstance(offset, bool) or offset < 0:
        raise CellIndexError(f"offset must be a non-negative int, got {offset!r}")
    if (indices is None) == (ids is None):
        raise CellIndexError("Provide exactly one of indices or ids")
    nb = _load(path)
    n = len(nb.cells)
    if ids is not None:
        indices = _resolve_read_ids(nb, ids)
    else:
        bad = [
            i
            for i in indices
            if not isinstance(i, int) or isinstance(i, bool) or i < 0 or i >= n
        ]
        if bad:
            raise CellIndexError(
                f"Invalid cell index(es) {bad}: notebook has {n} cell(s) "
                f"(valid 0..{n - 1})"
            )

    result: list[dict[str, Any]] = []
    used = 0
    omitting = False
    for i in indices:
        cell = nb.cells[i]
        if omitting:
            result.append(_omitted_view(cell, i))
            continue
        view = _cell_view(cell, i, offset)
        cost = len(view["source"]) + len(view.get("outputs_text", ""))
        # Always include the first emitted cell; omit once the budget is hit.
        if result and used + cost > _READ_BUDGET:
            omitting = True
            result.append(_omitted_view(cell, i))
            continue
        used += cost
        result.append(view)
    return result


def _omitted_view(cell: NotebookNode, index: int) -> dict[str, Any]:
    """Placeholder for a cell dropped from a read_cells response for size."""
    return {
        "index": index,
        "id": cell.get("id"),
        "type": cell.get("cell_type"),
        "source_length": len(_source_str(cell)),
        "content_omitted": True,
    }


# --------------------------------------------------------------------------- #
# Mutating functions (load -> mutate -> _save)
# --------------------------------------------------------------------------- #
def insert_cell(
    path: str | os.PathLike,
    index: int,
    cell_type: str,
    source: str,
    summary: str | None = None,
) -> dict[str, Any]:
    """Insert a new cell *before* ``index``. ``index == len`` appends.

    ``summary`` (optional) is stored in the cell's metadata and takes precedence
    in list_cells' outline.
    """
    _check_type(cell_type)
    nb = _load(path)
    n = len(nb.cells)
    if not isinstance(index, int) or index < 0:
        raise CellIndexError(f"Invalid insert index {index!r}")
    if index > n:
        raise CellIndexError(
            f"Cannot insert at {index}: notebook has {n} cell(s) (valid 0..{n})"
        )
    cell = _new_cell(cell_type, source)
    _set_summary(cell, summary)
    nb.cells.insert(index, cell)
    _save(nb, path)
    return {"index": index, "id": cell.get("id")}


def _validate_new_cells(cells: list[dict[str, Any]]) -> None:
    """Validate every item of an insert_cells batch up front.

    Collects all problems and raises once, naming each offending item, so a bad
    batch changes nothing and is cheap to fix and resend.
    """
    if not isinstance(cells, list):
        raise CellTypeError("cells must be a list of {cell_type, source, summary?}")
    problems = []
    for pos, item in enumerate(cells):
        if not isinstance(item, dict):
            problems.append(f"item {pos}: not an object")
            continue
        if item.get("cell_type") not in _CELL_TYPES:
            problems.append(
                f"item {pos}: invalid cell_type {item.get('cell_type')!r}"
            )
        if not isinstance(item.get("source", ""), str):
            problems.append(f"item {pos}: source must be a string")
    if problems:
        raise CellTypeError("; ".join(problems))


def insert_cells(
    path: str | os.PathLike, index: int, cells: list[dict[str, Any]]
) -> dict[str, Any]:
    """Insert several cells contiguously *before* ``index`` in one atomic write.

    ``cells`` is a list of ``{cell_type, source, summary?}`` inserted in order
    (``index == len`` appends). All items are validated first: if any is invalid
    the whole batch fails, naming the offenders, and nothing is written. Returns
    ``{"indices": [...]}`` — the positions the new cells landed at.
    """
    _validate_new_cells(cells)
    nb = _load(path)
    n = len(nb.cells)
    if not isinstance(index, int) or index < 0:
        raise CellIndexError(f"Invalid insert index {index!r}")
    if index > n:
        raise CellIndexError(
            f"Cannot insert at {index}: notebook has {n} cell(s) (valid 0..{n})"
        )
    new = []
    for item in cells:
        cell = _new_cell(item["cell_type"], item.get("source", ""))
        _set_summary(cell, item.get("summary"))
        new.append(cell)
    if new:
        nb.cells[index:index] = new
        _save(nb, path)
    return {
        "indices": list(range(index, index + len(new))),
        "ids": [c.get("id") for c in new],
    }


def edit_cell(
    path: str | os.PathLike,
    index: int | None = None,
    source: str | None = None,
    summary: str | None = None,
    cell_id: str | None = None,
) -> dict[str, Any]:
    """Replace a cell's entire source. Clears outputs if it's a code cell.

    Target the cell by ``index`` (0-based) or ``cell_id`` — exactly one.
    ``summary`` (optional): ``None`` keeps any existing summary, a string sets
    it, a blank string clears it.
    """
    if source is None:
        raise NotebookError("edit_cell requires a source string")
    nb = _load(path)
    pos = _resolve(nb, index=index, cell_id=cell_id, action="edit")
    cell = nb.cells[pos]
    cell["source"] = source
    _clear_outputs(cell)
    _set_summary(cell, summary)
    _save(nb, path)
    return {"index": pos, "id": cell.get("id")}


def patch_cell(
    path: str | os.PathLike,
    index: int | None = None,
    old: str | None = None,
    new: str | None = None,
    cell_id: str | None = None,
) -> dict[str, Any]:
    """Replace a unique ``old`` substring with ``new`` within one cell.

    Target the cell by ``index`` (0-based) or ``cell_id`` — exactly one.
    ``old`` must occur exactly once (0 or >1 occurrences raise PatchError).
    Clears outputs if it's a code cell.
    """
    if old is None or new is None:
        raise NotebookError("patch_cell requires both old and new strings")
    nb = _load(path)
    pos = _resolve(nb, index=index, cell_id=cell_id, action="patch")
    cell = nb.cells[pos]
    source = _source_str(cell)
    count = source.count(old)
    if count == 0:
        raise PatchError(f"`old` string not found in cell {pos}")
    if count > 1:
        raise PatchError(
            f"`old` string is not unique in cell {pos} ({count} matches); "
            "include more surrounding context to disambiguate"
        )
    cell["source"] = source.replace(old, new, 1)
    _clear_outputs(cell)
    _save(nb, path)
    return {"index": pos, "id": cell.get("id"), "replacements": 1}


def delete_cell(
    path: str | os.PathLike,
    index: int | None = None,
    cell_id: str | None = None,
) -> dict[str, Any]:
    """Delete a cell, addressed by ``index`` (0-based) or ``cell_id``."""
    nb = _load(path)
    pos = _resolve(nb, index=index, cell_id=cell_id, action="delete")
    cell = nb.cells[pos]
    deleted_id = cell.get("id")
    cell_type = cell.get("cell_type")
    del nb.cells[pos]
    _save(nb, path)
    return {"deleted_index": pos, "id": deleted_id, "type": cell_type}


def move_cell(
    path: str | os.PathLike,
    from_index: int | None = None,
    to_index: int | None = None,
    from_id: str | None = None,
) -> dict[str, Any]:
    """Move a cell to ``to_index`` (final position, 0-based).

    Address the moved cell by ``from_index`` or ``from_id`` (exactly one); the
    destination ``to_index`` is always positional. Does not clear outputs (source
    is unchanged).
    """
    nb = _load(path)
    from_pos = _resolve(nb, index=from_index, cell_id=from_id, action="move")
    _check_index(nb, to_index, action="move to")
    cell = nb.cells.pop(from_pos)
    nb.cells.insert(to_index, cell)
    _save(nb, path)
    return {"from": from_pos, "to": to_index, "id": cell.get("id")}
