from __future__ import annotations

import json
from pathlib import Path
from typing import List

from .spec import AgentSpec


MAIN_TEMPLATE = """
from agent_maker.core import Agent, AgentRunner, build_tools_from_names
from agent_maker.core.llm import DummyProvider, OpenAIProvider
import argparse
import os


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--task", required=True)
    ap.add_argument("--provider", choices=["dummy", "openai"], default="dummy")
    ap.add_argument("--max-steps", type=int, default=6)
    ns = ap.parse_args()

    if ns.provider == "openai":
        provider = OpenAIProvider(
            api_key=os.environ.get("OPENAI_API_KEY"),
            base_url=os.environ.get("OPENAI_BASE_URL"),
            model=os.environ.get("OPENAI_MODEL", "gpt-4o-mini"),
        )
    else:
        provider = DummyProvider()

    tools = build_tools_from_names({tools_list})
    system = (
        "你是一个专业的任务助手。遵循：先规划（必要时维护 TODO），再调用工具，最后输出结果。"
        "调用工具时输出严格 JSON：{thought, plan?, tool: {name, args}}；完成时输出 {final: string}。"
    )
    agent = Agent(name="{agent_name}", system_prompt=system, tools=tools, provider=provider, json_only=True)
    runner = AgentRunner(agent, max_steps=ns.max_steps)
    result = runner.run(task=ns.task)
    print(result.output)


if __name__ == "__main__":
    main()
"""


def scaffold_from_spec(spec: AgentSpec, dest: Path) -> None:
    dest.mkdir(parents=True, exist_ok=True)
    (dest / "agent.json").write_text(json.dumps(spec.to_dict(), ensure_ascii=False, indent=2), encoding="utf-8")
    tools_list = repr(spec.tools or ["todo", "fs"])  # python list literal
    main_py = MAIN_TEMPLATE.replace("{agent_name}", spec.name).replace("{tools_list}", tools_list)
    (dest / "main.py").write_text(main_py, encoding="utf-8")


def quick_new(name: str, description: str, tools: List[str]) -> AgentSpec:
    return AgentSpec(name=name, description=description, tools=tools or ["todo", "fs"])

