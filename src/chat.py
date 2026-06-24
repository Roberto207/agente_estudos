"""Modo chat interativo: Q&A sobre conteúdo (estilo NotebookLM) ou Tutor Socrático.

Busca semântica real (RAG) via tool search_vault — o LLM decide quando e quantas
vezes buscar antes de responder, em vez de receber todos os .md de uma vez.
Funciona igual numa pasta de um tema só ou apontando pra raiz do vault inteiro.
"""
from __future__ import annotations
from pathlib import Path

from rich.console import Console
from rich.markdown import Markdown
from rich.panel import Panel
from rich.prompt import Prompt

from .agent import ToolsNotSupportedError
from .indexer import build_or_update_index
from .llm import LLMClient
from .tools.registry import execute_tools_batch, get_tools_for_provider

console = Console()

_MAX_HISTORY = 20
_MAX_TOOL_TURNS = 6  # chamadas de search_vault por pergunta, antes de forçar resposta final

_SYSTEM_QA = """\
Você é um tutor especialista e assistente de estudos pessoal.
Use a ferramenta search_vault para buscar nos materiais de estudo ANTES de responder —
chame quantas vezes precisar, com queries diferentes, até reunir contexto suficiente.
Responda com base EXCLUSIVAMENTE no que a busca retornar. Seja claro, didático e preciso.
Adapte a profundidade ao nível da pergunta.
Ao final de cada resposta, cite a(s) fonte(s) entre colchetes: [Fonte: arquivo.md — Seção]
Se a busca não retornar nada relevante, diga isso claramente em vez de inventar.
Responda sempre em português brasileiro.
"""

_SYSTEM_SOCRATICO = """\
Você é um tutor socrático experiente e paciente.
Use a ferramenta search_vault para se basear nos materiais de estudo reais do usuário
antes de formular perguntas — não invente contexto que não esteja nos materiais.
Seu objetivo é desenvolver o pensamento crítico do estudante — nunca dê respostas diretas.
Em vez disso:
- Pergunte o que o estudante já sabe sobre o tema: "O que você entende por X?"
- Use perguntas que exponham lacunas: "Por que você acha que Y acontece?"
- Guie por analogias: "Como isso se compara a Z que você já conhece?"
- Confirme progressos: "Exatamente! Agora, dado isso, o que você conclui sobre...?"
- Adapte a dificuldade ao que o estudante demonstra saber
Responda sempre em português brasileiro.
"""


def run(config: dict, pasta: str, mode: str = "qa") -> None:
    pasta_path = Path(pasta).expanduser().resolve()

    if not pasta_path.exists():
        console.print(f"[red]Pasta não encontrada:[/red] {pasta}")
        return

    with console.status("[yellow]Indexando materiais de estudo...[/yellow]"):
        try:
            index = build_or_update_index(pasta_path, config)
        except Exception as exc:
            console.print(f"[red]Erro ao indexar pasta:[/red] {exc}")
            return

    if not index["chunks"]:
        console.print(f"[red]Nenhum conteúdo indexável (.md) encontrado em:[/red] {pasta}")
        return

    llm = LLMClient(config)
    provider = config.get("provider", "anthropic")
    chat_config = {**config, "_rag_pasta": str(pasta_path)}
    tools = get_tools_for_provider(provider, names={"search_vault"})

    history: list[dict] = []
    mode_label, mode_color = _mode_info(mode)
    system = _SYSTEM_QA if mode == "qa" else _SYSTEM_SOCRATICO

    console.print(Panel(
        f"[bold {mode_color}]Modo:[/bold {mode_color}] {mode_label}\n"
        f"[dim]Pasta:[/dim] {pasta_path.name}\n"
        f"[dim]Chunks indexados:[/dim] {len(index['chunks'])} "
        f"(embeddings: {index['embedding_provider']}/{index['embedding_model']})\n\n"
        "[dim]Comandos: [bold]/modo[/bold] (alterna QA ↔ Socrático) · "
        "[bold]/novo[/bold] (limpa histórico) · [bold]/sair[/bold][/dim]",
        title="[purple]Chat de Estudos[/purple]",
        border_style="purple",
    ))

    while True:
        try:
            user_input = Prompt.ask(f"[{mode_color}][{mode_label}] ▶[/{mode_color}]").strip()
        except (EOFError, KeyboardInterrupt):
            console.print("\n[dim]Encerrando chat...[/dim]")
            break

        if not user_input:
            continue

        cmd = user_input.lower()

        if cmd in ("/sair", "/quit", "/exit"):
            console.print("[dim]Até logo![/dim]")
            break

        if cmd == "/novo":
            history.clear()
            console.print("[dim]Histórico limpo.[/dim]")
            continue

        if cmd == "/modo":
            mode = "socratico" if mode == "qa" else "qa"
            mode_label, mode_color = _mode_info(mode)
            system = _SYSTEM_QA if mode == "qa" else _SYSTEM_SOCRATICO
            history.clear()
            console.print(f"[dim]Modo alterado para [bold]{mode_label}[/bold] (histórico limpo).[/dim]")
            continue

        history.append({"role": "user", "content": user_input})
        if len(history) > _MAX_HISTORY:
            history = history[-_MAX_HISTORY:]

        try:
            with console.status("[dim]Buscando e pensando...[/dim]"):
                response = _answer_with_tools(
                    llm, history.copy(), tools, system, provider, chat_config
                )
        except ToolsNotSupportedError:
            console.print(
                "[red]Este modelo/provider não suporta tool_use[/red], necessário para a "
                "busca semântica do chat.\nTroque o provider em config.yaml para "
                "anthropic, openai, groq, ou um modelo Ollama com suporte a tools."
            )
            history.pop()
            continue
        except Exception as exc:
            console.print(f"[red]Erro ao chamar LLM:[/red] {exc}")
            history.pop()
            continue

        history.append({"role": "assistant", "content": response})
        console.print()
        console.print(Markdown(response))
        console.print()


# ── Loop agentico de uma pergunta (search_vault 0-N vezes, depois resposta final) ──

def _answer_with_tools(
    llm: LLMClient,
    messages: list[dict],
    tools: list[dict],
    system: str,
    provider: str,
    config: dict,
) -> str:
    for _ in range(_MAX_TOOL_TURNS):
        resp = llm.chat_with_tools(messages=messages, tools=tools, system=system, max_tokens=2048)

        if resp.stop_reason == "end_turn" or not resp.tool_calls:
            return resp.content

        results = execute_tools_batch(resp.tool_calls, config)

        if provider == "anthropic":
            messages.append({"role": "assistant", "content": resp.raw_content})
            messages.append({
                "role": "user",
                "content": [
                    {"type": "tool_result", "tool_use_id": r["id"], "content": r["result"]}
                    for r in results
                ],
            })
        else:
            messages.append(resp.raw_content)
            for r in results:
                messages.append({"role": "tool", "tool_call_id": r["id"], "content": r["result"]})

    # Limite de chamadas de ferramenta atingido — força uma resposta final sem tools.
    return llm.chat(messages=messages, system=system, max_tokens=2048)


# ── Helpers ───────────────────────────────────────────────────────────────────

def _mode_info(mode: str) -> tuple[str, str]:
    if mode == "socratico":
        return "Socrático", "yellow"
    return "Q&A", "blue"
