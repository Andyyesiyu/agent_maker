from __future__ import annotations

import json
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

from .state import ConversationState


class ToolError(Exception):
    pass


@dataclass
class Tool:
    name: str
    description: str
    schema: Dict[str, Any]
    handler: Callable[[Dict[str, Any], ConversationState], Dict[str, Any]]

    def run(self, args: Dict[str, Any], state: ConversationState) -> Dict[str, Any]:
        return self.handler(args, state)


def _safe_join(base: Path, target: str) -> Path:
    p = (base / target).resolve()
    if not str(p).startswith(str(base.resolve())):
        raise ToolError("路径越界：拒绝访问工作区之外的文件")
    return p


def make_todo_tool() -> Tool:
    def handler(args: Dict[str, Any], state: ConversationState) -> Dict[str, Any]:
        op = args.get("op")
        if op == "add":
            text = str(args.get("text", "")).strip()
            if not text:
                raise ToolError("缺少 text")
            item = state.plan.add(text)
            return {"ok": True, "item": vars(item)}
        elif op == "done":
            item_id = str(args.get("id"))
            ok = state.plan.mark(item_id, "done")
            return {"ok": ok}
        elif op == "list":
            return {"ok": True, "plan": state.plan.to_dict()}
        else:
            raise ToolError("不支持的 op")

    schema = {
        "type": "object",
        "properties": {
            "op": {"type": "string", "enum": ["add", "done", "list"]},
            "text": {"type": "string"},
            "id": {"type": "string"},
        },
        "required": ["op"],
    }
    return Tool(name="todo", description="管理计划/待办事项", schema=schema, handler=handler)


def make_fs_read_tool(workspace: Path | None = None) -> Tool:
    base = workspace or Path(os.getcwd())

    def handler(args: Dict[str, Any], state: ConversationState) -> Dict[str, Any]:
        path = str(args.get("path"))
        p = _safe_join(base, path)
        if not p.exists() or not p.is_file():
            return {"ok": False, "error": "文件不存在"}
        text = p.read_text(encoding="utf-8")
        return {"ok": True, "path": str(p), "content": text[:10000]}

    schema = {
        "type": "object",
        "properties": {"path": {"type": "string"}},
        "required": ["path"],
    }
    return Tool(name="fs.read", description="读取工作区文件（只读）", schema=schema, handler=handler)


def make_fs_write_tool(workspace: Path | None = None) -> Tool:
    base = workspace or Path(os.getcwd())

    def handler(args: Dict[str, Any], state: ConversationState) -> Dict[str, Any]:
        path = str(args.get("path"))
        content = str(args.get("content", ""))
        overwrite = bool(args.get("overwrite", False))
        p = _safe_join(base, path)
        if p.exists() and not overwrite:
            return {"ok": False, "error": "文件已存在，需 overwrite=true"}
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(content, encoding="utf-8")
        return {"ok": True, "path": str(p), "bytes": len(content.encode("utf-8"))}

    schema = {
        "type": "object",
        "properties": {
            "path": {"type": "string"},
            "content": {"type": "string"},
            "overwrite": {"type": "boolean"},
        },
        "required": ["path", "content"],
    }
    return Tool(name="fs.write", description="写入工作区文件（默认不覆盖）", schema=schema, handler=handler)


def make_shell_tool(allow: Optional[List[str]] = None) -> Tool:
    allow = allow or ["echo", "ls"]

    def handler(args: Dict[str, Any], state: ConversationState) -> Dict[str, Any]:
        import shlex
        import subprocess

        cmd = str(args.get("cmd", "")).strip()
        if not cmd:
            return {"ok": False, "error": "缺少 cmd"}
        prog = shlex.split(cmd)[0]
        if prog not in allow:
            return {"ok": False, "error": f"命令不在允许列表：{prog}"}
        try:
            out = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=10)
            return {
                "ok": out.returncode == 0,
                "stdout": out.stdout[-8000:],
                "stderr": out.stderr[-2000:],
                "code": out.returncode,
            }
        except Exception as e:  # pragma: no cover - env dependent
            return {"ok": False, "error": str(e)}

    schema = {
        "type": "object",
        "properties": {"cmd": {"type": "string"}},
        "required": ["cmd"],
    }
    return Tool(name="shell", description="受限 Shell（白名单）", schema=schema, handler=handler)


def list_builtin_tools() -> List[Dict[str, Any]]:
    return [
        {"name": "todo", "description": "管理计划/待办"},
        {"name": "fs.read", "description": "读取文件（只读）"},
        {"name": "fs.write", "description": "写入文件（默认不覆盖）"},
        {"name": "shell", "description": "受限 Shell（默认 echo/ls）"},
    ]


def build_tools_from_names(names: List[str]) -> List[Tool]:
    built: List[Tool] = []
    for n in names:
        if n == "todo":
            built.append(make_todo_tool())
        elif n == "fs":
            # convenience: fs implies read+write
            built.append(make_fs_read_tool())
            built.append(make_fs_write_tool())
        elif n == "fs.read":
            built.append(make_fs_read_tool())
        elif n == "fs.write":
            built.append(make_fs_write_tool())
        elif n == "shell":
            built.append(make_shell_tool())
        else:
            raise ValueError(f"未知工具: {n}")
    return built

