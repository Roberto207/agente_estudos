from __future__ import annotations
import json
import re
from dataclasses import dataclass
from typing import Any


@dataclass
class AgentResponse:
    """Resposta normalizada do LLM para o loop agentico."""
    content: str               # texto da resposta (pode ser vazio se só tool_calls)
    stop_reason: str           # "end_turn" | "tool_use" | "tool_calls"
    tool_calls: list[dict]     # [{"id": str, "name": str, "inputs": dict}]
    raw_content: Any           # objeto bruto para reenviar ao provider (Anthropic list | OpenAI dict)


class LLMClient:
    """Cliente LLM unificado: Anthropic, OpenAI, Groq e Ollama."""

    def __init__(self, config: dict):
        self.provider = config.get("provider", "anthropic")
        self.config = config

    # ── Chat simples (sem tools) ──────────────────────────────────────────────

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
        response = self.chat(messages, system, max_tokens)
        return _extract_json(response)

    # ── Chat com tools (modo agentico) ────────────────────────────────────────

    def chat_with_tools(
        self,
        messages: list[dict],
        tools: list[dict],
        system: str | None = None,
        max_tokens: int = 8192,
    ) -> AgentResponse:
        if self.provider == "anthropic":
            return self._anthropic_chat_tools(messages, tools, system, max_tokens)
        if self.provider in ("openai", "groq", "ollama"):
            return self._openai_compat_chat_tools(messages, tools, system, max_tokens)
        raise ValueError(f"Provider desconhecido: {self.provider}")

    # ── Anthropic ────────────────────────────────────────────────────────────

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

    def _anthropic_chat_tools(
        self,
        messages: list[dict],
        tools: list[dict],
        system: str | None,
        max_tokens: int,
    ) -> AgentResponse:
        import anthropic

        cfg = self.config.get("anthropic", {})
        client = anthropic.Anthropic(api_key=cfg.get("api_key", ""))
        kwargs: dict[str, Any] = {
            "model": cfg.get("model", "claude-opus-4-8"),
            "max_tokens": max_tokens,
            "messages": messages,
            "tools": tools,
        }
        if system:
            kwargs["system"] = system

        resp = client.messages.create(**kwargs)

        text_parts = []
        tool_calls = []
        for block in resp.content:
            if block.type == "text":
                text_parts.append(block.text)
            elif block.type == "tool_use":
                tool_calls.append({
                    "id": block.id,
                    "name": block.name,
                    "inputs": block.input,
                })

        return AgentResponse(
            content="\n".join(text_parts),
            stop_reason=resp.stop_reason,
            tool_calls=tool_calls,
            raw_content=resp.content,  # lista de blocos — reenviar como está
        )

    # ── OpenAI / Groq / Ollama (API compatível) ───────────────────────────────

    def _openai_compat_chat(self, messages: list[dict], system: str | None, max_tokens: int) -> str:
        from openai import OpenAI

        cfg = self.config.get(self.provider, {})
        client = self._make_openai_client(cfg)
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

    def _openai_compat_chat_tools(
        self,
        messages: list[dict],
        tools: list[dict],
        system: str | None,
        max_tokens: int,
    ) -> AgentResponse:
        from openai import OpenAI

        cfg = self.config.get(self.provider, {})
        client = self._make_openai_client(cfg)
        model = cfg.get("model", "gpt-4o")

        msgs: list[dict] = []
        if system:
            msgs.append({"role": "system", "content": system})
        msgs.extend(messages)

        try:
            resp = client.chat.completions.create(
                model=model,
                messages=msgs,
                tools=tools,
                tool_choice="auto",
                max_tokens=max_tokens,
            )
        except Exception as exc:
            err = str(exc).lower()
            if "tool" in err or "function" in err or "not supported" in err:
                from .agent import ToolsNotSupportedError
                raise ToolsNotSupportedError(str(exc)) from exc
            raise

        choice = resp.choices[0]
        message = choice.message
        finish_reason = choice.finish_reason

        tool_calls = []
        if message.tool_calls:
            for tc in message.tool_calls:
                try:
                    inputs = json.loads(tc.function.arguments)
                except (json.JSONDecodeError, TypeError):
                    inputs = {}
                tool_calls.append({
                    "id": tc.id,
                    "name": tc.function.name,
                    "inputs": inputs,
                })

        # Constrói raw_content como dict para reenviar como mensagem OpenAI
        raw_msg = {
            "role": "assistant",
            "content": message.content or "",
        }
        if message.tool_calls:
            raw_msg["tool_calls"] = [
                {
                    "id": tc.id,
                    "type": "function",
                    "function": {
                        "name": tc.function.name,
                        "arguments": tc.function.arguments,
                    },
                }
                for tc in message.tool_calls
            ]

        return AgentResponse(
            content=message.content or "",
            stop_reason="tool_calls" if finish_reason == "tool_calls" else "end_turn",
            tool_calls=tool_calls,
            raw_content=raw_msg,
        )

    def _make_openai_client(self, cfg: dict):
        from openai import OpenAI

        if self.provider == "groq":
            return OpenAI(
                api_key=cfg.get("api_key", ""),
                base_url="https://api.groq.com/openai/v1",
            )
        if self.provider == "ollama":
            base_url = cfg.get("base_url", "http://localhost:11434")
            return OpenAI(api_key="ollama", base_url=f"{base_url}/v1")
        return OpenAI(api_key=cfg.get("api_key", ""))


def _extract_json(text: str) -> Any:
    """Extrai JSON de uma resposta LLM, lidando com blocos markdown."""
    match = re.search(r"```(?:json)?\s*(\{[\s\S]*?\}|\[[\s\S]*?\])\s*```", text)
    if match:
        return json.loads(match.group(1))
    match = re.search(r"(\{[\s\S]*\}|\[[\s\S]*\])", text)
    if match:
        return json.loads(match.group(1))
    raise ValueError(f"JSON não encontrado na resposta LLM:\n{text[:500]}")
