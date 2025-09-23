import unittest
import tempfile
from pathlib import Path

from agent_maker.core.state import ConversationState
from agent_maker.core.tools import (
    ToolError,
    _safe_join,
    build_tools_from_names,
    make_fs_read_tool,
    make_fs_write_tool,
    make_todo_tool,
)


class TestTools(unittest.TestCase):
    def test_safe_join_prevents_traversal(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            base = Path(tmpdir)
            with self.assertRaises(ToolError):
                _safe_join(base, "../outside.txt")

    def test_fs_write_and_read(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            base = Path(tmpdir)
            write_tool = make_fs_write_tool(workspace=base)
            read_tool = make_fs_read_tool(workspace=base)
            state = ConversationState()

            res = write_tool.run({"path": "file.txt", "content": "a"}, state)
            self.assertTrue(res["ok"])  # initial write

            res = write_tool.run({"path": "file.txt", "content": "b"}, state)
            self.assertFalse(res["ok"])  # overwrite disallowed

            res = write_tool.run({"path": "file.txt", "content": "b", "overwrite": True}, state)
            self.assertTrue(res["ok"])  # overwrite allowed

            res = read_tool.run({"path": "file.txt"}, state)
            self.assertTrue(res["ok"])
            self.assertEqual(res["content"], "b")

    def test_todo_tool_add_and_done(self):
        tool = make_todo_tool()
        state = ConversationState()

        added = tool.run({"op": "add", "text": "task"}, state)
        self.assertTrue(added["ok"])
        item_id = added["item"]["id"]

        listing = tool.run({"op": "list"}, state)
        self.assertEqual(len(listing["plan"]["items"]), 1)

        done = tool.run({"op": "done", "id": item_id}, state)
        self.assertTrue(done["ok"])

        listing = tool.run({"op": "list"}, state)
        self.assertEqual(listing["plan"]["items"][0]["status"], "done")

    def test_build_tools_from_names_fs(self):
        tools = build_tools_from_names(["fs"])
        names = {t.name for t in tools}
        self.assertIn("fs.read", names)
        self.assertIn("fs.write", names)


if __name__ == "__main__":
    unittest.main()
