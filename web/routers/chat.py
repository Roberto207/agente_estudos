"""Chat RAG (Q&A / Socrático) — síncrono, sem job (o loop de tool calls é de
segundos, não minutos; ver limitação de streaming documentada no plano)."""
from __future__ import annotations

from fastapi import APIRouter, HTTPException

from .. import deps
from ..schemas import ChatRequest

router = APIRouter()

_MAX_HISTORY = 20


@router.post("/api/spaces/{space_id}/chat")
def api_chat(space_id: str, body: ChatRequest):
    try:
        space_path = deps.resolve_space_path(space_id)
    except FileNotFoundError:
        raise HTTPException(404, "Espaço não encontrado")

    if body.mode not in ("qa", "socratico"):
        raise HTTPException(400, "mode deve ser 'qa' ou 'socratico'")

    from src.agent import ToolsNotSupportedError
    from src.chat import SYSTEM_QA, SYSTEM_SOCRATICO, answer_with_tools
    from src.llm import LLMClient
    from src.tools.registry import get_tools_for_provider

    config = deps.load_config()
    provider = config.get("provider", "anthropic")
    chat_config = {**config, "_rag_pasta": str(space_path)}
    tools = get_tools_for_provider(provider, names={"search_vault"})
    system = SYSTEM_QA if body.mode == "qa" else SYSTEM_SOCRATICO

    history = list(body.history[-_MAX_HISTORY:])
    history.append({"role": "user", "content": body.message})

    llm = LLMClient(config)
    try:
        reply = answer_with_tools(llm, history, tools, system, provider, chat_config)
    except ToolsNotSupportedError:
        raise HTTPException(
            400,
            "Este modelo/provider não suporta tool_use, necessário para a busca "
            "semântica do chat. Troque o provider em config.yaml.",
        )

    return {"reply": reply}
