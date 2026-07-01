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


async def test_lists_all_seven_tools():
    async def run(session):
        return {t.name for t in (await session.list_tools()).tools}

    names = await _session(run)
    assert names == {
        "list_cells", "read_cell", "insert_cell", "edit_cell",
        "patch_cell", "delete_cell", "move_cell",
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
        return await session.call_tool("read_cell", {"path": notebook, "index": 1})

    result = await _session(run)
    cell = json.loads(_text(result))
    assert cell["type"] == "code"
    assert cell["source"] == "print('world')"
    assert cell["outputs_text"] == ""  # code cell edited -> outputs cleared


async def test_error_surfaces_as_tool_error(notebook):
    async def run(session):
        return await session.call_tool("read_cell", {"path": notebook, "index": 99})

    result = await _session(run)
    assert result.isError is True
    assert "notebook has" in _text(result)  # the CellIndexError message
