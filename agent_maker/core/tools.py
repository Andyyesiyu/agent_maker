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
    # Ensure a non-optional allowlist for type-checkers
    allowed: List[str] = allow or ["echo", "ls"]

    def handler(args: Dict[str, Any], state: ConversationState) -> Dict[str, Any]:
        import shlex
        import subprocess

        cmd = str(args.get("cmd", "")).strip()
        if not cmd:
            return {"ok": False, "error": "缺少 cmd"}
        prog = shlex.split(cmd)[0]
        if prog not in allowed:
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
        {"name": "code.search", "description": "在工作区内检索代码片段"},
        {"name": "fs.patch", "description": "应用 unified diff（支持 dry-run）"},
        {"name": "test.run", "description": "运行测试并解析结果（限时）"},
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
        elif n == "code.search":
            built.append(make_code_search_tool())
        elif n == "fs.patch":
            built.append(make_fs_patch_tool())
        elif n == "test.run":
            built.append(make_test_run_tool())
        else:
            raise ValueError(f"未知工具: {n}")
    return built


def make_code_search_tool(workspace: Path | None = None) -> Tool:
    """Search code within the workspace using ripgrep if available, else fallback.

    Args schema:
      - query: required, string regex or plain text
      - path: optional subdir to limit search
      - globs: optional list of glob patterns (e.g., ["*.py", "*.md"])
      - max_results: optional int, total matches cap (default 40)
    """

    base = workspace or Path(os.getcwd())

    def _rg_available() -> bool:
        import shutil

        return shutil.which("rg") is not None

    def _run_rg(query: str, subpath: Optional[str], globs: List[str], cap: int) -> Dict[str, Any]:
        import subprocess

        cwd = base
        args = [
            "rg",
            "--line-number",
            "--no-heading",
            "--hidden",
            "--max-count",
            str(cap),
        ]
        for g in globs:
            if g:
                args.extend(["--glob", g])
        args.append(query)
        if subpath:
            p = _safe_join(base, subpath)
            args.append(str(p.relative_to(base)))
        try:
            out = subprocess.run(
                args,
                cwd=str(cwd),
                capture_output=True,
                text=True,
                timeout=10,
            )
        except Exception as e:  # pragma: no cover - env dependent
            return {"ok": False, "error": str(e)}
        if out.returncode not in (0, 1):  # 1 => no matches
            return {"ok": False, "error": out.stderr.strip()[:1000]}

        results: Dict[str, Any] = {}
        count = 0
        for line in out.stdout.splitlines():
            # format: path:line:content
            try:
                path_part, line_part, content = line.split(":", 2)
                file_path = str(_safe_join(base, path_part).relative_to(base))
                line_no = int(line_part)
            except Exception:
                continue
            if file_path not in results:
                results[file_path] = {"path": file_path, "matches": []}
            results[file_path]["matches"].append({"line": line_no, "text": content[:300]})
            count += 1
            if count >= cap:
                break
        return {"ok": True, "results": list(results.values())}

    def _fallback_scan(query: str, subpath: Optional[str], globs: List[str], cap: int) -> Dict[str, Any]:
        import re

        start_dir = _safe_join(base, subpath) if subpath else base
        # Prepare file filtering
        patterns = globs or ["*"]
        compiled = None
        try:
            compiled = re.compile(query)
        except Exception:
            compiled = re.compile(re.escape(query))

        results: Dict[str, Any] = {}
        count = 0
        max_files = 2000
        files_seen = 0
        for root, _, files in os.walk(start_dir):
            for fname in files:
                files_seen += 1
                if files_seen > 20000:  # hard cap to avoid heavy scan
                    break
                fp = Path(root) / fname
                rel = str(fp.relative_to(base))
                # glob filter
                matched = False
                for g in patterns:
                    if fp.match(g) or Path(rel).match(g):
                        matched = True
                        break
                if not matched:
                    continue
                try:
                    text = fp.read_text(encoding="utf-8", errors="ignore")
                except Exception:
                    continue
                for i, tline in enumerate(text.splitlines(), start=1):
                    if compiled.search(tline):
                        if rel not in results:
                            results[rel] = {"path": rel, "matches": []}
                        results[rel]["matches"].append({"line": i, "text": tline[:300]})
                        count += 1
                        if count >= cap:
                            return {"ok": True, "results": list(results.values())}
            if files_seen >= max_files and count:
                break
        return {"ok": True, "results": list(results.values())}

    def handler(args: Dict[str, Any], state: ConversationState) -> Dict[str, Any]:
        query = str(args.get("query", "")).strip()
        if not query:
            return {"ok": False, "error": "缺少 query"}
        subpath = args.get("path")
        if subpath is not None:
            _safe_join(base, str(subpath))  # validate
        globs = args.get("globs") or []
        if isinstance(globs, str):
            globs = [g.strip() for g in globs.split(",") if g.strip()]
        max_results = int(args.get("max_results", 40))
        if max_results <= 0:
            max_results = 40

        if _rg_available():
            return _run_rg(query, subpath, globs, max_results)
        return _fallback_scan(query, subpath, globs, max_results)

    schema = {
        "type": "object",
        "properties": {
            "query": {"type": "string"},
            "path": {"type": "string"},
            "globs": {
                "anyOf": [
                    {"type": "array", "items": {"type": "string"}},
                    {"type": "string"},
                ]
            },
            "max_results": {"type": "integer"},
        },
        "required": ["query"],
    }

    return Tool(
        name="code.search",
        description="检索工作区代码，支持 ripgrep/fallback",
        schema=schema,
        handler=handler,
    )


def make_fs_patch_tool(workspace: Path | None = None) -> Tool:
    """Apply a unified diff patch within the workspace using system 'patch' if available.

    Args schema:
      - patch: required, unified diff string
      - dry_run: optional bool (default False)
      - strip: optional int, -p level (default 0)
      - reverse: optional bool, apply in reverse (default False)
    Safety: validates paths in headers (---/+++) to remain inside workspace.
    """

    base = workspace or Path(os.getcwd())

    def _validate_diff_paths(patch_text: str) -> Optional[str]:
        import re

        paths: List[str] = []
        for line in patch_text.splitlines():
            if line.startswith("+++") or line.startswith("---"):
                # lines like: +++ a/path/file.py or +++ path/file.py
                part = line[3:].strip()
                if part.startswith("/dev/null"):
                    continue
                # strip prefixes like a/ or b/
                if part.startswith("a/") or part.startswith("b/"):
                    part = part[2:]
                # remove timestamps after tabs or spaces
                part = part.split("\t")[0].strip()
                part = part.split(" ")[0].strip()
                if not part or part == "/dev/null":
                    continue
                paths.append(part)
        for p in paths:
            if p.startswith("/"):
                return f"绝对路径不被允许: {p}"
            try:
                _safe_join(base, p)
            except Exception:
                return f"路径越界: {p}"
        return None

    def _patch_available() -> bool:
        import shutil

        return shutil.which("patch") is not None

    def handler(args: Dict[str, Any], state: ConversationState) -> Dict[str, Any]:
        import subprocess

        patch_text = str(args.get("patch", ""))
        if not patch_text.strip():
            return {"ok": False, "error": "缺少 patch 内容"}
        err = _validate_diff_paths(patch_text)
        if err:
            return {"ok": False, "error": err}

        if not _patch_available():
            return {"ok": False, "error": "系统未安装 'patch' 命令，无法应用 unified diff"}

        dry_run = bool(args.get("dry_run", False))
        strip = int(args.get("strip", 0))
        reverse = bool(args.get("reverse", False))

        cmd = ["patch", f"-p{strip}", "--posix", "--force", "--backup", "--reject-file", "-"]
        if dry_run:
            cmd.insert(1, "--dry-run")
        if reverse:
            cmd.insert(1, "-R")

        try:
            proc = subprocess.run(
                cmd,
                input=patch_text,
                text=True,
                cwd=str(base),
                capture_output=True,
                timeout=15,
            )
        except Exception as e:  # pragma: no cover - env dependent
            return {"ok": False, "error": str(e)}

        ok = proc.returncode == 0
        out = proc.stdout[-8000:]
        errout = proc.stderr[-2000:]
        return {
            "ok": ok,
            "stdout": out,
            "stderr": errout,
            "code": proc.returncode,
            "dry_run": dry_run,
        }

    schema = {
        "type": "object",
        "properties": {
            "patch": {"type": "string"},
            "dry_run": {"type": "boolean"},
            "strip": {"type": "integer"},
            "reverse": {"type": "boolean"},
        },
        "required": ["patch"],
    }
    return Tool(name="fs.patch", description="应用 unified diff 到工作区", schema=schema, handler=handler)


def make_test_run_tool(workspace: Path | None = None) -> Tool:
    """Run tests (prefer pytest) with a timeout and parse a summary.

    Args schema:
      - cmd: optional string, custom command to run tests
      - timeout: optional int seconds (default 60)
    """

    base = workspace or Path(os.getcwd())

    def _pick_cmd(custom: Optional[str]) -> List[List[str]]:
        import shutil

        if custom:
            return [[custom]]
        cmds: List[List[str]] = []
        if shutil.which("uv"):
            cmds.append(["uv", "run", "-m", "pytest", "-q"])  # prefer uv if available
        if shutil.which("pytest"):
            cmds.append(["pytest", "-q"])
        # always include python -m pytest fallback
        cmds.append(["python", "-m", "pytest", "-q"])
        return cmds

    def _run_one(cmd: List[str], timeout_s: int) -> Dict[str, Any]:
        import subprocess

        try:
            p = subprocess.run(
                cmd,
                cwd=str(base),
                capture_output=True,
                text=True,
                timeout=timeout_s,
            )
        except subprocess.TimeoutExpired:
            return {"ok": False, "timeout": True, "stdout": "", "stderr": "timeout"}
        except Exception as e:  # pragma: no cover - env dependent
            return {"ok": False, "error": str(e), "stdout": "", "stderr": ""}
        return {
            "ok": p.returncode == 0,
            "code": p.returncode,
            "stdout": p.stdout[-12000:],
            "stderr": p.stderr[-4000:],
        }

    def _parse_summary(stdout: str, stderr: str) -> Dict[str, Any]:
        import re

        text = (stdout or "") + "\n" + (stderr or "")
        summary = {}
        # typical line: 3 passed, 1 failed, 2 skipped in 1.23s
        m = re.search(r"(\d+)\s+passed.*?in\s+([0-9\.]+)s", text)
        if m:
            summary["passed"] = int(m.group(1))
            summary["time_s"] = float(m.group(2))
        m = re.search(r"(\d+)\s+failed", text)
        if m:
            summary["failed"] = int(m.group(1))
        m = re.search(r"(\d+)\s+skipped", text)
        if m:
            summary["skipped"] = int(m.group(1))
        # collect brief failures
        failures: List[Dict[str, Any]] = []
        for line in text.splitlines():
            if line.strip().startswith("FAILED "):
                # e.g., FAILED tests/test_x.py::test_y - AssertionError: ...
                failures.append({"entry": line.strip()[:500]})
        if failures:
            summary["failures"] = failures[:20]
        return summary

    def handler(args: Dict[str, Any], state: ConversationState) -> Dict[str, Any]:
        custom = args.get("cmd")
        timeout_s = int(args.get("timeout", 60))
        tried: List[Dict[str, Any]] = []
        for cmd in _pick_cmd(custom if isinstance(custom, str) and custom.strip() else None):
            res = _run_one(cmd, timeout_s)
            res["cmd"] = " ".join(cmd)
            tried.append(res)
            if res.get("ok"):
                summary = _parse_summary(res.get("stdout", ""), res.get("stderr", ""))
                return {"ok": True, "summary": summary, "stdout": res.get("stdout", ""), "stderr": res.get("stderr", ""), "cmd": res["cmd"]}
            # if custom provided, don't fallback further unless timeout
            if custom:
                break
        # none succeeded
        last = tried[-1] if tried else {"stdout": "", "stderr": ""}
        summary = _parse_summary(last.get("stdout", ""), last.get("stderr", ""))
        return {"ok": False, "summary": summary, "tried": [{"cmd": t.get("cmd"), "ok": t.get("ok"), "code": t.get("code", None)} for t in tried]}

    schema = {
        "type": "object",
        "properties": {
            "cmd": {"type": "string"},
            "timeout": {"type": "integer"},
        },
    }
    return Tool(name="test.run", description="运行 pytest 并解析结果", schema=schema, handler=handler)
