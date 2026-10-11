"""Pós-processamento compartilhado: canvas, flashcards, quiz e próximos passos.

Extraído de agent.py para ser reutilizável também por pipeline.py e pela camada
web (web/jobs.py), sem duplicar a lógica de geração. O canvas é gerado aqui de
forma determinística em vez de pedir pro LLM para redigi-lo via tool call —
redigir documentos grandes (JSON) à mão é frágil mesmo para modelos competentes.

Os HTMLs gerais (hub/índice, páginas de conceito e mapa mental) foram removidos
por desuso; os únicos HTMLs gerados são flashcards.html e quiz.html.
"""
from __future__ import annotations
from pathlib import Path
from typing import Callable

from rich.console import Console

from .generators.canvas import write_canvas_files
from .generators.flashcards import generate as gen_flashcards
from .generators.next_steps import generate as gen_next_steps
from .generators.quiz import generate as gen_quiz

console = Console()

_DEFAULT_OUTPUTS = {
    "flashcards": True, "quiz": True, "next_steps": True, "canvas": True,
}

OUTPUT_KEYS = tuple(_DEFAULT_OUTPUTS.keys())


def build_structure_from_folder(pasta: str) -> dict:
    """Reconstrói um dict de structure ({"subfolders": [...]}) a partir do que já
    existe em disco — usado quando não há um `structure` planejado disponível
    (ex: modo agent, onde o LLM organiza os arquivos livremente via tool calls).
    """
    pasta_path = Path(pasta)
    skip_dirs = {"transcripts", "html"}
    subfolders = []
    for sub in sorted(p for p in pasta_path.iterdir() if p.is_dir()):
        if sub.name.startswith(".") or sub.name in skip_dirs:
            continue
        files = []
        for md in sorted(sub.glob("*.md")):
            files.append({"name": md.stem, "title": _extract_title(md) or md.stem.replace("_", " ").title()})
        if files:
            subfolders.append({"name": sub.name, "label": sub.name.replace("_", " ").title(), "files": files})
    return {"subfolders": subfolders}


def _extract_title(md_path: Path) -> str:
    try:
        for line in md_path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if line.startswith("# "):
                return line[2:].strip()
    except Exception:
        pass
    return ""


def run_postprocessing(
    llm,
    pasta: str,
    tema: str = "",
    foco: str = "",
    on_event: Callable[[str, dict], None] | None = None,
    outputs: dict | None = None,
) -> dict:
    """Gera flashcards, quiz, próximos passos e canvas — nenhum via LLM freehand.

    `outputs` aceita as chaves flashcards/quiz/next_steps/canvas (bool).
    Default: todos ligados (ver pipeline.py, que gera o canvas por conta própria
    antes de chamar esta função — passa override explícito pra não duplicar).
    """
    outputs = {**_DEFAULT_OUTPUTS, **(outputs or {})}
    emit = on_event or (lambda *a, **k: None)
    result: dict = {}
    structure_cache: dict | None = None

    def get_structure() -> dict:
        nonlocal structure_cache
        if structure_cache is None:
            structure_cache = build_structure_from_folder(pasta)
        return structure_cache

    console.print("\n[bold purple]Pós-processamento[/bold purple]")
    emit("postprocessing_start", {})

    if outputs.get("flashcards", True):
        try:
            with console.status("[yellow]Gerando flashcards (SM-2)...[/yellow]"):
                fc_path = gen_flashcards(llm, pasta)
            result["flashcards"] = fc_path
            if fc_path:
                console.print(f"  [green]✓[/green] Flashcards: {fc_path}")
            else:
                console.print("  [dim]Flashcards: sem conteúdo suficiente[/dim]")
            emit("postprocessing_step", {"name": "flashcards", "status": "ok", "path": fc_path})
        except Exception as exc:
            result["flashcards"] = None
            console.print(f"  [dim]Flashcards: falhou ({exc})[/dim]")
            emit("postprocessing_step", {"name": "flashcards", "status": "error", "error": str(exc)})

    if outputs.get("quiz", True):
        try:
            with console.status("[yellow]Gerando quiz...[/yellow]"):
                quiz_path = gen_quiz(llm, pasta)
            result["quiz"] = quiz_path
            if quiz_path:
                console.print(f"  [green]✓[/green] Quiz: {quiz_path}")
            else:
                console.print("  [dim]Quiz: sem conteúdo suficiente[/dim]")
            emit("postprocessing_step", {"name": "quiz", "status": "ok", "path": quiz_path})
        except Exception as exc:
            result["quiz"] = None
            console.print(f"  [dim]Quiz: falhou ({exc})[/dim]")
            emit("postprocessing_step", {"name": "quiz", "status": "error", "error": str(exc)})

    if outputs.get("next_steps", True):
        try:
            with console.status("[yellow]Gerando recomendações de próximos passos...[/yellow]"):
                ns_path = gen_next_steps(llm, pasta)
            result["next_steps"] = ns_path
            if ns_path:
                console.print(f"  [green]✓[/green] Próximos passos: {ns_path}")
            else:
                console.print("  [dim]Próximos passos: sem conteúdo suficiente[/dim]")
            emit("postprocessing_step", {"name": "next_steps", "status": "ok", "path": ns_path})
        except Exception as exc:
            result["next_steps"] = None
            console.print(f"  [dim]Próximos passos: falhou ({exc})[/dim]")
            emit("postprocessing_step", {"name": "next_steps", "status": "error", "error": str(exc)})

    if outputs.get("canvas", True):
        try:
            with console.status("[yellow]Gerando canvas Obsidian...[/yellow]"):
                canvas_paths = write_canvas_files(pasta, tema or Path(pasta).name, get_structure())
            result["canvas"] = canvas_paths
            console.print(f"  [green]✓[/green] Canvas: {len(canvas_paths)} arquivo(s)")
            emit("postprocessing_step", {"name": "canvas", "status": "ok", "paths": canvas_paths})
        except Exception as exc:
            result["canvas"] = None
            console.print(f"  [dim]Canvas: falhou ({exc})[/dim]")
            emit("postprocessing_step", {"name": "canvas", "status": "error", "error": str(exc)})

    emit("postprocessing_done", result)
    return result
