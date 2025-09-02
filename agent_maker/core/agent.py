from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from .llm import ProviderBase
from .state import ConversationState
from .tools import Tool


JSON_BLOCK_RE = re.compile(r"\{[\s\S]*\}\s*\Z")


@dataclass
class Agent:
    name: str
    system_prompt: str
    tools: List[Tool]
    provider: ProviderBase
    json_only: bool = True
    state: ConversationState = field(default_factory=ConversationState)

    def _history(self) -> List[Dict[str, str]]:
        msgs = [{"role": "system", "content": self.system_prompt}]
        msgs += self.state.to_history()
        return msgs

    def _ensure_json(self, text: str) -> Dict[str, Any]:
        txt = (text or "").strip()
        if not txt:
            return {}
        # try direct
        try:
            return json.loads(txt)
        except Exception:
            pass
        # try last json block
        m = JSON_BLOCK_RE.search(txt)
        if m:
            try:
                return json.loads(m.group(0))
            except Exception:
                pass
        # fallback: wrap as final
        return {"final": txt[:1000]}

    def step(self, user_input: str | None = None) -> Dict[str, Any]:
        if user_input is not None:
            self.state.add_message("user", user_input)
        prompt_messages = self._history()
        out = self.provider.generate(prompt_messages, json_only=self.json_only)
        self.state.add_trace("model_output", {"raw": out})
        obj = self._ensure_json(out) if self.json_only else {"final": out}

        # Handle tool call
        if obj.get("tool"):
            tcall = obj["tool"]
            tname = tcall.get("name")
            targs = tcall.get("args", {})
            tool = next((t for t in self.tools if t.name == tname), None)
            if not tool:
                result = {"ok": False, "error": f"未找到工具: {tname}"}
            else:
                try:
                    result = tool.run(targs, self.state)
                except Exception as e:
                    result = {"ok": False, "error": str(e)}
            self.state.add_message("tool", json.dumps(result, ensure_ascii=False), name=tname)
            self.state.add_trace("tool", {"name": tname, "args": targs, "result": result})
            return {"type": "tool", "result": result}

        # Update plan if provided
        if obj.get("plan") and isinstance(obj["plan"], list):
            for step in obj["plan"]:
                self.state.plan.add(str(step))
            self.state.add_trace("plan", {"added": obj["plan"]})

        # Final answer
        if obj.get("final"):
            msg = str(obj["final"]).strip()
            self.state.add_message("assistant", msg)
            return {"type": "final", "output": msg}

        # Assistant thought (optional)
        thought = obj.get("thought")
        if thought:
            self.state.add_message("assistant", str(thought))
        return {"type": "continue", "obj": obj}

