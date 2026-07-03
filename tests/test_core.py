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
    assert cells[0]["summary"] == "# Title\nintro"
    assert cells[0]["num_lines"] == 2
    assert cells[1]["has_outputs"] is True
    assert cells[0]["has_outputs"] is False
    assert all(c["has_error"] is False for c in cells)


def test_list_cells_summary_truncated(nb_path):
    core.edit_cell(nb_path, 0, "z" * 200)
    summary = core.list_cells(nb_path)[0]["summary"]
    assert summary.endswith("…")
    assert len(summary) == 101  # 100 chars + ellipsis


def test_summary_uses_leading_comment_block(nb_path):
    core.edit_cell(nb_path, 1, "# step 1: load\n# step 2: transform\nx = 1")
    assert core.list_cells(nb_path)[1]["summary"] == "# step 1: load\n# step 2: transform"


def test_summary_caps_at_three_lines(nb_path):
    core.edit_cell(nb_path, 1, "# a\n# b\n# c\n# d\n# e\nx = 1")
    assert core.list_cells(nb_path)[1]["summary"] == "# a\n# b\n# c"


def test_summary_falls_back_without_comment(nb_path):
    core.edit_cell(nb_path, 1, "x = 1\ny = 2")
    assert core.list_cells(nb_path)[1]["summary"] == "x = 1"


def test_read_cell_renders_outputs(nb_path):
    cell = core.read_cells(nb_path, [1])[0]
    assert cell["type"] == "code"
    assert cell["source"] == "x = 1\nprint(x)"
    assert cell["execution_count"] == 5
    assert cell["outputs_text"] == "1"
    assert cell["has_error"] is False
    assert cell["output_types"] == ["stream"]


def test_read_cell_markdown_has_no_outputs_fields(nb_path):
    cell = core.read_cells(nb_path, [0])[0]
    assert "outputs_text" not in cell
    assert "has_error" not in cell
    assert cell["source"] == "# Title\nintro"


def _nb_with_error_cell(tmp_path):
    nb = nbformat.v4.new_notebook()
    code = nbformat.v4.new_code_cell("1 / 0")
    code["outputs"] = [
        nbformat.v4.new_output(
            "error",
            ename="ZeroDivisionError",
            evalue="division by zero",
            traceback=["Traceback...", "ZeroDivisionError: division by zero"],
        )
    ]
    nb.cells = [code]
    p = tmp_path / "err.ipynb"
    with p.open("w") as f:
        nbformat.write(nb, f)
    return p


def test_read_cell_renders_error(tmp_path):
    p = _nb_with_error_cell(tmp_path)
    cell = core.read_cells(p, [0])[0]
    assert cell["has_error"] is True
    assert cell["output_types"] == ["error"]
    assert "ZeroDivisionError: division by zero" in cell["outputs_text"]


def test_list_cells_flags_error(tmp_path):
    p = _nb_with_error_cell(tmp_path)
    assert core.list_cells(p)[0]["has_error"] is True


def test_read_cell_renders_image_placeholder(tmp_path):
    nb = nbformat.v4.new_notebook()
    code = nbformat.v4.new_code_cell("plot()")
    code["outputs"] = [
        nbformat.v4.new_output("display_data", data={"image/png": "BASE64…"}),
    ]
    nb.cells = [code]
    p = tmp_path / "img.ipynb"
    with p.open("w") as f:
        nbformat.write(nb, f)
    cell = core.read_cells(p, [0])[0]
    assert cell["outputs_text"] == "[image/png]"  # no base64 blob leaked
    assert cell["has_error"] is False


# --------------------------------------------------------------------------- #
# Batch read
# --------------------------------------------------------------------------- #
def test_read_cells_multiple_in_order(nb_path):
    cells = core.read_cells(nb_path, [2, 0])
    assert [c["index"] for c in cells] == [2, 0]
    assert [c["type"] for c in cells] == ["raw", "markdown"]


def test_read_cells_allows_duplicates(nb_path):
    cells = core.read_cells(nb_path, [1, 1])
    assert [c["index"] for c in cells] == [1, 1]


def test_read_cells_empty_returns_empty(nb_path):
    assert core.read_cells(nb_path, []) == []


def test_read_cells_strict_lists_bad_indices(nb_path):
    with pytest.raises(CellIndexError) as exc:
        core.read_cells(nb_path, [0, 99, -1])
    msg = str(exc.value)
    assert "99" in msg and "-1" in msg  # both offenders reported


def test_read_cells_small_source_has_no_window_fields(nb_path):
    cell = core.read_cells(nb_path, [0])[0]
    assert cell["source"] == "# Title\nintro"
    assert "source_truncated" not in cell  # small cell stays clean


def test_read_cells_windows_large_source(nb_path):
    big = "x" * (core._SOURCE_WINDOW + 500)
    core.edit_cell(nb_path, 1, big)
    cell = core.read_cells(nb_path, [1])[0]
    assert len(cell["source"]) == core._SOURCE_WINDOW
    assert cell["source_truncated"] is True
    assert cell["source_length"] == core._SOURCE_WINDOW + 500
    assert cell["source_offset"] == 0


def test_read_cells_offset_pages_source(nb_path):
    src = "A" * core._SOURCE_WINDOW + "B" * 500
    core.edit_cell(nb_path, 1, src)
    tail = core.read_cells(nb_path, [1], offset=core._SOURCE_WINDOW)[0]
    assert tail["source"] == "B" * 500
    assert tail["source_offset"] == core._SOURCE_WINDOW
    assert tail["source_truncated"] is True  # offset > 0


def test_read_cells_rejects_negative_offset(nb_path):
    with pytest.raises(CellIndexError):
        core.read_cells(nb_path, [0], offset=-1)


def test_read_cells_budget_omits_trailing_cells(tmp_path):
    nb = nbformat.v4.new_notebook()
    # Each cell ~ the window size; a few of them blow past the total budget.
    nb.cells = [nbformat.v4.new_code_cell("y" * core._SOURCE_WINDOW) for _ in range(6)]
    p = tmp_path / "big.ipynb"
    with p.open("w") as f:
        nbformat.write(nb, f)

    cells = core.read_cells(p, list(range(6)))
    included = [c for c in cells if not c.get("content_omitted")]
    omitted = [c for c in cells if c.get("content_omitted")]
    assert len(cells) == 6  # every requested index accounted for
    assert included and omitted  # some fit, the rest are omitted
    # Budget respected by the included cells.
    assert sum(len(c["source"]) for c in included) <= core._READ_BUDGET
    # Omitted entries still report their real length so the caller can re-read.
    assert all(c["source_length"] == core._SOURCE_WINDOW for c in omitted)


# --------------------------------------------------------------------------- #
# Explicit summary (cell metadata)
# --------------------------------------------------------------------------- #
def test_insert_with_summary_sets_metadata(nb_path):
    core.insert_cell(nb_path, 3, "code", "x = compute()", summary="データ読込")
    assert core.list_cells(nb_path)[3]["summary"] == "データ読込"


def test_metadata_summary_overrides_leading_comment(nb_path):
    core.insert_cell(nb_path, 3, "code", "# derived header\nx = 1", summary="explicit")
    assert core.list_cells(nb_path)[3]["summary"] == "explicit"


def test_edit_summary_none_keeps_existing(nb_path):
    core.insert_cell(nb_path, 3, "code", "x = 1", summary="keep me")
    core.edit_cell(nb_path, 3, "x = 2")  # no summary arg
    assert core.list_cells(nb_path)[3]["summary"] == "keep me"


def test_edit_summary_sets_and_clears(nb_path):
    core.insert_cell(nb_path, 3, "code", "x = 1", summary="old")
    core.edit_cell(nb_path, 3, "x = 2", summary="new")
    assert core.list_cells(nb_path)[3]["summary"] == "new"
    core.edit_cell(nb_path, 3, "# fallback\nx = 3", summary="")  # clear
    assert core.list_cells(nb_path)[3]["summary"] == "# fallback"


def test_metadata_summary_capped(nb_path):
    core.insert_cell(nb_path, 3, "code", "x = 1", summary="z" * 200)
    summary = core.list_cells(nb_path)[3]["summary"]
    assert summary.endswith("…") and len(summary) == 101


def test_read_does_not_create_backup(nb_path):
    core.list_cells(nb_path)
    core.read_cells(nb_path, [0])[0]
    assert not (nb_path.parent / (nb_path.name + ".bak")).exists()


# --------------------------------------------------------------------------- #
# Mutations
# --------------------------------------------------------------------------- #
def test_insert_before(nb_path):
    assert core.insert_cell(nb_path, 1, "markdown", "## mid")["index"] == 1
    cells = core.list_cells(nb_path)
    assert [c["type"] for c in cells] == ["markdown", "markdown", "code", "raw"]
    assert core.read_cells(nb_path, [1])[0]["source"] == "## mid"


def test_insert_append_at_len(nb_path):
    core.insert_cell(nb_path, 3, "code", "end = True")
    assert core.read_cells(nb_path, [3])[0]["source"] == "end = True"


# --------------------------------------------------------------------------- #
# Batch insert
# --------------------------------------------------------------------------- #
def test_insert_cells_contiguous_in_order(nb_path):
    result = core.insert_cells(
        nb_path,
        1,
        [
            {"cell_type": "markdown", "source": "## 前処理"},
            {"cell_type": "code", "source": "import pandas"},
            {"cell_type": "code", "source": "df = load()", "summary": "読込"},
        ],
    )
    assert result["indices"] == [1, 2, 3]
    cells = core.list_cells(nb_path)
    assert [c["type"] for c in cells[1:4]] == ["markdown", "code", "code"]
    assert cells[3]["summary"] == "読込"  # per-item summary applied
    # original cells pushed down, not lost
    assert [c["type"] for c in cells] == [
        "markdown", "markdown", "code", "code", "code", "raw"
    ]


def test_insert_cells_append_at_len(nb_path):
    r = core.insert_cells(nb_path, 3, [{"cell_type": "code", "source": "z = 1"}])
    assert r["indices"] == [3]
    assert core.read_cells(nb_path, [3])[0]["source"] == "z = 1"


def test_insert_cells_empty_is_noop(nb_path):
    before = core.list_cells(nb_path)
    assert core.insert_cells(nb_path, 1, []) == {"indices": [], "ids": []}
    assert core.list_cells(nb_path) == before
    assert not (nb_path.parent / (nb_path.name + ".bak")).exists()  # no write


def test_insert_cells_atomic_on_bad_item(nb_path):
    before = nb_path.read_bytes()
    with pytest.raises(CellTypeError) as exc:
        core.insert_cells(
            nb_path,
            1,
            [
                {"cell_type": "code", "source": "ok"},
                {"cell_type": "python", "source": "bad type"},  # invalid
            ],
        )
    assert "item 1" in str(exc.value)  # offender named
    assert nb_path.read_bytes() == before  # nothing written


def test_insert_cells_bad_index_writes_nothing(nb_path):
    before = nb_path.read_bytes()
    with pytest.raises(CellIndexError):
        core.insert_cells(nb_path, 99, [{"cell_type": "code", "source": "x"}])
    assert nb_path.read_bytes() == before


def test_edit_clears_code_outputs(nb_path):
    core.edit_cell(nb_path, 1, "y = 2")
    cell = core.read_cells(nb_path, [1])[0]
    assert cell["source"] == "y = 2"
    assert cell["outputs_text"] == ""
    assert cell["has_error"] is False
    assert cell["execution_count"] is None


def test_edit_markdown_no_output_side_effect(nb_path):
    core.edit_cell(nb_path, 0, "# New")
    assert core.read_cells(nb_path, [0])[0]["source"] == "# New"


def test_patch_unique(nb_path):
    result = core.patch_cell(nb_path, 1, "x = 1", "x = 99")
    assert result["index"] == 1 and result["replacements"] == 1
    cell = core.read_cells(nb_path, [1])[0]
    assert cell["source"] == "x = 99\nprint(x)"
    assert cell["outputs_text"] == ""  # cleared


def test_delete(nb_path):
    result = core.delete_cell(nb_path, 0)
    assert result["deleted_index"] == 0 and result["type"] == "markdown"
    assert [c["type"] for c in core.list_cells(nb_path)] == ["code", "raw"]


def test_move(nb_path):
    core.move_cell(nb_path, 0, 2)
    assert [c["type"] for c in core.list_cells(nb_path)] == ["code", "raw", "markdown"]


def test_move_preserves_outputs(nb_path):
    core.move_cell(nb_path, 1, 0)
    cell = core.read_cells(nb_path, [0])[0]
    assert cell["type"] == "code"
    assert cell["execution_count"] == 5  # move must NOT clear outputs
    assert cell["outputs_text"] == "1"


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
        core.read_cells(nb_path, [99])[0]


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


# --------------------------------------------------------------------------- #
# Cell-id addressing (ADR-0014)
# --------------------------------------------------------------------------- #
def _id_at(nb_path, index):
    return core.list_cells(nb_path)[index]["id"]


def test_list_and_read_expose_id(nb_path):
    listed = core.list_cells(nb_path)
    assert all(isinstance(c["id"], str) and c["id"] for c in listed)
    read = core.read_cells(nb_path, [1])[0]
    assert read["id"] == listed[1]["id"]


def test_read_cells_by_id(nb_path):
    cid = _id_at(nb_path, 1)
    cell = core.read_cells(nb_path, ids=[cid])[0]
    assert cell["id"] == cid
    assert cell["source"] == "x = 1\nprint(x)"


def test_read_cells_rejects_both_index_and_id(nb_path):
    with pytest.raises(CellIndexError):
        core.read_cells(nb_path, [0], ids=[_id_at(nb_path, 0)])


def test_read_cells_rejects_neither(nb_path):
    with pytest.raises(CellIndexError):
        core.read_cells(nb_path)


def test_read_cells_unknown_id_lists_offender(nb_path):
    with pytest.raises(CellIndexError) as exc:
        core.read_cells(nb_path, ids=["nope-not-real"])
    assert "nope-not-real" in str(exc.value)


def test_edit_by_id_hits_right_cell(nb_path):
    cid = _id_at(nb_path, 1)
    result = core.edit_cell(nb_path, source="y = 2", cell_id=cid)
    assert result == {"index": 1, "id": cid}
    assert core.read_cells(nb_path, ids=[cid])[0]["source"] == "y = 2"


def test_patch_by_id(nb_path):
    cid = _id_at(nb_path, 1)
    result = core.patch_cell(nb_path, old="x = 1", new="x = 99", cell_id=cid)
    assert result["id"] == cid
    assert core.read_cells(nb_path, ids=[cid])[0]["source"] == "x = 99\nprint(x)"


def test_delete_by_id(nb_path):
    cid = _id_at(nb_path, 0)
    result = core.delete_cell(nb_path, cell_id=cid)
    assert result["id"] == cid
    assert cid not in [c["id"] for c in core.list_cells(nb_path)]


def test_move_by_from_id_preserves_outputs(nb_path):
    cid = _id_at(nb_path, 1)  # the code cell with stale output
    core.move_cell(nb_path, to_index=0, from_id=cid)
    moved = core.read_cells(nb_path, [0])[0]
    assert moved["id"] == cid
    assert moved["execution_count"] == 5  # move must not clear outputs


def test_id_is_stable_across_insert_shift(nb_path):
    """The whole point: an id keeps pointing at the same cell after an insert
    shifts every index below it."""
    cid = _id_at(nb_path, 1)  # code cell at index 1
    core.insert_cell(nb_path, 0, "markdown", "## new top")  # pushes it to index 2
    # index 1 now addresses a different cell; the id still finds the original.
    assert _id_at(nb_path, 2) == cid
    core.patch_cell(nb_path, old="x = 1", new="x = 7", cell_id=cid)
    assert core.read_cells(nb_path, ids=[cid])[0]["source"].startswith("x = 7")


def test_resolve_rejects_both_index_and_id(nb_path):
    with pytest.raises(CellIndexError):
        core.delete_cell(nb_path, index=0, cell_id=_id_at(nb_path, 0))


def test_resolve_rejects_neither_index_nor_id(nb_path):
    with pytest.raises(CellIndexError):
        core.delete_cell(nb_path)


def test_insert_returns_id(nb_path):
    result = core.insert_cell(nb_path, 0, "code", "a = 1")
    assert isinstance(result["id"], str) and result["id"]
    assert _id_at(nb_path, 0) == result["id"]


def test_insert_cells_returns_ids(nb_path):
    result = core.insert_cells(
        nb_path, 0, [{"cell_type": "code", "source": "a"}, {"cell_type": "raw", "source": "b"}]
    )
    assert result["indices"] == [0, 1]
    assert [_id_at(nb_path, i) for i in (0, 1)] == result["ids"]
