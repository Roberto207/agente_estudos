"""
Loop agentico principal.

O LLM recebe o sistema de prompt do criar-estudo + tools disponíveis e decide
sozinho quais ferramentas chamar, em que ordem e com que argumentos.
Sem sequência fixa — comportamento genuinamente agentico.
"""
from __future__ import annotations
import os
from pathlib import Path
from typing import Callable

from rich.console import Console
from rich.panel import Panel
from rich.live import Live
from rich.spinner import Spinner
from rich.text import Text

from .llm import LLMClient, AgentResponse
from .tools.registry import get_tools_for_provider, execute_tools_batch
from .postprocessing import run_postprocessing

MAX_ITERATIONS = 60

console = Console()

# search_vault é exclusiva do --chat (precisa de uma pasta já indexada na sessão);
# não faz sentido no modo de criação.
_CREATION_TOOLS = {
    "web_search", "fetch_url", "transcribe_video", "write_file", "read_file",
    "create_directory", "list_directory", "search_sources", "fetch_github_content",
    "recommend_next_steps",
}


# ── System Prompt ─────────────────────────────────────────────────────────────

# HTML, canvas, flashcards, quiz, próximos-passos e mapa mental são TODOS gerados
# deterministicamente em pós-processamento (src/postprocessing.py), não pelo LLM —
# pedir pro modelo redigir documentos grandes (HTML/JSON) via tool call é frágil:
# modelos mais fracos (ex: gpt-4o-mini) já produziram HTML com `\n` literal em vez
# de quebra de linha real, ou simplesmente pularam o canvas. O LLM só cuida de
# pesquisar, processar fontes e escrever markdown — o resto é Python confiável.
_SYSTEM = """\
Você é um agente especialista em criar estruturas de estudo de alta qualidade no vault Obsidian.
Seu objetivo é produzir uma pasta de estudos completa e navegável a partir do tema e fontes fornecidos.

## Produto Final Esperado

Seu trabalho é produzir:
- Subpastas temáticas com arquivos .md ricos (fundamentos/, avancado/, aplicacoes/, etc)
- `transcripts/` com os resumos de cada fonte processada
- `guia_de_estudos.md` com ordem de leitura recomendada

NOTA: Você NÃO precisa gerar HTML, canvas (.canvas), flashcards, quiz ou mapa mental — o
sistema gera tudo isso automaticamente e de forma confiável a partir dos seus arquivos .md,
depois que você terminar. Não tente criar esses arquivos.

## Padrão de Qualidade dos Arquivos .md

Cada arquivo .md DEVE seguir esta estrutura com os três níveis obrigatórios:

```markdown
# Título do Conceito

> Blockquote de uma linha explicando o escopo.

---

## TL;DR
[2 parágrafos curtos com o ESSENCIAL — para leitura rápida de 2 minutos]

---

## Resumo (5 min)
[Principais pontos com exemplos diretos — para revisão em 5 minutos]

---

## Conteúdo Completo

### Seção Principal
Conteúdo profundo e didático com tabelas, blocos de código e exemplos.

---

- Voltar: [[arquivo_anterior]]
- Próximo: [[arquivo_seguinte]]
- Ver também: [[arquivo_relacionado]]
```

Os três níveis (TL;DR, Resumo, Conteúdo Completo) permitem ao estudante escolher a profundidade.
O HTML gerado pelo sistema apresentará tabs "⚡ Rápido / 📖 Médio / 📚 Completo" automaticamente.

## Processo Recomendado

1. Crie a estrutura de pastas (`transcripts/`, subpastas temáticas)
2. Processe cada fonte fornecida (`transcribe_video` para vídeos, `fetch_url` para artigos/papers, `web_search` para nomes de livros/cursos)
3. Planeje a estrutura de arquivos com base no conteúdo extraído + tema + foco
4. Para cada tópico, use `web_search` para pesquisa complementar
5. Escreva os arquivos .md com `write_file` — conteúdo rico, profundo, com os três níveis (TL;DR / Resumo / Conteúdo Completo)
6. Crie o guia_de_estudos.md

Processe fontes do mesmo tipo em paralelo quando possível.
Adapte a profundidade e linguagem à didática solicitada.
Escreva sempre em português brasileiro.
"""


# ── Ponto de entrada ──────────────────────────────────────────────────────────

def run(
    config: dict,
    tema: str,
    foco: str,
    didatica: str,
    pasta: str,
    fontes: list[str],
    on_event: Callable[[str, dict], None] | None = None,
    outputs: dict | None = None,
) -> None:
    """`on_event(event_type, payload)` e `outputs` (toggles de canvas/html/
    flashcards/quiz/mapa_mental) são opcionais e aditivos — chamadas existentes
    sem esses parâmetros mantêm o comportamento de hoje inalterado.
    """
    emit = on_event or (lambda *a, **k: None)
    llm = LLMClient(config)
    provider = config.get("provider", "anthropic")
    system = _SYSTEM

    console.print(Panel(
        f"[bold purple]Agente Estudos[/bold purple] [dim](modo agentico)[/dim]\n"
        f"[blue]Tema:[/blue] {tema}\n"
        f"[blue]Foco:[/blue] {foco or '—'}\n"
        f"[blue]Pasta:[/blue] {pasta}\n"
        f"[blue]Provider:[/blue] {provider}\n"
        f"[blue]Fontes:[/blue] {len(fontes)} fonte(s)",
        title="Iniciando",
        border_style="purple",
    ))

    tools = get_tools_for_provider(provider, names=_CREATION_TOOLS)
    user_message = _build_task(tema, foco, didatica, pasta, fontes)
    messages: list[dict] = [{"role": "user", "content": user_message}]

    iteration = 0
    total_tool_calls = 0

    try:
        while iteration < MAX_ITERATIONS:
            iteration += 1
            emit("iteration_start", {"iteration": iteration})

            with Live(
                Spinner("dots", text=Text(f"[Iteração {iteration}] LLM pensando...", style="yellow")),
                console=console,
                refresh_per_second=10,
            ):
                resp: AgentResponse = llm.chat_with_tools(
                    messages=messages,
                    tools=tools,
                    system=system,
                )

            if resp.stop_reason == "end_turn" or not resp.tool_calls:
                if resp.content:
                    console.print(Panel(
                        resp.content[:2000] + ("..." if len(resp.content) > 2000 else ""),
                        title="[green]Agente Finalizado[/green]",
                        border_style="green",
                    ))
                emit("agent_finished", {"content": resp.content})
                break

            # Exibe e executa as tool calls
            _print_tool_calls(resp.tool_calls, iteration)
            emit("tool_calls", {"iteration": iteration, "calls": resp.tool_calls})
            results = execute_tools_batch(resp.tool_calls, config)
            total_tool_calls += len(resp.tool_calls)

            # Atualiza messages de acordo com o provider
            if provider == "anthropic":
                messages.append({"role": "assistant", "content": resp.raw_content})
                messages.append({
                    "role": "user",
                    "content": [
                        {
                            "type": "tool_result",
                            "tool_use_id": r["id"],
                            "content": r["result"],
                        }
                        for r in results
                    ],
                })
            else:
                # OpenAI / Groq / Ollama
                messages.append(resp.raw_content)
                for r in results:
                    messages.append({
                        "role": "tool",
                        "tool_call_id": r["id"],
                        "content": r["result"],
                    })

        else:
            console.print(f"[yellow]Aviso: limite de {MAX_ITERATIONS} iterações atingido.[/yellow]")

    except ToolsNotSupportedError:
        console.print(
            "[red]Este modelo/provider não suporta tool_use.[/red]\n"
            "Use [bold]--mode pipeline[/bold] para o modo legado (sem tool_use).\n"
            "Ou troque para um provider com suporte: anthropic, openai, groq (llama-3.x)."
        )
        return

    console.print(
        f"\n[dim]Total de chamadas de ferramentas: {total_tool_calls} em {iteration} iterações[/dim]"
    )

    run_postprocessing(llm, pasta, tema=tema, foco=foco, on_event=on_event, outputs=outputs)

    index_path = os.path.join(pasta, "html", "index.html")
    if Path(index_path).exists():
        console.print(f"\n[bold]Abrir hub:[/bold] [cyan]file://{os.path.abspath(index_path)}[/cyan]")


# ── Helpers ───────────────────────────────────────────────────────────────────

def _build_task(tema: str, foco: str, didatica: str, pasta: str, fontes: list[str]) -> str:
    lines = [
        f"Tema: {tema}",
        f"Foco: {foco or tema}",
        f"Didática: {didatica or 'prático com exemplos do mundo real'}",
        f"Pasta destino: {pasta}",
    ]
    if fontes:
        lines.append("Fontes:")
        for f in fontes:
            lines.append(f"- {f}")
    else:
        lines.append("Fontes: nenhuma fornecida — use apenas pesquisa web sobre o tema e foco.")

    lines.append(
        "\nCrie a estrutura completa de estudo conforme as instruções do sistema. "
        "Comece criando as pastas, depois processe as fontes, depois escreva o conteúdo."
    )
    return "\n".join(lines)


def _print_tool_calls(tool_calls: list[dict], iteration: int) -> None:
    for tc in tool_calls:
        name = tc["name"]
        inputs = tc["inputs"]
        # Exibe um resumo compacto dos inputs
        summary = ", ".join(
            f"{k}={str(v)[:60]!r}" for k, v in inputs.items()
        )
        console.print(f"  [cyan]→ {name}[/cyan]({summary})")


class ToolsNotSupportedError(Exception):
    pass
