import argparse
import json
import os
from pathlib import Path
from typing import List

from .scaffold import scaffold_from_spec, quick_new
from .spec import AgentSpec
from .core.tools import list_builtin_tools
from .core.llm import DummyProvider, OpenAIProvider, ProviderBase
from .core.agent import Agent
from .core.runner import AgentRunner


def cmd_list_tools(_: argparse.Namespace) -> None:
    tools = list_builtin_tools()
    for t in tools:
        print(f"- {t['name']}: {t['description']}")


def cmd_new(ns: argparse.Namespace) -> None:
    name = ns.name
    desc = ns.desc or ""
    tools = [t.strip() for t in (ns.tools or "").split(",") if t.strip()]
    dest = Path(ns.dest or f"agents/{name}")
    dest.parent.mkdir(parents=True, exist_ok=True)
    spec = quick_new(name=name, description=desc, tools=tools)
    scaffold_from_spec(spec, dest)
    print(f"Scaffolded agent at: {dest}")


def _provider_from_ns(ns: argparse.Namespace) -> ProviderBase:
    provider = (ns.provider or "dummy").lower()
    if provider == "openai":
        return OpenAIProvider(
            api_key=os.environ.get("OPENAI_API_KEY"),
            base_url=os.environ.get("OPENAI_BASE_URL"),
            model=os.environ.get("OPENAI_MODEL", "gpt-4o-mini"),
        )
    return DummyProvider()


def cmd_design(ns: argparse.Namespace) -> None:
    prompt = ns.prompt
    out = Path(ns.out or "spec.json")
    provider = _provider_from_ns(ns)

    system = (
        "你是一个专业的 Agent 架构设计师。"
        "请根据用户需求，输出一个 JSON 规范：{name, description, tools: [string]}。"
        "工具可从内置工具列表选择：todo, fs, shell(默认禁用)。"
        "输出必须是严格 JSON，不含额外注释。"
    )

    agent = Agent(
        name="AgentMakerDesigner",
        system_prompt=system,
        tools=[],
        provider=provider,
        json_only=True,
    )
    runner = AgentRunner(agent, max_steps=1)
    result = runner.run(task=prompt)

    try:
        spec_obj = json.loads(result.output)
    except Exception:
        # 回退：用最小可行 spec
        spec_obj = {
            "name": ns.fallback_name or "auto_agent",
            "description": prompt,
            "tools": ["todo", "fs"],
        }

    spec = AgentSpec.from_dict(spec_obj)
    out.write_text(json.dumps(spec.to_dict(), ensure_ascii=False, indent=2))
    print(f"Design spec written: {out}")

    if ns.scaffold:
        dest = Path(ns.dest or f"agents/{spec.name}")
        dest.parent.mkdir(parents=True, exist_ok=True)
        scaffold_from_spec(spec, dest)
        print(f"Scaffolded agent at: {dest}")


def cmd_scaffold(ns: argparse.Namespace) -> None:
    spec_path = Path(ns.spec)
    spec = AgentSpec.from_dict(json.loads(spec_path.read_text()))
    dest = Path(ns.dest or f"agents/{spec.name}")
    dest.parent.mkdir(parents=True, exist_ok=True)
    scaffold_from_spec(spec, dest)
    print(f"Scaffolded agent at: {dest}")


def cmd_run(ns: argparse.Namespace) -> None:
    # 运行一个最小内置 Agent（无需脚手架），方便快速试用
    provider = _provider_from_ns(ns)
    from .core.tools import build_tools_from_names

    tools = build_tools_from_names(ns.tools or ["todo", "fs"])  # type: ignore[arg-type]
    agent = Agent(
        name="InlineAgent",
        system_prompt=(
            "你是实用型助手。优先：明确目标→规划→使用工具→给出结果。"
            "若要调用工具，返回严格 JSON：{thought, plan, tool: {name, args}}；"
            "若完成，返回严格 JSON：{final: string}。"
        ),
        tools=tools,
        provider=provider,
        json_only=True,
    )
    runner = AgentRunner(agent, max_steps=ns.max_steps)
    result = runner.run(task=ns.task)
    print("Final:", result.output)


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="agent_maker", description="Agent Maker CLI")
    sub = p.add_subparsers(dest="cmd", required=True)

    sp = sub.add_parser("list-tools", help="列出内置工具")
    sp.set_defaults(func=cmd_list_tools)

    sp = sub.add_parser("new", help="快速创建新 Agent")
    sp.add_argument("name")
    sp.add_argument("--desc", default="")
    sp.add_argument("--tools", default="todo,fs")
    sp.add_argument("--dest", default=None)
    sp.set_defaults(func=cmd_new)

    sp = sub.add_parser("design", help="使用 LLM 设计 Agent 规范")
    sp.add_argument("--prompt", required=True)
    sp.add_argument("--out", default="spec.json")
    sp.add_argument("--provider", choices=["dummy", "openai"], default="dummy")
    sp.add_argument("--fallback-name", default="auto_agent")
    sp.add_argument("--scaffold", action="store_true")
    sp.add_argument("--dest", default=None)
    sp.set_defaults(func=cmd_design)

    sp = sub.add_parser("scaffold", help="根据 spec.json 生成工程")
    sp.add_argument("--spec", required=True)
    sp.add_argument("--dest", default=None)
    sp.set_defaults(func=cmd_scaffold)

    sp = sub.add_parser("run", help="运行一个内置最小 Agent")
    sp.add_argument("--task", required=True)
    sp.add_argument("--tools", nargs="*", default=["todo", "fs"])
    sp.add_argument("--provider", choices=["dummy", "openai"], default="dummy")
    sp.add_argument("--max-steps", type=int, default=6)
    sp.set_defaults(func=cmd_run)

    return p


def main(argv: List[str] | None = None) -> None:
    p = build_parser()
    ns = p.parse_args(argv)
    ns.func(ns)  # type: ignore[misc]


if __name__ == "__main__":
    main()

