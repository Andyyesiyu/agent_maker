import argparse
import os

from agent_maker.core import Agent, AgentRunner, build_tools_from_names
from agent_maker.core.config import Config, load_dotenv
from agent_maker.core.llm import DummyProvider, OpenAIProvider


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--task", required=True)
    ap.add_argument("--provider", choices=["dummy", "openai"], default="dummy")
    ap.add_argument("--max-steps", type=int, default=6)
    ns = ap.parse_args()
    # Load environment from .env (if present)
    load_dotenv()

    if ns.provider == "openai":
        provider = OpenAIProvider(
            api_key=os.environ.get("OPENAI_API_KEY"),
            base_url=os.environ.get("OPENAI_BASE_URL"),
            model=os.environ.get("OPENAI_MODEL", "gpt-4o-mini"),
        )
    else:
        provider = DummyProvider()

    tools = build_tools_from_names(["todo", "fs"])
    system = (
        "你是一个专业的任务助手。遵循：先规划（必要时维护 TODO），再调用工具，最后输出结果。"
        "调用工具时输出严格 JSON：{thought, plan?, tool: {name, args}}；完成时输出 {final: string}。"
    )
    agent = Agent(
        name="demo_agent",
        system_prompt=system,
        tools=tools,
        provider=provider,
        json_only=True,
    )
    runner = AgentRunner(agent, max_steps=ns.max_steps, config=Config.from_env())
    result = runner.run(task=ns.task)
    print(result.output)


if __name__ == "__main__":
    main()
