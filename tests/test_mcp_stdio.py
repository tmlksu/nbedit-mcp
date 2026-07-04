"""Integration tests: drive the MCP server over real stdio.

These spawn the server as a subprocess (`python -m notebook_edit.mcp_server`) and
talk to it through the MCP client, exactly as any MCP client would. They verify
the wiring (tool registration, argument passing, NotebookError -> ToolError) that
the pure-core tests in test_core.py cannot reach.
"""

from __future__ import annotations

import json
import sys

import nbformat
import pytest
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

import notebook_edit


def _text(result) -> str:
    """Concatenate the text payload of a CallToolResult."""
    return "".join(c.text for c in result.content if c.type == "text")


@pytest.fixture
def notebook(tmp_path):
    """A one-cell notebook on disk; returns its absolute path as str."""
    nb = nbformat.v4.new_notebook()
    nb.cells = [nbformat.v4.new_markdown_cell("# Demo")]
    p = tmp_path / "demo.ipynb"
    with p.open("w") as f:
        nbformat.write(nb, f)
    return str(p)


async def _session(fn):
    """Spawn the stdio server, run `fn(session)`, tear everything down."""
    params = StdioServerParameters(
        command=sys.executable,
        args=["-m", "notebook_edit.mcp_server"],
    )
    async with stdio_client(params) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()
            return await fn(session)


async def test_initialize_reports_server_version():
    """The MCP initialize handshake carries __version__ in serverInfo — this is
    how a client (e.g. a VS Code extension) reads the server version."""
    async def run(session):
        return await session.initialize()

    result = await _session(run)
    assert result.serverInfo.name == "notebook-edit"
    assert result.serverInfo.version == notebook_edit.__version__


async def test_lists_all_tools():
    async def run(session):
        return {t.name for t in (await session.list_tools()).tools}

    names = await _session(run)
    assert names == {
        "create_notebook", "notebook_rev", "list_cells", "read_cells",
        "insert_cell", "insert_cells", "edit_cell", "patch_cell", "delete_cell",
        "move_cell",
    }


async def test_insert_patch_read_roundtrip(notebook):
    async def run(session):
        await session.call_tool("insert_cell", {
            "path": notebook, "index": 1, "cell_type": "code",
            "source": "print('hi')",
        })
        await session.call_tool("patch_cell", {
            "path": notebook, "index": 1, "old": "hi", "new": "world",
        })
        return await session.call_tool("read_cells", {"path": notebook, "indices": [1]})

    result = await _session(run)
    cells = [json.loads(c.text) for c in result.content if c.type == "text"]
    cell = cells[0]
    assert cell["type"] == "code"
    assert cell["source"] == "print('world')"
    assert cell["outputs_text"] == ""  # code cell edited -> outputs cleared


async def test_id_addressing_roundtrip(notebook):
    """Insert, then patch/read the cell by its stable id across the stdio boundary."""
    async def run(session):
        ins = await session.call_tool("insert_cell", {
            "path": notebook, "index": 1, "cell_type": "code",
            "source": "print('hi')",
        })
        cid = json.loads(_text(ins))["id"]
        await session.call_tool("patch_cell", {
            "path": notebook, "cell_id": cid, "old": "hi", "new": "world",
        })
        read = await session.call_tool("read_cells", {"path": notebook, "ids": [cid]})
        return cid, [json.loads(c.text) for c in read.content if c.type == "text"]

    cid, cells = await _session(run)
    assert cells[0]["id"] == cid
    assert cells[0]["source"] == "print('world')"


async def test_expected_rev_guard_over_stdio(notebook):
    """notebook_rev + a stale expected_rev must surface as a tool error."""
    async def run(session):
        rev = json.loads(_text(
            await session.call_tool("notebook_rev", {"path": notebook})
        ))["rev"]
        # external change (unguarded) invalidates `rev`
        await session.call_tool("edit_cell", {
            "path": notebook, "index": 0, "source": "# moved on",
        })
        return await session.call_tool("patch_cell", {
            "path": notebook, "index": 0, "old": "moved", "new": "x",
            "expected_rev": rev,
        })

    result = await _session(run)
    assert result.isError is True
    assert "changed on disk" in _text(result)


async def test_error_surfaces_as_tool_error(notebook):
    async def run(session):
        return await session.call_tool("read_cells", {"path": notebook, "indices": [99]})

    result = await _session(run)
    assert result.isError is True
    assert "notebook has" in _text(result)  # the CellIndexError message
