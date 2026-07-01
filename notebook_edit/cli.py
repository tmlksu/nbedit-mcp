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

    p = sub.add_parser("read-cell", help="Read one cell's full source/outputs")
    p.add_argument("path")
    p.add_argument("index", type=int)
    p.set_defaults(func=lambda a: core.read_cell(a.path, a.index))

    p = sub.add_parser("insert-cell", help="Insert a new cell before index")
    p.add_argument("path")
    p.add_argument("index", type=int)
    p.add_argument("cell_type", choices=core._CELL_TYPES)
    p.add_argument("source")
    p.set_defaults(func=lambda a: core.insert_cell(a.path, a.index, a.cell_type, a.source))

    p = sub.add_parser("edit-cell", help="Replace a cell's entire source")
    p.add_argument("path")
    p.add_argument("index", type=int)
    p.add_argument("source")
    p.set_defaults(func=lambda a: core.edit_cell(a.path, a.index, a.source))

    p = sub.add_parser("patch-cell", help="Replace a unique old substring with new")
    p.add_argument("path")
    p.add_argument("index", type=int)
    p.add_argument("old")
    p.add_argument("new")
    p.set_defaults(func=lambda a: core.patch_cell(a.path, a.index, a.old, a.new))

    p = sub.add_parser("delete-cell", help="Delete the cell at index")
    p.add_argument("path")
    p.add_argument("index", type=int)
    p.set_defaults(func=lambda a: core.delete_cell(a.path, a.index))

    p = sub.add_parser("move-cell", help="Move a cell from one index to another")
    p.add_argument("path")
    p.add_argument("from_index", type=int)
    p.add_argument("to_index", type=int)
    p.set_defaults(func=lambda a: core.move_cell(a.path, a.from_index, a.to_index))

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
