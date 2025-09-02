from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Literal, Optional


Role = Literal["system", "user", "assistant", "tool"]


@dataclass
class Message:
    role: Role
    content: str
    name: Optional[str] = None
    created_at: str = field(default_factory=lambda: datetime.utcnow().isoformat())


Status = Literal["pending", "in_progress", "done"]


@dataclass
class PlanItem:
    id: str
    text: str
    status: Status = "pending"


@dataclass
class Plan:
    items: List[PlanItem] = field(default_factory=list)

    def add(self, text: str, _id: Optional[str] = None) -> PlanItem:
        from uuid import uuid4
        item = PlanItem(id=_id or str(uuid4()), text=text)
        self.items.append(item)
        return item

    def mark(self, item_id: str, status: Status) -> bool:
        for it in self.items:
            if it.id == item_id:
                it.status = status
                return True
        return False

    def to_dict(self) -> Dict[str, Any]:
        return {"items": [vars(i) for i in self.items]}


@dataclass
class TraceEvent:
    type: str
    data: Dict[str, Any]
    timestamp: str = field(default_factory=lambda: datetime.utcnow().isoformat())


@dataclass
class ConversationState:
    messages: List[Message] = field(default_factory=list)
    plan: Plan = field(default_factory=Plan)
    scratchpad: Dict[str, Any] = field(default_factory=dict)
    trace: List[TraceEvent] = field(default_factory=list)

    def add_message(self, role: Role, content: str, name: Optional[str] = None) -> None:
        self.messages.append(Message(role=role, content=content, name=name))

    def add_trace(self, type_: str, data: Dict[str, Any]) -> None:
        self.trace.append(TraceEvent(type=type_, data=data))

    def to_history(self) -> List[Dict[str, str]]:
        return [
            {"role": m.role, "content": m.content, **({"name": m.name} if m.name else {})}
            for m in self.messages
        ]

    def to_trace_jsonl(self) -> str:
        return "\n".join(json.dumps(vars(e), ensure_ascii=False) for e in self.trace)
