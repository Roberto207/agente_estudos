"""
Loop agentico principal.

O LLM recebe o sistema de prompt do criar-estudo + tools disponíveis e decide
sozinho quais ferramentas chamar, em que ordem e com que argumentos.
Sem sequência fixa — comportamento genuinamente agentico.
"""
from __future__ import annotations
import os
from pathlib import Path

from rich.console import Console
from rich.panel import Panel
from rich.live import Live
from rich.spinner import Spinner
from rich.text import Text

from .llm import LLMClient, AgentResponse
from .tools.registry import get_tools_for_provider, execute_tools_batch

MAX_ITERATIONS = 60

console = Console()


# ── System Prompt ─────────────────────────────────────────────────────────────

_SYSTEM = """\
Você é um agente especialista em criar estruturas de estudo de alta qualidade no vault Obsidian.
Seu objetivo é produzir uma pasta de estudos completa e navegável a partir do tema e fontes fornecidos.

## Produto Final Esperado

Ao finalizar, a pasta destino deve conter:
- Subpastas temáticas com arquivos .md ricos (fundamentos/, avancado/, aplicacoes/, etc)
- `transcripts/` com os resumos de cada fonte processada
- `guia_de_estudos.md` com ordem de leitura recomendada
- Dois arquivos `.canvas` (fundamentos e avançado) para Obsidian
- `html/index.html` e HTMLs individuais (Catppuccin Mocha, sem dependências externas)

NOTA: Após sua execução, o sistema gerará automaticamente `html/flashcards.html` e `html/quiz.html`.
Portanto, no `index.html` e na sidebar de cada HTML, inclua os links:
  `<a href="flashcards.html">🃏 Flashcards</a>` e `<a href="quiz.html">📝 Quiz</a>`

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

## Padrão do Canvas Obsidian

```json
{
  "nodes": [
    {"id": "txt_intro", "type": "text", "text": "# Tema — Canvas\\n...", "x": -1200, "y": -100, "width": 340, "height": 140},
    {"id": "file_1", "type": "file", "file": "<caminho_relativo_ao_vault>", "x": -780, "y": -380, "width": 520, "height": 400}
  ],
  "edges": [
    {"id": "e1", "fromNode": "file_1", "fromSide": "bottom", "toNode": "file_2", "toSide": "top"}
  ]
}
```

Os `file` nodes devem usar caminhos **relativos à raiz do vault**.

## Padrão HTML (Catppuccin Mocha)

Paleta obrigatória em todos os HTMLs:
```css
:root {
  --base:#1e1e2e; --mantle:#181825; --crust:#11111b; --surface0:#313244;
  --surface1:#45475a; --overlay0:#6c7086; --text:#cdd6f4; --subtext:#a6adc8;
  --purple:#cba6f7; --blue:#89b4fa; --green:#a6e3a1; --yellow:#f9e2af;
  --red:#f38ba8; --teal:#94e2d5;
}
```

- `index.html`: sidebar com todos os arquivos por subpasta + links para Flashcards e Quiz, cards de tópicos
- HTMLs individuais: conversão fiel do .md com mesma sidebar e footer de navegação

## Processo Recomendado

1. Crie a estrutura de pastas (`transcripts/`, `html/`, subpastas temáticas)
2. Processe cada fonte fornecida (`transcribe_video` para vídeos, `fetch_url` para artigos/papers, `web_search` para nomes de livros/cursos)
3. Planeje a estrutura de arquivos com base no conteúdo extraído + tema + foco
4. Para cada tópico, use `web_search` para pesquisa complementar
5. Escreva os arquivos .md com `write_file` — conteúdo rico, profundo, com os três níveis (TL;DR / Resumo / Conteúdo Completo)
6. Crie os canvas files (.canvas são JSON)
7. Crie o guia_de_estudos.md
8. Gere todos os HTMLs (incluindo links para flashcards.html e quiz.html)

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
) -> None:
    llm = LLMClient(config)
    provider = config.get("provider", "anthropic")

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

    tools = get_tools_for_provider(provider)
    user_message = _build_task(tema, foco, didatica, pasta, fontes)
    messages: list[dict] = [{"role": "user", "content": user_message}]

    iteration = 0
    total_tool_calls = 0

    try:
        while iteration < MAX_ITERATIONS:
            iteration += 1

            with Live(
                Spinner("dots", text=Text(f"[Iteração {iteration}] LLM pensando...", style="yellow")),
                console=console,
                refresh_per_second=10,
            ):
                resp: AgentResponse = llm.chat_with_tools(
                    messages=messages,
                    tools=tools,
                    system=_SYSTEM,
                )

            if resp.stop_reason == "end_turn" or not resp.tool_calls:
                if resp.content:
                    console.print(Panel(
                        resp.content[:2000] + ("..." if len(resp.content) > 2000 else ""),
                        title="[green]Agente Finalizado[/green]",
                        border_style="green",
                    ))
                break

            # Exibe e executa as tool calls
            _print_tool_calls(resp.tool_calls, iteration)
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

    _run_postprocessing(llm, pasta)

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


def _run_postprocessing(llm, pasta: str) -> None:
    """Gera flashcards e quiz após o loop do agente."""
    from .generators.flashcards import generate as gen_flashcards
    from .generators.quiz import generate as gen_quiz

    console.print("\n[bold purple]Pós-processamento[/bold purple]")

    try:
        with console.status("[yellow]Gerando flashcards (SM-2)...[/yellow]"):
            fc_path = gen_flashcards(llm, pasta)
        if fc_path:
            console.print(f"  [green]✓[/green] Flashcards: {fc_path}")
        else:
            console.print("  [dim]Flashcards: sem conteúdo suficiente[/dim]")
    except Exception as exc:
        console.print(f"  [dim]Flashcards: falhou ({exc})[/dim]")

    try:
        with console.status("[yellow]Gerando quiz...[/yellow]"):
            quiz_path = gen_quiz(llm, pasta)
        if quiz_path:
            console.print(f"  [green]✓[/green] Quiz: {quiz_path}")
        else:
            console.print("  [dim]Quiz: sem conteúdo suficiente[/dim]")
    except Exception as exc:
        console.print(f"  [dim]Quiz: falhou ({exc})[/dim]")


class ToolsNotSupportedError(Exception):
    pass
