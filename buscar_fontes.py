#!/usr/bin/env python3
"""
Busca e cura fontes de estudo de alta qualidade para um tema.

Uso:
  python buscar_fontes.py --tema "RAG" --foco "parent context chunking"
  python buscar_fontes.py --tema "Transformers" --max 5
  python buscar_fontes.py --tema "RL" --json fontes.json
"""
from __future__ import annotations
import json
import sys
from pathlib import Path
from urllib.parse import urlparse

import typer
import yaml
from rich.console import Console
from rich.panel import Panel
from rich.prompt import Prompt, Confirm
from rich.table import Table

sys.path.insert(0, str(Path(__file__).parent))
from src.llm import LLMClient
from src.source_discovery import DiscoveredSource, SourceDiscoverer


app = typer.Typer(name="buscar-fontes", add_completion=False,
                  help="Descobre e cura fontes de estudo de alta qualidade.")
console = Console()

_CONFIG_PATHS = [Path("config.yaml"), Path(__file__).parent / "config.yaml"]

_CAMADA_ICONS = {"fundamentos": "📚", "moderno": "⚡", "pratico": "🔧"}
_TIPO_ICONS = {"youtube": "▶", "paper": "📄", "github": "🐙", "article": "📰"}
_CAMADAS_ORDER = ["fundamentos", "moderno", "pratico"]


@app.command()
def main(
    tema: str = typer.Option(..., "--tema", "-t", help="Tema principal de estudo"),
    foco: str = typer.Option("", "--foco", "-f", help="Tópicos específicos de foco"),
    max_per_camada: int = typer.Option(5, "--max", "-m", help="Máximo de fontes por camada"),
    json_out: str = typer.Option("", "--json", "-j", help="Salvar resultado em JSON e sair"),
    config_path: str = typer.Option("", "--config", help="Caminho para config.yaml"),
):
    config = _load_config(config_path)
    llm = LLMClient(config)

    console.print(Panel(
        f"[bold orange1]Busca de Fontes[/bold orange1]\n"
        f"[blue]Tema:[/blue]  {tema}\n"
        f"[blue]Foco:[/blue]  {foco or '(geral)'}\n"
        f"[blue]Max/camada:[/blue] {max_per_camada}\n"
        f"[blue]Provider:[/blue] {config.get('provider', '?')}",
        border_style="orange1",
        title="Agente Estudos — Descoberta de Fontes",
    ))

    discoverer = SourceDiscoverer(config, llm)

    with console.status("[yellow]Buscando fontes em YouTube, arXiv, GitHub e web...[/yellow]"):
        sources = discoverer.discover(tema, foco, max_per_camada)

    if not sources:
        console.print("[red]Nenhuma fonte encontrada. Tente um tema diferente ou verifique a conexão.[/red]")
        raise typer.Exit(1)

    console.print(f"\n[green]✓ {len(sources)} fonte(s) descoberta(s)[/green]")

    # JSON-only mode (sem interação)
    if json_out:
        data = [
            {
                "url": s.url, "titulo": s.titulo, "tipo": s.tipo,
                "camada": s.camada, "score": s.score,
                "motivo": s.motivo, "metadata": s.metadata,
            }
            for s in sources
        ]
        Path(json_out).write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
        console.print(f"[green]✓[/green] Salvo em {json_out}")
        return

    # Modo interativo: exibir tabela e coletar seleção
    selected = _interactive_selection(sources, tema, foco)

    if not selected:
        console.print("[dim]Nenhuma fonte selecionada. Encerrando.[/dim]")
        return

    console.print(f"\n[bold green]{len(selected)} fonte(s) selecionada(s).[/bold green]")
    for s in selected:
        console.print(f"  [dim]{s.tipo:8}[/dim]  {s.url}")

    if Confirm.ask("\nCriar material de estudo com essas fontes agora?", default=True):
        pasta = Prompt.ask("[blue]Pasta destino[/blue] (caminho absoluto)")
        pasta = str(Path(pasta).expanduser().resolve())
        didatica = Prompt.ask(
            "[blue]Didática[/blue]",
            default="prático com exemplos do mundo real",
        )
        console.print()
        from src.agent import run
        run(
            config=config,
            tema=tema,
            foco=foco,
            didatica=didatica,
            pasta=pasta,
            fontes=[s.url for s in selected],
        )
    else:
        console.print("\n[dim]Para usar depois, execute:[/dim]")
        urls_str = " ".join(f'--fonte "{s.url}"' for s in selected)
        console.print(
            f"[cyan]python main.py --tema \"{tema}\" --foco \"{foco}\" "
            f"--pasta PASTA {urls_str}[/cyan]"
        )


# ── Display ───────────────────────────────────────────────────────────────────

def _interactive_selection(
    sources: list[DiscoveredSource],
    tema: str,
    foco: str,
) -> list[DiscoveredSource]:
    """Exibe tabela por camada e coleta seleção numerada do usuário."""
    indexed: list[DiscoveredSource] = []
    default_selected: set[int] = set()
    by_camada: dict[str, list[tuple[int, DiscoveredSource]]] = {c: [] for c in _CAMADAS_ORDER}

    for s in sources:
        camada = s.camada if s.camada in _CAMADAS_ORDER else "fundamentos"
        idx = len(indexed) + 1
        indexed.append(s)
        by_camada[camada].append((idx, s))
        if s.score >= 8.0:
            default_selected.add(idx)

    table = Table(
        title=f"FONTES — {tema.upper()}" + (f" / {foco}" if foco else ""),
        border_style="blue",
        show_header=False,
        show_lines=True,
        expand=True,
        title_style="bold white",
    )
    table.add_column("#", width=7, style="bold cyan")
    table.add_column("Fonte", ratio=4)
    table.add_column("★", width=7, justify="right")

    for camada in _CAMADAS_ORDER:
        items = by_camada.get(camada, [])
        if not items:
            continue
        icon = _CAMADA_ICONS.get(camada, "")
        table.add_row(
            "", f"[bold]{icon} {camada.upper()}[/bold]", "",
            style="on grey19",
        )
        for idx, s in items:
            check = "[green]✓[/green]" if idx in default_selected else " "
            tipo_icon = _TIPO_ICONS.get(s.tipo, "")

            meta_parts: list[str] = []
            if s.tipo == "youtube" and s.metadata.get("duration"):
                meta_parts.append(f"{s.metadata['duration'] // 60}min")
                if s.metadata.get("uploader"):
                    meta_parts.append(s.metadata["uploader"][:20])
            if s.tipo == "github" and s.metadata.get("stars"):
                meta_parts.append(f"⭐{s.metadata['stars']:,}")
            if s.tipo == "paper" and s.metadata.get("citationCount"):
                meta_parts.append(f"{s.metadata['citationCount']} cit.")
            if s.tipo == "paper" and s.metadata.get("year"):
                meta_parts.append(str(s.metadata["year"]))
            meta_str = "  " + " · ".join(meta_parts) if meta_parts else ""

            titulo = s.titulo[:58] + "..." if len(s.titulo) > 61 else s.titulo
            domain = _domain(s.url)
            motivo = s.motivo[:90] + "..." if len(s.motivo) > 93 else s.motivo

            fonte_text = (
                f"[white]{tipo_icon} {titulo}[/white]\n"
                f"[dim]{domain}{meta_str}[/dim]\n"
                f"[dim italic]↳ {motivo}[/dim italic]"
            )
            table.add_row(
                f"[{idx}] {check}",
                fonte_text,
                f"[yellow]{s.score:.1f}[/yellow]",
            )

    console.print()
    console.print(table)
    console.print()
    console.print("[dim]Seleção: '1,3,5' · '1-4' · 'a' (todos) · Enter (manter ✓)[/dim]")

    choice = Prompt.ask("[bold]Selecionar fontes[/bold]", default="")

    if not choice.strip():
        return [indexed[i - 1] for i in sorted(default_selected)]

    if choice.strip().lower() == "a":
        return list(indexed)

    selected_nums: set[int] = set()
    for part in choice.split(","):
        part = part.strip()
        if "-" in part:
            try:
                a, b = part.split("-", 1)
                for n in range(int(a.strip()), int(b.strip()) + 1):
                    if 1 <= n <= len(indexed):
                        selected_nums.add(n)
            except ValueError:
                pass
        else:
            try:
                n = int(part)
                if 1 <= n <= len(indexed):
                    selected_nums.add(n)
            except ValueError:
                pass

    return [indexed[i - 1] for i in sorted(selected_nums)]


def _domain(url: str) -> str:
    try:
        return urlparse(url).netloc.replace("www.", "")
    except Exception:
        return url[:40]


# ── Config ────────────────────────────────────────────────────────────────────

def _load_config(config_path: str) -> dict:
    paths = ([Path(config_path)] if config_path else []) + list(_CONFIG_PATHS)
    for p in paths:
        if p.exists():
            with open(p, encoding="utf-8") as f:
                cfg = yaml.safe_load(f)
            return cfg or {}
    console.print("[red]config.yaml não encontrado.[/red]")
    raise typer.Exit(1)


if __name__ == "__main__":
    app()
