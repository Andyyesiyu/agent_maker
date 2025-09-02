from __future__ import annotations

import json
import os
from dataclasses import dataclass
from typing import Any, Dict, List, Optional


Messages = List[Dict[str, str]]


@dataclass
class ProviderBase:
    def generate(self, messages: Messages, json_only: bool = False) -> str:  # pragma: no cover - interface
        raise NotImplementedError


@dataclass
class DummyProvider(ProviderBase):
    """A minimal provider for offline dev.

    - If json_only=True, will try to synthesize a reasonable JSON.
    - Otherwise echoes the last user message.
    """

    def generate(self, messages: Messages, json_only: bool = False) -> str:
        last_user = next((m for m in reversed(messages) if m.get("role") == "user"), None)
        text = (last_user or {}).get("content", "")
        if json_only:
            # naive heuristics: when designing spec
            lowered = text.lower()
            if "spec" in lowered or "规范" in lowered or "json" in lowered:
                obj = {
                    "name": "auto_agent",
                    "description": text[:200],
                    "tools": ["todo", "fs"],
                }
                return json.dumps(obj, ensure_ascii=False)
            # generic act step
            obj = {
                "thought": "分析任务并尝试添加待办或读写文件。",
                "plan": ["明确目标", "必要时调用工具", "返回结果"],
                "final": text[:200],
            }
            return json.dumps(obj, ensure_ascii=False)
        return text


@dataclass
class OpenAIProvider(ProviderBase):
    api_key: Optional[str] = None
    base_url: Optional[str] = None
    model: str = "gpt-4o-mini"
    temperature: float = 0.2

    def _client(self):  # lazy import; no hard dep if unused
        try:
            import openai  # type: ignore
        except Exception as e:  # pragma: no cover - env dependent
            raise RuntimeError(
                "OpenAI SDK 未安装。请先 `pip install openai` 或改用 --provider dummy"
            ) from e
        client = openai.OpenAI(api_key=self.api_key or os.environ.get("OPENAI_API_KEY"))
        if self.base_url:
            client.base_url = self.base_url
        return client

    def generate(self, messages: Messages, json_only: bool = False) -> str:  # pragma: no cover - env dependent
        client = self._client()
        extra = {}
        if json_only:
            extra = {"response_format": {"type": "json_object"}}
        resp = client.chat.completions.create(
            model=self.model,
            temperature=self.temperature,
            messages=[{"role": m["role"], "content": m["content"]} for m in messages],
            **extra,
        )
        return resp.choices[0].message.content or ""

