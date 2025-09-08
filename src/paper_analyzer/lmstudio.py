import os
from typing import Any, Dict, List, Optional

import requests

from .cache import JsonlCache


class LMStudioClient:
    def __init__(
        self,
        model: str,
        base_url: Optional[str] = None,
        api_key: Optional[str] = None,
        cache: Optional[JsonlCache] = None,
        timeout: int = 120,
        pre_messages: Optional[List[Dict[str, str]]] = None,
    ) -> None:
        self.model = model
        self.base_url = base_url or os.getenv("LMSTUDIO_BASE_URL", "http://localhost:1234/v1")
        self.api_key = api_key or os.getenv("LMSTUDIO_API_KEY", "lm-studio")
        self.cache = cache
        self.timeout = timeout
        # Optional messages to prepend to every request (e.g., instruction.md)
        self.pre_messages: List[Dict[str, str]] = pre_messages or []

    def _headers(self) -> Dict[str, str]:
        return {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.api_key}",
        }

    def chat_complete(
        self,
        messages: List[Dict[str, str]],
        temperature: float = 0.2,
        max_tokens: Optional[int] = None,
    ) -> str:
        """Try chat.completions; on 400 fallback to completions."""
        # Merge any pre_messages so that custom system instructions come last among system messages
        if self.pre_messages:
            sys_msgs = [m for m in messages if m.get("role") == "system"]
            other_msgs = [m for m in messages if m.get("role") != "system"]
            pre_sys = [m for m in self.pre_messages if m.get("role") == "system"]
            pre_other = [m for m in self.pre_messages if m.get("role") != "system"]
            merged_messages = sys_msgs + pre_sys + pre_other + other_msgs
        else:
            merged_messages = messages

        chat_url = f"{self.base_url.rstrip('/')}/chat/completions"
        chat_payload: Dict[str, Any] = {
            "model": self.model,
            "messages": merged_messages,
            "temperature": temperature,
        }
        if max_tokens is not None:
            chat_payload["max_tokens"] = max_tokens

        if self.cache:
            cached = self.cache.get({"endpoint": "chat", **chat_payload})
            if cached is not None:
                return cached

        resp = requests.post(chat_url, json=chat_payload, headers=self._headers(), timeout=self.timeout)
        if resp.ok:
            data = resp.json()
            content = data["choices"][0]["message"]["content"].strip()
            if self.cache:
                self.cache.set({"endpoint": "chat", **chat_payload}, content)
            return content

        # Fallback to /completions (prompt-based) on chat 400/404
        def _messages_to_prompt(msgs: List[Dict[str, str]]) -> str:
            lines: List[str] = []  # type: ignore[name-defined]
            for m in msgs:
                role = m.get("role", "user")
                content = m.get("content", "")
                if role == "system":
                    lines.append(f"[System]\n{content}\n")
                elif role == "user":
                    lines.append(f"[User]\n{content}\n")
                else:
                    lines.append(f"[Assistant]\n{content}\n")
            lines.append("[Assistant]\n")
            return "\n".join(lines)

        comp_url = f"{self.base_url.rstrip('/')}/completions"
        prompt = _messages_to_prompt(merged_messages)
        comp_payload: Dict[str, Any] = {
            "model": self.model,
            "prompt": prompt,
            "temperature": temperature,
        }
        if max_tokens is not None:
            comp_payload["max_tokens"] = max_tokens

        if self.cache:
            cached = self.cache.get({"endpoint": "completions", **comp_payload})
            if cached is not None:
                return cached

        comp_resp = requests.post(comp_url, json=comp_payload, headers=self._headers(), timeout=self.timeout)
        comp_resp.raise_for_status()
        comp_data = comp_resp.json()
        # Some servers return choices[].text for completions
        if "choices" in comp_data and comp_data["choices"]:
            choice = comp_data["choices"][0]
            content = (choice.get("text") or choice.get("message", {}).get("content") or "").strip()
        else:
            content = ""
        if self.cache:
            self.cache.set({"endpoint": "completions", **comp_payload}, content)
        return content
