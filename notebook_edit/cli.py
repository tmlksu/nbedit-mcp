"""argparse CLI wrapping notebook_edit.core.

Same core functions as the MCP server. Results are printed as JSON so the CLI is
scriptable; NotebookError is caught and reported to stderr with exit code 1.
"""

from __future__ import annotations

import argparse
import json
import sys

from notebook_edit import core
from notebook_edit.core import NotebookError


def _emit(obj) -> None:
    print(json.dumps(obj, ensure_ascii=False, indent=2))


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="nb-edit",
        description="Structural editing of Jupyter notebooks. No kernel execution.",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    p = sub.add_parser("list-cells", help="List all cells with a preview")
    p.add_argument("path")
    p.set_defaults(func=lambda a: core.list_cells(a.path))

    p = sub.add_parser("read-cells", help="Read one or more cells' source/outputs")
    p.add_argument("path")
    p.add_argument("indices", type=int, nargs="*", help="one or more 0-based indices")
    p.add_argument("--id", dest="ids", nargs="+", help="one or more stable cell ids (instead of indices)")
    p.add_argument("--offset", type=int, default=0, help="start source window at this char offset")
    p.set_defaults(
        func=lambda a: core.read_cells(
            a.path, a.indices if a.indices else None, a.offset, a.ids
        )
    )

    p = sub.add_parser("insert-cell", help="Insert a new cell before index")
    p.add_argument("path")
    p.add_argument("index", type=int)
    p.add_argument("cell_type", choices=core._CELL_TYPES)
    p.add_argument("source")
    p.add_argument("--summary", default=None, help="summary stored in cell metadata")
    p.set_defaults(
        func=lambda a: core.insert_cell(a.path, a.index, a.cell_type, a.source, a.summary)
    )

    p = sub.add_parser("insert-cells", help="Insert several cells (JSON array) before index")
    p.add_argument("path")
    p.add_argument("index", type=int)
    p.add_argument(
        "--json",
        required=True,
        dest="cells_json",
        help='JSON array of {cell_type, source, summary?}',
    )
    p.set_defaults(func=lambda a: core.insert_cells(a.path, a.index, json.loads(a.cells_json)))

    def _target(p):
        """Add mutually exclusive --index / --id for addressing an existing cell."""
        g = p.add_mutually_exclusive_group(required=True)
        g.add_argument("--index", type=int, help="0-based cell index")
        g.add_argument("--id", dest="cell_id", help="stable cell id (from list-cells)")

    p = sub.add_parser("edit-cell", help="Replace a cell's entire source")
    p.add_argument("path")
    p.add_argument("source")
    _target(p)
    p.add_argument("--summary", default=None, help="summary stored in cell metadata")
    p.set_defaults(
        func=lambda a: core.edit_cell(a.path, a.index, a.source, a.summary, a.cell_id)
    )

    p = sub.add_parser("patch-cell", help="Replace a unique old substring with new")
    p.add_argument("path")
    p.add_argument("old")
    p.add_argument("new")
    _target(p)
    p.set_defaults(
        func=lambda a: core.patch_cell(a.path, a.index, a.old, a.new, a.cell_id)
    )

    p = sub.add_parser("delete-cell", help="Delete a cell (by --index or --id)")
    p.add_argument("path")
    _target(p)
    p.set_defaults(func=lambda a: core.delete_cell(a.path, a.index, a.cell_id))

    p = sub.add_parser("move-cell", help="Move a cell to a final position")
    p.add_argument("path")
    p.add_argument("to_index", type=int, help="destination position (0-based)")
    g = p.add_mutually_exclusive_group(required=True)
    g.add_argument("--from-index", type=int, dest="from_index", help="0-based source index")
    g.add_argument("--from-id", dest="from_id", help="stable id of the cell to move")
    p.set_defaults(
        func=lambda a: core.move_cell(a.path, a.from_index, a.to_index, a.from_id)
    )

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        _emit(args.func(args))
    except NotebookError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
