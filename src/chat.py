"""Modo chat interativo: Q&A sobre conteúdo (estilo NotebookLM) ou Tutor Socrático."""
from __future__ import annotations
from pathlib import Path

from rich.console import Console
from rich.markdown import Markdown
from rich.panel import Panel
from rich.prompt import Prompt

from .llm import LLMClient

console = Console()

_MAX_CONTEXT_CHARS = 60_000
_MAX_HISTORY = 20

_SYSTEM_QA = """\
Você é um tutor especialista e assistente de estudos pessoal.
Responda perguntas com base EXCLUSIVAMENTE nos materiais de estudo fornecidos abaixo.
Seja claro, didático e preciso. Adapte a profundidade ao nível da pergunta.
Ao final de cada resposta, cite a fonte entre colchetes: [Fonte: nome_do_arquivo.md]
Se a resposta não estiver no material, diga isso claramente em vez de inventar.
Responda sempre em português brasileiro.
"""

_SYSTEM_SOCRATICO = """\
Você é um tutor socrático experiente e paciente.
Seu objetivo é desenvolver o pensamento crítico do estudante — nunca dê respostas diretas.
Em vez disso:
- Pergunte o que o estudante já sabe sobre o tema: "O que você entende por X?"
- Use perguntas que exponham lacunas: "Por que você acha que Y acontece?"
- Guie por analogias: "Como isso se compara a Z que você já conhece?"
- Confirme progressos: "Exatamente! Agora, dado isso, o que você conclui sobre...?"
- Baseie as perguntas no material de estudo disponível (não invente contexto)
- Adapte a dificuldade ao que o estudante demonstra saber
Responda sempre em português brasileiro.
"""


def run(config: dict, pasta: str, mode: str = "qa") -> None:
    llm = LLMClient(config)
    pasta_path = Path(pasta).expanduser().resolve()

    if not pasta_path.exists():
        console.print(f"[red]Pasta não encontrada:[/red] {pasta}")
        return

    ctx = _load_context(pasta_path)
    if not ctx:
        console.print(f"[red]Nenhum arquivo .md encontrado em:[/red] {pasta}")
        return

    history: list[dict] = []
    mode_label, mode_color = _mode_info(mode)
    system = _build_system(mode, ctx)

    console.print(Panel(
        f"[bold {mode_color}]Modo:[/bold {mode_color}] {mode_label}\n"
        f"[dim]Pasta:[/dim] {pasta_path.name}\n"
        f"[dim]Arquivos carregados:[/dim] {ctx['file_count']} arquivos\n\n"
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
            system = _build_system(mode, ctx)
            history.clear()
            console.print(f"[dim]Modo alterado para [bold]{mode_label}[/bold] (histórico limpo).[/dim]")
            continue

        history.append({"role": "user", "content": user_input})
        if len(history) > _MAX_HISTORY:
            history = history[-_MAX_HISTORY:]

        try:
            response = llm.chat(
                messages=history.copy(),
                system=system,
                max_tokens=2048,
            )
        except Exception as exc:
            console.print(f"[red]Erro ao chamar LLM:[/red] {exc}")
            history.pop()
            continue

        history.append({"role": "assistant", "content": response})
        console.print()
        console.print(Markdown(response))
        console.print()


# ── Helpers ───────────────────────────────────────────────────────────────────

def _mode_info(mode: str) -> tuple[str, str]:
    if mode == "socratico":
        return "Socrático", "yellow"
    return "Q&A", "blue"


def _load_context(pasta_path: Path) -> dict | None:
    skip = {"guia_de_estudos.md"}
    md_files = [
        p for p in sorted(pasta_path.rglob("*.md"))
        if p.name not in skip and "transcripts" not in p.parts
    ]
    if not md_files:
        return None

    parts: list[str] = []
    total = 0
    for md in md_files:
        content = md.read_text(encoding="utf-8")
        relative = md.relative_to(pasta_path)
        header = f"\n\n=== Arquivo: {relative} ===\n"
        chunk = header + content
        if total + len(chunk) > _MAX_CONTEXT_CHARS:
            remaining = _MAX_CONTEXT_CHARS - total - len(header) - 200
            if remaining > 500:
                parts.append(header + content[:remaining] + "\n[...truncado...]")
            break
        parts.append(chunk)
        total += len(chunk)

    return {"text": "".join(parts), "file_count": len(md_files)}


def _build_system(mode: str, ctx: dict) -> str:
    base = _SYSTEM_QA if mode == "qa" else _SYSTEM_SOCRATICO
    return base + f"\n\n## Material de Estudo Disponível\n\n{ctx['text']}"
