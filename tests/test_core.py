"""Tests for notebook_edit.core.

Covers round-trips, stale-output clearing, atomic-write/backup safety, and the
three NotebookError subtypes.
"""

from __future__ import annotations

import nbformat
import pytest

from notebook_edit import core
from notebook_edit.core import (
    CellIndexError,
    CellTypeError,
    NotebookError,
    PatchError,
)


@pytest.fixture
def nb_path(tmp_path):
    """A notebook: [markdown '# Title', code with stale output, raw]."""
    nb = nbformat.v4.new_notebook()
    code = nbformat.v4.new_code_cell("x = 1\nprint(x)")
    code["outputs"] = [nbformat.v4.new_output("stream", name="stdout", text="1\n")]
    code["execution_count"] = 5
    nb.cells = [
        nbformat.v4.new_markdown_cell("# Title\nintro"),
        code,
        nbformat.v4.new_raw_cell("raw body"),
    ]
    p = tmp_path / "nb.ipynb"
    with p.open("w") as f:
        nbformat.write(nb, f)
    return p


# --------------------------------------------------------------------------- #
# Read-only
# --------------------------------------------------------------------------- #
def test_list_cells(nb_path):
    cells = core.list_cells(nb_path)
    assert [c["type"] for c in cells] == ["markdown", "code", "raw"]
    assert [c["index"] for c in cells] == [0, 1, 2]
    assert cells[0]["source_preview"] == "# Title"
    assert cells[0]["num_lines"] == 2
    assert cells[1]["has_outputs"] is True
    assert cells[0]["has_outputs"] is False


def test_list_cells_preview_truncated(nb_path):
    core.edit_cell(nb_path, 0, "z" * 200)
    preview = core.list_cells(nb_path)[0]["source_preview"]
    assert preview.endswith("…")
    assert len(preview) == 81  # 80 chars + ellipsis


def test_read_cell_code_includes_outputs(nb_path):
    cell = core.read_cell(nb_path, 1)
    assert cell["type"] == "code"
    assert cell["source"] == "x = 1\nprint(x)"
    assert cell["execution_count"] == 5
    assert cell["outputs"] and cell["outputs"][0]["text"] == "1\n"


def test_read_cell_markdown_has_no_outputs_key(nb_path):
    cell = core.read_cell(nb_path, 0)
    assert "outputs" not in cell
    assert cell["source"] == "# Title\nintro"


def test_read_does_not_create_backup(nb_path):
    core.list_cells(nb_path)
    core.read_cell(nb_path, 0)
    assert not (nb_path.parent / (nb_path.name + ".bak")).exists()


# --------------------------------------------------------------------------- #
# Mutations
# --------------------------------------------------------------------------- #
def test_insert_before(nb_path):
    assert core.insert_cell(nb_path, 1, "markdown", "## mid") == {"index": 1}
    cells = core.list_cells(nb_path)
    assert [c["type"] for c in cells] == ["markdown", "markdown", "code", "raw"]
    assert core.read_cell(nb_path, 1)["source"] == "## mid"


def test_insert_append_at_len(nb_path):
    core.insert_cell(nb_path, 3, "code", "end = True")
    assert core.read_cell(nb_path, 3)["source"] == "end = True"


def test_edit_clears_code_outputs(nb_path):
    core.edit_cell(nb_path, 1, "y = 2")
    cell = core.read_cell(nb_path, 1)
    assert cell["source"] == "y = 2"
    assert cell["outputs"] == []
    assert cell["execution_count"] is None


def test_edit_markdown_no_output_side_effect(nb_path):
    core.edit_cell(nb_path, 0, "# New")
    assert core.read_cell(nb_path, 0)["source"] == "# New"


def test_patch_unique(nb_path):
    assert core.patch_cell(nb_path, 1, "x = 1", "x = 99") == {
        "index": 1,
        "replacements": 1,
    }
    cell = core.read_cell(nb_path, 1)
    assert cell["source"] == "x = 99\nprint(x)"
    assert cell["outputs"] == []  # cleared


def test_delete(nb_path):
    assert core.delete_cell(nb_path, 0) == {"deleted_index": 0, "type": "markdown"}
    assert [c["type"] for c in core.list_cells(nb_path)] == ["code", "raw"]


def test_move(nb_path):
    core.move_cell(nb_path, 0, 2)
    assert [c["type"] for c in core.list_cells(nb_path)] == ["code", "raw", "markdown"]


def test_move_preserves_outputs(nb_path):
    core.move_cell(nb_path, 1, 0)
    cell = core.read_cell(nb_path, 0)
    assert cell["type"] == "code"
    assert cell["execution_count"] == 5  # move must NOT clear outputs
    assert cell["outputs"]


# --------------------------------------------------------------------------- #
# Safety: atomic write + backup
# --------------------------------------------------------------------------- #
def test_backup_created_on_mutation(nb_path):
    bak = nb_path.parent / (nb_path.name + ".bak")
    original = nb_path.read_bytes()
    core.edit_cell(nb_path, 0, "# changed")
    assert bak.exists()
    assert bak.read_bytes() == original  # .bak holds the pre-edit content


def test_no_temp_file_left_behind(nb_path):
    core.edit_cell(nb_path, 0, "# changed")
    leftovers = [p.name for p in nb_path.parent.iterdir() if p.name.startswith(".")]
    assert leftovers == []


def test_written_notebook_is_valid(nb_path):
    core.insert_cell(nb_path, 0, "code", "a = 1")
    nb = nbformat.read(str(nb_path), as_version=4)
    nbformat.validate(nb)  # raises if invalid


# --------------------------------------------------------------------------- #
# Errors
# --------------------------------------------------------------------------- #
def test_index_out_of_range(nb_path):
    with pytest.raises(CellIndexError):
        core.read_cell(nb_path, 99)


def test_negative_index_rejected(nb_path):
    with pytest.raises(CellIndexError):
        core.edit_cell(nb_path, -1, "nope")


def test_insert_beyond_len_rejected(nb_path):
    with pytest.raises(CellIndexError):
        core.insert_cell(nb_path, 99, "code", "x")


def test_bad_cell_type(nb_path):
    with pytest.raises(CellTypeError):
        core.insert_cell(nb_path, 0, "banana", "x")


def test_patch_not_found(nb_path):
    with pytest.raises(PatchError):
        core.patch_cell(nb_path, 1, "NOPE", "x")


def test_patch_not_unique(nb_path):
    core.edit_cell(nb_path, 1, "a=1\na=1")
    with pytest.raises(PatchError):
        core.patch_cell(nb_path, 1, "a=1", "b=2")


def test_missing_file_raises(tmp_path):
    with pytest.raises(NotebookError):
        core.list_cells(tmp_path / "nope.ipynb")


def test_failed_mutation_leaves_file_intact(nb_path):
    """A rejected edit must not touch the original file."""
    before = nb_path.read_bytes()
    with pytest.raises(CellIndexError):
        core.edit_cell(nb_path, 99, "boom")
    assert nb_path.read_bytes() == before
