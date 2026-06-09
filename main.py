#!/usr/bin/env python3
"""
Agente Estudos — script chamável que replica o agente criar-estudo.

Uso:
  python main.py --tema "Redes Neurais" --foco "backpropagation, gradient descent" \\
                 --pasta ~/obsidian/redes_neurais \\
                 --fonte "https://youtu.be/..." --fonte "https://arxiv.org/..."

  # Ou interativo (sem argumentos):
  python main.py --interactive
"""
from __future__ import annotations
import os
import sys
from pathlib import Path

import typer
import yaml
from rich.console import Console
from rich.prompt import Prompt, Confirm


def _load_dotenv_if_available() -> None:
    """Carrega .env sem exigir python-dotenv instalado."""
    env_paths = [Path(".env"), Path(__file__).parent / ".env"]
    for env_path in env_paths:
        if env_path.exists():
            try:
                from dotenv import load_dotenv
                load_dotenv(env_path, override=False)
            except ImportError:
                _parse_env_file(env_path)
            return


def _parse_env_file(path: Path) -> None:
    """Parser manual de .env como fallback quando python-dotenv não está instalado."""
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        if key and key not in os.environ:
            os.environ[key] = value


# Carrega .env se existir (antes de criar app/console)
_load_dotenv_if_available()

app = typer.Typer(
    name="agente-estudos",
    help="Gera pastas de estudo estruturadas no Obsidian a partir de fontes e um prompt.",
    add_completion=False,
)
console = Console()

_CONFIG_PATHS = [
    Path("config.yaml"),
    Path(__file__).parent / "config.yaml",
]


@app.command()
def main(
    tema: str = typer.Option("", "--tema", "-t", help="Tema principal de estudo"),
    foco: str = typer.Option("", "--foco", "-f", help="Tópicos específicos (separados por vírgula)"),
    didatica: str = typer.Option("", "--didatica", "-d", help="Estilo didático (ex: formal, prático, exemplos do mundo real)"),
    pasta: str = typer.Option("", "--pasta", "-p", help="Caminho absoluto da pasta destino"),
    fontes: list[str] = typer.Option([], "--fonte", "-s", help="URL ou caminho de fonte (repita para múltiplas)"),
    config_path: str = typer.Option("", "--config", help="Caminho para config.yaml"),
    interactive: bool = typer.Option(False, "--interactive", "-i", help="Modo interativo (ignora outros argumentos)"),
    mode: str = typer.Option("agent", "--mode", "-m", help="Modo de execução: agent (agentico) | pipeline (legado)"),
    chat: bool = typer.Option(False, "--chat", "-c", help="Abre chat interativo sobre a pasta de estudos"),
    chat_mode: str = typer.Option("qa", "--chat-mode", help="Modo do chat: qa (NotebookLM) | socratico"),
):
    config = _load_config(config_path)

    # ── Modo chat ────────────────────────────────────────────────────────────
    if chat:
        if not pasta:
            pasta = Prompt.ask("[blue]Pasta de estudos[/blue] (caminho absoluto)")
        pasta = str(Path(pasta).expanduser().resolve())
        if chat_mode not in ("qa", "socratico"):
            console.print(f"[red]--chat-mode inválido:[/red] '{chat_mode}'. Use: qa | socratico")
            sys.exit(1)
        from src.chat import run as chat_run
        chat_run(config=config, pasta=pasta, mode=chat_mode)
        return

    # ── Modo geração ─────────────────────────────────────────────────────────
    if interactive or not tema:
        tema, foco, didatica, pasta, fontes = _interactive_prompt(tema, foco, didatica, pasta, fontes)

    _validate_inputs(tema, pasta, config)

    pasta = str(Path(pasta).expanduser().resolve())

    if mode == "pipeline":
        from src.pipeline import run
    else:
        from src.agent import run

    run(
        config=config,
        tema=tema,
        foco=foco,
        didatica=didatica,
        pasta=pasta,
        fontes=list(fontes),
    )


# ── Config ────────────────────────────────────────────────────────────────────

def _load_config(config_path: str) -> dict:
    paths = ([Path(config_path)] if config_path else []) + list(_CONFIG_PATHS)

    for p in paths:
        if p.exists():
            with open(p, encoding="utf-8") as f:
                cfg = yaml.safe_load(f)
            console.print(f"[dim]Config carregada: {p}[/dim]")
            return cfg or {}

    console.print(
        "[yellow]Aviso: config.yaml não encontrado.[/yellow] "
        "Copie config.example.yaml para config.yaml e configure suas API keys.\n"
        "Tentando continuar com variáveis de ambiente..."
    )
    return _config_from_env()


def _config_from_env() -> dict:
    """Monta config a partir de variáveis de ambiente (inclui .env carregado acima)."""
    e = os.environ.get

    anthropic_key = e("ANTHROPIC_API_KEY", "")
    openai_key    = e("OPENAI_API_KEY", "")
    groq_key      = e("GROQ_API_KEY", "")
    ollama_url    = e("OLLAMA_BASE_URL", "http://localhost:11434")

    explicit = e("LLM_PROVIDER", "")
    if explicit:
        provider = explicit
    elif anthropic_key:
        provider = "anthropic"
    elif groq_key:
        provider = "groq"
    elif openai_key:
        provider = "openai"
    else:
        console.print("[red]Erro: nenhuma API key encontrada.[/red]")
        console.print(
            "Opções:\n"
            "  1. cp config.example.yaml config.yaml  (e edite as keys)\n"
            "  2. cp .env.example .env                (e edite as keys)\n"
            "  3. export ANTHROPIC_API_KEY=sk-ant-..."
        )
        sys.exit(1)

    return {
        "provider": provider,
        "anthropic": {
            "api_key": anthropic_key,
            "model": e("ANTHROPIC_MODEL", "claude-opus-4-8"),
        },
        "openai": {
            "api_key": openai_key,
            "model": e("OPENAI_MODEL", "gpt-4o"),
        },
        "groq": {
            "api_key": groq_key,
            "model": e("GROQ_MODEL", "llama-3.3-70b-versatile"),
        },
        "ollama": {
            "base_url": ollama_url,
            "model": e("OLLAMA_MODEL", "llama3.2:latest"),
        },
        "transcription": {
            "provider": e("TRANSCRIPTION_PROVIDER", "auto"),
            "groq_api_key": e("TRANSCRIPTION_GROQ_API_KEY", ""),
            "local_model": e("TRANSCRIPTION_LOCAL_MODEL", "base"),
        },
        "search": {
            "max_results": int(e("SEARCH_MAX_RESULTS", "5")),
        },
    }


# ── Validação ──────────────────────────────────────────────────────────────────

def _validate_inputs(tema: str, pasta: str, config: dict) -> None:
    errors = []
    if not tema.strip():
        errors.append("--tema é obrigatório")
    if not pasta.strip():
        errors.append("--pasta é obrigatório")

    provider = config.get("provider", "")
    if provider and not _has_api_key(config, provider):
        errors.append(
            f"API key não configurada para provider '{provider}'. "
            "Edite config.yaml ou defina a variável de ambiente correspondente."
        )

    if errors:
        for e in errors:
            console.print(f"[red]✗[/red] {e}")
        sys.exit(1)


def _has_api_key(config: dict, provider: str) -> bool:
    if provider == "ollama":
        return True
    key = config.get(provider, {}).get("api_key", "")
    return bool(key and key != f"sk-..." and not key.endswith("..."))


# ── Modo interativo ───────────────────────────────────────────────────────────

def _interactive_prompt(
    tema: str, foco: str, didatica: str, pasta: str, fontes: list[str]
) -> tuple[str, str, str, str, list[str]]:
    console.print("\n[bold purple]Agente Estudos — Modo Interativo[/bold purple]\n")

    if not tema:
        tema = Prompt.ask("[blue]Tema[/blue]")
    if not foco:
        foco = Prompt.ask("[blue]Foco[/blue] (tópicos específicos, separados por vírgula)")
    if not didatica:
        didatica = Prompt.ask(
            "[blue]Didática[/blue]",
            default="prático com exemplos do mundo real",
        )
    if not pasta:
        pasta = Prompt.ask("[blue]Pasta destino[/blue] (caminho absoluto)")

    if not fontes:
        console.print("\n[dim]Adicione fontes (URLs YouTube, artigos, papers, nomes de livros).[/dim]")
        console.print("[dim]Deixe vazio e pressione Enter para terminar.[/dim]\n")
        while True:
            fonte = Prompt.ask("[blue]Fonte[/blue] (ou Enter para finalizar)", default="")
            if not fonte:
                break
            fontes = list(fontes) + [fonte]

    return tema, foco, didatica, pasta, list(fontes)


if __name__ == "__main__":
    app()
