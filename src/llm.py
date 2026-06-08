from __future__ import annotations
import json
import re
from typing import Any


class LLMClient:
    """Cliente LLM unificado: Anthropic, OpenAI, Groq e Ollama."""

    def __init__(self, config: dict):
        self.provider = config.get("provider", "anthropic")
        self.config = config

    def chat(
        self,
        messages: list[dict],
        system: str | None = None,
        max_tokens: int = 8192,
    ) -> str:
        if self.provider == "anthropic":
            return self._anthropic_chat(messages, system, max_tokens)
        if self.provider in ("openai", "groq", "ollama"):
            return self._openai_compat_chat(messages, system, max_tokens)
        raise ValueError(f"Provider desconhecido: {self.provider}. Use: anthropic | openai | groq | ollama")

    def chat_json(
        self,
        messages: list[dict],
        system: str | None = None,
        max_tokens: int = 8192,
    ) -> Any:
        """Chama o LLM e faz parse do JSON retornado."""
        response = self.chat(messages, system, max_tokens)
        return _extract_json(response)

    # ── Anthropic ────────────────────────────────────────────

    def _anthropic_chat(self, messages: list[dict], system: str | None, max_tokens: int) -> str:
        import anthropic

        cfg = self.config.get("anthropic", {})
        client = anthropic.Anthropic(api_key=cfg.get("api_key", ""))
        kwargs: dict[str, Any] = {
            "model": cfg.get("model", "claude-opus-4-8"),
            "max_tokens": max_tokens,
            "messages": messages,
        }
        if system:
            kwargs["system"] = system

        resp = client.messages.create(**kwargs)
        return resp.content[0].text

    # ── OpenAI / Groq / Ollama (API compatível) ──────────────

    def _openai_compat_chat(self, messages: list[dict], system: str | None, max_tokens: int) -> str:
        from openai import OpenAI

        cfg = self.config.get(self.provider, {})

        if self.provider == "groq":
            client = OpenAI(
                api_key=cfg.get("api_key", ""),
                base_url="https://api.groq.com/openai/v1",
            )
        elif self.provider == "ollama":
            base_url = cfg.get("base_url", "http://localhost:11434")
            client = OpenAI(api_key="ollama", base_url=f"{base_url}/v1")
        else:
            client = OpenAI(api_key=cfg.get("api_key", ""))

        model = cfg.get("model", "gpt-4o")

        msgs: list[dict] = []
        if system:
            msgs.append({"role": "system", "content": system})
        msgs.extend(messages)

        resp = client.chat.completions.create(
            model=model,
            messages=msgs,
            max_tokens=max_tokens,
        )
        return resp.choices[0].message.content


def _extract_json(text: str) -> Any:
    """Extrai JSON de uma resposta LLM, lidando com blocos markdown."""
    match = re.search(r"```(?:json)?\s*(\{[\s\S]*?\}|\[[\s\S]*?\])\s*```", text)
    if match:
        return json.loads(match.group(1))
    match = re.search(r"(\{[\s\S]*\}|\[[\s\S]*\])", text)
    if match:
        return json.loads(match.group(1))
    raise ValueError(f"JSON não encontrado na resposta LLM:\n{text[:500]}")
