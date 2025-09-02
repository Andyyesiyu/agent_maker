from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List


@dataclass
class AgentSpec:
    name: str = "agent"
    description: str = ""
    tools: List[str] = None  # type: ignore[assignment]

    @staticmethod
    def from_dict(d: Dict) -> "AgentSpec":
        return AgentSpec(
            name=str(d.get("name", "agent")),
            description=str(d.get("description", "")),
            tools=[str(x) for x in d.get("tools", [])],
        )

    def to_dict(self) -> Dict:
        return {"name": self.name, "description": self.description, "tools": self.tools or []}
