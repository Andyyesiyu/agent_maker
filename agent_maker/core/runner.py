from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict

from .agent import Agent
from .config import Config


@dataclass
class RunResult:
    output: str
    steps: int


class AgentRunner:
    def __init__(self, agent: Agent, max_steps: int = 6, run_dir: str | None = None, config: Config | None = None) -> None:
        self.agent = agent
        self.max_steps = max_steps
        self.run_dir = Path(run_dir or "runs")
        self.run_dir.mkdir(parents=True, exist_ok=True)
        self.config = config or Config.from_env()

    def _dump_trace(self, run_id: str) -> None:
        if not self.config.tracing_enabled:
            return
        tdir = self.run_dir / run_id
        tdir.mkdir(parents=True, exist_ok=True)
        redact = self.config.redactor()
        (tdir / "trace.jsonl").write_text(self.agent.state.to_trace_jsonl(redact=redact), encoding="utf-8")

    def run(self, task: str) -> RunResult:
        from uuid import uuid4

        run_id = str(uuid4())
        self.agent.state.add_message("user", task)
        self.agent.state.add_trace("start", {"task": task, "run_id": run_id})
        output = ""
        for i in range(self.max_steps):
            res: Dict[str, Any] = self.agent.step()
            if res.get("type") == "final":
                output = res.get("output", "")
                break
        self._dump_trace(run_id)
        return RunResult(output=output, steps=i + 1)
