from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass, field
from typing import Dict, List, Mapping


@dataclass
class AgentSpec:
    name: str = "agent"
    description: str = ""
    tools: List[str] = field(default_factory=list)

    @staticmethod
    def from_dict(d: Mapping[str, object]) -> "AgentSpec":
        raw_tools = d.get("tools", [])
        tools_iter: Iterable[object]
        if isinstance(raw_tools, Iterable) and not isinstance(raw_tools, (str, bytes)):
            tools_iter = raw_tools
        else:
            tools_iter = []
        return AgentSpec(
            name=str(d.get("name", "agent")),
            description=str(d.get("description", "")),
            tools=[str(x) for x in tools_iter],
        )

    def to_dict(self) -> Dict[str, object]:
        return {"name": self.name, "description": self.description, "tools": self.tools or []}
