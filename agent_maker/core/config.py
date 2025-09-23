from __future__ import annotations

import os
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, Optional


def _parse_bool(value: Optional[str], default: bool) -> bool:
    if value is None:
        return default
    v = value.strip().lower()
    return v in {"1", "true", "yes", "on"}


def load_dotenv(path: str = ".env", override: bool = False) -> None:
    """Load simple KEY=VALUE pairs from a .env file into os.environ.

    - Ignores missing file and commented/blank lines.
    - Does not support variable expansion; keeps it minimal to avoid new deps.
    - By default, does not override existing env vars unless override=True.
    """
    try:
        with open(path, "r", encoding="utf-8") as f:
            for raw in f:
                line = raw.strip()
                if not line or line.startswith("#"):
                    continue
                if "=" not in line:
                    continue
                key, val = line.split("=", 1)
                key = key.strip()
                val = val.strip().strip('"').strip("'")
                if key and (override or key not in os.environ):
                    os.environ[key] = val
    except FileNotFoundError:
        return


SensitiveKeys = {
    "api_key",
    "authorization",
    "token",
    "password",
    "secret",
    "openid",
    "sessionid",
    "cookie",
    "openai_api_key",
}


def _redact_value(value: Any, placeholder: str, max_len: int, strict: bool) -> Any:
    if value is None:
        return None
    # For strings, optionally truncate or replace in strict mode
    if isinstance(value, str):
        if strict:
            return placeholder
        if len(value) > max_len:
            return value[: max_len - 3] + "..."
        return value
    # For lists/dicts, the caller will handle recursion
    return value


def _redact_obj(obj: Any, *, placeholder: str, max_len: int, strict: bool) -> Any:
    if isinstance(obj, dict):
        out: Dict[str, Any] = {}
        for k, v in obj.items():
            key_l = str(k).lower()
            if any(s in key_l for s in SensitiveKeys):
                out[k] = placeholder
                continue
            out[k] = _redact_obj(v, placeholder=placeholder, max_len=max_len, strict=strict)
        return out
    if isinstance(obj, list):
        return [_redact_obj(v, placeholder=placeholder, max_len=max_len, strict=strict) for v in obj]
    return _redact_value(obj, placeholder, max_len, strict)


@dataclass
class Config:
    """Runtime config loaded from environment or defaults.

    - privacy: off | standard | strict
    - tracing_enabled: whether to write trace files
    - redact_placeholder: replacement for sensitive fields
    - max_value_length: truncate long values when not strict
    """

    privacy: str = "standard"
    tracing_enabled: bool = True
    redact_placeholder: str = "***"
    max_value_length: int = 2000
    dotenv_path: str = ".env"

    # internal: cache a redactor callable
    _redactor: Optional[Callable[[Dict[str, Any]], Dict[str, Any]]] = field(default=None, init=False, repr=False)

    @staticmethod
    def from_env() -> "Config":
        # Load .env if present (do not override existing env by default)
        load_dotenv(os.environ.get("AGENT_MAKER_DOTENV", ".env"), override=False)
        privacy = (os.environ.get("AGENT_MAKER_PRIVACY", "standard") or "standard").strip().lower()
        tracing = _parse_bool(os.environ.get("AGENT_MAKER_TRACE_ENABLED"), True)
        placeholder = os.environ.get("AGENT_MAKER_REDACT_PLACEHOLDER", "***")
        try:
            max_len = int(os.environ.get("AGENT_MAKER_MAX_VALUE_LEN", "2000"))
        except Exception:
            max_len = 2000
        cfg = Config(
            privacy=privacy if privacy in {"off", "standard", "strict"} else "standard",
            tracing_enabled=tracing,
            redact_placeholder=placeholder,
            max_value_length=max_len,
            dotenv_path=os.environ.get("AGENT_MAKER_DOTENV", ".env"),
        )
        return cfg

    def redactor(self) -> Callable[[Dict[str, Any]], Dict[str, Any]]:
        if self._redactor is not None:
            return self._redactor

        strict = self.privacy == "strict"
        placeholder = self.redact_placeholder
        max_len = self.max_value_length

        def redact_event(event: Dict[str, Any]) -> Dict[str, Any]:
            # Work on a shallow copy
            ev = dict(event)
            etype = str(ev.get("type", ""))
            data = ev.get("data")
            if isinstance(data, dict):
                # Special-case tool events and known large fields
                name = str(data.get("name", ""))
                if etype == "tool":
                    # Redact tool args and results deeply
                    redacted = _redact_obj(data, placeholder=placeholder, max_len=max_len, strict=strict)
                    # For filesystem tools, hide file contents in strict mode
                    if name in {"fs.read", "fs.write", "fs.patch", "test.run", "shell"}:
                        res = redacted.get("result")
                        if isinstance(res, dict):
                            for k in ("content", "stdout", "stderr", "patch"):
                                if k in res:
                                    res[k] = _redact_value(res.get(k), placeholder, max_len, strict=True if name in {"fs.read", "fs.write", "fs.patch"} and strict else strict)
                    ev["data"] = redacted
                elif etype in {"model_output", "start", "plan"}:
                    # Redact generic payloads
                    ev["data"] = _redact_obj(data, placeholder=placeholder, max_len=max_len, strict=strict)
                else:
                    ev["data"] = _redact_obj(data, placeholder=placeholder, max_len=max_len, strict=strict)
            # In strict mode, omit raw model output entirely
            if strict and etype == "model_output":
                ev["data"] = {"omitted": True}
            return ev

        self._redactor = redact_event
        return redact_event

