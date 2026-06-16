"""
Pipeline principal — replica o comportamento do agente criar-estudo.

Fases:
  1. Preparação de pastas
  2. Extração das fontes (distillation)
  3. Planejamento da estrutura (LLM)
  4. Pesquisa complementar (web search)
  5. Escrita dos arquivos .md
  6. Criação dos canvas Obsidian
  7. Criação do guia_de_estudos.md
  8. Geração dos HTMLs
"""
from __future__ import annotations
import os
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

from rich.console import Console
from rich.panel import Panel
from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn, TaskProgressColumn
from rich.table import Table

from .llm import LLMClient
from .distiller import distill_source
from .tools.web import web_search
from .generators.content import plan_structure, research_topics, write_content_files, write_guia
from .generators.canvas import write_canvas_files
from .generators.html_gen import generate_html_files
from .generators.visual_map import generate_visual_map


def run(
    config: dict,
    tema: str,
    foco: str,
    didatica: str,
    pasta: str,
    fontes: list[str],
) -> None:
    console = Console()
    llm = LLMClient(config)

    console.print(Panel(
        f"[bold purple]Agente Estudos[/bold purple]\n"
        f"[blue]Tema:[/blue] {tema}\n"
        f"[blue]Foco:[/blue] {foco}\n"
        f"[blue]Pasta:[/blue] {pasta}\n"
        f"[blue]Provider:[/blue] {config.get('provider', '?')}\n"
        f"[blue]Fontes:[/blue] {len(fontes)} fonte(s)",
        title="Iniciando",
        border_style="purple",
    ))

    # ── Fase 1: Pastas ────────────────────────────────────────────────────────
    _step(console, 1, "Preparando estrutura de pastas")
    _setup_folders(pasta)

    # ── Fase 2: Extração das fontes ───────────────────────────────────────────
    transcript_paths: list[str] = []
    if fontes:
        _step(console, 2, f"Extraindo {len(fontes)} fonte(s) em paralelo")
        transcript_paths = _extract_sources(fontes, pasta, config, llm, console)
    else:
        _step(console, 2, "Nenhuma fonte fornecida — usando apenas pesquisa web")

    # Lê conteúdo das transcrições para contexto
    transcripts_content = _read_transcripts(transcript_paths)
    if not transcripts_content:
        transcripts_content = f"Nenhuma transcrição disponível. Tema: {tema}. Foco: {foco}."

    # ── Fase 3: Planejamento ──────────────────────────────────────────────────
    _step(console, 3, "Planejando estrutura de conteúdo com o LLM")
    structure = plan_structure(llm, tema, foco, didatica, transcripts_content)
    _print_structure(console, structure)

    # ── Fase 4: Pesquisa complementar ─────────────────────────────────────────
    _step(console, 4, "Pesquisa complementar na web")
    search_cfg = config.get("search", {})
    research_content = research_topics(
        llm, tema, foco, structure, web_search,
        max_results=search_cfg.get("max_results", 5),
    )

    # ── Fase 5: Escrita dos arquivos .md ──────────────────────────────────────
    total_files = sum(len(sf.get("files", [])) for sf in structure.get("subfolders", []))
    _step(console, 5, f"Escrevendo {total_files} arquivo(s) .md")

    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        BarColumn(),
        TaskProgressColumn(),
        console=console,
    ) as progress:
        task = progress.add_task("Gerando conteúdo...", total=total_files)

        def on_progress(current, total, title):
            progress.update(task, completed=current, description=f"[cyan]{title}[/cyan]")

        written = write_content_files(
            llm=llm,
            pasta=pasta,
            tema=tema,
            foco=foco,
            didatica=didatica,
            structure=structure,
            transcripts_content=transcripts_content,
            research_content=research_content,
            progress_cb=on_progress,
        )

    # ── Fase 6: Canvas ────────────────────────────────────────────────────────
    _step(console, 6, "Criando canvas Obsidian")
    canvas_paths = write_canvas_files(pasta, tema, structure)

    # ── Fase 7: Guia de estudos ───────────────────────────────────────────────
    _step(console, 7, "Gerando guia_de_estudos.md")
    guia_path = write_guia(llm, pasta, tema, foco, structure)

    # ── Fase 8: HTML ──────────────────────────────────────────────────────────
    _step(console, 8, "Gerando arquivos HTML")
    html_paths = generate_html_files(pasta, tema, foco, structure)

    # ── Fase 9: Mapa Mental ───────────────────────────────────────────────────
    _step(console, 9, "Gerando mapa mental visual")
    visual_path = generate_visual_map(pasta, tema, structure)

    # ── Relatório Final ───────────────────────────────────────────────────────
    _print_report(console, pasta, written, html_paths, canvas_paths, transcript_paths, visual_path)


# ── Helpers ───────────────────────────────────────────────────────────────────

def _setup_folders(pasta: str) -> None:
    for sub in ["transcripts", "html"]:
        Path(os.path.join(pasta, sub)).mkdir(parents=True, exist_ok=True)


def _extract_sources(
    fontes: list[str],
    pasta: str,
    config: dict,
    llm: LLMClient,
    console: Console,
) -> list[str]:
    paths = [None] * len(fontes)
    with Progress(SpinnerColumn(), TextColumn("{task.description}"), console=console) as progress:
        tasks = {
            progress.add_task(f"[yellow]{_short(fonte)}[/yellow]", total=None): (i, fonte)
            for i, fonte in enumerate(fontes)
        }

        def process(tid, i, fonte):
            try:
                path = distill_source(fonte, pasta, i + 1, config, llm)
                progress.update(tid, description=f"[green]✓ {_short(fonte)}[/green]")
                return i, path
            except Exception as exc:
                progress.update(tid, description=f"[red]✗ {_short(fonte)}: {exc}[/red]")
                return i, None

        with ThreadPoolExecutor(max_workers=4) as executor:
            futures = {
                executor.submit(process, tid, i, fonte): tid
                for tid, (i, fonte) in tasks.items()
            }
            for future in as_completed(futures):
                i, path = future.result()
                paths[i] = path

    return [p for p in paths if p]


def _read_transcripts(paths: list[str]) -> str:
    parts = []
    for p in paths:
        try:
            text = Path(p).read_text(encoding="utf-8")
            parts.append(f"--- {os.path.basename(p)} ---\n{text[:3000]}")
        except Exception:
            pass
    return "\n\n".join(parts)


def _step(console: Console, n: int, desc: str) -> None:
    console.print(f"\n[bold blue]Fase {n}[/bold blue] — {desc}")


def _short(s: str, max_len: int = 60) -> str:
    return s if len(s) <= max_len else s[:max_len - 3] + "..."


def _print_structure(console: Console, structure: dict) -> None:
    table = Table(title="Estrutura Planejada", border_style="blue", show_header=True)
    table.add_column("Subpasta", style="cyan")
    table.add_column("Arquivo", style="white")
    table.add_column("Título", style="yellow")
    for sf in structure.get("subfolders", []):
        for f in sf.get("files", []):
            table.add_row(sf["name"], f["name"], f.get("title", ""))
    console.print(table)


def _print_report(
    console: Console,
    pasta: str,
    md_files: list[str],
    html_files: list[str],
    canvas_files: list[str],
    transcript_files: list[str],
    visual_path: str = "",
) -> None:
    index_path = os.path.join(pasta, "html", "index.html")
    visual_line = (
        f"[bold]Mapa mental:[/bold]\n[cyan]file://{os.path.abspath(visual_path)}[/cyan]\n\n"
        if visual_path else ""
    )
    console.print(Panel(
        f"[bold green]Concluído![/bold green]\n\n"
        f"[blue]Arquivos .md criados:[/blue] {len(md_files)}\n"
        f"[blue]Arquivos HTML gerados:[/blue] {len(html_files)}\n"
        f"[blue]Canvas Obsidian:[/blue] {len(canvas_files)}\n"
        f"[blue]Transcrições:[/blue] {len(transcript_files)}\n\n"
        f"{visual_line}"
        f"[bold]Abrir hub:[/bold]\n"
        f"[cyan]file://{os.path.abspath(index_path)}[/cyan]",
        title="Relatório Final",
        border_style="green",
    ))
